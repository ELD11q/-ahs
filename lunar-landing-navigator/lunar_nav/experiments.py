"""Robustness experiments on the NASA data (run after `--nasa`).

1. Weight sensitivity: re-rank with five decision-maker profiles and measure
   how stable the selected regions are (overlap with the baseline top 9).
2. Multi-year availability: count fully-lit 6.5-day windows in 2026-2028 for
   every baseline candidate (illumination seasons drift ~2-3 weeks per year).
3. Threshold sensitivity: maximum slope 8 / 10 / 12 deg.

    python -m lunar_nav.experiments --data-dir data/nasa -o results/nasa_2027
"""
from __future__ import annotations

import argparse
import copy
import json
import time
from pathlib import Path

import numpy as np

from . import hazards, illumination, terrain
from .config import MissionConstraints, ScoringWeights
from .nasa import Grid, _resample, load_nasa_scene
from .nasa_pipeline import mission_availability
from .regions import rank_regions
from .scoring import GREEN, Layers, score

PROFILES = {
    "baseline": ScoringWeights(),
    "equal": ScoringWeights(0.2, 0.2, 0.2, 0.2, 0.2),
    "power_first": ScoringWeights(0.25, 0.45, 0.10, 0.10, 0.10),
    "comms_first": ScoringWeights(0.25, 0.20, 0.35, 0.10, 0.10),
    "science_first": ScoringWeights(0.25, 0.15, 0.10, 0.40, 0.10),
    "safety_first": ScoringWeights(0.45, 0.15, 0.10, 0.05, 0.25),
}


def _select(sc, cls, layers, scene, c, excluded):
    _, cands = rank_regions(sc, cls, layers, scene.pixel_size_m, c.region_size_m, scene.pole_rc,
                            n_keep=13, n_candidates=13, max_overlap=c.region_max_overlap, excluded=excluded,
                            min_separation_km=c.min_region_separation_km,
                            sufficient_safe=c.sufficient_safe_fraction)
    return cands


def run(data_dir, out_dir, years=(2026, 2027, 2028), log=print):
    t0 = time.time()
    c0 = MissionConstraints.nasa_long_term()
    scene, N = load_nasa_scene(data_dir, Grid(240_000, 80), download=True, log=log)
    px = scene.pixel_size_m
    _, cmask = hazards.detect_craters_classic(scene.dem, px, min_diameter_m=400, scales_px=(4, 10, 25))
    haz = hazards.hazard_map(scene.rocks, cmask, terrain.roughness(scene.dem))
    layers = Layers(slope=N.slope, illumination=N.sun_avg, illumination_annual=N.sun_avg, earth=N.earth_avg,
                    psr=N.psr, psr_distance=illumination.distance_to(N.psr, px), hazard=haz)
    x, y = scene.xy_m()
    excluded = np.degrees(2 * np.arctan(np.hypot(x, y) / (2 * 1_737_400.0))) > c0.max_colatitude_deg
    del x, y

    g80 = Grid(304_000, 80)
    dem80 = _resample(Path(data_dir) / "LDEM_80S_80MPP_ADJ.TIF", g80, "bilinear")
    dem80 = np.nan_to_num(dem80, nan=float(np.nanmean(dem80))).astype(np.float64)
    pole80 = (g80.n / 2 - 0.5, g80.n / 2 - 0.5)

    def final9(cands, year=2027):
        av = mission_availability(dem80, 80.0, pole80, [(r.lat_deg, r.lon_deg) for r in cands], year,
                                  c0.mission_duration_d, log=log)
        amax = max(a["availability"] for a in av) or 1e-9
        smax = max(r.score for r in cands)
        fs = [0.6 * r.score / smax + 0.4 * a["availability"] / amax for r, a in zip(cands, av)]
        order = np.argsort(fs)[::-1]
        return [cands[i] for i in order[:9]], av

    out = {"profiles": {}, "slope": {}, "years": {}}
    base_final = None
    for name, w in PROFILES.items():
        sc, cls, _ = score(layers, c0, w, px, excluded)
        cands = _select(sc, cls, layers, scene, c0, excluded)
        fin, _ = final9(cands)
        if name == "baseline":
            base_final = fin
        out["profiles"][name] = {
            "weights": w.normalised(),
            "green_share": round(float(np.mean(cls == GREEN)), 4),
            "final9": [(round(r.lat_deg, 3), round(r.lon_deg, 2)) for r in fin],
        }
        log(f"profile {name}: done")
    # overlap vs baseline (rows/cols recomputed from lat/lon)
    from .reference import latlon_to_xy

    def rc(ll):
        xx, yy = latlon_to_xy(*ll)
        return scene.pole_rc[0] - yy / px, scene.pole_rc[1] + xx / px

    base_rc = [rc(ll) for ll in out["profiles"]["baseline"]["final9"]]
    for name, d in out["profiles"].items():
        pts = [rc(ll) for ll in d["final9"]]
        d["overlap_with_baseline"] = int(sum(any(np.hypot(a[0] - b[0], a[1] - b[1]) * px / 1000 <= 15 for b in base_rc)
                                             for a in pts))

    for ms in (8.0, 10.0, 12.0):
        c = copy.deepcopy(c0)
        c.max_slope_deg = ms
        c.preferred_slope_deg = min(8.0, ms)
        sc, cls, _ = score(layers, c, ScoringWeights(), px, excluded)
        cands = _select(sc, cls, layers, scene, c, excluded)
        fin, _ = final9(cands)
        pts = [rc((r.lat_deg, r.lon_deg)) for r in fin]
        out["slope"][f"{ms:g}"] = {
            "green_share": round(float(np.mean(cls == GREEN)), 4),
            "overlap_with_baseline": int(sum(any(np.hypot(a[0] - b[0], a[1] - b[1]) * px / 1000 <= 15
                                                 for b in base_rc) for a in pts)),
        }
        log(f"slope {ms}: done")

    for yr in years:
        av = mission_availability(dem80, 80.0, pole80, [(r.lat_deg, r.lon_deg) for r in base_final], yr,
                                  c0.mission_duration_d, log=log)
        out["years"][str(yr)] = [{"availability": a["availability"], "best_window": a["best_window"]} for a in av]
        log(f"year {yr}: done")
    out["baseline_final9"] = [(round(r.lat_deg, 3), round(r.lon_deg, 2)) for r in base_final]
    out["runtime_s"] = round(time.time() - t0, 1)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "experiments.json").write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    figure(out, out_dir / "experiments.png")
    return out


