// Lunar Landing Navigator — 3D story site (page logic).
// The 3D scene lives in scene3d.js and is loaded only when WebGL works;
// everything else on the page works without it.
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const lite = new URLSearchParams(location.search).has("lite");
const mobile = matchMedia("(max-width: 760px)").matches;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const hideLoader = () => $("#loader").classList.add("done");
// never leave visitors on the loading screen
const loaderGuard = setTimeout(hideLoader, 20000);

function webglWorks() {
  try {
    const c = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
  } catch (e) { return false; }
}

/* ------------------------------------------------------------------ data */
let DATA;
try {
  DATA = await fetch("site/assets/site_data.json").then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
} catch (e) {
  console.error("site data unavailable", e);
  DATA = { regions: [], nasa_regions: [], landmarks: [], years: {}, terrain: {} };
}

/* ------------------------------------------------------------ state + tl */
// Everything the scroll controls lives in S; the 3D render loop applies it.
const S = {
  cx: 0, cy: 0.4, cz: 4.2, tx: 0, ty: 0, tz: 0, // camera + target (globe space)
  moonSpin: 0, pole: 0, mix: 0,                  // mix: 0 globe -> 1 terrain
  tcx: 0, tcy: 330, tcz: 330, ttx: 0, tty: 0, ttz: 0, // terrain camera
  overlay: 0, beams: 0, nasa: 0, lm: 0, sunSpeed: 1, sunElev: 3.2, orbit: 0,
};
gsap.registerPlugin(ScrollTrigger);
const lenis = reduceMotion ? null : new Lenis({ duration: 1.15, smoothWheel: true });
if (lenis) {
  lenis.on("scroll", ScrollTrigger.update);
  gsap.ticker.add(t => lenis.raf(t * 1000));
  gsap.ticker.lagSmoothing(0);
}

/* ---------------------------------------------------------------- 3D scene */
let scene3d = null;
if (webglWorks()) {
  try {
    const m = await import("./scene3d.js");
    scene3d = await m.start({ DATA, S, $, mobile, lite, reduceMotion, onPick: rank => flyToRegion(rank) });
  } catch (e) {
    console.warn("3D scene disabled:", e);
    scene3d = null;
  }
}
if (!scene3d) document.body.classList.add("no-webgl");

let tl;
function buildTimeline() {
  if (!scene3d) return;
  if (tl) { tl.scrollTrigger && tl.scrollTrigger.kill(); tl.kill(); }
  const story = $("#story"), vh = innerHeight, top0 = story.offsetTop;
  const at = id => $("#" + id).offsetTop - top0;          // scroll offset where a section's top reaches the top
  const seg = id => [Math.max(0, at(id) - vh * 0.85), vh * 0.85]; // animate while the section rises into view
  tl = gsap.timeline({ defaults: { ease: "power2.inOut" },
    scrollTrigger: { trigger: story, start: "top top", end: "bottom bottom", scrub: reduceMotion ? true : 1.1, invalidateOnRefresh: false } });
  let [p, d] = seg("why");
  tl.to(S, { cx: -1.1, cy: 0.2, cz: 3.0, duration: d }, p);
  [p, d] = seg("descent");
  tl.to(S, { cx: 0, cy: -2.6, cz: 1.15, ty: -0.6, pole: 1, duration: d }, p);
  [p, d] = seg("dive");
  tl.to(S, { cy: -1.45, cz: 0.18, ty: -1.0, duration: d * 0.7, ease: "power3.in" }, p);
  tl.to(S, { mix: 1, duration: d * 0.45, ease: "none" }, p + d * 0.45);
  [p, d] = seg("terrain");
  tl.fromTo(S, { tcx: 0, tcy: 520, tcz: 40 }, { tcx: 0, tcy: 190, tcz: 300, duration: d, immediateRender: false }, p);
  [p, d] = seg("shadows");
  tl.to(S, { tcx: -150, tcy: 70, tcz: 230, ttx: -20, tty: 0, ttz: -20, sunSpeed: 3.5, duration: d }, p);
  [p, d] = seg("classes");
  tl.to(S, { tcx: 0, tcy: 360, tcz: 160, ttx: 0, ttz: 0, overlay: 0.85, lm: 1, sunSpeed: 1, duration: d }, p);
  [p, d] = seg("regions");
  tl.to(S, { tcx: -40, tcy: 250, tcz: 250, ttx: -70, ttz: -20, beams: 1, nasa: 1, duration: d }, p);
  tl.to(S, { orbit: 1, duration: 1 }, story.offsetHeight - vh - 1); // fill to the end of the story
}
let rsz;
addEventListener("resize", () => { clearTimeout(rsz); rsz = setTimeout(() => { buildTimeline(); ScrollTrigger.refresh(); }, 250); });

