"""Candidate regions (~15 x 15 km, like NASA's Artemis III regions) and ranking."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy import ndimage

from .scoring import GREEN, RED


@dataclass
class Region:
    rank: int
    row0: int
    col0: int
    row1: int
    col1: int
    score: float
    safe_fraction: float
    marginal_fraction: float
    mean_slope_deg: float
    mean_illumination: float
    mean_earth_visibility: float
    min_psr_distance_km: float
    best_row: int
    best_col: int
    best_score: float
    best_slope_deg: float
    best_illumination: float
    best_earth_visibility: float
    best_psr_distance_km: float
    lat_deg: float = 0.0
    lon_deg: float = 0.0

    def to_dict(self):
        return asdict(self)


def pixel_to_latlon(row, col, pole_rc, pixel_size_m, radius_m=1_737_400.0):
    x = (col - pole_rc[1]) * pixel_size_m
    y = (pole_rc[0] - row) * pixel_size_m
    rho = np.hypot(x, y)
    # inverse polar stereographic (south)
    lat = -90.0 + np.degrees(2 * np.arctan(rho / (2 * radius_m)))
    lon = np.degrees(np.arctan2(x, y)) % 360.0
    return float(lat), float(lon)


def rank_regions(score, cls, layers, pixel_size_m, region_size_m, pole_rc,
                 n_keep: int = 9, n_candidates: int = 13) -> tuple[list[Region], list[Region]]:
    """Slide a region-sized window over the map (half-overlapping), score each,
    keep the best non-overlapping `n_candidates`, then the top `n_keep`.

    Returns (final regions, all candidates) – mirroring NASA's 13 -> 9 cut."""
    h, w = score.shape
    size = max(4, int(round(region_size_m / pixel_size_m)))
    size = min(size, h, w)
    stride = max(1, size // 2)
    # Score each pixel's suitability as the centre of a small landing area.
    smooth = ndimage.uniform_filter(np.where(cls == RED, 0, score), 3)

    cands = []
    for r0 in range(0, h - size + 1, stride):
        for c0 in range(0, w - size + 1, stride):
            sl = (slice(r0, r0 + size), slice(c0, c0 + size))
            sub_cls = cls[sl]
            safe = float((sub_cls == GREEN).mean())
            marg = float((sub_cls == 1).mean())
            sub = smooth[sl]
            br, bc = np.unravel_index(np.argmax(sub), sub.shape)
            top = np.sort(sub, axis=None)[-max(1, sub.size // 20):].mean()
            reg_score = 0.45 * safe + 0.15 * marg + 0.40 * float(top)
            R, Cc = r0 + br, c0 + bc
            lat, lon = pixel_to_latlon(R, Cc, pole_rc, pixel_size_m)
            cands.append(Region(
                rank=0, row0=r0, col0=c0, row1=r0 + size, col1=c0 + size,
                score=round(reg_score, 4), safe_fraction=round(safe, 4),
                marginal_fraction=round(marg, 4),
                mean_slope_deg=round(float(layers.slope[sl].mean()), 2),
                mean_illumination=round(float(layers.illumination[sl].mean()), 3),
                mean_earth_visibility=round(float(layers.earth[sl].mean()), 3),
                min_psr_distance_km=round(float(layers.psr_distance[sl].min()) / 1000, 2),
                best_row=int(R), best_col=int(Cc), best_score=round(float(score[R, Cc]), 4),
                best_slope_deg=round(float(layers.slope[R, Cc]), 2),
                best_illumination=round(float(layers.illumination[R, Cc]), 3),
                best_earth_visibility=round(float(layers.earth[R, Cc]), 3),
                best_psr_distance_km=round(float(layers.psr_distance[R, Cc]) / 1000, 2),
                lat_deg=round(lat, 4), lon_deg=round(lon, 3)))

    cands.sort(key=lambda r: r.score, reverse=True)
    chosen: list[Region] = []
    for r in cands:  # greedy non-overlap (allow <=25% overlap)
        ok = True
        for q in chosen:
            if q.row0 <= r.best_row < q.row1 and q.col0 <= r.best_col < q.col1:
                ok = False  # same best landing point already covered
                break
            ov_r = max(0, min(r.row1, q.row1) - max(r.row0, q.row0))
            ov_c = max(0, min(r.col1, q.col1) - max(r.col0, q.col0))
            if ov_r * ov_c > 0.25 * size * size:
                ok = False
                break
        if ok:
            chosen.append(r)
        if len(chosen) == n_candidates:
            break
    for i, r in enumerate(chosen, 1):
        r.rank = i
    return chosen[:n_keep], chosen
