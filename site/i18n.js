// Arabic / English switch shared by index.html and classic.html.
// Arabic is written in the HTML itself; this file holds the English text.
// Elements opt in with:
//   data-i18n="key"                 -> innerHTML
//   data-i18n-attr="attr:key;..."   -> attributes
//   data-href-en="url"              -> link target in English
// The choice is kept in localStorage and can be forced with ?lang=en / ?lang=ar.
(function () {
  "use strict";
  var EN = {
    // ---- page
    title: "Lunar Landing Navigator · Where do we land on the Moon?",
    meta_desc: "Lunar Landing Site Navigator: an open-source system that ranks landing sites at the lunar south pole using official NASA data and real 2027 launch windows.",
    gl_aria: "3D scene of the Moon and the south-pole terrain",
    nav_home: "Start", nav_terrain: "Terrain", nav_regions: "Regions", nav_valid: "Accuracy", nav_run: "Run it",
    // ---- hero
    hero_title: "Where do we land on the Moon?",
    hero_sub: "An open-source system that picks the best landing sites at the lunar south pole, using official NASA data and the real 2027 launch windows, with its accuracy checked.",
    hero_start: "Start the journey ↓",
    hero_map: "Interactive map",
    // ---- why
    why_k: "WHY THE SOUTH POLE?",
    why_h: "Water ice in craters that have not seen the Sun for billions of years",
    why_p: "Craters in permanent shadow, colder than −200 °C, may hold water ice: drinking water, oxygen and rocket fuel. The evidence comes from LCROSS (2009), M3 on Chandrayaan-1 (2018) and Diviner on LRO.",
    why_f1: "highest Sun elevation above the horizon",
    why_f2: "Earth's wobble in the sky",
    why_f3b: "6.5 days", why_f3: "mission time on the surface",
    // ---- descent
    desc_k: "DESCENT",
    desc_h: "Heading for the south pole",
    desc_p: "The golden ring on the Moon is the Artemis Exploration Zone: within 6° of the pole. NASA picked 13 regions inside it, then 9.",
    // ---- terrain
    ter_k: "REAL TERRAIN · 480 × 480 KM",
    ter_h: "This is the south pole, from the LOLA laser",
    ter_p: "Every point here is a real height measured by the laser on the LRO spacecraft (height exaggerated ×3.2 to make it visible). Blue areas are permanent shadow, meaning possible ice.",
    psr: "Permanent shadow (possible ice)",
    // ---- shadows
    sh_k: "A POLAR DAY",
    sh_h: "Watch the shadows move",
    sh_p: "At the pole the Sun never climbs overhead; it circles along the horizon. So shadows sweep around every mountain, and light never reaches the crater floors. That is what makes choosing a landing site hard.",
    sh_tg: "Move the Sun",
    // ---- classes
    cl_k: "CLASSIFICATION",
    cl_h: "36 million pixels, each with a score",
    cl_p: "Slope 30%, sunlight 25%, Earth visibility 15%, closeness to ice 15%, rocks 15%. Any hazard within 200 m (the landing ellipse) turns a point red.",
    safe: "Safe", marg: "Marginal", unsafe: "Unsafe",
    cl_tg: "Classification layer",
    // ---- regions
    rg_k: "RESULTS",
    rg_h: "The best 9 landing regions",
    rg_p: "Click any region and the camera flies to it. Stars ★ are NASA's Artemis III regions.",
    // ---- windows
    win_k: "LAUNCH WINDOWS",
    win_h: "When do we land? Share of start times that give 6.5 days of continuous light",
    win_p: "Computed hour by hour from the real positions of the Sun and Earth (astropy + the IAU 2009 model), over a real horizon in 128 directions. Region 1 is the best in all three years.",
    // ---- validation
    val_k: "VALIDATION",
    val_h: "We did not stop at results: we checked them against three independent references",
    val_1: "Sun correlation with NASA's maps",
    val_2: "Earth-visibility correlation with NASA",
    val_3: "of the independent TOPSIS study's best points fall in our top 10%",
    val_4: "of NASA's regions covered by our regions (5 of 9 with the candidates)",
    val_p: "111,556 points × 13,588 moments over 18.6 years. And we did not tune the model to force a match with NASA.",
    // ---- how
    how_k: "HOW IT WORKS",
    how_h: "From raw NASA data to a landing decision",
    st1b: "6 NASA files", st1: "LOLA and illumination maps, 1.2 GB",
    st2b: "One grid", st2: "480 km · 80 m · 36 million pixels",
    st3b: "Scores and classes", st3: "5 weighted criteria",
    st4b: "13 → 9", st4: "60% terrain + 40% 2027 windows",
    st5b: "Validation", st5: "NASA · TOPSIS · Artemis III",
    // ---- run
    run_k: "RUN IT YOURSELF",
    run_h: "Three commands, or from GitHub with nothing to install",
    copy: "Copy", copied: "Copied ✓",
    run_p: "Or from your own GitHub account: <b>Fork</b> the repository, open <b>Actions</b> and enable workflows, choose <b>Lunar Landing Navigator</b> and click <b>Run workflow</b>.",
    run_vid: "▶ How-to-run video (3 min)",
    f_map: "🗺️ Interactive map", f_map_s: "detailed 2D",
    f_rep: "📕 Technical report", f_rep_s: "23 pages",
    f_gd: "📘 User guide", f_gd_s: "33 pages",
    f_res: "📄 Results report", f_res_s: "every number",
    f_cl: "🧾 Classic version", f_cl_s: "a simple, light page",
    ft_data: "Data:", ft_moon: "Moon imagery:",
    ft_disc: "A research and education tool, not a certified flight tool.",
    close: "✕ Close", close_aria: "Close",
    // ---- dynamic (app.js)
    d_windows: "windows", d_earth: "Earth",
    d_region: "Region {n}", d_loc: "Location", d_av: "Fully-lit windows in 2027", d_best: "Best window",
    d_slope: "Slope", d_sun: "Sunlight (NASA average)", d_earthv: "Earth visibility", d_ice: "Nearest possible ice",
    d_nasa: "Nearby NASA region", d_km: "km",
    d_years_aria: "Launch windows for each region in 2026, 2027 and 2028",
    // ---- classic.html
    c_title: "Lunar Landing Site Navigator",
    c_h1: "🌕 Lunar Landing Site Navigator",
    c_lead: "An open-source system that ranks landing sites at the lunar south pole, using official NASA data and the real 2027 launch windows.",
    c_btn_map: "🗺️ Open the interactive map", c_btn_rep: "📕 Full report (PDF)", c_btn_code: "⌨️ Code on GitHub",
    c_img_alt: "Interactive map of landing sites at the south pole",
    c_k1: "Sun-model correlation with NASA's maps", c_k2: "Earth-visibility correlation with NASA's maps",
    c_k3: "of the independent TOPSIS study's best points fall in our top 10%", c_k4: "of NASA's Artemis III regions covered by our regions",
    c_vid: "🎬 Video: how to run the project <span class=\"ltr\" style=\"font-size:16px;color:var(--muted)\">(3 min)</span>",
    c_files: "All files",
    c_map: "<b>🗺️ Interactive map</b><span>the best 9 regions, NASA's regions, and a 2027 chart for each region</span>",
    c_rep: "<b>📕 Technical report</b><span>23 pages: method, results, validation and business model</span>",
    c_gd: "<b>📘 User guide</b><span>33 pages: installing and running from A to Z</span>",
    c_res: "<b>📄 Results report</b><span>full tables of numbers</span>",
    c_val: "<b>📈 Accuracy checks</b><span>our model vs NASA's maps, and the 2027 calendar</span>",
    c_exp: "<b>🧪 Robustness tests</b><span>weights, slope limit, and the years 2026 to 2028</span>",
    c_run: "Run it yourself",
    c_run_p: "Or from your GitHub account with nothing to install: <b>Fork</b> the repository, open <b>Actions</b> and enable workflows, choose <b>Lunar Landing Navigator</b> and click <b>Run workflow</b>.",
    c_full: "🌌 Full 3D site",
  };
  var AR = {
    copy: "نسخ", copied: "تم النسخ ✓",
    d_windows: "نوافذ", d_earth: "أرض",
    d_region: "المنطقة {n}", d_loc: "الموقع", d_av: "نوافذ مضيئة في 2027", d_best: "أفضل نافذة",
    d_slope: "الميلان", d_sun: "الإضاءة (متوسط ناسا)", d_earthv: "رؤية الأرض", d_ice: "أقرب جليد محتمل",
    d_nasa: "منطقة ناسا القريبة", d_km: "كم",
    d_years_aria: "نوافذ الإطلاق لكل منطقة في 2026 و2027 و2028",
  };

  var root = document.documentElement;
  var original = new Map();     // element -> Arabic innerHTML
  var originalAttr = new Map(); // element -> {attr: Arabic value}
  var originalTitle = document.title;
  var listeners = [];

  function pick() {
    var q = null;
    try { q = new URLSearchParams(location.search).get("lang"); } catch (e) {}
    if (q === "en" || q === "ar") return q;
    try { var s = localStorage.getItem("lang"); if (s === "en" || s === "ar") return s; } catch (e) {}
    return "ar";
  }

  var lang = pick();

  function t(key, vars) {
    var v = (lang === "en" ? EN[key] : AR[key]);
    if (v == null) v = EN[key] != null ? EN[key] : key;
    if (vars) for (var k in vars) v = v.replace("{" + k + "}", vars[k]);
    return v;
  }

  function apply() {
    var en = lang === "en";
    root.lang = en ? "en" : "ar";
    root.dir = en ? "ltr" : "rtl";
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      if (!original.has(el)) original.set(el, el.innerHTML);
      var k = el.getAttribute("data-i18n");
      el.innerHTML = en && EN[k] != null ? EN[k] : original.get(el);
    });
    document.querySelectorAll("[data-i18n-attr]").forEach(function (el) {
      if (!originalAttr.has(el)) originalAttr.set(el, {});
      var store = originalAttr.get(el);
      el.getAttribute("data-i18n-attr").split(";").forEach(function (pair) {
        var p = pair.split(":"), a = p[0].trim(), k = p[1].trim();
        if (!(a in store)) store[a] = el.getAttribute(a);
        el.setAttribute(a, en && EN[k] != null ? EN[k] : store[a]);
      });
    });
    document.querySelectorAll("[data-href-en]").forEach(function (el) {
      if (!el.hasAttribute("data-href-ar")) el.setAttribute("data-href-ar", el.getAttribute("href"));
      el.setAttribute("href", en ? el.getAttribute("data-href-en") : el.getAttribute("data-href-ar"));
    });
    document.querySelectorAll("[data-src-en]").forEach(function (el) {
      if (!el.hasAttribute("data-src-ar")) el.setAttribute("data-src-ar", el.getAttribute("src"));
      el.setAttribute("src", en ? el.getAttribute("data-src-en") : el.getAttribute("data-src-ar"));
    });
    var titleKey =root.getAttribute("data-title-key") || "title";
    document.title = en ? EN[titleKey] : originalTitle;
    var btn = document.getElementById("langbtn");
    if (btn) {
      btn.innerHTML = "<span>" + (en ? "ع" : "EN") + "</span>";
      btn.setAttribute("aria-label", en ? "التبديل إلى العربية" : "Switch to English");
      btn.setAttribute("title", en ? "العربية" : "English");
      btn.setAttribute("lang", en ? "ar" : "en");
    }
  }

  function set(next) {
    if (next === lang) return;
    lang = next;
    try { localStorage.setItem("lang", lang); } catch (e) {}
    try {
      var u = new URL(location.href);
      if (u.searchParams.has("lang")) { u.searchParams.set("lang", lang); history.replaceState(null, "", u); }
    } catch (e) {}
    apply();
    listeners.forEach(function (fn) { try { fn(lang); } catch (e) { console.error(e); } });
  }

  apply();
  var btn = document.getElementById("langbtn");
  if (btn) btn.addEventListener("click", function () {
    var next = lang === "en" ? "ar" : "en";
    var calm = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (calm) return set(next);
    // fade the text out, swap while invisible, fade back in
    document.body.classList.add("lang-swap");
    setTimeout(function () {
      set(next);
      requestAnimationFrame(function () { document.body.classList.remove("lang-swap"); });
    }, 300);
  });

  window.I18N = {
    get lang() { return lang; },
    t: t,
    set: set,
    onChange: function (fn) { listeners.push(fn); },
  };
})();
