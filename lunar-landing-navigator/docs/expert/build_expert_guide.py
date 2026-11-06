"""Build the Arabic Expert Guide (HTML -> PDF) from expert_series.json,
the same script the expert video series is narrated from."""
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / "expert_series.json").read_text(encoding="utf-8"))


def fx(t):
    t = html.escape(t)
    t = re.sub(r"و(?=[A-Za-z0-9.])", "و ", t)
    return re.sub(r"([A-Za-z][A-Za-z0-9 .\-/_:#+{}]*[A-Za-z0-9}])", r"<bdi>\1</bdi>", t)


toc = "".join(f"<li>الفصل {c['chapter']}: {fx(c['title_ar'])} <span class='en'>{html.escape(c['title_en'])}</span></li>" for c in data)
body = []
for c in data:
    body.append(f"<section class='chapter'><h2 class='ch'><span class='n'>{c['chapter']}</span>{fx(c['title_ar'])}</h2>"
                f"<p class='chsub'>{html.escape(c['title_en'])} · فيديو: <span class='ltr'>chapter_{c['chapter']}.mp4</span></p>")
    for i, s in enumerate(c["scenes"], 1):
        img = f"<figure><img src='../guide/img/{s['img']}' alt=''></figure>" if s.get("img") and s["img"] != "site.png" else ""
        bl = "".join(f"<li>{fx(b)}</li>" for b in s["b"])
        body.append(f"<div class='scene'><h3><span class='k'>{c['chapter']}.{i}</span>{fx(s['t'])}</h3>"
                    f"<ul class='pts'>{bl}</ul><p>{fx(s['ar'])}</p>{img}"
                    f"<details open><summary>النص الإنجليزي للفيديو</summary><p class='en'>{html.escape(s['en'])}</p></details></div>")
    body.append("</section>")

page = (HERE / "template.html").read_text(encoding="utf-8").replace("{{TOC}}", toc).replace("{{BODY}}", "\n".join(body))
(HERE / "EXPERT_GUIDE_AR.html").write_text(page, encoding="utf-8")
print("wrote", HERE / "EXPERT_GUIDE_AR.html")
