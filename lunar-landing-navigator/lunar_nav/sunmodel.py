"""Physically based Sun/Earth visibility over real LOLA terrain (numba).

1. `horizon`: for every analysis pixel, march rays in `n_az` directions over a
   (larger) DEM with bilinear sampling and lunar curvature, recording the
   elevation angle of the horizon (deg). Steps are 1 px near the pixel and grow
   geometrically, out to `max_dist_m` (default 150 km — distant massifs matter
   when the Sun is <2 deg high).
2. `visibility`: for real epochs (from `ephemeris`), compute the elevation and
   grid azimuth of the Sun/Earth seen from each pixel (with parallax for
   Earth), compare with the horizon (linearly interpolated in azimuth), and
   accumulate the visible fraction of the disc.

Conventions: grid +x = lon 90E, +y = lon 0; azimuth clockwise from +y.
"""
from __future__ import annotations

import math

import numpy as np

try:
    from numba import njit, prange
    HAVE_NUMBA = True
except ImportError:  # pragma: no cover
    HAVE_NUMBA = False

    def njit(*a, **k):
        def deco(f):
            return f
        return deco if not (a and callable(a[0])) else a[0]

    prange = range

R_MOON = 1_737_400.0


@njit(cache=True, fastmath=True)
def _bilinear(z, r, c):
    h, w = z.shape
    if r < 0.0 or c < 0.0 or r > h - 1.001 or c > w - 1.001:
        return np.nan
    r0 = int(r)
    c0 = int(c)
    fr = r - r0
    fc = c - c0
    return ((z[r0, c0] * (1 - fc) + z[r0, c0 + 1] * fc) * (1 - fr)
            + (z[r0 + 1, c0] * (1 - fc) + z[r0 + 1, c0 + 1] * fc) * fr)


@njit(parallel=True, cache=True, fastmath=True)
def _horizon_kernel(z, res, r0, c0, n_rows, n_cols, stride, n_az, max_dist, growth, obs_h):
    out = np.full((n_az, n_rows, n_cols), -90.0, dtype=np.float32)
    for i in prange(n_rows):
        for j in range(n_cols):
            rr = r0 + i * stride
            cc = c0 + j * stride
            z0 = z[rr, cc] + obs_h
            for k in range(n_az):
                az = 2.0 * math.pi * k / n_az
                dr = -math.cos(az)
                dc = math.sin(az)
                best = -1e9
                d = res
                while d <= max_dist:
                    zt = _bilinear(z, rr + dr * d / res, cc + dc * d / res)
                    if zt != zt:  # NaN -> left the DEM
                        break
                    t = (zt - z0 - d * d / (2.0 * R_MOON)) / d
                    if t > best:
                        best = t
                    d = d + res if d < 40 * res else d * growth
                out[k, i, j] = math.degrees(math.atan(best)) if best > -1e8 else -90.0
    return out


def horizon(dem: np.ndarray, res_m: float, rows: slice, cols: slice, stride: int = 1,
            n_az: int = 64, max_dist_m: float = 150_000, growth: float = 1.02, observer_h_m: float = 0.0):
    """Horizon (deg) for dem[rows, cols][::stride, ::stride] -> (n_az, H, W)."""
    z = np.ascontiguousarray(dem, dtype=np.float64)
    n_rows = len(range(rows.start, rows.stop, stride))
    n_cols = len(range(cols.start, cols.stop, stride))
    return _horizon_kernel(z, float(res_m), rows.start, cols.start, n_rows, n_cols, stride,
                           n_az, float(max_dist_m), float(growth), float(observer_h_m))


@njit(cache=True, fastmath=True)
def _local_frame(x, y, h):
    """Position (m) on the sphere for grid point (x, y) at height h, the up
    vector, and the tangent directions of grid +x and +y (south stereographic)."""
    rho = math.sqrt(x * x + y * y)
    c = 2.0 * math.atan(rho / (2.0 * R_MOON))  # colatitude from the S pole
    sc, cc = math.sin(c), math.cos(c)
    if rho > 0:
        sl, cl = x / rho, y / rho  # sin(lon), cos(lon)
    else:
        sl, cl = 0.0, 1.0
    ux, uy, uz = sc * cl, sc * sl, -cc
    # d(u)/d(rho) and d(u)/d(lon) -> grid tangents (conformal projection)
    dc = 1.0 / (R_MOON * (1 + (rho / (2 * R_MOON)) ** 2))  # dc/drho
    # derivative along rho (radial in grid)
    rx, ry, rz = cc * cl * dc, cc * sl * dc, sc * dc
    # derivative along lon
    lx, ly, lz = -sc * sl, sc * cl, 0.0
    # grid +x = rho-direction*sl + lon-direction*cl/rho ; grid +y = rho-dir*cl - lon-dir*sl/rho
    if rho > 1e-6:
        gxx = rx * sl + lx * cl / rho
        gxy = ry * sl + ly * cl / rho
        gxz = rz * sl + lz * cl / rho
        gyx = rx * cl - lx * sl / rho
        gyy = ry * cl - ly * sl / rho
        gyz = rz * cl - lz * sl / rho
    else:
        gxx, gxy, gxz = 0.0, 1.0, 0.0
        gyx, gyy, gyz = 1.0, 0.0, 0.0
    nx = math.sqrt(gxx * gxx + gxy * gxy + gxz * gxz)
    ny = math.sqrt(gyx * gyx + gyy * gyy + gyz * gyz)
    rr = R_MOON + h
    return (rr * ux, rr * uy, rr * uz, ux, uy, uz,
            gxx / nx, gxy / nx, gxz / nx, gyx / ny, gyy / ny, gyz / ny)


