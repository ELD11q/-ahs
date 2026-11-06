"""Markdown report (Arabic) for a NASA-data run."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .scoring import GREEN, RED, YELLOW


def _p(v):
    return "—" if v is None else f"{v * 100:.0f}%"


def write_report(res, path):
    sc = res.scene
    v = res.validation
    L = []
    a = L.append
    a(f"# تقرير مواقع الهبوط — القطب الجنوبي للقمر (بيانات ناسا الرسمية، نوافذ {res.year})\n")
    a("## البيانات المستخدمة\n")
    a("| الطبقة | المنتج | المصدر |\n|---|---|---|")
    for k, p in sc.meta.get("products", {}).items():
        a(f"| {k} | `{p['url'].rsplit('/', 1)[-1]}` — {p['desc']} | {p['ref']} |")
    g = sc.meta.get("grid", {})
    a(f"\nشبكة التحليل: {sc.shape[1]}×{sc.shape[0]} بكسل بدقة {sc.pixel_size_m:g} م "
      f"(±{g.get('half_width_m', 0) / 1000:.0f} كم حول القطب)، داخل منطقة استكشاف Artemis (6° من القطب).\n")
    a(f"التصنيف: 🟩 آمن {np.mean(res.cls == GREEN) * 100:.1f}% · 🟨 متوسط {np.mean(res.cls == YELLOW) * 100:.1f}% · "
      f"🟥 خطر/خارج المنطقة {np.mean(res.cls == RED) * 100:.1f}% · 🟦 ظل دائم {res.layers.psr.mean() * 100:.1f}% · "
      f"حفر مكتشفة: {len(res.craters):,}\n")

    a("## أفضل 9 مناطق\n")
    a("| # | النقاط النهائية | نقاط التضاريس | نوافذ مضيئة بالكامل " + str(res.year) +
      " | أفضل نافذة (UTC) | الميلان | الإضاءة (ناسا) | رؤية الأرض (ناسا) | أقرب ظل دائم | الإحداثيات | منطقة ناسا القريبة |")
    a("|---|---|---|---|---|---|---|---|---|---|---|")
    near = {}
    for x in res.references.get("nasa_regions", []):
        for k in x["our_final_regions_within_radius"]:
            near.setdefault(k, set()).add(x["name"])
    for r in res.regions:
        e = r.extra
        bw = e.get("best_window") or {}
        a(f"| {r.rank} | {e.get('final_score', r.score):.3f} | {r.score:.3f} | {_p(e.get('availability'))} | "
          f"{bw.get('start', '—')} | {r.best_slope_deg}° | {_p(r.best_illumination)} | {_p(r.best_earth_visibility)} | "
          f"{r.best_psr_distance_km} كم | {abs(r.lat_deg):.3f}°S, {r.lon_deg:.2f}°E | {' / '.join(sorted(near.get(r.rank, []))) or '—'} |")

    a("\n## التحقق من الدقة\n")
    mv = v.get("model_vs_nasa")
    if mv:
        a(f"### 1) نموذج الإضاءة مقابل خرائط ناسا\n")
        a(f"حسبنا متوسط 18.6 سنة بأنفسنا (تتبع أشعة الأفق على LOLA + مواقع الشمس والأرض الحقيقية) لـ "
          f"{mv['n_pixels']:,} نقطة × {mv['n_epochs']:,} لحظة زمنية، وقارنّاه بخرائط Mazarico et al. (2011):\n")
        a("| | الارتباط r | متوسط الخطأ | الانحياز | خطأ < 5 نقاط | خطأ < 10 نقاط |\n|---|---|---|---|---|---|")
        for k, n in (("sun", "الشمس"), ("earth", "الأرض")):
            m = mv[k]
            a(f"| {n} | {m['r']} | {m['mae'] * 100:.1f} نقطة | {m['bias'] * 100:+.1f} نقطة | {_p(m['within_0.05'])} | {_p(m['within_0.10'])} |")
    tp = v.get("topsis", {})
    a("\n### 2) مقارنة مع دراسة مستقلة (arXiv:2406.19863، طريقة TOPSIS)\n")
    a(f"- {_p(tp.get('share_top10pct'))} من أفضل 20 نقطة عندهم تقع ضمن أفضل 10% من خريطتنا "
      f"(الوسيط: أعلى من {_p(tp.get('median_percentile'))} من المنطقة).")
    b = tp.get("best_point_358") or {}
    if b:
        a(f"- أفضل نقطة عندهم (#358، Nobile Rim 2): نقاطها عندنا {b.get('our_score')} — أعلى من "
          f"{_p(b.get('our_percentile'))} من المنطقة، والتصنيف {'آمن' if b.get('our_class') == GREEN else 'غير آمن'}.")
    a("\n| النقطة | المنطقة | R (TOPSIS) | نقاطنا | ترتيبها عندنا (percentile) | الميلان |\n|---|---|---|---|---|---|")
    for x in res.references.get("topsis", []):
        a(f"| {x['id']} | {x['region']} | {x['topsis']} | {x['our_score']} | {_p(x['our_percentile'])} | {x['slope']}° |")
    nr = v.get("nasa_regions", {})
    a("\n### 3) مقارنة مع مناطق ناسا التسع لـ Artemis III (أكتوبر 2024)\n")
    a(f"- {nr.get('n_with_our_final_region')}/9 من مناطق ناسا عندها منطقة من مناطقنا التسع، "
      f"و{nr.get('n_with_our_candidate')}/9 من مرشحينا الـ13.")
    a("- ناسا ما تنشر حدود المناطق، فموقع كل منطقة هنا هو مركز المَعْلم اللي سُمّيت عليه (دليل IAU)، "
      "ونصف قطر المطابقة = نصف قطر المعلم + 10 كم (بين 20 و50 كم).\n")
    a("| منطقة ناسا | المعلم | نصف قطر المطابقة | أقرب منطقة لنا | مناطقنا داخلها | أفضل نقاط قريبة (percentile) |\n|---|---|---|---|---|---|")
    for x in res.references.get("nasa_regions", []):
        a(f"| {x['name']} | {x['feature']} | {x['match_radius_km']:.0f} كم | {x['km_to_nearest_final_region']} كم | "
          f"{', '.join('#%d' % k for k in x['our_final_regions_within_radius']) or '—'} | {_p(x['best_percentile_within_radius'])} |")

    a("\n## ملاحظات وحدود\n")
    a("- متوسطات ناسا (18.6 سنة) تشمل الشتاء القطبي، فقيمها أقل من إضاءة نافذة مهمة صيفية؛ لهذا نحسب نوافذ "
      f"{res.year} الحقيقية لكل منطقة مرشحة ونعطيها 40% من الترتيب النهائي.")
    a("- 'نافذة مضيئة بالكامل' = 6.5 يوم متواصلة فيها أكثر من نصف قرص الشمس فوق الأفق في كل ساعة، لراصد على ارتفاع 2 م.")
    a("- مناطق ناسا تعتمد كمان على قيود ما تدخل في نموذجنا: مدار NRHO، مسارات الإطلاق، تصميم مركبة SpaceX HLS، "
      "وصور LROC NAC عالية الدقة للصخور. اختلافنا معها في بعض المناطق متوقع ومفسَّر.")
    a("- الخشونة والصخور من LOLA (خط أساس 100 م)؛ الصخور الأصغر تحتاج صور NAC + YOLO.")
    a("\n## المراجع\n")
    a("- Barker, M.K. et al. (2023). A New View of the Lunar South Pole from LOLA. PGDA product 90.")
    a("- Mazarico, E. et al. (2011). Illumination conditions of the lunar polar regions using LOLA topography. Icarus 211.")
    a("- Peña-Asensio, E., Neira-Acosta, Á.-S., Sánchez-Lozano, J.M. (2024). arXiv:2406.19863.")
    a("- NASA (2025). Artemis III Site Selection Update: Downselection From Thirteen to Nine Candidate Regions. NTRS 20250011660.")
    a("- Archinal, B.A. et al. (2011). Report of the IAU WGCCRE: 2009. Celest. Mech. Dyn. Astr. 109.")
    a("- IAU/USGS Gazetteer of Planetary Nomenclature.")
    Path(path).write_text("\n".join(L) + "\n", encoding="utf-8")
    return Path(path)
