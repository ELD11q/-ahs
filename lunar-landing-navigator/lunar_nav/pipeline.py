"""End-to-end pipeline: Scene -> layers -> scores -> ranked regions."""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from . import hazards, illumination, terrain
from .config import Config
from .data import Scene
from .regions import Region, rank_regions
from .scoring import Layers, score


@dataclass
class Result:
    scene: Scene
    layers: Layers
    score: np.ndarray
    cls: np.ndarray
    criteria: dict
    regions: list[Region]
    candidates: list[Region]
    craters: list
    mission_window: tuple[float, float]
    timings: dict


def run(scene: Scene, cfg: Config | None = None, yolo_weights: str | None = None,
        yolo_image: np.ndarray | None = None, log=print) -> Result:
    cfg = cfg or Config()
    c = cfg.constraints
    t = {}
    px = scene.pixel_size_m

    t0 = time.time()
    slope = terrain.slope_deg(scene.dem, px)
    rough = terrain.roughness(scene.dem)
    t["terrain"] = time.time() - t0
    log(f"[1/5] slope: {np.mean(slope <= c.max_slope_deg) * 100:.1f}% of area <= {c.max_slope_deg} deg")

    t0 = time.time()
    hor = illumination.horizon_map(scene.dem, px, cfg.n_azimuths, cfg.horizon_max_distance_m)
    t["horizon"] = time.time() - t0
    x, y = scene.xy_m()
    start = cfg.mission_start_day
    if start is None:
        start = illumination.default_mission_start(c.mission_duration_d)
    mission_t = np.arange(start, start + c.mission_duration_d, cfg.mission_step_h / 24.0)
    annual_t = np.linspace(0, 6 * illumination.C.DRACONIC_YEAR_D, cfg.annual_samples, endpoint=False)

    t0 = time.time()
    illum_m = illumination.illumination_fraction(hor, x, y, mission_t)
    if scene.illumination is not None:
        illum_a = scene.illumination
    else:
        illum_a = illumination.illumination_fraction(hor, x, y, annual_t)
    earth = illumination.earth_visibility_fraction(hor, x, y, mission_t)
    psr = illumination.psr_mask(illum_a, c.psr_illum_threshold)
    psr_d = illumination.distance_to(psr, px)
    t["illumination"] = time.time() - t0
    log(f"[2/5] illumination: mission mean {illum_m.mean():.2f}, "
        f"PSR {psr.mean() * 100:.1f}% of area, Earth visible {earth.mean():.2f}")

    t0 = time.time()
    craters, cmask = hazards.detect_craters_classic(scene.dem, px)
    if yolo_weights and yolo_image is not None:
        yc, ym = hazards.detect_hazards_yolo(yolo_image, yolo_weights, out_shape=scene.shape)
        craters += yc
        cmask |= ym
    haz = hazards.hazard_map(scene.rocks, cmask, rough)
    t["hazards"] = time.time() - t0
    log(f"[3/5] hazards: {len(craters)} craters detected")

    layers = Layers(slope=slope, illumination=illum_m, illumination_annual=illum_a,
                    earth=earth, psr=psr, psr_distance=psr_d, hazard=haz)
    t0 = time.time()
    sc, cls, crit = score(layers, c, cfg.weights, px)
    t["scoring"] = time.time() - t0
    log(f"[4/5] classes: green {np.mean(cls == 2) * 100:.1f}%  "
        f"yellow {np.mean(cls == 1) * 100:.1f}%  red {np.mean(cls == 0) * 100:.1f}%")

    regions, cands = rank_regions(sc, cls, layers, px, c.region_size_m, scene.pole_rc,
                                  n_keep=c.n_final_regions)
    log(f"[5/5] regions: {len(cands)} candidates -> top {len(regions)}")
    return Result(scene, layers, sc, cls, crit, regions, cands, craters,
                  (float(start), float(start + c.mission_duration_d)), t)
