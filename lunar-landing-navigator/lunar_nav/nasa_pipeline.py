"""End-to-end analysis on official NASA data.

Stages
------
1. Co-register NASA products on one grid (LOLA DEM/slope/roughness, Barker
   2023; average Sun/Earth visibility and PSRs, Mazarico 2011).
2. Detect craters on the DEM and build a hazard map (roughness + craters).
3. Score every pixel, classify green/yellow/red, select 13 candidate regions.
4. Mission availability for a real year (default 2027): ray-trace the horizon
   of each candidate's best landing point on the 80 m DEM (150 km range), then
   step the real Sun and Earth hourly through the year and count the 6.5-day
   windows with continuous sunlight (and how much Earth contact they have).
5. Final 13 -> 9 selection: 60% terrain/long-term score + 40% availability.
6. Validation: (a) our ray-traced long-term averages vs NASA's maps;
   (b) where the independent TOPSIS top-20 points (arXiv:2406.19863) and
   NASA's nine Artemis III regions fall in our results.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import ephemeris, hazards, illumination, sunmodel, terrain
from .config import Config, MissionConstraints
from .nasa import Grid, _resample, load_nasa_scene
from .reference import (LANDMARKS, NASA_ARTEMIS3_REGIONS, TOPSIS_REGION_NAMES, TOPSIS_TOP20, latlon_to_xy,
                        match_radius_km)
from .regions import pixel_to_latlon, rank_regions
from .scoring import GREEN, RED, Layers, score


@dataclass
class NasaResult:
    scene: object
    layers: Layers
    score: np.ndarray
    cls: np.ndarray
    criteria: dict
    regions: list
    candidates: list
    craters: list
    mission_window: tuple
    timings: dict
    availability: dict = field(default_factory=dict)
    validation: dict = field(default_factory=dict)
    references: dict = field(default_factory=dict)
    year: int = 2027


def _px(scene, lat, lon):
    x, y = latlon_to_xy(lat, lon)
    return scene.pole_rc[0] - y / scene.pixel_size_m, scene.pole_rc[1] + x / scene.pixel_size_m


def _windows(sun, earth, step_h, duration_d, start_stride_h=6):
    """Slide a mission window over hourly series; return per-start metrics."""
    n = int(round(duration_d * 24 / step_h))
    starts = np.arange(0, len(sun) - n, max(1, int(start_stride_h / step_h)))
    lit = np.array([sun[s:s + n].min() >= 0.5 for s in starts])
    lit90 = np.array([(sun[s:s + n] >= 0.5).mean() >= 0.9 for s in starts])
    earth_frac = np.array([(earth[s:s + n] >= 0.5).mean() for s in starts])
    return starts, lit, lit90, earth_frac


def mission_availability(dem80, res, pole_rc80, points_latlon, year=2027, duration_d=6.5,
                         step_h=1.0, n_az=128, log=print):
    """Hourly Sun/Earth visibility for a list of (lat, lon) over a year."""
    pts = []
    for lat, lon in points_latlon:
        x, y = latlon_to_xy(lat, lon)
        pts.append((x, y, pole_rc80[0] - y / res, pole_rc80[1] + x / res))
    hors = []
    for x, y, r, c in pts:
        r, c = int(round(r)), int(round(c))
        hors.append(sunmodel.horizon(dem80, res, slice(r, r + 1), slice(c, c + 1), 1, n_az, 150_000, 1.01,
                                     observer_h_m=2.0)[:, 0, 0])
    hor = np.stack(hors, axis=1)
    T = ephemeris.time_grid(f"{year}-01-01", 365 + duration_d, step_h)
    s_km, e_km = ephemeris.sun_earth_vectors(T)
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    hs = np.array([dem80[int(round(p[2])), int(round(p[3]))] + 2.0 for p in pts])
    sun = sunmodel.visibility_series(xs, ys, hs, hor, s_km, sunmodel.SUN_WIDTH_DEG)
    earth = sunmodel.visibility_series(xs, ys, hs, hor, e_km, sunmodel.EARTH_WIDTH_DEG)
    out = []
    dates = T.to_datetime()
    for i in range(len(pts)):
        starts, lit, lit90, ef = _windows(sun[i], earth[i], step_h, duration_d)
        best = None
        if lit.any():
            k = np.argmax(np.where(lit, ef, -1))
            best = {"start": dates[starts[k]].strftime("%Y-%m-%d %H:%M"), "earth_contact": round(float(ef[k]), 3)}
        # daily means for charts
        hpd = int(24 / step_h)
        nd = 365
        out.append({
            "availability": round(float(lit.mean()), 4),
            "availability_90": round(float(lit90.mean()), 4),
            "lit_window_days": int(round(lit.sum() * 6 / 24)),
            "annual_sun": round(float(sun[i, :nd * hpd].mean()), 3),
            "annual_earth": round(float(earth[i, :nd * hpd].mean()), 3),
            "best_window": best,
            "daily_sun": np.round(sun[i, :nd * hpd].reshape(nd, hpd).mean(1), 3).tolist(),
            "daily_earth": np.round(earth[i, :nd * hpd].reshape(nd, hpd).mean(1), 3).tolist(),
        })
    return out


def validate_against_nasa(dem240, n240, sun_nasa240, earth_nasa240, half_m=240_000, stride=6, log=print):
    """Ray-trace our own 18.6-year averages on a sample of pixels and compare."""
    off = int(round((n240 * 240 / 2 - half_m) / 240))
    m = int(round(2 * half_m / 240))
    rows = slice(off, off + m)
    hor = sunmodel.horizon(dem240, 240.0, rows, rows, stride, 64, 150_000)
    idx = np.arange(off, off + m, stride)
    cc, rr = np.meshgrid(idx, idx)
    c0 = n240 / 2 - 0.5
    x, y, h = (cc - c0) * 240.0, (c0 - rr) * 240.0, dem240[rr, cc]
    T = ephemeris.time_grid("2010-01-01", 18.6 * 365.25, 12)
    s_km, e_km = ephemeris.sun_earth_vectors(T)
    hf = hor.reshape(hor.shape[0], -1)
    ours_s = sunmodel.mean_visibility(x.ravel(), y.ravel(), h.ravel(), hf, s_km, sunmodel.SUN_WIDTH_DEG)
    ours_e = sunmodel.mean_visibility(x.ravel(), y.ravel(), h.ravel(), hf, e_km, sunmodel.EARTH_WIDTH_DEG)
    res = {"n_pixels": int(ours_s.size), "n_epochs": int(len(T)), "span_years": 18.6, "step_hours": 12}
    for name, a, b in (("sun", ours_s, sun_nasa240[rr, cc].ravel()), ("earth", ours_e, earth_nasa240[rr, cc].ravel())):
        ok = np.isfinite(b)
        a, b = a[ok], b[ok]
        res[name] = {"r": round(float(np.corrcoef(a, b)[0, 1]), 3), "mae": round(float(np.abs(a - b).mean()), 3),
                     "bias": round(float((a - b).mean()), 3),
                     "within_0.05": round(float(np.mean(np.abs(a - b) < 0.05)), 3),
                     "within_0.10": round(float(np.mean(np.abs(a - b) < 0.10)), 3)}
    res["sample"] = {"ours_sun": ours_s[::7].round(3).tolist(), "nasa_sun": sun_nasa240[rr, cc].ravel()[::7].round(3).tolist(),
                     "ours_earth": ours_e[::7].round(3).tolist(), "nasa_earth": earth_nasa240[rr, cc].ravel()[::7].round(3).tolist()}
    return res


def run_nasa(data_dir, half_width_km=240, res_m=80, year=2027, cfg: Config | None = None,
             download=True, validate=True, log=print) -> NasaResult:
    cfg = cfg or Config(constraints=MissionConstraints.nasa_long_term())
    c = cfg.constraints
    t = {}
    t0 = time.time()
    scene, N = load_nasa_scene(data_dir, Grid(half_width_km * 1000, res_m), download, log)
    t["load"] = time.time() - t0
    px = scene.pixel_size_m

    t0 = time.time()
    craters, cmask = hazards.detect_craters_classic(scene.dem, px, min_diameter_m=400, scales_px=(4, 10, 25))
    rough_dem = terrain.roughness(scene.dem)
    haz = hazards.hazard_map(scene.rocks, cmask, rough_dem)
    psr_d = illumination.distance_to(N.psr, px)
    t["hazards"] = time.time() - t0
    log(f"[1/6] NASA layers ready: PSR {N.psr.mean() * 100:.1f}% of area, {len(craters)} craters detected")

    layers = Layers(slope=N.slope, illumination=N.sun_avg, illumination_annual=N.sun_avg,
                    earth=N.earth_avg, psr=N.psr, psr_distance=psr_d, hazard=haz)
    excluded = None
    if c.max_colatitude_deg:
        x, y = scene.xy_m()
        colat = np.degrees(2 * np.arctan(np.hypot(x, y) / (2 * 1_737_400.0)))
        excluded = colat > c.max_colatitude_deg
        del x, y, colat
    t0 = time.time()
    sc, cls, crit = score(layers, c, cfg.weights, px, excluded)
    t["scoring"] = time.time() - t0
    log(f"[2/6] classes: green {np.mean(cls == GREEN) * 100:.1f}%  yellow {np.mean(cls == 1) * 100:.1f}%  "
        f"red {np.mean(cls == RED) * 100:.1f}%")

    t0 = time.time()
    _, cands = rank_regions(sc, cls, layers, px, c.region_size_m, scene.pole_rc, n_keep=13, n_candidates=13,
                            max_overlap=c.region_max_overlap, excluded=excluded,
                            min_separation_km=c.min_region_separation_km,
                            sufficient_safe=c.sufficient_safe_fraction)
    t["regions"] = time.time() - t0
    log(f"[3/6] {len(cands)} candidate regions of 15x15 km")

    # --- mission availability on real dates -------------------------------
    t0 = time.time()
    g80 = Grid(304_000, 80)
    dem80 = _resample(Path(data_dir) / "LDEM_80S_80MPP_ADJ.TIF", g80, "bilinear")
    dem80 = np.nan_to_num(dem80, nan=float(np.nanmean(dem80))).astype(np.float64)
    pole80 = (g80.n / 2 - 0.5, g80.n / 2 - 0.5)
    av = mission_availability(dem80, 80.0, pole80, [(r.lat_deg, r.lon_deg) for r in cands], year,
                              c.mission_duration_d, log=log)
    for r, a in zip(cands, av):
        r.extra.update(a)
    t["availability"] = time.time() - t0
    log(f"[4/6] mission availability in {year}: " + ", ".join(f"#{r.rank}:{r.extra['availability'] * 100:.0f}%" for r in cands))

    # --- final 13 -> 9 ------------------------------------------------------
    amax = max([r.extra["availability"] for r in cands] + [1e-9])
    smax = max(r.score for r in cands)
    for r in cands:
        r.extra["terrain_rank"] = r.rank
        r.extra["final_score"] = round(0.6 * r.score / smax + 0.4 * r.extra["availability"] / amax, 4)
    cands.sort(key=lambda r: r.extra["final_score"], reverse=True)
    for i, r in enumerate(cands, 1):
        r.rank = i
    regions = cands[: c.n_final_regions]
    log("[5/6] final 9: " + ", ".join(f"#{r.rank} ({r.lat_deg:.2f},{r.lon_deg:.1f}E)" for r in regions))

    # --- references & validation -------------------------------------------
    t0 = time.time()
    refs = {"nasa_regions": [], "topsis": [], "landmarks": []}
    valid = ~N.psr if excluded is None else (~N.psr & ~excluded)
    flat_sorted = np.sort(sc[valid])

    def pct(v):
        return float(np.searchsorted(flat_sorted, v) / flat_sorted.size)

    for pid, code, ri, lat, lon in TOPSIS_TOP20:
        r, cc = _px(scene, lat, lon)
        ri_, ci_ = int(round(r)), int(round(cc))
        inside = 0 <= ri_ < scene.shape[0] and 0 <= ci_ < scene.shape[1]
        d_best = min(np.hypot(q.best_row - r, q.best_col - cc) * px / 1000 for q in regions)
        in_final = any(q.row0 <= r < q.row1 and q.col0 <= cc < q.col1 for q in regions)
        refs["topsis"].append({
            "id": pid, "code": code, "region": TOPSIS_REGION_NAMES.get(code, code), "topsis": ri,
            "lat": lat, "lon": lon, "row": r, "col": cc,
            "our_score": round(float(sc[ri_, ci_]), 3) if inside else None,
            "our_percentile": round(pct(sc[ri_, ci_]), 3) if inside else None,
            "our_class": int(cls[ri_, ci_]) if inside else None,
            "slope": round(float(N.slope[ri_, ci_]), 2) if inside else None,
            "inside_our_final_regions": bool(in_final), "km_to_nearest_our_best_point": round(float(d_best), 1)})
    for name, lat, lon, feat, diam, note in NASA_ARTEMIS3_REGIONS:
        r, cc = _px(scene, lat, lon)
        rad = match_radius_km(diam)
        dist = lambda q: float(np.hypot(q.best_row - r, q.best_col - cc) * px / 1000)  # noqa: E731
        near = [q for q in regions if dist(q) <= rad]
        near_c = [q for q in cands if dist(q) <= rad]
        ri_, ci_ = int(round(r)), int(round(cc))
        inside = 0 <= ri_ < scene.shape[0] and 0 <= ci_ < scene.shape[1]
        k = int(min(rad, 25.0) * 1000 / px)
        if inside:
            sub = np.s_[max(ri_ - k, 0):ri_ + k, max(ci_ - k, 0):ci_ + k]
            best_local = float(sc[sub].max())
        refs["nasa_regions"].append({
            "name": name, "feature": feat, "note": note, "lat": lat, "lon": lon, "row": r, "col": cc,
            "inside_aoi": bool(inside),
            "match_radius_km": rad,
            "best_score_within_radius": round(best_local, 3) if inside else None,
            "best_percentile_within_radius": round(pct(best_local), 3) if inside else None,
            "our_final_regions_within_radius": [q.rank for q in near],
            "our_candidates_within_radius": [q.rank for q in near_c],
            "km_to_nearest_final_region": round(min(dist(q) for q in regions), 1)})
    for name, lat, lon in LANDMARKS:
        r, cc = _px(scene, lat, lon)
        refs["landmarks"].append({"name": name, "lat": lat, "lon": lon, "row": r, "col": cc})

    val = {}
    if validate:
        g240 = Grid(304_000, 240)
        dem240 = _resample(Path(data_dir) / "LDEM_80S_80MPP_ADJ.TIF", g240, "average")
        dem240 = np.nan_to_num(dem240, nan=float(np.nanmean(dem240))).astype(np.float64)
        from .nasa import PRODUCTS
        p = Path(data_dir)
        s240 = _resample(p / PRODUCTS["sun"][0].rsplit("/", 1)[-1], g240, "average")
        e240 = _resample(p / PRODUCTS["earth"][0].rsplit("/", 1)[-1], g240, "average")
        val["model_vs_nasa"] = validate_against_nasa(dem240, g240.n, s240, e240, half_width_km * 1000, log=log)
        v = val["model_vs_nasa"]
        log(f"      model vs NASA: sun r={v['sun']['r']} MAE={v['sun']['mae']}; "
            f"earth r={v['earth']['r']} MAE={v['earth']['mae']}")
    tp = refs["topsis"]
    inside = [x for x in tp if x["our_percentile"] is not None]
    val["topsis"] = {
        "n": len(tp), "n_inside_aoi": len(inside),
        "median_percentile": round(float(np.median([x["our_percentile"] for x in inside])), 3) if inside else None,
        "share_top10pct": round(float(np.mean([x["our_percentile"] >= 0.9 for x in inside])), 3) if inside else None,
        "share_inside_final_regions": round(float(np.mean([x["inside_our_final_regions"] for x in tp])), 3),
        "best_point_358": next((x for x in tp if x["id"] == 358), None),
    }
    nr = refs["nasa_regions"]
    val["nasa_regions"] = {
        "n": len(nr), "n_inside_aoi": sum(x["inside_aoi"] for x in nr),
        "n_with_our_final_region": sum(bool(x["our_final_regions_within_radius"]) for x in nr),
        "n_with_our_candidate": sum(bool(x["our_candidates_within_radius"]) for x in nr),
        "median_km_to_nearest_final": round(float(np.median([x["km_to_nearest_final_region"] for x in nr])), 1),
        "median_best_percentile": round(float(np.median([x["best_percentile_within_radius"] for x in nr
                                                         if x["best_percentile_within_radius"] is not None])), 3),
    }
    t["validation"] = time.time() - t0
    log(f"[6/6] validation: TOPSIS points median percentile {val['topsis']['median_percentile']}, "
        f"{val['nasa_regions']['n_with_our_final_region']}/9 NASA regions matched by our final 9 "
        f"({val['nasa_regions']['n_with_our_candidate']}/9 by our 13 candidates)")

    lat0, lon0 = pixel_to_latlon(0, 0, scene.pole_rc, px)
    scene.meta.update({"year": year, "corner_lat": lat0})
    return NasaResult(scene, layers, sc, cls, crit, regions, cands, craters, (0.0, c.mission_duration_d), t,
                      validation=val, references=refs, year=year)
