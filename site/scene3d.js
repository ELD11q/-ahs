// three.js scene for the Lunar Landing Navigator site.
// Loaded only when WebGL is available; the page works without it.
import * as THREE from "./vendor/three.module.min.js";

export async function start({ DATA, S, $, mobile, lite, reduceMotion, onPick }) {
  /* -------------------------------------------------------------- renderer */
  const canvas = $("#gl");
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
  } catch (e) {
    document.body.classList.add("no-webgl");
  }
  if (!renderer) throw new Error("WebGL unavailable");
  renderer.setPixelRatio(Math.min(devicePixelRatio, mobile ? 1.5 : 2));
  renderer.setSize(innerWidth, innerHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.95;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x02040a);
  const camera = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, 0.01, 5000);
  camera.position.set(0, 0.4, 4.2);

  /* --------------------------------------------------------------- loading */
  const manager = new THREE.LoadingManager();
  const bar = $("#loader .bar i");
  manager.onProgress = (_, done, total) => { bar.style.width = `${(done / total) * 100}%`; };
  const texLoader = new THREE.TextureLoader(manager);
  const loaded = new Promise(res => { manager.onLoad = res; });

  /* ----------------------------------------------------------------- stars */
  function makeStars(n, r) {
    const g = new THREE.BufferGeometry();
    const p = new Float32Array(n * 3), c = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const u = Math.random() * 2 - 1, t = Math.random() * Math.PI * 2, rr = r * (0.6 + Math.random() * 0.4);
      const s = Math.sqrt(1 - u * u);
      p.set([rr * s * Math.cos(t), rr * u, rr * s * Math.sin(t)], i * 3);
      const warm = Math.random();
      c.set(warm > 0.85 ? [1, 0.85, 0.7] : warm < 0.15 ? [0.7, 0.8, 1] : [1, 1, 1], i * 3);
    }
    g.setAttribute("position", new THREE.BufferAttribute(p, 3));
    g.setAttribute("color", new THREE.BufferAttribute(c, 3));
    const m = new THREE.PointsMaterial({ size: 1.6, sizeAttenuation: false, vertexColors: true, transparent: true, opacity: 0.9, depthWrite: false });
    return new THREE.Points(g, m);
  }
  const stars = makeStars(mobile ? 2500 : 6000, 1500);
  scene.add(stars);

  /* ------------------------------------------------------------------ moon */
  const moonGroup = new THREE.Group();
  scene.add(moonGroup);
  const moonColor = texLoader.load("site/assets/moon_color.jpg");
  moonColor.colorSpace = THREE.SRGBColorSpace;
  moonColor.anisotropy = 8;
  const moonDisp = texLoader.load("site/assets/moon_disp.jpg");
  const moon = new THREE.Mesh(
    new THREE.SphereGeometry(1, mobile ? 160 : 256, mobile ? 80 : 128),
    new THREE.MeshStandardMaterial({ map: moonColor, displacementMap: moonDisp, displacementScale: 0.035, displacementBias: -0.017,
      bumpMap: moonDisp, bumpScale: 0.6, roughness: 1, metalness: 0 })
  );
  moonGroup.add(moon);
  // south-pole marker ring on the globe
  const poleRing = new THREE.Mesh(new THREE.RingGeometry(0.11, 0.118, 96),
    new THREE.MeshBasicMaterial({ color: 0xf5b942, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false }));
  poleRing.position.set(0, -1.02, 0);
  poleRing.rotation.x = Math.PI / 2;
  moonGroup.add(poleRing);

  const sunLight = new THREE.DirectionalLight(0xfff4e0, 3.2);
  sunLight.position.set(-5, 1.5, 4);
  scene.add(sunLight);
  scene.add(new THREE.AmbientLight(0x223344, 0.18));
  const rim = new THREE.DirectionalLight(0x6fa8ff, 0.5);
  rim.position.set(4, 1, -5);
  scene.add(rim);

  /* --------------------------------------------------------------- terrain */
  const T = DATA.terrain;
  const SIZE = 480, EXAG = 3.2, SEG = lite ? 127 : mobile ? 255 : 511;
  const hbuf = await fetch("site/assets/terrain_h.bin").then(r => r.arrayBuffer());
  const H = new Uint16Array(hbuf); // 512x512
  const hAt = (u, v) => { // u,v in [0,1], bilinear
    const x = Math.min(510.999, Math.max(0, u * 511)), y = Math.min(510.999, Math.max(0, v * 511));
    const x0 = Math.floor(x), y0 = Math.floor(y), fx = x - x0, fy = y - y0;
    const g = (i, j) => H[j * 512 + i];
    const a = g(x0, y0) * (1 - fx) + g(x0 + 1, y0) * fx, b = g(x0, y0 + 1) * (1 - fx) + g(x0 + 1, y0 + 1) * fx;
    const n = (a * (1 - fy) + b * fy) / 65535;
    return ((T.h_min_m + n * (T.h_max_m - T.h_min_m)) / 1000) * EXAG; // km * exaggeration
  };
  const terrainGroup = new THREE.Group();
  terrainGroup.visible = false;
  scene.add(terrainGroup);
  const tg = new THREE.PlaneGeometry(SIZE, SIZE, SEG, SEG);
  tg.rotateX(-Math.PI / 2);
  {
    const pos = tg.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const u = pos.getX(i) / SIZE + 0.5, v = pos.getZ(i) / SIZE + 0.5;
      pos.setY(i, hAt(u, v));
    }
    tg.computeVertexNormals();
  }
  const albedo = texLoader.load("site/assets/terrain_albedo.jpg");
  albedo.colorSpace = THREE.SRGBColorSpace;
  albedo.anisotropy = 8;
  const terrain = new THREE.Mesh(tg, new THREE.MeshStandardMaterial({ map: albedo, roughness: 1, metalness: 0 }));
  terrain.castShadow = terrain.receiveShadow = true;
  terrainGroup.add(terrain);
  const classesTex = texLoader.load("site/assets/terrain_classes.png");
  classesTex.colorSpace = THREE.SRGBColorSpace;
  const overlay = new THREE.Mesh(tg, new THREE.MeshBasicMaterial({ map: classesTex, transparent: true, opacity: 0, depthWrite: false,
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }));
  overlay.renderOrder = 2;
  terrainGroup.add(overlay);

  // polar sun: low, circling the horizon -> moving shadows
  const polarSun = new THREE.DirectionalLight(0xffefd2, 2.9);
  polarSun.castShadow = true;
  const SM = lite ? 512 : mobile ? 1024 : 2048;
  polarSun.shadow.mapSize.set(SM, SM);
  Object.assign(polarSun.shadow.camera, { left: -280, right: 280, top: 280, bottom: -280, near: 1, far: 2000 });
  polarSun.shadow.bias = -0.0004;
  polarSun.shadow.normalBias = 0.6;
  terrainGroup.add(polarSun, polarSun.target);
  const hemi = new THREE.HemisphereLight(0x8fb4ff, 0x0b0f17, 0.12);
  terrainGroup.add(hemi);
  // faint sun disc on the horizon
  const sunDisc = new THREE.Mesh(new THREE.SphereGeometry(9, 32, 16), new THREE.MeshBasicMaterial({ color: 0xffe2a8 }));
  terrainGroup.add(sunDisc);
  const sunGlow = new THREE.Sprite(new THREE.SpriteMaterial({
    map: (() => { const c = document.createElement("canvas"); c.width = c.height = 128; const x = c.getContext("2d");
      const g = x.createRadialGradient(64, 64, 0, 64, 64, 64); g.addColorStop(0, "rgba(255,226,168,0.9)"); g.addColorStop(0.3, "rgba(255,190,90,0.35)"); g.addColorStop(1, "rgba(255,160,60,0)");
      x.fillStyle = g; x.fillRect(0, 0, 128, 128); return new THREE.CanvasTexture(c); })(),
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  sunGlow.scale.set(120, 120, 1);
  terrainGroup.add(sunGlow);

  // region beams
  const uvToXZ = ([u, v]) => new THREE.Vector3((u - 0.5) * SIZE, hAt(u, v), (v - 0.5) * SIZE);
  const beams = [];
  const beamGeo = new THREE.CylinderGeometry(0.9, 2.4, 60, 24, 1, true);
  beamGeo.translate(0, 30, 0);
  for (const r of DATA.regions) {
    const p = uvToXZ(r.uv);
    const m = new THREE.Mesh(beamGeo, new THREE.MeshBasicMaterial({ color: r.rank === 1 ? 0xf5b942 : 0x4ade80, transparent: true, opacity: 0,
      blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
    m.position.copy(p);
    m.scale.y = 0.001;
    m.userData = r;
    terrainGroup.add(m);
    const ring = new THREE.Mesh(new THREE.RingGeometry(3.2, 4.2, 48), new THREE.MeshBasicMaterial({ color: r.rank === 1 ? 0xf5b942 : 0x4ade80,
      transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false }));
    ring.rotation.x = -Math.PI / 2;
    ring.position.copy(p).add(new THREE.Vector3(0, 0.6, 0));
    terrainGroup.add(ring);
    beams.push({ beam: m, ring, p, r });
  }

  /* --------------------------------------------------------- DOM 3D labels */
  const labelLayer = $("#labels");
  const labels = [];
  function addLabel(html, cls, posFn, group) {
    const el = document.createElement("div");
    el.className = "lbl " + cls;
    el.innerHTML = html;
    labelLayer.appendChild(el);
    labels.push({ el, posFn, group });
    return el;
  }
  for (const b of beams) {
    const el = addLabel(`<b>${b.r.rank}</b>`, "reg", () => b.p.clone().add(new THREE.Vector3(0, 64 * b.beam.scale.y + 6, 0)), "regions");
    el.addEventListener("click", () => onPick(b.r.rank));
  }
  const nasaSeen = new Map();
  for (const n of DATA.nasa_regions) {
    const k = n.uv.join(",");
    if (!nasaSeen.has(k)) nasaSeen.set(k, []);
    nasaSeen.get(k).push(n.name);
  }
  for (const [k, names] of nasaSeen) {
    const uv = k.split(",").map(Number);
    if (uv.some(t => t < 0 || t > 1)) continue;
    addLabel(`<i>★</i><span>${names.join(" · ")}</span>`, "nasa", () => uvToXZ(uv).add(new THREE.Vector3(0, 4, 0)), "nasa");
  }
  for (const l of DATA.landmarks) {
    if (l.uv.some(t => t < 0.02 || t > 0.98)) continue;
    addLabel(`<span>${l.name}</span>`, "lm", () => uvToXZ(l.uv).add(new THREE.Vector3(0, 3, 0)), "lm");
  }
  const tmpV = new THREE.Vector3();
  function updateLabels() {
    const show = { regions: S.beams > 0.6, nasa: S.nasa > 0.5, lm: S.lm > 0.5 };
    for (const l of labels) {
      if (!terrainGroup.visible || !show[l.group]) { l.el.style.opacity = 0; continue; }
      tmpV.copy(l.posFn()).project(camera);
      const vis = tmpV.z < 1 && Math.abs(tmpV.x) < 1.05 && Math.abs(tmpV.y) < 1.05;
      l.el.style.opacity = vis ? 1 : 0;
      l.el.style.transform = `translate(${(tmpV.x * 0.5 + 0.5) * innerWidth}px, ${(-tmpV.y * 0.5 + 0.5) * innerHeight}px) translate(-50%, -100%)`;
    }
  }

  function flyTo(rank) {
    const b = beams.find(x => x.r.rank === rank);
    if (!b) return;
      const p = b.p;
      // camera south-east of the region, looking slightly past it so the region sits
      // in the free half of the screen (the card occupies the other half)
      const cam = new THREE.Vector3(p.x + 70, p.y + 95, p.z + 120);
      const fwd = p.clone().sub(cam).normalize();
      const right = new THREE.Vector3().crossVectors(fwd, new THREE.Vector3(0, 1, 0)).normalize();
      const shift = innerWidth > 900 ? 48 : 0;
      const tgt = p.clone().addScaledVector(right, -shift);
      gsap.to(S, { tcx: cam.x, tcy: cam.y, tcz: cam.z, ttx: tgt.x, tty: tgt.y, ttz: tgt.z, duration: 1.8, ease: "power3.inOut", overwrite: "auto" });
  }

  /* ----------------------------------------------------------- render loop */
  const clock = new THREE.Clock();
  let sunAz = 0.6, orbitA = 0;
  let perfN = 0, perfT = 0, degraded = false;
  function adapt(raw) {
    if (degraded || reduceMotion) return;
    perfN++; perfT += raw;
    if (perfN === 90) {
      if (perfT / perfN > 0.034) {           // slower than ~30 fps: lighten the scene
        degraded = true;
        renderer.setPixelRatio(1);
        polarSun.shadow.mapSize.set(1024, 1024);
        polarSun.shadow.map?.dispose(); polarSun.shadow.map = null;
      }
      perfN = 0; perfT = 0;
    }
  }
  function frame() {
    const raw = clock.getDelta(), dt = Math.min(raw, 0.05), t = clock.elapsedTime;
    if (terrainGroup.visible) adapt(raw);
    // globe
    moonGroup.rotation.y = reduceMotion ? 0.6 : t * 0.04 + S.moonSpin;
    moonGroup.rotation.x = S.pole * 0.35;
    poleRing.material.opacity = Math.max(0, S.pole - 0.2) * (0.65 + 0.35 * Math.sin(t * 3)) * (1 - S.mix);
    stars.rotation.y = t * 0.004;
    // fade between globe and terrain through a dark flash
    const f = 1 - Math.abs(S.mix * 2 - 1);
    $("#fader").style.opacity = Math.pow(f, 1.4).toFixed(3);
    const inTerrain = S.mix >= 0.5;
    moonGroup.visible = !inTerrain;
    terrainGroup.visible = inTerrain;
    if (!inTerrain) {
      camera.position.set(S.cx, S.cy, S.cz);
      camera.lookAt(S.tx, S.ty, S.tz);
      camera.near = 0.01; camera.far = 5000;
    } else {
      const after = scrollY > ($("#story").offsetTop + $("#story").offsetHeight - innerHeight * 1.05);
      if (after && !reduceMotion) {
        orbitA += dt * 0.05;
        const r = 330;
        camera.position.set(Math.sin(orbitA) * r, 230, Math.cos(orbitA) * r);
        camera.lookAt(0, 0, 0);
      } else {
        orbitA = Math.atan2(S.tcx, S.tcz);
        camera.position.set(S.tcx, S.tcy, S.tcz);
        camera.lookAt(S.ttx, S.tty, S.ttz);
      }
      camera.near = 1; camera.far = 6000;
    }
    camera.updateProjectionMatrix();
    // polar sun circling the horizon
    if (!reduceMotion) sunAz += dt * 0.12 * S.sunSpeed;
    const el = THREE.MathUtils.degToRad(S.sunElev), R = 900;
    polarSun.position.set(Math.cos(sunAz) * Math.cos(el) * R, Math.sin(el) * R + 10, Math.sin(sunAz) * Math.cos(el) * R);
    sunDisc.position.copy(polarSun.position).multiplyScalar(0.9);
    sunGlow.position.copy(sunDisc.position);
    overlay.material.opacity = S.overlay;
    for (const b of beams) {
      const k = THREE.MathUtils.clamp(S.beams * 9 - (b.r.rank - 1) * 0.9, 0, 1);
      b.beam.scale.y = Math.max(0.001, k * (b.r.rank === 1 ? 1.25 : 1));
      b.beam.material.opacity = k * (0.45 + 0.15 * Math.sin(t * 2 + b.r.rank));
      b.ring.material.opacity = k * 0.9;
      b.ring.scale.setScalar(1 + 0.25 * Math.sin(t * 2.4 + b.r.rank));
    }
    renderer.render(scene, camera);
    updateLabels();
    requestAnimationFrame(frame);
  }

  addEventListener("resize", () => {
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
  });

  return { loaded, flyTo, run: () => requestAnimationFrame(frame) };
}