// region selection (cards + 3D labels)
function flyToRegion(rank) {
  if (scene3d) scene3d.flyTo(rank);
  $$(".rcard").forEach(c => c.classList.toggle("on", +c.dataset.rank === rank));
  showRegion(rank);
}
window.flyToRegion = flyToRegion;

/* ------------------------------------------------------------- DOM parts */
const pct = v => `${Math.round(v * 100)}%`;
// region cards
const list = $("#rlist");
for (const r of DATA.regions) {
  const el = document.createElement("button");
  el.className = "rcard";
  el.dataset.rank = r.rank;
  el.innerHTML = `<span class="rk">${r.rank}</span><span class="rt"><b dir="ltr">${Math.abs(r.lat).toFixed(1)}°S ${r.lon.toFixed(0)}°E</b>
    <small>نوافذ <b>${pct(r.availability)}</b> · أرض <b>${pct(r.earth)}</b></small></span>`;
  el.addEventListener("click", () => flyToRegion(r.rank));
  list.appendChild(el);
}
function showRegion(rank) {
  const r = DATA.regions.find(x => x.rank === rank);
  if (!r) return;
  const near = DATA.nasa_regions.filter(n => n.near.includes(rank)).map(n => n.name);
  $("#rdetail").innerHTML = `<h4>المنطقة ${r.rank}</h4>
    <div class="kv"><span>الموقع</span><b dir="ltr">${Math.abs(r.lat).toFixed(3)}°S, ${r.lon.toFixed(2)}°E</b>
    <span>نوافذ مضيئة في 2027</span><b>${pct(r.availability)}</b>
    <span>أفضل نافذة</span><b dir="ltr">${(r.window || "—").slice(0, 10)}</b>
    <span>الميلان</span><b>${r.slope}°</b>
    <span>الإضاءة (متوسط ناسا)</span><b>${pct(r.sun)}</b>
    <span>رؤية الأرض</span><b>${pct(r.earth)}</b>
    <span>أقرب جليد محتمل</span><b>${r.psr_km} كم</b>
    <span>منطقة ناسا القريبة</span><b dir="ltr">${[...new Set(near)].join(" / ") || "—"}</b></div>`;
}
showRegion(1);

// years chart
(() => {
  const yrs = Object.keys(DATA.years), n = DATA.years[yrs[0]].length;
  const W = 640, Hh = 260, pad = 28, bw = (W - pad * 2) / n;
  const cols = ["#7DD3FC", "#F5B942", "#4ADE80"];
  let s = `<svg viewBox="0 0 ${W} ${Hh + 40}" role="img" aria-label="نوافذ الإطلاق لكل منطقة في 2026 و2027 و2028">`;
  for (let g = 0; g <= 4; g++) { const y = Hh - (g / 4) * (Hh - 20); s += `<line x1="${pad}" x2="${W - pad}" y1="${y}" y2="${y}" class="grid"/><text x="${pad - 6}" y="${y + 4}" class="ax" text-anchor="end">${g * 10}%</text>`; }
  for (let i = 0; i < n; i++) {
    yrs.forEach((y, k) => {
      const v = DATA.years[y][i], h = (v / 0.4) * (Hh - 20), x = pad + i * bw + 6 + k * ((bw - 12) / 3);
      s += `<rect class="yb" x="${x}" y="${Hh - h}" width="${(bw - 12) / 3 - 2}" height="${h}" rx="2" fill="${cols[k]}" style="--d:${i * 60 + k * 20}ms"><title>${y} · #${i + 1}: ${pct(v)}</title></rect>`;
    });
    s += `<text x="${pad + i * bw + bw / 2}" y="${Hh + 22}" class="ax" text-anchor="middle">#${i + 1}</text>`;
  }
  s += "</svg>";
  $("#years").innerHTML = s + `<div class="legend">${yrs.map((y, k) => `<span><i style="background:${cols[k]}"></i>${y}</span>`).join("")}</div>`;
})();

