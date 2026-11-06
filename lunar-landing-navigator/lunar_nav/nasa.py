"""Official NASA south-pole products: catalogue, download and co-registration.

Every product below is a south polar stereographic raster (sphere R=1737.4 km,
lon 0 up), so co-registration is an exact resample onto one analysis grid.

Products
--------
* LOLA DEM + slope + roughness — Barker et al. (2023), PGDA product 90
  "A New View of the Lunar South Pole from LOLA".
* Average solar illumination, average Earth visibility and permanently
  shadowed regions — Mazarico et al. (2011), PGDA product 69 "Lunar Polar
  Illumination" (hourly over a full 18.6-year nutation cycle).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .data import Scene

PGDA = "https://pgda.gsfc.nasa.gov/data"

# key: (url, description, citation)
PRODUCTS = {
    "dem": (f"{PGDA}/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF",
            "LOLA elevation, 80-90S, 80 m/px (m above 1737.4 km sphere)", "Barker et al. 2023"),
    "slope": (f"{PGDA}/LOLA_20mpp/LDSM_80S_80MPP_ADJ.TIF",
              "LOLA slope, 80-90S, 80 m/px (deg)", "Barker et al. 2023"),
    "roughness": (f"{PGDA}/LOLA_20mpp/LDRM_80S_50MPP_ADJ_ROUGH_100M.TIF",
                  "LOLA roughness at 100 m baseline, 50 m/px (m)", "Barker et al. 2023"),
    "sun": (f"{PGDA}/MoonIllumination/AVGVISIB_75S_120M_201608.TIF",
            "Average solar visibility over 18.6 yr, 75-90S, 120 m/px (0-1)", "Mazarico et al. 2011"),
    "earth": (f"{PGDA}/MoonIllumination/AVGVISIB_75S_120M_201608_EARTH.TIF",
              "Average Earth visibility over 18.6 yr, 75-90S, 120 m/px (0-1)", "Mazarico et al. 2011"),
    "psr": (f"{PGDA}/MoonIllumination/LPSR_75S_120M_201608.TIF",
            "Permanently shadowed regions, 75-90S, 120 m/px (1 = PSR)", "Mazarico et al. 2011"),
}


def ensure_products(data_dir: str | Path, keys=None, log=print) -> dict[str, Path]:
    """Download any missing product into data_dir (resumable)."""
    import urllib.request
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for k in keys or PRODUCTS:
        url = PRODUCTS[k][0]
        dest = data_dir / url.rsplit("/", 1)[-1]
        if not dest.exists() or dest.stat().st_size == 0:
            log(f"downloading {dest.name} ...")
            tmp = dest.with_suffix(dest.suffix + ".part")
            req = urllib.request.Request(url, headers={"User-Agent": "lunar-landing-navigator"})
            with urllib.request.urlopen(req) as r, open(tmp, "wb") as f:
                while chunk := r.read(1 << 22):
                    f.write(chunk)
            tmp.rename(dest)
        paths[k] = dest
    return paths


@dataclass
class Grid:
    """Square analysis grid centred on the south pole."""
    half_width_m: float = 200_000
    res_m: float = 80.0

    @property
    def n(self) -> int:
        return int(round(2 * self.half_width_m / self.res_m))

    @property
    def bounds(self):
        h = self.half_width_m
        return (-h, -h, h, h)

    def transform(self):
        from rasterio.transform import from_origin
        return from_origin(-self.half_width_m, self.half_width_m, self.res_m, self.res_m)


def _resample(path: Path, grid: Grid, kind: str) -> np.ndarray:
    """Read a product and resample it onto `grid` (same CRS, exact maths)."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    with rasterio.open(path) as src:
        # read only what we need (+margin) to keep memory low
        from rasterio.windows import from_bounds
        m = 2 * max(src.res[0], grid.res_m)
        b = grid.bounds
        win = from_bounds(b[0] - m, b[1] - m, b[2] + m, b[3] + m, src.transform).round_offsets().round_lengths()
        a = src.read(1, window=win).astype(np.float32)
        if src.nodata is not None and not np.isnan(src.nodata):
            a[a == src.nodata] = np.nan
        a = a * float(src.scales[0]) + float(src.offsets[0])
        src_tf = src.window_transform(win)
        crs = src.crs
    out = np.full((grid.n, grid.n), np.nan, dtype=np.float32)
    method = {"categorical": Resampling.nearest, "average": Resampling.average}.get(kind, Resampling.bilinear)
    if kind == "auto":
        method = Resampling.average if grid.res_m > src_tf.a * 1.4 else Resampling.bilinear
    reproject(a, out, src_transform=src_tf, src_crs=crs, dst_transform=grid.transform(),
              dst_crs=crs, resampling=method, src_nodata=np.nan, dst_nodata=np.nan)
    return out


@dataclass
class NasaLayers:
    sun_avg: np.ndarray
    earth_avg: np.ndarray
    psr: np.ndarray
    slope: np.ndarray
    roughness: np.ndarray
    sources: dict = field(default_factory=dict)


def load_nasa_scene(data_dir: str | Path, grid: Grid | None = None, download: bool = True,
                    log=print) -> tuple[Scene, NasaLayers]:
    grid = grid or Grid()
    data_dir = Path(data_dir)
    paths = ensure_products(data_dir, log=log) if download else {
        k: data_dir / v[0].rsplit("/", 1)[-1] for k, v in PRODUCTS.items()}
    log(f"co-registering NASA products onto a {grid.n}x{grid.n} grid @ {grid.res_m:g} m "
        f"(±{grid.half_width_m / 1000:.0f} km around the pole)")
    dem = _resample(paths["dem"], grid, "auto")
    slope = _resample(paths["slope"], grid, "auto")
    rough = _resample(paths["roughness"], grid, "average")
    sun = _resample(paths["sun"], grid, "bilinear")
    earth = _resample(paths["earth"], grid, "bilinear")
    psr = _resample(paths["psr"], grid, "categorical") > 0.5

    def fill(a, v):
        return np.where(np.isfinite(a), a, v).astype(np.float32)

    dem = fill(dem, np.nanmean(dem))
    slope = fill(slope, 90.0)  # unknown -> unsafe
    rough = fill(rough, np.nanpercentile(rough, 99))
    sun = np.clip(fill(sun, 0.0), 0, 1)
    earth = np.clip(fill(earth, 0.0), 0, 1)

    # Roughness (m at 100 m baseline) -> 0..1 hazard. ~1 m is already rough
    # for a lander pad; >= 3 m is boulder-field/rugged terrain.
    rocks = np.clip((rough - 0.5) / 2.5, 0, 1).astype(np.float32)

    c = grid.n / 2.0 - 0.5  # pixel centres sit at (i + 0.5) * res from the edge
    scene = Scene(dem=dem, pixel_size_m=grid.res_m, pole_rc=(c, c),
                  name="LOLA south pole (NASA)", rocks=rocks, illumination=sun,
                  meta={"synthetic": False, "source": "NASA PGDA", "grid": grid.__dict__,
                        "illum_display_max": 0.6,
                        "products": {k: {"url": v[0], "desc": v[1], "ref": v[2]} for k, v in PRODUCTS.items()}})
    layers = NasaLayers(sun, earth, psr, slope, rough,
                        {k: v[0] for k, v in PRODUCTS.items()})
    return scene, layers
