"""Interactive HTML map (Leaflet, fully offline) + static PNG figures."""
from __future__ import annotations

import base64
import io
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from .scoring import GREEN, RED, YELLOW
from .terrain import hillshade

CLASS_RGBA = {GREEN: (34, 197, 94, 150), YELLOW: (234, 179, 8, 150), RED: (220, 38, 38, 110)}
MAX_DISPLAY_PX = 1800


def _png_b64(rgba: np.ndarray, lossy: bool = False) -> str:
    """Encode an RGBA layer for embedding. WebP keeps alpha and is ~5-10x
    smaller than PNG; categorical layers stay lossless."""
    buf = io.BytesIO()
    img = Image.fromarray(rgba)
    if lossy:
        img.save(buf, format="WEBP", quality=82, method=4)
    else:
        img.save(buf, format="WEBP", lossless=True, method=4)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


def _factor(shape) -> int:
    return max(1, math.ceil(max(shape) / MAX_DISPLAY_PX))


def _ds(a: np.ndarray, f: int, how="mean"):
    if f <= 1:
        return a
    h, w = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    b = a[:h, :w].reshape(h // f, f, w // f, f)
    if how == "max":
        return b.max(axis=(1, 3))
    if how == "mode":
        return b[:, 0, :, 0]
    return b.mean(axis=(1, 3))


def _cmap(arr, name, vmin, vmax, alpha=200, mask=None):
    import matplotlib
    cm = matplotlib.colormaps[name]
    a = np.clip((arr - vmin) / (vmax - vmin + 1e-12), 0, 1)
    rgba = (cm(a) * 255).astype(np.uint8)
    rgba[..., 3] = alpha
    if mask is not None:
        rgba[~mask, 3] = 0
    return rgba


def class_rgba(cls):
    out = np.zeros(cls.shape + (4,), dtype=np.uint8)
    for k, v in CLASS_RGBA.items():
        out[cls == k] = v
    return out


def _class_ds(cls, f):
    """Downsample a class map conservatively: a display pixel is green only if
    all its sub-pixels are green, red if any is red."""
    if f <= 1:
        return cls
    h, w = (cls.shape[0] // f) * f, (cls.shape[1] // f) * f
    b = cls[:h, :w].reshape(h // f, f, w // f, f)
    return b.min(axis=(1, 3)).astype(np.uint8)


def build_layers(res):
    L, sc = res.layers, res.scene
    f = _factor(sc.shape)
    dem = _ds(sc.dem, f)
    hs = hillshade(dem, sc.pixel_size_m * f, z_factor=1.5)
    base = np.dstack([(hs * 255).astype(np.uint8)] * 3 + [np.full(hs.shape, 255, np.uint8)])
    psr_d = _ds(L.psr.astype(np.float32), f) > 0.5
    psr = np.zeros(psr_d.shape + (4,), np.uint8)
    psr[psr_d] = (59, 130, 246, 190)
    illum_max = getattr(res.scene, "meta", {}).get("illum_display_max", 1.0)
    return {
        "base": _png_b64(base, lossy=True),
        "classes": _png_b64(class_rgba(_class_ds(res.cls, f))),
        "score": _png_b64(_cmap(_ds(res.score, f), "viridis", 0, 1), lossy=True),
        "slope": _png_b64(_cmap(_ds(L.slope, f), "magma_r", 0, 20), lossy=True),
        "illumination": _png_b64(_cmap(_ds(L.illumination, f), "inferno", 0, illum_max), lossy=True),
        "earth": _png_b64(_cmap(_ds(L.earth, f), "cividis", 0, 1), lossy=True),
        "hazard": _png_b64(_cmap(_ds(L.hazard, f), "Reds", 0, 1), lossy=True),
        "psr": _png_b64(psr),
    }


def _graticule(res):
    """Latitude circles and meridians in pixel coordinates (polar grids only)."""
    sc = res.scene
    if sc.meta.get("synthetic"):
        return []
    R = 1_737_400.0
    pr, pc = sc.pole_rc
    px = sc.pixel_size_m
    h, w = sc.shape
    lines = []
    corner = math.hypot(h, w) / 2 * px
    for lat in range(-89, -79):
        rho = 2 * R * math.tan(math.radians(90 + lat) / 2)
        if rho > corner:
            break
        pts = [[pr - rho * math.cos(math.radians(a)) / px, pc + rho * math.sin(math.radians(a)) / px]
               for a in range(0, 361, 3)]
        lines.append({"label": f"{-lat}°S", "pts": pts, "kind": "lat"})
    for lon in range(0, 360, 30):
        pts = [[pr - rho * math.cos(math.radians(lon)) / px, pc + rho * math.sin(math.radians(lon)) / px]
               for rho in (0, corner)]
        lines.append({"label": f"{lon}°E", "pts": pts, "kind": "lon"})
    return lines


EN_PAIRS = [('<html lang="ar" dir="rtl">', '<html lang="en" dir="ltr">'), ('lang="en" title="English version">EN</a>', 'lang="ar" title="Arabic version">AR</a>'), ('<h1>🌕 مستكشف مواقع الهبوط القمري</h1>', '<h1>🌕 Lunar Landing Site Navigator</h1>'), ('<i style="background:var(--green)"></i>آمن</span>', '<i style="background:var(--green)"></i>Safe</span>'), ('<i style="background:var(--yellow)"></i>متوسط</span>', '<i style="background:var(--yellow)"></i>Marginal</span>'), ('<i style="background:var(--red)"></i>خطر</span>', '<i style="background:var(--red)"></i>Unsafe</span>'), ('<i style="background:var(--blue)"></i>ظل دائم (جليد محتمل)</span>', '<i style="background:var(--blue)"></i>Permanent shadow (possible ice)</span>'), ('</span> مناطق ناسا · <span', '</span> NASA regions · <span'), ('</span> أفضل نقاط TOPSIS</span>', '</span> Top TOPSIS points</span>'), ('<h2>الطبقات</h2>', '<h2>Layers</h2>'), ('<h2>أفضل المناطق (مرتبة)</h2>', '<h2>Top regions (ranked)</h2>'), ('`المنطقة: <b>${D.name}</b> · دقة ${D.px} م/بكسل · ${(D.w*D.px/1000).toFixed(0)}×${(D.h*D.px/1000).toFixed(0)} كم`', '`Scene: <b>${D.name}</b> · ${D.px} m/px · ${(D.w*D.px/1000).toFixed(0)}×${(D.h*D.px/1000).toFixed(0)} km`'), ('`<br>تحليل نوافذ المهمة لعام <b>${D.year}</b> (مدة ${D.window[1]} يوم)`', '`<br>Mission windows analysed for <b>${D.year}</b> (${D.window[1]}-day stay)`'), ('`<br>نافذة المهمة: يوم ${D.window[0].toFixed(1)} → ${D.window[1].toFixed(1)}`', '`<br>Mission window: day ${D.window[0].toFixed(1)} → ${D.window[1].toFixed(1)}`'), ('بيانات تجريبية مُولّدة — للعرض فقط', 'Synthetic demo data, for illustration only'), ('بيانات ناسا الرسمية: LOLA (Barker 2023) + الإضاءة والظل الدائم (Mazarico 2011)', 'Official NASA data: LOLA (Barker 2023) + illumination and permanent shadow (Mazarico 2011)'), ('[["آمن",pct(S.green),"var(--green)"],["متوسط",pct(S.yellow),"var(--yellow)"],["خطر",pct(S.red),"var(--red)"],', '[["Safe",pct(S.green),"var(--green)"],["Marginal",pct(S.yellow),"var(--yellow)"],["Unsafe",pct(S.red),"var(--red)"],'), ('["ظل دائم",pct(S.psr),"var(--blue)"],["حفر مكتشفة",S.craters.toLocaleString("en"),"var(--text)"],["مناطق",D.regions.length,"var(--text)"]]', '["Permanent shadow",pct(S.psr),"var(--blue)"],["Craters found",S.craters.toLocaleString("en"),"var(--text)"],["Regions",D.regions.length,"var(--text)"]]'), ('"التصنيف (آمن/متوسط/خطر)"', '"Classification (safe / marginal / unsafe)"'), ('"الظل الدائم (PSR)"', '"Permanent shadow (PSR)"'), ('"النقاط الكلية"', '"Total score"'), ('["slope","الميلان",false]', '["slope","Slope",false]'), ('"متوسط الإضاءة 18.6 سنة (ناسا)":"الإضاءة خلال المهمة"', '"Mean sunlight over 18.6 years (NASA)":"Sunlight during the mission"'), ('["earth","رؤية الأرض",false],["hazard","الصخور والحفر والخشونة",false]', '["earth","Earth visibility",false],["hazard","Rocks, craters and roughness",false]'), ('addToggle("شبكة خطوط العرض والطول", g, true);', 'addToggle("Latitude / longitude grid", g, true);'), ('bindTooltip("القطب الجنوبي")', 'bindTooltip("South pole")'), ('`<b>منطقة ناسا لـ Artemis III:</b><br>${names.join(" / ")}<br>', '`<b>NASA Artemis III region:</b><br>${names.join(" / ")}<br>'), ('<small>موقعها على الخريطة تقريبي (مركز المَعْلم <bdi>${x.feature}</bdi> من دليل IAU)</small><br>', '<small>Approximate position (centre of the feature <bdi>${x.feature}</bdi>, IAU gazetteer)</small><br>'), ('أقرب منطقة من مناطقنا: <b>${x.km_to_nearest_final_region} كم</b>`', 'Nearest of our regions: <b>${x.km_to_nearest_final_region} km</b>`'), ('`<b>نقطة TOPSIS رقم ${x.id}</b> (<bdi>${x.region}</bdi>)<br>ترتيبها في الورقة: R=${x.topsis}<br>', '`<b>TOPSIS point #${x.id}</b> (<bdi>${x.region}</bdi>)<br>Score in the paper: R=${x.topsis}<br>'), ('نقاطها عندنا: ${x.our_score} — أعلى من <b>${pct(x.our_percentile)}</b> من المنطقة<br>', 'Our score: ${x.our_score}, higher than <b>${pct(x.our_percentile)}</b> of the area<br>'), ('addToggle("مناطق ناسا التسع لـ Artemis III ★", g, true);', 'addToggle("NASA\'s nine Artemis III regions ★", g, true);'), ('addToggle("أفضل 20 نقطة في دراسة TOPSIS ◆", t, true);', 'addToggle("Top 20 points of the TOPSIS study ◆", t, true);'), ('addToggle("أسماء المعالم (IAU)", m, true);', 'addToggle("Landmark names (IAU)", m, true);'), ('<h2>التحقق من الدقة</h2>', '<h2>Validation</h2>'), ('`نموذجنا للإضاءة مقابل خرائط ناسا (${mv.n_pixels.toLocaleString("en")} نقطة × ${mv.n_epochs.toLocaleString("en")} لحظة زمنية على 18.6 سنة):<br>', '`Our illumination model vs NASA\'s maps (${mv.n_pixels.toLocaleString("en")} points × ${mv.n_epochs.toLocaleString("en")} epochs over 18.6 years):<br>'), ('☀️ الشمس: ارتباط <b class="ok">r = ${mv.sun.r}</b> · متوسط الخطأ <b>${(mv.sun.mae*100).toFixed(1)}</b> نقطة مئوية<br>', '☀️ Sun: correlation <b class="ok">r = ${mv.sun.r}</b> · mean error <b>${(mv.sun.mae*100).toFixed(1)}</b> percentage points<br>'), ('🌍 الأرض: ارتباط <b class="ok">r = ${mv.earth.r}</b> · متوسط الخطأ <b>${(mv.earth.mae*100).toFixed(1)}</b> نقطة مئوية<br>', '🌍 Earth: correlation <b class="ok">r = ${mv.earth.r}</b> · mean error <b>${(mv.earth.mae*100).toFixed(1)}</b> percentage points<br>'), ('`أفضل 20 نقطة في دراسة TOPSIS المستقلة: <b class="ok">${pct(tp.share_top10pct)}</b> منها داخل أفضل 10% من خريطتنا (الوسيط: أعلى من ${pct(tp.median_percentile)}).<br>`', '`Top 20 points of the independent TOPSIS study: <b class="ok">${pct(tp.share_top10pct)}</b> fall in our top 10% (median: above ${pct(tp.median_percentile)}).<br>`'), ('`مناطق ناسا التسع: <b class="ok">${nr.n_with_our_final_region}/9</b> عندها منطقة من مناطقنا التسع، و<b>${nr.n_with_our_candidate}/9</b> من مرشحينا الـ13.`', '`NASA\'s nine regions: <b class="ok">${nr.n_with_our_final_region}/9</b> have one of our nine regions nearby, <b>${nr.n_with_our_candidate}/9</b> one of our 13 candidates.`'), ('`مرشحة مستبعدة #${r.rank} · ', '`Dropped candidate #${r.rank} · '), ('<span style="color:#facc15">━ الشمس</span><span style="color:#38bdf8">┅ الأرض</span><span>يناير ← ديسمبر ${D.year}</span>', '<span style="color:#facc15">━ Sun</span><span style="color:#38bdf8">┅ Earth</span><span>January → December ${D.year}</span>'), ('`<b>المنطقة #${r.rank}</b> — نقاط ', '`<b>Region #${r.rank}</b>, score '), ('أفضل نقطة هبوط: <bdi dir="ltr">', 'Best landing point: <bdi dir="ltr">'), ('الميلان: ${r.best_slope_deg}° · الإضاءة: ${pct(r.best_illumination)}<br>', 'Slope: ${r.best_slope_deg}° · Sunlight: ${pct(r.best_illumination)}<br>'), ('رؤية الأرض: ${pct(r.best_earth_visibility)} · أقرب ظل دائم: ${r.best_psr_distance_km} كم`', 'Earth visibility: ${pct(r.best_earth_visibility)} · Nearest permanent shadow: ${r.best_psr_distance_km} km`'), ('`<br>نوافذ مضيئة بالكامل في ${D.year}: <b>${pct(r.availability)}</b> من السنة`', '`<br>Fully-lit windows in ${D.year}: <b>${pct(r.availability)}</b> of the year`'), ('`<br>أفضل نافذة: <bdi dir="ltr">${r.best_window.start}</bdi> UTC (تواصل مع الأرض ${pct(r.best_window.earth_contact)})`', '`<br>Best window: <bdi dir="ltr">${r.best_window.start}</bdi> UTC (Earth contact ${pct(r.best_window.earth_contact)})`'), ('`<div class="near">★ قريبة من منطقة ناسا: <bdi>', '`<div class="near">★ Near NASA region: <bdi>'), ('</span>المنطقة ${r.rank}</span>', '</span>Region ${r.rank}</span>'), ('<span>مساحة آمنة <b>${pct(r.safe_fraction)}</b></span><span>ميلان أفضل نقطة <b>${r.best_slope_deg}°</b></span>', '<span>Safe area <b>${pct(r.safe_fraction)}</b></span><span>Best-point slope <b>${r.best_slope_deg}°</b></span>'), ('<span>الإضاءة <b>${pct(r.best_illumination)}</b></span><span>رؤية الأرض <b>${pct(r.best_earth_visibility)}</b></span>', '<span>Sunlight <b>${pct(r.best_illumination)}</b></span><span>Earth visibility <b>${pct(r.best_earth_visibility)}</b></span>'), ('<span>أقرب ظل دائم <b>${r.best_psr_distance_km} كم</b></span><span>الموقع <b>', '<span>Nearest permanent shadow <b>${r.best_psr_distance_km} km</b></span><span>Location <b>'), ('`<span>نوافذ ${D.year} <b>${pct(r.availability)}</b></span><span>أفضل نافذة <b>', '`<span>Windows ${D.year} <b>${pct(r.availability)}</b></span><span>Best window <b>'), ('.leaflet-popup-content{direction:rtl;', '.leaflet-popup-content{direction:ltr;'), ('aside{background:var(--panel);border-left:1px solid var(--line);', 'aside{background:var(--panel);border-right:1px solid var(--line);'), ('display:inline-flex;align-items:center;justify-content:center;font-size:13px;margin-left:6px}', 'display:inline-flex;align-items:center;justify-content:center;font-size:13px;margin-right:6px}')]


def localize(html: str, lang: str) -> str:
    """Return the map page in English (lang="en") or unchanged Arabic."""
    if lang != "en":
        return html
    for ar, en in EN_PAIRS:
        if ar not in html:
            raise ValueError(f"missing translation anchor: {ar[:60]}")
        html = html.replace(ar, en)
    return html


def _other_lang_name(path: Path, lang: str) -> str:
    """File name of the same map in the other language (written next to it by the CLI)."""
    if lang == "en":
        stem = path.stem[:-3] if path.stem.endswith("_en") else "landing_sites_map"
        return f"{stem}{path.suffix}"
    return f"{path.stem}_en{path.suffix}"


def write_html(res, path: str | Path, lang: str = "ar"):
    h, w = res.scene.shape
    refs = getattr(res, "references", {}) or {}
    val = getattr(res, "validation", {}) or {}
    if "model_vs_nasa" in val:
        val = {**val, "model_vs_nasa": {k: v for k, v in val["model_vs_nasa"].items() if k != "sample"}}
    payload = {
        "h": h, "w": w, "px": res.scene.pixel_size_m, "name": res.scene.name,
        "synthetic": bool(res.scene.meta.get("synthetic")),
        "nasa": not res.scene.meta.get("synthetic") and "products" in res.scene.meta,
        "year": getattr(res, "year", None),
        "window": res.mission_window,
        "pole": res.scene.pole_rc,
        "regions": [r.to_dict(series=True) for r in res.regions],
        "candidates": [r.to_dict() for r in res.candidates if r not in res.regions],
        "stats": {
            "green": float(np.mean(res.cls == GREEN)), "yellow": float(np.mean(res.cls == YELLOW)),
            "red": float(np.mean(res.cls == RED)), "psr": float(res.layers.psr.mean()),
            "craters": len(res.craters),
        },
        "refs": refs, "validation": val, "graticule": _graticule(res),
        "products": res.scene.meta.get("products", {}),
    }
    layers = build_layers(res)
    vendor = Path(__file__).parent / "vendor"
    html = (TEMPLATE
            .replace("__LEAFLET_CSS__", (vendor / "leaflet.css").read_text(encoding="utf-8"))
            .replace("__LEAFLET_JS__", (vendor / "leaflet.js").read_text(encoding="utf-8"))
            .replace("__DATA__", json.dumps(payload, default=float))
            .replace("__LAYERS__", json.dumps(layers))
            .replace("__OTHER_LANG__", _other_lang_name(Path(path), lang)))
    Path(path).write_text(localize(html, lang), encoding="utf-8")
    return Path(path)


def write_png_summary(res, path: str | Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    L = res.layers
    f = _factor(res.scene.shape)
    illum_max = res.scene.meta.get("illum_display_max", 1.0)
    fig, axs = plt.subplots(2, 3, figsize=(15, 10), dpi=110)
    panels = [("Slope (deg)", L.slope, "magma_r", 0, 20),
              ("Sunlight" + (" (18.6-yr mean, NASA)" if illum_max < 1 else " (mission)"), L.illumination, "inferno", 0, illum_max),
              ("Earth visibility", L.earth, "cividis", 0, 1), ("Hazard (rocks/craters)", L.hazard, "Reds", 0, 1),
              ("Score", res.score, "viridis", 0, 1)]
    for ax, (t, a, cm, lo, hi) in zip(axs.flat, panels):
        im = ax.imshow(_ds(a, f), cmap=cm, vmin=lo, vmax=hi)
        ax.set_title(t)
        fig.colorbar(im, ax=ax, fraction=0.046)
    ax = axs.flat[5]
    ax.imshow(hillshade(_ds(res.scene.dem, f), res.scene.pixel_size_m * f), cmap="gray")
    ax.imshow(class_rgba(_class_ds(res.cls, f)))
    for r in res.regions:
        ax.add_patch(Rectangle((r.col0 / f, r.row0 / f), (r.col1 - r.col0) / f, (r.row1 - r.row0) / f,
                               fill=False, ec="white", lw=1.2))
        ax.text(r.best_col / f, r.best_row / f, str(r.rank), color="white", fontsize=9,
                ha="center", va="center", weight="bold",
                bbox=dict(boxstyle="circle,pad=0.2", fc="black", ec="white", lw=0.8))
    for x in (getattr(res, "references", {}) or {}).get("nasa_regions", []):
        if x["inside_aoi"]:
            ax.plot(x["col"] / f, x["row"] / f, marker="*", ms=11, mfc="#38bdf8", mec="black", mew=0.6)
    ax.set_title("Safe / marginal / unsafe  (★ NASA Artemis III region names)")
    for a in axs.flat:
        a.set_xticks([]), a.set_yticks([])
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def write_validation_figure(res, path: str | Path):
    """Scatter of our ray-traced long-term averages vs NASA's, plus the 2027
    daily illumination/Earth-visibility of the top regions."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    v = res.validation.get("model_vs_nasa")
    fig, axs = plt.subplots(1, 3, figsize=(16, 5), dpi=110)
    if v:
        s = v["sample"]
        for ax, k, lab in ((axs[0], "sun", "Sun"), (axs[1], "earth", "Earth")):
            a, b = np.array(s[f"ours_{k}"]), np.array(s[f"nasa_{k}"])
            ok = np.isfinite(b)
            ax.hexbin(b[ok], a[ok], gridsize=45, bins="log", cmap="viridis", mincnt=1)
            ax.plot([0, 1], [0, 1], "w--", lw=1)
            m = v[k]
            ax.set_title(f"{lab} visibility, 18.6-yr mean\nr = {m['r']}, MAE = {m['mae']}, bias = {m['bias']:+}")
            ax.set_xlabel("NASA (Mazarico et al. 2011)")
            ax.set_ylabel("This model (ray-traced on LOLA)")
            ax.set_xlim(0, 1), ax.set_ylim(0, 1)
            ax.set_facecolor("#111")
    ax = axs[2]
    regs = [r for r in res.regions if "daily_sun" in r.extra]
    if regs:
        sun = np.array([r.extra["daily_sun"] for r in regs])
        earth = np.array([r.extra["daily_earth"] for r in regs])
        # one image: yellow = Sun up, blue tint = Earth up as well
        rgb = np.zeros(sun.shape + (3,))
        rgb[..., 0] = sun * 0.98
        rgb[..., 1] = sun * 0.80
        rgb[..., 2] = np.clip(earth * 0.9, 0, 1) * (0.35 + 0.65 * (1 - sun))
        ax.imshow(rgb, aspect="auto", interpolation="nearest", extent=(0, 365, len(regs) + .5, .5))
        ax.set_yticks(range(1, len(regs) + 1), [f"#{r.rank}" for r in regs])
        months = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
        ax.set_xticks(months, ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
        ax.set_title(f"{getattr(res, 'year', '')} calendar per region\n"
                     "yellow = Sun up · blue = only Earth up · black = dark")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


TEMPLATE = r"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lunar Landing Navigator</title>
<style>__LEAFLET_CSS__</style>
<script>__LEAFLET_JS__</script>
<style>
:root{--bg:#0b0f17;--panel:#121826;--line:#243047;--text:#e6ebf5;--muted:#93a1bb;
--green:#22c55e;--yellow:#eab308;--red:#dc2626;--blue:#3b82f6;--sky:#38bdf8;--pink:#f472b6}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--text);
font-family:"Segoe UI",Tahoma,system-ui,sans-serif}
.app{display:grid;grid-template-columns:400px 1fr;height:100vh}
aside{background:var(--panel);border-left:1px solid var(--line);overflow:auto;padding:18px 16px}
h1{font-size:19px;margin:0 0 4px}
.langsw{float:left;display:grid;place-items:center;width:38px;height:38px;border-radius:50%;border:1px solid var(--line);color:var(--text);text-decoration:none;font-weight:700;font-size:13px;margin:-4px 0 6px 10px;transition:border-color .2s,background .2s}
.langsw:hover{border-color:var(--sky);background:#0c2233}
html[dir=ltr] .langsw{float:right;margin:-4px 0 6px 10px}
.sub{color:var(--muted);font-size:13px;margin-bottom:12px;line-height:1.6}
.badge{display:inline-block;border-radius:6px;padding:2px 8px;font-size:12px;margin-bottom:10px;line-height:1.6}
.b-demo{background:#3b2a07;color:#facc15;border:1px solid #6b4f0e}
.b-nasa{background:#06283b;color:#7dd3fc;border:1px solid #0c4a6e}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0 14px}
.stat{background:#0e1420;border:1px solid var(--line);border-radius:8px;padding:8px;text-align:center}
.stat b{display:block;font-size:18px}
.stat span{font-size:11px;color:var(--muted)}
h2{font-size:14px;margin:16px 0 8px;color:var(--muted);font-weight:600}
.layers label{display:flex;align-items:center;gap:8px;font-size:13px;padding:3px 0;cursor:pointer}
.reg{border:1px solid var(--line);border-radius:8px;padding:10px;margin-bottom:8px;cursor:pointer;
background:#0e1420;transition:border-color .15s}
.reg:hover,.reg.on{border-color:#4b6cb7}
.reg .top{display:flex;justify-content:space-between;align-items:center;font-weight:600}
.rank{background:var(--green);color:#04210f;border-radius:50%;width:24px;height:24px;
display:inline-flex;align-items:center;justify-content:center;font-size:13px;margin-left:6px}
.bar{height:6px;background:#1f2a3d;border-radius:4px;overflow:hidden;margin:6px 0}
.bar i{display:block;height:100%;background:linear-gradient(90deg,var(--yellow),var(--green))}
.kv{display:grid;grid-template-columns:1fr 1fr;gap:2px 10px;font-size:12px;color:var(--muted)}
.kv b{color:var(--text);font-weight:500}
.near{font-size:12px;color:var(--sky);margin-top:4px}
.chart{margin-top:8px;display:none}
.reg.on .chart{display:block}
.chart svg{width:100%;height:70px;background:#0b111c;border-radius:6px}
.chart .lg{font-size:11px;color:var(--muted);display:flex;gap:12px}
.legend{display:flex;gap:12px;font-size:12px;color:var(--muted);flex-wrap:wrap}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-left:4px;vertical-align:-2px}
.val{font-size:12.5px;line-height:1.75;background:#0e1420;border:1px solid var(--line);border-radius:8px;padding:10px}
.val b{color:#fff}
.val .ok{color:var(--green)}
#map{height:100%;background:#000}
.leaflet-container{font-family:inherit;background:#000}
.lbl{background:#000c;color:#fff;border:1px solid #fff;border-radius:50%;width:24px;height:24px;
display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px}
.star{color:var(--sky);font-size:20px;text-shadow:0 0 3px #000,0 0 2px #000;line-height:1}
.dia{width:9px;height:9px;background:var(--pink);transform:rotate(45deg);border:1px solid #000}
.lm{color:#cbd5e1;font-size:11px;text-shadow:0 0 3px #000,0 0 3px #000;white-space:nowrap;direction:ltr}
.gl{color:#94a3b8;font-size:10px;text-shadow:0 0 3px #000;white-space:nowrap;direction:ltr}
.leaflet-popup-content{direction:rtl;font-size:13px;line-height:1.7}
bdi{unicode-bidi:isolate}
@media (max-width:800px){.app{grid-template-columns:1fr;grid-template-rows:55vh auto;height:auto}
#map{height:55vh}aside{border-left:0;border-top:1px solid var(--line);order:2}}
</style>
</head>
<body>
<div class="app">
<aside>
  <a class="langsw" href="__OTHER_LANG__" lang="en" title="English version">EN</a>
  <h1>🌕 مستكشف مواقع الهبوط القمري</h1>
  <div class="sub" id="sub"></div>
  <div id="badge"></div>
  <div class="legend">
    <span><i style="background:var(--green)"></i>آمن</span>
    <span><i style="background:var(--yellow)"></i>متوسط</span>
    <span><i style="background:var(--red)"></i>خطر</span>
    <span><i style="background:var(--blue)"></i>ظل دائم (جليد محتمل)</span>
    <span id="lg-ref" style="display:none"><span style="color:var(--sky)">★</span> مناطق ناسا · <span style="color:var(--pink)">◆</span> أفضل نقاط TOPSIS</span>
  </div>
  <div class="stats" id="stats"></div>
  <h2>الطبقات</h2>
  <div class="layers" id="layers"></div>
  <div id="valbox"></div>
  <h2>أفضل المناطق (مرتبة)</h2>
  <div id="regions"></div>
</aside>
<div id="map"></div>
</div>
<script>
const D = __DATA__;
const IMG = __LAYERS__;
const pct = v => (v==null? "—" : (v*100).toFixed(0) + "%");
const ll = (r,c) => [D.h - r, c];
document.getElementById("sub").innerHTML =
  `المنطقة: <b>${D.name}</b> · دقة ${D.px} م/بكسل · ${(D.w*D.px/1000).toFixed(0)}×${(D.h*D.px/1000).toFixed(0)} كم` +
  (D.nasa ? `<br>تحليل نوافذ المهمة لعام <b>${D.year}</b> (مدة ${D.window[1]} يوم)` :
   `<br>نافذة المهمة: يوم ${D.window[0].toFixed(1)} → ${D.window[1].toFixed(1)}`);
document.getElementById("badge").innerHTML = D.synthetic
  ? '<span class="badge b-demo">بيانات تجريبية مُولّدة — للعرض فقط</span>'
  : '<span class="badge b-nasa">بيانات ناسا الرسمية: LOLA (Barker 2023) + الإضاءة والظل الدائم (Mazarico 2011)</span>';
const S = D.stats;
document.getElementById("stats").innerHTML =
  [["آمن",pct(S.green),"var(--green)"],["متوسط",pct(S.yellow),"var(--yellow)"],["خطر",pct(S.red),"var(--red)"],
   ["ظل دائم",pct(S.psr),"var(--blue)"],["حفر مكتشفة",S.craters.toLocaleString("en"),"var(--text)"],["مناطق",D.regions.length,"var(--text)"]]
  .map(([t,v,c])=>`<div class="stat"><b style="color:${c}">${v}</b><span>${t}</span></div>`).join("");

const map = L.map("map",{crs:L.CRS.Simple,minZoom:-4,maxZoom:4,zoomSnap:.25,attributionControl:false});
const B = [[0,0],[D.h,D.w]];
L.imageOverlay(IMG.base, B).addTo(map);
const defs = [["classes","التصنيف (آمن/متوسط/خطر)",true],["psr","الظل الدائم (PSR)",true],["score","النقاط الكلية",false],
  ["slope","الميلان",false],["illumination", D.nasa?"متوسط الإضاءة 18.6 سنة (ناسا)":"الإضاءة خلال المهمة",false],
  ["earth","رؤية الأرض",false],["hazard","الصخور والحفر والخشونة",false]];
const over = {};
const box = document.getElementById("layers");
function addToggle(t, layer, on){
  if (on) layer.addTo(map);
  const lab = document.createElement("label");
  lab.innerHTML = `<input type="checkbox" ${on?"checked":""}> ${t}`;
  lab.querySelector("input").onchange = e => e.target.checked ? layer.addTo(map) : map.removeLayer(layer);
  box.appendChild(lab);
}
defs.forEach(([k,t,on])=>{ over[k] = L.imageOverlay(IMG[k], B, {opacity:.85}); addToggle(t, over[k], on); });
map.fitBounds(B);

if (D.graticule.length){
  const g = L.layerGroup();
  D.graticule.forEach(l=>{
    L.polyline(l.pts.map(p=>ll(p[0],p[1])),{color:"#94a3b8",weight:.7,opacity:.55,interactive:false}).addTo(g);
    const p = l.kind==="lat" ? l.pts[0] : l.pts[1];
    const q = l.kind==="lat" ? p : [Math.max(10,Math.min(D.h-10,p[0])), Math.max(10,Math.min(D.w-10,p[1]))];
    L.marker(ll(q[0],q[1]),{icon:L.divIcon({className:"",html:`<span class="gl">${l.label}</span>`,iconSize:[40,12]}),interactive:false}).addTo(g);
  });
  addToggle("شبكة خطوط العرض والطول", g, true);
}
L.marker(ll(D.pole[0],D.pole[1]),{icon:L.divIcon({className:"",html:'<div style="color:#fff;font-size:18px">✛</div>',iconSize:[18,18]})})
  .addTo(map).bindTooltip("القطب الجنوبي");

const R = D.refs || {};
if (R.nasa_regions){
  document.getElementById("lg-ref").style.display="";
  const g = L.layerGroup(), t = L.layerGroup(), m = L.layerGroup();
  const seen = {};
  R.nasa_regions.forEach(x=>{
    const key = x.lat+","+x.lon; const names = (seen[key]=seen[key]||[]); names.push(x.name);
  });
  Object.entries(seen).forEach(([k,names])=>{
    const x = R.nasa_regions.find(z=>z.lat+","+z.lon===k);
    L.marker(ll(x.row,x.col),{icon:L.divIcon({className:"",html:'<div class="star">★</div>',iconSize:[20,20],iconAnchor:[10,10]})})
     .addTo(g).bindPopup(`<b>منطقة ناسا لـ Artemis III:</b><br>${names.join(" / ")}<br>
       <small>موقعها على الخريطة تقريبي (مركز المَعْلم <bdi>${x.feature}</bdi> من دليل IAU)</small><br>
       أقرب منطقة من مناطقنا: <b>${x.km_to_nearest_final_region} كم</b>`);
  });
  (R.topsis||[]).forEach(x=>{
    L.marker(ll(x.row,x.col),{icon:L.divIcon({className:"",html:'<div class="dia"></div>',iconSize:[9,9],iconAnchor:[5,5]})})
     .addTo(t).bindPopup(`<b>نقطة TOPSIS رقم ${x.id}</b> (<bdi>${x.region}</bdi>)<br>ترتيبها في الورقة: R=${x.topsis}<br>
       نقاطها عندنا: ${x.our_score} — أعلى من <b>${pct(x.our_percentile)}</b> من المنطقة<br><small>arXiv:2406.19863</small>`);
  });
  (R.landmarks||[]).forEach(x=>{
    L.marker(ll(x.row,x.col),{icon:L.divIcon({className:"",html:`<span class="lm">${x.name}</span>`,iconSize:[80,12],iconAnchor:[-4,6]}),interactive:false}).addTo(m);
  });
  addToggle("مناطق ناسا التسع لـ Artemis III ★", g, true);
  addToggle("أفضل 20 نقطة في دراسة TOPSIS ◆", t, true);
  addToggle("أسماء المعالم (IAU)", m, true);
}

const V = D.validation || {};
if (V.model_vs_nasa || V.topsis){
  const mv = V.model_vs_nasa, tp = V.topsis, nr = V.nasa_regions;
  document.getElementById("valbox").innerHTML = `<h2>التحقق من الدقة</h2><div class="val">` +
   (mv ? `نموذجنا للإضاءة مقابل خرائط ناسا (${mv.n_pixels.toLocaleString("en")} نقطة × ${mv.n_epochs.toLocaleString("en")} لحظة زمنية على 18.6 سنة):<br>
     ☀️ الشمس: ارتباط <b class="ok">r = ${mv.sun.r}</b> · متوسط الخطأ <b>${(mv.sun.mae*100).toFixed(1)}</b> نقطة مئوية<br>
     🌍 الأرض: ارتباط <b class="ok">r = ${mv.earth.r}</b> · متوسط الخطأ <b>${(mv.earth.mae*100).toFixed(1)}</b> نقطة مئوية<br>` : "") +
   (tp ? `أفضل 20 نقطة في دراسة TOPSIS المستقلة: <b class="ok">${pct(tp.share_top10pct)}</b> منها داخل أفضل 10% من خريطتنا (الوسيط: أعلى من ${pct(tp.median_percentile)}).<br>` : "") +
   (nr ? `مناطق ناسا التسع: <b class="ok">${nr.n_with_our_final_region}/9</b> عندها منطقة من مناطقنا التسع، و<b>${nr.n_with_our_candidate}/9</b> من مرشحينا الـ13.` : "") +
   `</div>`;
}

D.candidates.forEach(r=>L.rectangle([ll(r.row1,r.col0),ll(r.row0,r.col1)],
  {color:"#94a3b8",weight:1,dashArray:"4 4",fill:false}).addTo(map)
  .bindTooltip(`مرشحة مستبعدة #${r.rank} · ${(r.final_score??r.score).toFixed(2)}`));

function spark(r){
  if (!r.daily_sun) return "";
  const W=365,H=70, p=(arr,col,dash)=>`<polyline fill="none" stroke="${col}" stroke-width="1.2" ${dash?'stroke-dasharray="3 2"':''} points="${arr.map((v,i)=>`${(i/(arr.length-1)*W).toFixed(1)},${(H-2-v*(H-6)).toFixed(1)}`).join(" ")}"/>`;
  return `<div class="chart"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${p(r.daily_sun,"#facc15")}${p(r.daily_earth,"#38bdf8",true)}</svg>
   <div class="lg"><span style="color:#facc15">━ الشمس</span><span style="color:#38bdf8">┅ الأرض</span><span>يناير ← ديسمبر ${D.year}</span></div></div>`;
}
const popup = r => `<b>المنطقة #${r.rank}</b> — نقاط ${(r.final_score??r.score).toFixed(2)}<br>
أفضل نقطة هبوط: <bdi dir="ltr">${Math.abs(r.lat_deg).toFixed(3)}°S, ${r.lon_deg.toFixed(2)}°E</bdi><br>
الميلان: ${r.best_slope_deg}° · الإضاءة: ${pct(r.best_illumination)}<br>
رؤية الأرض: ${pct(r.best_earth_visibility)} · أقرب ظل دائم: ${r.best_psr_distance_km} كم` +
(r.availability!=null ? `<br>نوافذ مضيئة بالكامل في ${D.year}: <b>${pct(r.availability)}</b> من السنة` +
  (r.best_window ? `<br>أفضل نافذة: <bdi dir="ltr">${r.best_window.start}</bdi> UTC (تواصل مع الأرض ${pct(r.best_window.earth_contact)})` : "") : "");
function nearNasa(r){
  if (!R.nasa_regions) return "";
  const n = R.nasa_regions.filter(x=>x.our_final_regions_within_radius.includes(r.rank)).map(x=>x.name);
  return n.length ? `<div class="near">★ قريبة من منطقة ناسا: <bdi>${[...new Set(n)].join(" / ")}</bdi></div>` : "";
}
const list = document.getElementById("regions");
const rects = {};
D.regions.forEach(r=>{
  rects[r.rank] = L.rectangle([ll(r.row1,r.col0),ll(r.row0,r.col1)],{color:"#fff",weight:1.5,fill:false}).addTo(map);
  const m = L.marker(ll(r.best_row+.5,r.best_col+.5),{icon:L.divIcon({className:"",html:`<div class="lbl">${r.rank}</div>`,iconSize:[24,24],iconAnchor:[12,12]})})
    .addTo(map).bindPopup(popup(r));
  const sc = r.final_score ?? r.score;
  const el = document.createElement("div");
  el.className = "reg";
  el.innerHTML = `<div class="top"><span><span class="rank">${r.rank}</span>المنطقة ${r.rank}</span><span>${sc.toFixed(2)}</span></div>
  <div class="bar"><i style="width:${Math.min(100,sc*100)}%"></i></div>
  <div class="kv"><span>مساحة آمنة <b>${pct(r.safe_fraction)}</b></span><span>ميلان أفضل نقطة <b>${r.best_slope_deg}°</b></span>
  <span>الإضاءة <b>${pct(r.best_illumination)}</b></span><span>رؤية الأرض <b>${pct(r.best_earth_visibility)}</b></span>
  <span>أقرب ظل دائم <b>${r.best_psr_distance_km} كم</b></span><span>الموقع <b><bdi dir="ltr">${Math.abs(r.lat_deg).toFixed(2)}°S, ${r.lon_deg.toFixed(0)}°E</bdi></b></span>
  ${r.availability!=null?`<span>نوافذ ${D.year} <b>${pct(r.availability)}</b></span><span>أفضل نافذة <b><bdi dir="ltr">${r.best_window?r.best_window.start.slice(0,10):"—"}</bdi></b></span>`:""}</div>
  ${nearNasa(r)}${spark(r)}`;
  el.onclick = () => {
    document.querySelectorAll(".reg").forEach(x=>x.classList.remove("on")); el.classList.add("on");
    map.fitBounds(rects[r.rank].getBounds().pad(.6)); m.openPopup();
  };
  list.appendChild(el);
});
</script>
</body>
</html>
"""
