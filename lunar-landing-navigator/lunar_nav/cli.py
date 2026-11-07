"""Command line entry point.

    python -m lunar_nav --demo
    python -m lunar_nav --dem data/LDEM_80S_80M.tif --pixel-size 80 --downsample 2
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from .config import Config
from .data import load_scene, read_raster, synthetic_south_pole
from .pipeline import run
from .viz import write_html, write_png_summary


def parse(argv=None):
    p = argparse.ArgumentParser(prog="lunar_nav", description="Lunar south-pole landing site navigator")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--demo", action="store_true", help="use a synthetic south-pole scene")
    src.add_argument("--dem", help="LOLA DEM raster (GeoTIFF / IMG / .npy)")
    src.add_argument("--nasa", action="store_true",
                     help="full analysis on official NASA products (downloads ~1.2 GB on first run)")
    p.add_argument("--data-dir", default="data/nasa", help="where NASA products are stored (--nasa)")
    p.add_argument("--year", type=int, default=2027, help="mission year for availability analysis (--nasa)")
    p.add_argument("--half-width-km", type=float, default=240, help="analysis half-width around the pole (--nasa)")
    p.add_argument("--res", type=float, default=80, help="analysis resolution in metres (--nasa)")
    p.add_argument("--no-validate", action="store_true", help="skip the model-vs-NASA validation (--nasa)")
    p.add_argument("--pixel-size", type=float, help="DEM pixel size in metres")
    p.add_argument("--dem-scale", type=float, default=1.0, help="multiply DEM values to get metres")
    p.add_argument("--downsample", type=int, default=1, help="block-average factor for big rasters")
    p.add_argument("--pole", type=float, nargs=2, metavar=("ROW", "COL"), help="pole pixel in the original raster")
    p.add_argument("--rocks", help="Diviner rock-abundance raster on the same grid")
    p.add_argument("--illum", help="precomputed average illumination raster (0..1 or %%)")
    p.add_argument("--yolo-weights", help="YOLO weights for crater/boulder detection")
    p.add_argument("--yolo-image", help="orbital image (e.g. LROC NAC) on the same grid for YOLO")
    p.add_argument("--size", type=int, default=600, help="demo scene size in pixels")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--mission-start", type=float, help="mission start day (default: summer peak)")
    p.add_argument("--max-slope", type=float, default=10.0)
    p.add_argument("--weights", type=str,
                   help='JSON, e.g. \'{"slope":0.4,"illumination":0.3}\'')
    p.add_argument("--azimuths", type=int, default=32)
    p.add_argument("-o", "--out", default="output", help="output directory")
    p.add_argument("--summary-md", help="also write a Markdown results table (e.g. $GITHUB_STEP_SUMMARY)")
    return p.parse_args(argv)


def write_markdown_summary(res, path):
    st = res.cls
    lines = [
        f"## 🌕 Lunar Landing Navigator — {res.scene.name}",
        "",
        f"- Grid: {res.scene.shape[1]}x{res.scene.shape[0]} px @ {res.scene.pixel_size_m:g} m"
        f" · mission window: day {res.mission_window[0]:.1f} → {res.mission_window[1]:.1f}",
        f"- 🟩 safe {np.mean(st == 2) * 100:.1f}% · 🟨 marginal {np.mean(st == 1) * 100:.1f}%"
        f" · 🟥 unsafe {np.mean(st == 0) * 100:.1f}% · 🟦 PSR {res.layers.psr.mean() * 100:.1f}%",
        "",
        "| # | score | safe area | slope | sunlight | Earth view | nearest PSR | fully-lit windows | lat, lon |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in res.regions:
        lines.append(f"| {r.rank} | {r.extra.get('final_score', r.score):.2f} | {r.safe_fraction * 100:.0f}% | {r.best_slope_deg:.1f}° "
                     f"| {r.best_illumination * 100:.0f}% | {r.best_earth_visibility * 100:.0f}% "
                     f"| {r.best_psr_distance_km:.2f} km "
                     f"| {(str(round(r.extra['availability'] * 100)) + '%') if 'availability' in r.extra else '—'} "
                     f"| {abs(r.lat_deg):.3f}°S, {r.lon_deg:.1f}°E |")
    v = getattr(res, "validation", {}) or {}
    if v.get("model_vs_nasa"):
        m = v["model_vs_nasa"]
        lines += ["", "### Validation",
                  f"- Illumination model vs NASA (Mazarico 2011): Sun r = {m['sun']['r']}, MAE = {m['sun']['mae']}; "
                  f"Earth r = {m['earth']['r']}, MAE = {m['earth']['mae']}"]
    if v.get("topsis"):
        lines.append(f"- Independent TOPSIS study (arXiv:2406.19863): {v['topsis']['share_top10pct'] * 100:.0f}% of its "
                     f"top-20 points fall in our top 10%")
    if v.get("nasa_regions"):
        lines.append(f"- NASA Artemis III regions matched: {v['nasa_regions']['n_with_our_final_region']}/9 by our final 9, "
                     f"{v['nasa_regions']['n_with_our_candidate']}/9 by our 13 candidates")
    lines += ["", "Download the **landing-sites** artifact below for the interactive map.", ""]
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main(argv=None):
    a = parse(argv)
    cfg = Config(n_azimuths=a.azimuths, mission_start_day=a.mission_start)
    cfg.constraints.max_slope_deg = a.max_slope
    cfg.constraints.preferred_slope_deg = min(cfg.constraints.preferred_slope_deg, a.max_slope)
    if a.weights:
        for k, v in json.loads(a.weights).items():
            if not hasattr(cfg.weights, k):
                raise SystemExit(f"unknown weight '{k}'")
            setattr(cfg.weights, k, float(v))

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.nasa:
        from .config import MissionConstraints
        from .nasa_pipeline import run_nasa
        from .report import write_report, write_report_en
        from .viz import write_validation_figure
        cfg.constraints = MissionConstraints.nasa_long_term()
        cfg.constraints.max_slope_deg = a.max_slope
        cfg.constraints.preferred_slope_deg = min(8.0, a.max_slope)
        res = run_nasa(a.data_dir, a.half_width_km, a.res, a.year, cfg, download=True,
                       validate=not a.no_validate)
        write_validation_figure(res, out / "validation.png")
        slim = {k: ({kk: vv for kk, vv in v.items() if kk != "sample"} if isinstance(v, dict) else v)
                for k, v in res.validation.items()}
        (out / "validation.json").write_text(json.dumps(
            {"validation": slim, "references": res.references}, indent=2, default=float), encoding="utf-8")
        write_report(res, out / "REPORT.md")
        write_report_en(res, out / "REPORT_EN.md")
    else:
        if a.demo:
            scene = synthetic_south_pole(a.size, seed=a.seed)
        else:
            scene = load_scene(a.dem, a.pixel_size, tuple(a.pole) if a.pole else None,
                               a.downsample, a.dem_scale, a.rocks, a.illum)
        print(f"scene '{scene.name}': {scene.shape[1]}x{scene.shape[0]} px @ {scene.pixel_size_m} m")
        yimg = None
        if a.yolo_image:
            yimg, _ = read_raster(a.yolo_image)
        res = run(scene, cfg, a.yolo_weights, yimg)

    write_html(res, out / "landing_sites_map.html")
    write_html(res, out / "landing_sites_map_en.html", lang="en")
    write_png_summary(res, out / "summary.png")
    rows = [r.to_dict() for r in res.regions]
    with open(out / "ranked_regions.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    (out / "ranked_regions.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    if not a.nasa:
        np.savez_compressed(out / "layers.npz", slope=res.layers.slope, illumination=res.layers.illumination,
                            earth=res.layers.earth, psr=res.layers.psr, hazard=res.layers.hazard,
                            score=res.score, classes=res.cls)

    print("\nTop regions:")
    print(f"{'#':>2} {'score':>6} {'safe':>5} {'slope':>6} {'sun':>5} {'earth':>5} {'PSR km':>7} {'windows':>8}  lat, lon")
    for r in res.regions:
        e = r.extra
        sc = e.get("final_score", r.score)
        av = f"{e['availability'] * 100:6.0f}%" if "availability" in e else "      -"
        print(f"{r.rank:>2} {sc:6.2f} {r.safe_fraction * 100:4.0f}% {r.best_slope_deg:5.1f}° "
              f"{r.best_illumination * 100:4.0f}% {r.best_earth_visibility * 100:4.0f}% "
              f"{r.best_psr_distance_km:7.2f} {av}   {r.lat_deg:.3f}, {r.lon_deg:.1f}E")
    print(f"\nwrote {out}/landing_sites_map.html, landing_sites_map_en.html, summary.png, ranked_regions.csv/json"
          + (", validation.png/json, REPORT.md, REPORT_EN.md" if a.nasa else ", layers.npz"))
    return res


if __name__ == "__main__":
    main()
