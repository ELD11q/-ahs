"""Sun illumination and Earth visibility from horizon ray-casting.

At the lunar south pole the Sun never rises more than ~1.5 deg above the
horizon (plus the site's distance from the pole), so whether a spot is lit is
decided almost entirely by the local horizon. We therefore:

1. cast rays from every pixel in N azimuths and record the highest horizon
   elevation angle (with lunar curvature);
2. move the Sun (and Earth) around the polar sky over time;
3. count the fraction of time the body clears the horizon.

This is the same idea behind the LOLA illumination maps (Mazarico et al.
2011), simplified so it runs in seconds on a laptop.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from . import config as C


def horizon_map(dem: np.ndarray, pixel_size_m: float, n_azimuths: int = 32,
                max_distance_m: float = 40_000, radius_m: float = C.MOON_RADIUS_M):
    """Return horizon elevation (deg), shape (n_azimuths, H, W).

    Azimuth k is k*360/n degrees clockwise from grid-up (lon 0 direction).
    Samples are spaced 1 px apart near the pixel and grow geometrically
    further out, which keeps the cost low while catching distant mountains.
    """
    h, w = dem.shape
    z = dem.astype(np.float32)
    rows, cols = np.indices((h, w), dtype=np.float32)

    dists = []
    d = pixel_size_m
    while d <= max_distance_m:
        dists.append(d)
        d = d + pixel_size_m if d < 20 * pixel_size_m else d * 1.08
    dists = np.asarray(dists, dtype=np.float32)

    out = np.full((n_azimuths, h, w), -90.0, dtype=np.float32)
    for k in range(n_azimuths):
        az = np.deg2rad(360.0 * k / n_azimuths)
        dr, dc = -np.cos(az), np.sin(az)
        best = np.full((h, w), -np.inf, dtype=np.float32)
        for dist in dists:
            step = dist / pixel_size_m
            rr = np.rint(rows + dr * step).astype(np.int32)
            cc = np.rint(cols + dc * step).astype(np.int32)
            valid = (rr >= 0) & (rr < h) & (cc >= 0) & (cc < w)
            if not valid.any():
                break
            zt = z[np.clip(rr, 0, h - 1), np.clip(cc, 0, w - 1)]
            drop = dist * dist / (2 * radius_m)  # curvature of the Moon
            ang = np.arctan2(zt - z - drop, dist)
            np.maximum(best, np.where(valid, ang, -np.inf), out=best)
        out[k] = np.degrees(np.where(np.isfinite(best), best, -np.pi / 2))
    return out


def _pixel_polar(x, y, radius_m=C.MOON_RADIUS_M):
    colat_deg = np.degrees(np.hypot(x, y) / radius_m)
    az_p = np.degrees(np.arctan2(x, y)) % 360.0  # clockwise from up
    return colat_deg, az_p


def _visible_fraction(elev, horizon_at_az, diameter_deg):
    """Fraction of the disc above the horizon (linear approximation)."""
    return np.clip((elev - horizon_at_az) / diameter_deg + 0.5, 0.0, 1.0)


def _horizon_lookup(horizon, az_deg):
    n = horizon.shape[0]
    k = int(np.rint((az_deg % 360.0) / 360.0 * n)) % n
    return horizon[k]


def sun_state(t_days):
    """Sun azimuth (grid frame) and sub-solar latitude at time t (days)."""
    az = (360.0 * t_days / C.SYNODIC_MONTH_D) % 360.0
    dec = C.SUN_MAX_DECLINATION_DEG * np.sin(2 * np.pi * t_days / C.DRACONIC_YEAR_D)
    return az, dec


def earth_state(t_days):
    az = C.EARTH_LON_LIBRATION_DEG * np.sin(2 * np.pi * t_days / C.ANOMALISTIC_MONTH_D)
    lat = C.EARTH_LAT_LIBRATION_DEG * np.sin(2 * np.pi * t_days / C.DRACONIC_MONTH_D)
    return az % 360.0, lat


def body_elevation(colat, az_p, body_az, body_lat):
    """Elevation of a body seen from a near-polar site.

    `body_lat` is the latitude of the sub-body point; a negative value means
    the body is over the southern hemisphere, i.e. higher in a south-pole
    sky. Being `colat` deg away from the pole towards `az_p` raises the body
    by colat*cos(angle between them)."""
    return -body_lat + colat * np.cos(np.deg2rad(body_az - az_p))


def illumination_fraction(horizon, x, y, times_days):
    colat, az_p = _pixel_polar(x, y)
    acc = np.zeros(horizon.shape[1:], dtype=np.float64)
    for t in times_days:
        az, dec = sun_state(t)
        elev = body_elevation(colat, az_p, az, -dec)
        acc += _visible_fraction(elev, _horizon_lookup(horizon, az), C.SUN_ANGULAR_DIAMETER_DEG)
    return (acc / len(times_days)).astype(np.float32)


def earth_visibility_fraction(horizon, x, y, times_days):
    colat, az_p = _pixel_polar(x, y)
    acc = np.zeros(horizon.shape[1:], dtype=np.float64)
    for t in times_days:
        az, lat = earth_state(t)
        elev = body_elevation(colat, az_p, az, lat)
        acc += _visible_fraction(elev, _horizon_lookup(horizon, az), C.EARTH_ANGULAR_DIAMETER_DEG)
    return (acc / len(times_days)).astype(np.float32)


def default_mission_start(duration_d: float, step_d: float = 0.25) -> float:
    """Pick the start day (within one draconic year) that maximises Sun height
    and Earth visibility as seen from the pole on flat ground.

    Real missions pick their launch window the same way: during southern
    summer, and at a phase of the libration cycle where Earth stays up."""
    best, best_t = -np.inf, 0.0
    for t0 in np.arange(0, C.DRACONIC_YEAR_D, step_d):
        t = np.arange(t0, t0 + duration_d, 1 / 8)
        _, dec = sun_state(t)
        _, elat = earth_state(t)
        sun = np.clip(dec / C.SUN_MAX_DECLINATION_DEG, -1, 1).mean()
        earth = np.clip(-elat / 2.0 + 0.5, 0, 1).mean()  # Earth up when sub-Earth lat < 0
        val = sun + 2 * earth
        if val > best:
            best, best_t = val, float(t0)
    return best_t


def psr_mask(annual_illum: np.ndarray, threshold: float) -> np.ndarray:
    m = annual_illum < threshold
    return ndimage.binary_opening(m, iterations=1)  # drop single-pixel noise


def distance_to(mask: np.ndarray, pixel_size_m: float) -> np.ndarray:
    if not mask.any():
        return np.full(mask.shape, np.inf, dtype=np.float32)
    return (ndimage.distance_transform_edt(~mask) * pixel_size_m).astype(np.float32)
