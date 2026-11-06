"""Interactive HTML map (Leaflet) + static PNG summary."""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from .scoring import GREEN, RED, YELLOW
from .terrain import hillshade

CLASS_RGBA = {GREEN: (34, 197, 94, 150), YELLOW: (234, 179, 8, 150), RED: (220, 38, 38, 130)}


def _png_b64(rgba: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(rgba).save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


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


def build_layers(res):
    L, sc = res.layers, res.scene
    hs = hillshade(sc.dem, sc.pixel_size_m)
    base = np.dstack([(hs * 255).astype(np.uint8)] * 3 + [np.full(hs.shape, 255, np.uint8)])
    psr = np.zeros(L.psr.shape + (4,), np.uint8)
    psr[L.psr] = (59, 130, 246, 190)
    return {
        "base": _png_b64(base),
        "classes": _png_b64(class_rgba(res.cls)),
        "score": _png_b64(_cmap(res.score, "viridis", 0, 1)),
        "slope": _png_b64(_cmap(L.slope, "magma_r", 0, 20)),
        "illumination": _png_b64(_cmap(L.illumination, "inferno", 0, 1)),
        "earth": _png_b64(_cmap(L.earth, "cividis", 0, 1)),
        "hazard": _png_b64(_cmap(L.hazard, "Reds", 0, 1)),
        "psr": _png_b64(psr),
    }


def write_html(res, path: str | Path):
    h, w = res.scene.shape
    payload = {
        "h": h, "w": w, "px": res.scene.pixel_size_m, "name": res.scene.name,
        "synthetic": bool(res.scene.meta.get("synthetic")),
        "window": res.mission_window,
        "pole": res.scene.pole_rc,
        "regions": [r.to_dict() for r in res.regions],
        "candidates": [r.to_dict() for r in res.candidates[len(res.regions):]],
        "stats": {
            "green": float(np.mean(res.cls == GREEN)), "yellow": float(np.mean(res.cls == YELLOW)),
            "red": float(np.mean(res.cls == RED)), "psr": float(res.layers.psr.mean()),
            "craters": len(res.craters),
        },
    }
    layers = build_layers(res)
    vendor = Path(__file__).parent / "vendor"
    html = (TEMPLATE
            .replace("__LEAFLET_CSS__", (vendor / "leaflet.css").read_text(encoding="utf-8"))
            .replace("__LEAFLET_JS__", (vendor / "leaflet.js").read_text(encoding="utf-8"))
            .replace("__DATA__", json.dumps(payload))
            .replace("__LAYERS__", json.dumps(layers)))
    Path(path).write_text(html, encoding="utf-8")
    return path


def write_png_summary(res, path: str | Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    L = res.layers
    fig, axs = plt.subplots(2, 3, figsize=(15, 10), dpi=110)
    panels = [("Slope (deg)", L.slope, "magma_r", 0, 20), ("Mission illumination", L.illumination, "inferno", 0, 1),
              ("Earth visibility", L.earth, "cividis", 0, 1), ("Hazard (rocks/craters)", L.hazard, "Reds", 0, 1),
              ("Score", res.score, "viridis", 0, 1)]
    for ax, (t, a, cm, lo, hi) in zip(axs.flat, panels):
        im = ax.imshow(a, cmap=cm, vmin=lo, vmax=hi)
        ax.set_title(t)
        fig.colorbar(im, ax=ax, fraction=0.046)
    ax = axs.flat[5]
    hs = hillshade(res.scene.dem, res.scene.pixel_size_m)
    ax.imshow(hs, cmap="gray")
    ax.imshow(class_rgba(res.cls))
    for r in res.regions:
        ax.add_patch(Rectangle((r.col0, r.row0), r.col1 - r.col0, r.row1 - r.row0,
                               fill=False, ec="white", lw=1.2))
        ax.text(r.best_col, r.best_row, str(r.rank), color="white", fontsize=9,
                ha="center", va="center", weight="bold",
                bbox=dict(boxstyle="circle,pad=0.2", fc="black", ec="white", lw=0.8))
    ax.set_title("Safe (green) / marginal (yellow) / unsafe (red)")
    for a in axs.flat:
        a.set_xticks([]), a.set_yticks([])
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
--green:#22c55e;--yellow:#eab308;--red:#dc2626;--blue:#3b82f6}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--text);
font-family:"Segoe UI",Tahoma,system-ui,sans-serif}
.app{display:grid;grid-template-columns:380px 1fr;height:100vh}
aside{background:var(--panel);border-left:1px solid var(--line);overflow:auto;padding:18px 16px}
h1{font-size:19px;margin:0 0 4px}
.sub{color:var(--muted);font-size:13px;margin-bottom:14px;line-height:1.6}
.badge{display:inline-block;background:#3b2a07;color:#facc15;border:1px solid #6b4f0e;
border-radius:6px;padding:2px 8px;font-size:12px;margin-bottom:10px}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0 16px}
.stat{background:#0e1420;border:1px solid var(--line);border-radius:8px;padding:8px;text-align:center}
.stat b{display:block;font-size:18px}
.stat span{font-size:11px;color:var(--muted)}
h2{font-size:14px;margin:16px 0 8px;color:var(--muted);font-weight:600}
.layers label{display:flex;align-items:center;gap:8px;font-size:13px;padding:4px 0;cursor:pointer}
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
.legend{display:flex;gap:12px;font-size:12px;color:var(--muted);flex-wrap:wrap}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-left:4px;vertical-align:-2px}
#map{height:100%;background:#000}
.leaflet-container{font-family:inherit}
.lbl{background:#000c;color:#fff;border:1px solid #fff;border-radius:50%;width:24px;height:24px;
display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px}
.leaflet-popup-content{direction:rtl;font-size:13px;line-height:1.7}
@media (max-width:800px){.app{grid-template-columns:1fr;grid-template-rows:55vh auto;height:auto}
#map{height:55vh}aside{border-left:0;border-top:1px solid var(--line);order:2}}
</style>
</head>
<body>
<div class="app">
<aside>
  <h1>🌕 مستكشف مواقع الهبوط القمري</h1>
  <div class="sub" id="sub"></div>
  <div id="synth"></div>
  <div class="legend">
    <span><i style="background:var(--green)"></i>آمن</span>
    <span><i style="background:var(--yellow)"></i>متوسط</span>
    <span><i style="background:var(--red)"></i>خطر</span>
    <span><i style="background:var(--blue)"></i>ظل دائم (جليد محتمل)</span>
  </div>
  <div class="stats" id="stats"></div>
  <h2>الطبقات</h2>
  <div class="layers" id="layers"></div>
  <h2>أفضل المناطق (مرتبة)</h2>
  <div id="regions"></div>
</aside>
<div id="map"></div>
</div>
<script>
const D = __DATA__;
const IMG = __LAYERS__;
const pct = v => (v*100).toFixed(0) + "%";
document.getElementById("sub").innerHTML =
  `المنطقة: <b>${D.name}</b> · دقة ${D.px} م/بكسل · ${(D.w*D.px/1000).toFixed(0)}×${(D.h*D.px/1000).toFixed(0)} كم<br>` +
  `نافذة المهمة: يوم ${D.window[0].toFixed(1)} → ${D.window[1].toFixed(1)} (${(D.window[1]-D.window[0]).toFixed(1)} يوم)`;
if (D.synthetic) document.getElementById("synth").innerHTML =
  '<span class="badge">بيانات تجريبية مُولّدة — شغّل الأداة على بيانات LOLA الحقيقية للنتائج الفعلية</span>';
const S = D.stats;
document.getElementById("stats").innerHTML =
  [["آمن",pct(S.green),"var(--green)"],["متوسط",pct(S.yellow),"var(--yellow)"],["خطر",pct(S.red),"var(--red)"],
   ["ظل دائم",pct(S.psr),"var(--blue)"],["حفر مكتشفة",S.craters,"var(--text)"],["مناطق",D.regions.length,"var(--text)"]]
  .map(([t,v,c])=>`<div class="stat"><b style="color:${c}">${v}</b><span>${t}</span></div>`).join("");

const map = L.map("map",{crs:L.CRS.Simple,minZoom:-3,maxZoom:4,zoomSnap:.25,attributionControl:false});
const B = [[0,0],[D.h,D.w]];
const ll = (r,c) => [D.h - r, c];
L.imageOverlay(IMG.base, B).addTo(map);
const defs = [["classes","التصنيف (آمن/متوسط/خطر)",true],["psr","الظل الدائم (PSR)",true],["score","النقاط الكلية",false],
  ["slope","الميلان",false],["illumination","الإضاءة خلال المهمة",false],["earth","رؤية الأرض",false],["hazard","الصخور والحفر",false]];
const over = {};
const box = document.getElementById("layers");
defs.forEach(([k,t,on])=>{
  over[k] = L.imageOverlay(IMG[k], B, {opacity:.85});
  if (on) over[k].addTo(map);
  const lab = document.createElement("label");
  lab.innerHTML = `<input type="checkbox" ${on?"checked":""}> ${t}`;
  lab.querySelector("input").onchange = e => e.target.checked ? over[k].addTo(map) : map.removeLayer(over[k]);
  box.appendChild(lab);
});
map.fitBounds(B);
L.marker(ll(D.pole[0],D.pole[1]),{icon:L.divIcon({className:"",html:'<div style="color:#fff;font-size:18px">✛</div>',iconSize:[18,18]})})
  .addTo(map).bindTooltip("القطب الجنوبي");

D.candidates.forEach(r=>L.rectangle([ll(r.row1,r.col0),ll(r.row0,r.col1)],
  {color:"#94a3b8",weight:1,dashArray:"4 4",fill:false}).addTo(map)
  .bindTooltip(`مرشحة مستبعدة #${r.rank} · ${r.score.toFixed(2)}`));

const popup = r => `<b>المنطقة #${r.rank}</b> — نقاط ${r.score.toFixed(2)}<br>
أفضل نقطة هبوط: <bdi dir="ltr">${r.lat_deg.toFixed(3)}°, ${r.lon_deg.toFixed(2)}°E</bdi><br>
الميلان: ${r.best_slope_deg}° · الإضاءة: ${pct(r.best_illumination)}<br>
رؤية الأرض: ${pct(r.best_earth_visibility)} · أقرب ظل دائم: ${r.best_psr_distance_km} كم`;
const list = document.getElementById("regions");
const rects = {};
D.regions.forEach(r=>{
  rects[r.rank] = L.rectangle([ll(r.row1,r.col0),ll(r.row0,r.col1)],{color:"#fff",weight:1.5,fill:false}).addTo(map);
  const m = L.marker(ll(r.best_row+.5,r.best_col+.5),{icon:L.divIcon({className:"",html:`<div class="lbl">${r.rank}</div>`,iconSize:[24,24],iconAnchor:[12,12]})})
    .addTo(map).bindPopup(popup(r));
  const el = document.createElement("div");
  el.className = "reg";
  el.innerHTML = `<div class="top"><span><span class="rank">${r.rank}</span>المنطقة ${r.rank}</span><span>${r.score.toFixed(2)}</span></div>
  <div class="bar"><i style="width:${Math.min(100,r.score*100)}%"></i></div>
  <div class="kv"><span>مساحة آمنة <b>${pct(r.safe_fraction)}</b></span><span>متوسط الميلان <b>${r.mean_slope_deg}°</b></span>
  <span>الإضاءة <b>${pct(r.mean_illumination)}</b></span><span>رؤية الأرض <b>${pct(r.mean_earth_visibility)}</b></span>
  <span>أقرب ظل دائم <b>${r.best_psr_distance_km} كم</b></span><span>الموقع <b><bdi dir="ltr">${r.lat_deg.toFixed(2)}°, ${r.lon_deg.toFixed(0)}°E</bdi></b></span></div>`;
  el.onclick = () => {
    document.querySelectorAll(".reg").forEach(x=>x.classList.remove("on")); el.classList.add("on");
    map.fitBounds(rects[r.rank].getBounds().pad(.3)); m.openPopup();
  };
  list.appendChild(el);
});
</script>
</body>
</html>
"""