@njit(cache=True, fastmath=True)
def _vis_one(px, py, pz, ux, uy, uz, gxx, gxy, gxz, gyx, gyy, gyz, bx, by, bz, hor, n_az, width):
    dx, dy, dz = bx - px, by - py, bz - pz
    n = math.sqrt(dx * dx + dy * dy + dz * dz)
    dx, dy, dz = dx / n, dy / n, dz / n
    s = dx * ux + dy * uy + dz * uz
    elev = math.degrees(math.asin(min(1.0, max(-1.0, s))))
    if elev > 10.0:
        return 1.0
    if elev < -5.0:
        return 0.0
    ex = dx * gxx + dy * gxy + dz * gxz
    ey = dx * gyx + dy * gyy + dz * gyz
    az = math.degrees(math.atan2(ex, ey)) % 360.0
    f = az / 360.0 * n_az
    k0 = int(f) % n_az
    k1 = (k0 + 1) % n_az
    w = f - int(f)
    hz = hor[k0] * (1 - w) + hor[k1] * w
    v = (elev - hz) / width + 0.5
    return 0.0 if v < 0 else (1.0 if v > 1 else v)


@njit(parallel=True, cache=True, fastmath=True)
def _visibility_kernel(xs, ys, hs, hor, body_m, width, out_mean):
    n_az = hor.shape[0]
    npx = xs.shape[0]
    nt = body_m.shape[0]
    for p in prange(npx):
        (px, py, pz, ux, uy, uz, gxx, gxy, gxz, gyx, gyy, gyz) = _local_frame(xs[p], ys[p], hs[p])
        acc = 0.0
        for t in range(nt):
            acc += _vis_one(px, py, pz, ux, uy, uz, gxx, gxy, gxz, gyx, gyy, gyz,
                            body_m[t, 0], body_m[t, 1], body_m[t, 2], hor[:, p], n_az, width)
        out_mean[p] = acc / nt


@njit(parallel=True, cache=True, fastmath=True)
def _series_kernel(xs, ys, hs, hor, body_m, width, out):
    n_az = hor.shape[0]
    for p in prange(xs.shape[0]):
        (px, py, pz, ux, uy, uz, gxx, gxy, gxz, gyx, gyy, gyz) = _local_frame(xs[p], ys[p], hs[p])
        for t in range(body_m.shape[0]):
            out[p, t] = _vis_one(px, py, pz, ux, uy, uz, gxx, gxy, gxz, gyx, gyy, gyz,
                                 body_m[t, 0], body_m[t, 1], body_m[t, 2], hor[:, p], n_az, width)


SUN_WIDTH_DEG = 0.53
EARTH_WIDTH_DEG = 1.9


def mean_visibility(x_m, y_m, h_m, hor_flat, body_km, width_deg):
    """Mean visible fraction for points (x, y, h) with horizons hor_flat (n_az, N)."""
    out = np.zeros(len(x_m), dtype=np.float64)
    _visibility_kernel(np.asarray(x_m, np.float64), np.asarray(y_m, np.float64),
                       np.asarray(h_m, np.float64), np.ascontiguousarray(hor_flat, np.float64),
                       np.ascontiguousarray(body_km * 1000.0, np.float64), float(width_deg), out)
    return out


def visibility_series(x_m, y_m, h_m, hor_flat, body_km, width_deg):
    out = np.zeros((len(x_m), len(body_km)), dtype=np.float32)
    _series_kernel(np.asarray(x_m, np.float64), np.asarray(y_m, np.float64),
                   np.asarray(h_m, np.float64), np.ascontiguousarray(hor_flat, np.float64),
                   np.ascontiguousarray(body_km * 1000.0, np.float64), float(width_deg), out)
    return out