// counters
for (const el of $$("[data-count]")) {
  const target = parseFloat(el.dataset.count), dec = +(el.dataset.dec || 0), suf = el.dataset.suf || "";
  const o = { v: 0 };
  ScrollTrigger.create({ trigger: el, start: "top 85%", once: true,
    onEnter: () => gsap.to(o, { v: target, duration: reduceMotion ? 0 : 1.8, ease: "power3.out",
      onUpdate: () => { el.textContent = o.v.toFixed(dec) + suf; } }) });
}
// reveal animations
for (const el of $$("[data-rev]")) {
  gsap.from(el, { y: 50, opacity: 0, duration: 1, ease: "power3.out",
    scrollTrigger: { trigger: el, start: "top 88%", toggleActions: "play none none reverse" } });
}
ScrollTrigger.create({ trigger: "#years", start: "top 80%", onEnter: () => $("#years").classList.add("in") });
// kinetic hero title
const ht = $("#htitle");
ht.innerHTML = ht.textContent.split(" ").map(w => `<span class="w"><span>${w}</span></span>`).join(" ");
gsap.from("#htitle .w > span", { yPercent: 110, duration: 1.2, ease: "power4.out", stagger: 0.08, delay: 0.4 });
gsap.from("#hero .fade-in", { opacity: 0, y: 20, duration: 1, stagger: 0.12, delay: 0.9 });
// progress rail
const rail = $("#rail i");
ScrollTrigger.create({ trigger: "#story", start: "top top", end: "bottom bottom", onUpdate: s => { rail.style.height = `${s.progress * 100}%`; } });
// nav highlight
for (const sec of $$("section[data-nav]")) {
  ScrollTrigger.create({ trigger: sec, start: "top center", end: "bottom center",
    onToggle: s => { if (s.isActive) $$("#nav a").forEach(a => a.classList.toggle("on", a.getAttribute("href") === "#" + sec.id)); } });
}
$$("#nav a, .jump").forEach(a => a.addEventListener("click", e => {
  const id = a.getAttribute("href");
  if (!id || !id.startsWith("#")) return;
  e.preventDefault();
  lenis ? lenis.scrollTo(id, { duration: 2 }) : $(id).scrollIntoView();
}));
// layer toggles on the terrain
$("#tg-classes").addEventListener("change", e => gsap.to(S, { overlay: e.target.checked ? 0.85 : 0, duration: 0.6 }));
$("#tg-sun").addEventListener("change", e => gsap.to(S, { sunSpeed: e.target.checked ? 3.5 : 0, duration: 0.6 }));
// video modal
$$("[data-video]").forEach(b => b.addEventListener("click", () => {
  const m = $("#vmodal");
  $("video", m).src = b.dataset.video;
  m.showModal();
  $("video", m).play().catch(() => {});
}));
$("#vmodal").addEventListener("close", () => { const v = $("#vmodal video"); v.pause(); v.removeAttribute("src"); v.load(); });
$("#vmodal .x").addEventListener("click", () => $("#vmodal").close());
// copy button
$$(".copy").forEach(b => b.addEventListener("click", async () => {
  try { await navigator.clipboard.writeText($(b.dataset.copy).innerText); b.textContent = "تم النسخ ✓"; setTimeout(() => (b.textContent = "نسخ"), 1600); } catch (e) {}
}));

/* ----------------------------------------------------------------- start */
if (scene3d) {
  await Promise.race([scene3d.loaded, new Promise(r => setTimeout(r, 20000))]);
}
await document.fonts.ready;
clearTimeout(loaderGuard);
hideLoader();
buildTimeline();
ScrollTrigger.refresh();
if (scene3d) scene3d.run();
