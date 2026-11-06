"""Weighted multi-criteria scoring and green / yellow / red classification."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from .config import MissionConstraints, ScoringWeights

GREEN, YELLOW, RED = 2, 1, 0


@dataclass
class Layers:
    slope: np.ndarray
    illumination: np.ndarray        # mission-window mean
    illumination_annual: np.ndarray
    earth: np.ndarray
    psr: np.ndarray
    psr_distance: np.ndarray
    hazard: np.ndarray


def criteria_scores(L: Layers, c: MissionConstraints) -> dict[str, np.ndarray]:
    """Map every criterion to 0 (bad) .. 1 (ideal)."""
    s_slope = np.clip(1 - L.slope / c.max_slope_deg, 0, 1)
    s_illum = np.clip(L.illumination, 0, 1)
    s_earth = np.clip(L.earth, 0, 1)
    d = L.psr_distance
    s_psr = np.where(d <= c.psr_ideal_distance_m, 1.0,
                     np.clip(1 - (d - c.psr_ideal_distance_m)
                             / (c.psr_max_distance_m - c.psr_ideal_distance_m), 0, 1))
    s_haz = np.clip(1 - L.hazard, 0, 1)
    return {"slope": s_slope, "illumination": s_illum, "earth_visibility": s_earth,
            "psr_proximity": s_psr, "hazard": s_haz}


def score(L: Layers, c: MissionConstraints, w: ScoringWeights, pixel_size_m: float):
    """Return (score 0..1, class map GREEN/YELLOW/RED, per-criterion scores)."""
    crit = criteria_scores(L, c)
    wn = w.normalised()
    total = sum(wn[k] * crit[k] for k in wn)

    unsafe = ((L.slope > c.max_slope_deg) | L.psr
              | (L.illumination < c.min_illumination)
              | (L.hazard > c.max_rock_abundance))
    # A lander needs the whole landing ellipse to be safe, not one pixel.
    r = max(1, int(round(c.landing_ellipse_radius_m / pixel_size_m)))
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    disk = xx**2 + yy**2 <= r * r
    unsafe = ndimage.binary_dilation(unsafe, structure=disk)
    # Near the raster edge the far horizon is missing, so lighting is
    # over-estimated there: never recommend those pixels.
    m = int(round(c.edge_margin_m / pixel_size_m))
    if m > 0 and 2 * m < min(unsafe.shape):
        unsafe[:m] = unsafe[-m:] = True
        unsafe[:, :m] = unsafe[:, -m:] = True

    marginal = ((L.slope > c.preferred_slope_deg)
                | (L.earth < c.min_earth_visibility) | (total < 0.55))
    cls = np.full(L.slope.shape, GREEN, dtype=np.uint8)
    cls[marginal] = YELLOW
    cls[unsafe] = RED
    total = np.where(unsafe, total * 0.3, total)  # keep ordering but penalise
    return total.astype(np.float32), cls, crit
