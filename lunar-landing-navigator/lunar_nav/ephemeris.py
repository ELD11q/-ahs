"""Sun and Earth positions in the Moon body-fixed frame for real dates.

* Body positions: astropy's built-in ERFA ephemeris (no download needed).
* Lunar orientation: IAU WGCCRE 2009 model (Archinal et al. 2011, Celest.
  Mech. Dyn. Astr. 109:101), which approximates the Mean-Earth/polar-axis
  frame used by LOLA products to ~0.005 deg.

Returns vectors in km: X toward 0E on the equator, Y toward 90E, Z north.
"""
from __future__ import annotations

import numpy as np

J2000_JD = 2451545.0


def _moon_orientation(d):
    """IAU 2009 lunar pole (alpha0, delta0) and prime meridian W, in degrees."""
    T = d / 36525.0
    E = np.deg2rad(np.array([
        125.045 - 0.0529921 * d, 250.089 - 0.1059842 * d, 260.008 + 13.0120009 * d,
        176.625 + 13.3407154 * d, 357.529 + 0.9856003 * d, 311.589 + 26.4057084 * d,
        134.963 + 13.0649930 * d, 276.617 + 0.3287146 * d, 34.226 + 1.7484877 * d,
        15.134 - 0.1589763 * d, 119.743 + 0.0036096 * d, 239.961 + 0.1643573 * d,
        25.053 + 12.9590088 * d]))
    s, c = np.sin(E), np.cos(E)
    a0 = (269.9949 + 0.0031 * T - 3.8787 * s[0] - 0.1204 * s[1] + 0.0700 * s[2] - 0.0172 * s[3]
          + 0.0072 * s[5] - 0.0052 * s[9] + 0.0043 * s[12])
    d0 = (66.5392 + 0.0130 * T + 1.5419 * c[0] + 0.0239 * c[1] - 0.0278 * c[2] + 0.0068 * c[3]
          - 0.0029 * c[5] + 0.0009 * c[6] + 0.0008 * c[9] - 0.0009 * c[12])
    W = (38.3213 + 13.17635815 * d - 1.4e-12 * d * d + 3.5610 * s[0] + 0.1208 * s[1] - 0.0642 * s[2]
         + 0.0158 * s[3] + 0.0252 * s[4] - 0.0066 * s[5] - 0.0047 * s[6] - 0.0046 * s[7]
         + 0.0028 * s[8] + 0.0052 * s[9] + 0.0040 * s[10] + 0.0019 * s[11] - 0.0044 * s[12])
    return a0, d0, W


def _rot_z(a):
    c, s = np.cos(a), np.sin(a)
    z, o = np.zeros_like(a), np.ones_like(a)
    return np.stack([np.stack([c, s, z], -1), np.stack([-s, c, z], -1), np.stack([z, z, o], -1)], -2)


def _rot_x(a):
    c, s = np.cos(a), np.sin(a)
    z, o = np.zeros_like(a), np.ones_like(a)
    return np.stack([np.stack([o, z, z], -1), np.stack([z, c, s], -1), np.stack([z, -s, c], -1)], -2)


def icrf_to_moon_fixed(jd_tdb):
    d = np.asarray(jd_tdb, dtype=np.float64) - J2000_JD
    a0, d0, W = _moon_orientation(d)
    r = np.deg2rad
    return _rot_z(r(W)) @ _rot_x(r(90.0 - d0)) @ _rot_z(r(90.0 + a0))


def sun_earth_vectors(times):
    """times: astropy Time array. Returns (sun_km, earth_km), each (N, 3),
    as seen from the Moon's centre in the Moon body-fixed frame."""
    from astropy.coordinates import get_body_barycentric
    from astropy.utils import iers
    iers.conf.auto_download = False
    t = times.tdb
    moon = get_body_barycentric("moon", t, ephemeris="builtin").xyz.to_value("km").T
    sun = get_body_barycentric("sun", t, ephemeris="builtin").xyz.to_value("km").T
    earth = get_body_barycentric("earth", t, ephemeris="builtin").xyz.to_value("km").T
    M = icrf_to_moon_fixed(t.jd)
    rs = np.einsum("nij,nj->ni", M, sun - moon)
    re = np.einsum("nij,nj->ni", M, earth - moon)
    return rs, re


def time_grid(start_iso: str, days: float, step_hours: float):
    from astropy.time import Time, TimeDelta
    n = int(np.floor(days * 24 / step_hours)) + 1
    t0 = Time(start_iso, scale="utc")
    return t0 + TimeDelta(np.arange(n) * step_hours * 3600.0, format="sec")


def subpoint_latlon(vec):
    v = vec / np.linalg.norm(vec, axis=-1, keepdims=True)
    return np.degrees(np.arcsin(v[..., 2])), np.degrees(np.arctan2(v[..., 1], v[..., 0])) % 360
