"""Export the assets of the 3D website (site/assets/) from the NASA analysis.

    python scripts/export_site_assets.py --data-dir data/nasa --moon-dir <dir with NASA CGI Moon Kit files>

Writes:
  terrain_h.bin        512x512 uint16 heights of the south pole (LOLA, Barker 2023)
  terrain_albedo.jpg   2048 px surface tone with permanently shadowed regions tinted blue
  terrain_classes.png  2048 px safe / marginal / unsafe overlay (RGBA)
  moon_color.jpg       LROC color mosaic (NASA SVS CGI Moon Kit) for the globe
  moon_disp.jpg        LOLA global elevation (CGI Moon Kit) for globe displacement
  site_data.json       regions, NASA regions, validation numbers, terrain metadata
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lunar_nav import hazards, illumination, terrain  # noqa: E402
from lunar_nav.config import Config, MissionConstraints  # noqa: E402
from lunar_nav.nasa import Grid, load_nasa_scene  # noqa: E402
from lunar_nav.scoring import Layers, score  # noqa: E402


def block(a, f, how="mean"):
    h, w = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    b = a[:h, :w].reshape(h // f, f, w // f, f)
    return b.min(axis=(1, 3)) if how == "min" else b.max(axis=(1, 3)) if how == "max" else b.mean(axis=(1, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(ROOT / "data/nasa"))
    ap.add_argument("--moon-dir", required=True)
    ap.add_argument("-o", "--out", default=str(ROOT.parent / "site/assets"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    c = MissionConstraints.nasa_long_term()
    scene, N = load_nasa_scene(a.data_dir, Grid(240_000, 80), download=False, log=lambda *x: None)
    px = scene.pixel_size_m
    _, cmask = hazards.detect_craters_classic(scene.dem, px, min_diameter_m=400, scales_px=(4, 10, 25))
    haz = hazards.hazard_map(scene.rocks, cmask, terrain.roughness(scene.dem))
    L = Layers(slope=N.slope, illumination=N.sun_avg, illumination_annual=N.sun_avg, earth=N.earth_avg,
               psr=N.psr, psr_distance=illumination.distance_to(N.psr, px), hazard=haz)
    x, y = scene.xy_m()
    excl = np.degrees(2 * np.arctan(np.hypot(x, y) / (2 * 1_737_400.0))) > c.max_colatitude_deg
    _, cls, _ = score(L, c, Config().weights, px, excl)

    n = scene.shape[0]  # 6000
    # heights 512x512 (bilinear-ish block mean on 6000 -> 500, then pad to 512 by resize)
    h500 = block(scene.dem.astype(np.float64), 12)
    h512 = np.asarray(Image.fromarray(h500.astype(np.float32)).resize((512, 512), Image.BILINEAR))
    hmin, hmax = float(h512.min()), float(h512.max())
    q = np.round((h512 - hmin) / (hmax - hmin) * 65535).astype("<u2")
    (out / "terrain_h.bin").write_bytes(q.tobytes())

    # albedo: uniform regolith tone + subtle texture, PSR tinted blue (lighting comes from the 3D light)
    f = 3  # 6000/3 = 2000 -> 2048
    psr = block(N.psr.astype(np.float32), f) > 0.5
    rough = block(N.roughness, f)
    tone = 150 + 25 * np.tanh((rough - np.median(rough)) / 1.0)
    rgb = np.dstack([tone, tone * 0.98, tone * 0.95])
    rgb[psr] = rgb[psr] * 0.35 + np.array([40, 110, 230]) * 0.65
    Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).resize((2048, 2048), Image.BILINEAR).save(
        out / "terrain_albedo.jpg", quality=86)

    cl = block(cls.astype(np.float32), f, "min").astype(np.uint8)
    over = np.zeros(cl.shape + (4,), np.uint8)
    over[cl == 2] = (34, 197, 94, 200)
    over[cl == 1] = (234, 179, 8, 190)
    over[(cl == 0) & ~excl[::f, ::f][:cl.shape[0], :cl.shape[1]]] = (220, 38, 38, 90)
    Image.fromarray(over).resize((2048, 2048), Image.NEAREST).save(out / "terrain_classes.png", optimize=True)

    # NASA CGI Moon Kit textures for the globe
    Image.MAX_IMAGE_PIXELS = None
    md = Path(a.moon_dir)
    Image.open(md / "lroc_color_poles_4k.tif").convert("RGB").save(out / "moon_color.jpg", quality=84)
    d = np.asarray(Image.open(md / "ldem_4_uint.tif"), dtype=np.float32)
    d = (d - d.min()) / (d.max() - d.min()) * 255
    Image.fromarray(d.astype(np.uint8)).save(out / "moon_disp.jpg", quality=90)

    res = ROOT / "results/nasa_2027"
    regions = json.loads((res / "ranked_regions.json").read_text())
    val = json.loads((res / "validation.json").read_text())
    exp = json.loads((res / "experiments.json").read_text())
    uv = lambda r, c_: [round(c_ / n, 4), round(r / n, 4)]  # noqa: E731
    data = {
        "terrain": {"size_km": 480, "h_min_m": hmin, "h_max_m": hmax, "grid": 512},
        "regions": [{
            "rank": r["rank"], "uv": uv(r["best_row"], r["best_col"]), "lat": r["lat_deg"], "lon": r["lon_deg"],
            "score": r["final_score"], "availability": r["availability"], "window": (r["best_window"] or {}).get("start"),
            "slope": r["best_slope_deg"], "sun": r["best_illumination"], "earth": r["best_earth_visibility"],
            "psr_km": r["best_psr_distance_km"], "safe": r["safe_fraction"],
            "daily_sun": None} for r in regions],
        "nasa_regions": [{"name": x["name"], "uv": uv(x["row"], x["col"]), "near": x["our_final_regions_within_radius"]}
                         for x in val["references"]["nasa_regions"]],
        "landmarks": [{"name": x["name"], "uv": uv(x["row"], x["col"])} for x in val["references"]["landmarks"]],
        "validation": {k: v for k, v in val["validation"].items()},
        "years": {y: [round(v["availability"], 3) for v in lst] for y, lst in exp["years"].items()},
        "profiles": {k: v["overlap_with_baseline"] for k, v in exp["profiles"].items()},
    }
    (out / "site_data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=float))
    for p in sorted(out.iterdir()):
        print(f"{p.name:22s} {p.stat().st_size / 1e6:6.2f} MB")


if __name__ == "__main__":
    main()
