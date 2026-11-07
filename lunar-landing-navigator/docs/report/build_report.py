"""Build the full technical report (HTML -> PDF) from the result files, in Arabic and English.

    python docs/report/build_report.py            # writes docs/report/REPORT_AR.html and REPORT_EN.html
    # PDF: open the HTML in Chrome and print, or use Playwright (see README).

Every number in the report is read from results/nasa_2027/*.json so the text
and the data can never disagree.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RES = ROOT / "results" / "nasa_2027"

regions = json.loads((RES / "ranked_regions.json").read_text(encoding="utf-8"))
V = json.loads((RES / "validation.json").read_text(encoding="utf-8"))
X = json.loads((RES / "experiments.json").read_text(encoding="utf-8"))
val, refs = V["validation"], V["references"]
mv, tp, nr = val["model_vs_nasa"], val["topsis"], val["nasa_regions"]


def pct(v, d=0):
    return "—" if v is None else f"{v * 100:.{d}f}%"


def latlon(r):
    return f'<span class="ltr nw">{abs(r["lat_deg"]):.2f}°S {r["lon_deg"]:.1f}°E</span>'


near = {}
SHORT = {"Mons Mouton Plateau": "Mons Mouton", "Nobile Rim 1": "Nobile", "Nobile Rim 2": "Nobile"}
for x in refs["nasa_regions"]:
    for k in x["our_final_regions_within_radius"]:
        near.setdefault(k, set()).add(SHORT.get(x["name"], x["name"]))

for AR, TPL, OUT in ((True, "template.html", "REPORT_AR.html"), (False, "template_en.html", "REPORT_EN.html")):
    KM, SAFE = (" كم", "آمن") if AR else (" km", "safe")
    rows_regions = "\n".join(
        f'<tr{" class=hl" if r["rank"] == 1 else ""}><td>{r["rank"]}</td><td>{latlon(r)}</td>'
        f'<td>{r["final_score"]:.3f}</td><td>{pct(r["availability"])}</td>'
        f'<td><span class="ltr nw">{(r["best_window"] or {}).get("start", "—")[5:10]}</span></td>'
        f'<td>{r["best_slope_deg"]:.2f}°</td><td>{pct(r["best_illumination"])}</td>'
        f'<td>{pct(r["best_earth_visibility"])}</td><td class="nw">{r["best_psr_distance_km"]}{KM}</td>'
        f'<td>{pct(r["safe_fraction"])}</td>'
        f'<td class="ltr small">{" / ".join(sorted(near.get(r["rank"], []))) or "—"}</td></tr>'
        for r in regions)

    rows_nasa = "\n".join(
        f'<tr><td class="ltr">{x["name"]}</td><td class="ltr small">{x["feature"]}</td>'
        f'<td>{x["match_radius_km"]:.0f}{KM}</td><td>{x["km_to_nearest_final_region"]}{KM}</td>'
        f'<td>{", ".join("#%d" % k for k in x["our_final_regions_within_radius"]) or "—"}</td>'
        f'<td>{pct(x["best_percentile_within_radius"])}</td></tr>'
        for x in refs["nasa_regions"])

    rows_topsis = "\n".join(
        f'<tr><td>{x["id"]}</td><td class="ltr small">{x["region"]}</td><td>{x["topsis"]}</td>'
        f'<td>{x["our_score"]}</td><td>{pct(x["our_percentile"])}</td><td>{x["slope"]}°</td></tr>'
        for x in refs["topsis"])

    PROFILE_AR = {"baseline": "الأساسي", "equal": "أوزان متساوية", "power_first": "الطاقة أولًا",
                  "comms_first": "الاتصال أولًا", "science_first": "العلم (الجليد) أولًا",
                  "safety_first": "السلامة أولًا"}
    PROFILE_EN = {"baseline": "Baseline", "equal": "Equal weights", "power_first": "Power first",
                  "comms_first": "Comms first", "science_first": "Science (ice) first",
                  "safety_first": "Safety first"}
    rows_profiles = "\n".join(
        f'<tr><td>{(PROFILE_AR.get(k, k) if AR else PROFILE_EN.get(k, k))}</td>'
        + "".join(f'<td>{v["weights"][w] * 100:.0f}%</td>' for w in
                  ("slope", "illumination", "earth_visibility", "psr_proximity", "hazard"))
        + f'<td><b>{v["overlap_with_baseline"]}/9</b></td></tr>'
        for k, v in X["profiles"].items())
    rows_years = "\n".join(
        f'<tr><td>#{i + 1}</td>' + "".join(
            f'<td>{pct(X["years"][y][i]["availability"])}<br><span class="ltr small">'
            f'{((X["years"][y][i]["best_window"] or {}).get("start") or "—")[:10]}</span></td>' for y in X["years"])
        + "</tr>" for i in range(len(X["years"]["2027"])))
    rows_slope = "".join(
        f'<td>{v["overlap_with_baseline"]}/9 <span class="small">({SAFE} {pct(v["green_share"], 1)})</span></td>'
        for v in X["slope"].values())

    r1 = regions[0]
    html = (HERE / TPL).read_text(encoding="utf-8")
    for k, v in {
        "{{ROWS_REGIONS}}": rows_regions, "{{ROWS_NASA}}": rows_nasa, "{{ROWS_TOPSIS}}": rows_topsis,
        "{{ROWS_PROFILES}}": rows_profiles, "{{ROWS_YEARS}}": rows_years, "{{ROWS_SLOPE}}": rows_slope,
        "{{SUN_R}}": str(mv["sun"]["r"]), "{{EARTH_R}}": str(mv["earth"]["r"]),
        "{{SUN_MAE}}": f'{mv["sun"]["mae"] * 100:.1f}', "{{EARTH_MAE}}": f'{mv["earth"]["mae"] * 100:.1f}',
        "{{SUN_BIAS}}": f'{mv["sun"]["bias"] * 100:+.1f}', "{{EARTH_BIAS}}": f'{mv["earth"]["bias"] * 100:+.1f}',
        "{{SUN_W10}}": pct(mv["sun"]["within_0.10"]), "{{EARTH_W10}}": pct(mv["earth"]["within_0.10"]),
        "{{SUN_W5}}": pct(mv["sun"]["within_0.05"]), "{{EARTH_W5}}": pct(mv["earth"]["within_0.05"]),
        "{{NPIX}}": f'{mv["n_pixels"]:,}', "{{NEPOCH}}": f'{mv["n_epochs"]:,}',
        "{{TOP10}}": pct(tp["share_top10pct"]), "{{TMED}}": pct(tp["median_percentile"]),
        "{{P358}}": pct(tp["best_point_358"]["our_percentile"]), "{{S358}}": str(tp["best_point_358"]["our_score"]),
        "{{NASA_FINAL}}": str(nr["n_with_our_final_region"]), "{{NASA_CAND}}": str(nr["n_with_our_candidate"]),
        "{{R1_LATLON}}": latlon(r1), "{{R1_AV}}": pct(r1["availability"]), "{{R1_EARTH}}": pct(r1["best_earth_visibility"]),
        "{{R1_PSR}}": str(r1["best_psr_distance_km"]), "{{R1_WIN}}": r1["best_window"]["start"][:10],
        "{{EXP_RUNTIME}}": str(X["runtime_s"]),
    }.items():
        html = html.replace(k, v)
    assert "{{" not in html, html[html.index("{{"):html.index("{{") + 40]
    (HERE / OUT).write_text(html, encoding="utf-8")
    print("wrote", HERE / OUT)