def figure(out, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axs = plt.subplots(1, 3, figsize=(17, 4.8), dpi=110)
    names = list(out["profiles"])
    ov = [out["profiles"][n]["overlap_with_baseline"] for n in names]
    axs[0].barh(names, ov, color=["#16a34a" if v >= 6 else "#ca8a04" for v in ov])
    axs[0].set_xlim(0, 10)
    axs[0].set_title("Weight profiles: regions shared with baseline top 9")
    for i, v in enumerate(ov):
        axs[0].text(v + 0.1, i, f"{v}/9", va="center")
    sl = list(out["slope"])
    axs[1].bar([f"max {s}°" for s in sl], [out["slope"][s]["overlap_with_baseline"] for s in sl], color="#2f5bd3")
    axs[1].set_ylim(0, 10)
    axs[1].set_title("Slope limit: regions shared with baseline (10°)")
    for i, s in enumerate(sl):
        axs[1].text(i, out["slope"][s]["overlap_with_baseline"] + 0.15, f"{out['slope'][s]['overlap_with_baseline']}/9",
                    ha="center")
    yrs = list(out["years"])
    n = len(out["years"][yrs[0]])
    w = 0.8 / len(yrs)
    for k, yr in enumerate(yrs):
        axs[2].bar(np.arange(1, n + 1) + (k - (len(yrs) - 1) / 2) * w,
                   [a["availability"] * 100 for a in out["years"][yr]], w, label=yr)
    axs[2].set_xticks(range(1, n + 1), [f"#{i}" for i in range(1, n + 1)])
    axs[2].set_ylabel("% of start times with 6.5 lit days")
    axs[2].set_title("Fully-lit mission windows per region and year")
    axs[2].legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/nasa")
    ap.add_argument("-o", "--out", default="results/nasa_2027")
    a = ap.parse_args()
    r = run(a.data_dir, a.out)
    print(json.dumps({k: v for k, v in r.items() if k != "years"}, indent=1, default=float)[:3000])
