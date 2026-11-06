"""Input data: a synthetic south-pole scene for demos, and loaders for real
NASA rasters (LOLA DEM, LOLA/LRO illumination maps, Diviner rock abundance).

All rasters are assumed to be on a polar-stereographic grid centred near the
south pole, with lon 0 pointing up (-row) and lon 90E pointing right (+col),
which is how the LOLA polar GDR products are laid out.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import ndimage


@dataclass
class Scene:
    dem: np.ndarray                 # elevation, metres
    pixel_size_m: float
    pole_rc: tuple[float, float]    # (row, col) of the south pole in the grid
    name: str = "scene"
    rocks: np.ndarray | None = None          # Diviner-like rock abundance 0..1
    illumination: np.ndarray | None = None   # precomputed annual mean 0..1
    meta: dict = field(default_factory=dict)

    @property
    def shape(self):
        return self.dem.shape

    def xy_m(self):
        """Grid-frame coordinates (metres) of every pixel relative to the pole.
        +x = right (lon 90E), +y = up (lon 0)."""
        rows, cols = np.indices(self.dem.shape, dtype=np.float64)
        x = (cols - self.pole_rc[1]) * self.pixel_size_m
        y = (self.pole_rc[0] - rows) * self.pixel_size_m
        return x, y


# ---------------------------------------------------------------------------
# Synthetic scene
# ---------------------------------------------------------------------------
def _crater_profile(r, radius, depth, rim_height):
    """Simple bowl crater with a raised rim and an ejecta blanket."""
    rr = r / radius
    bowl = np.where(rr < 1.0, -depth * (1 - rr**2) + rim_height, 0.0)
    ejecta = np.where(rr >= 1.0, rim_height * np.maximum(rr, 1.0) ** -3.0, 0.0)
    return bowl + ejecta


def synthetic_south_pole(size_px: int = 600, pixel_size_m: float = 100.0,
                         seed: int = 7) -> Scene:
    """Generate a ~60 x 60 km polar scene that behaves like the real one:
    one big deep crater on the pole (Shackleton-like, permanently shadowed
    floor), a high connecting ridge, smaller craters following a power-law
    size distribution, and boulder fields around fresh craters."""
    rng = np.random.default_rng(seed)
    n = size_px
    rows, cols = np.indices((n, n), dtype=np.float64)
    pole = (n / 2.0, n / 2.0)

    # Large-scale rolling terrain (fractal-ish noise).
    dem = np.zeros((n, n))
    for sigma, amp in [(60, 600.0), (25, 110.0), (8, 14.0), (3, 2.0)]:
        noise = ndimage.gaussian_filter(rng.standard_normal((n, n)), sigma)
        dem += amp * noise / (noise.std() + 1e-9)

    # A high ridge running away from the pole (like the Shackleton–de Gerlache
    # ridge, one of the best-lit places on the Moon).
    ang = np.deg2rad(35)
    d_line = ((cols - pole[1]) * np.cos(ang) - (rows - pole[0]) * np.sin(ang))
    along = ((cols - pole[1]) * np.sin(ang) + (rows - pole[0]) * np.cos(ang))
    dem += 1500 * np.exp(-(d_line / 40.0) ** 2) * np.clip(1 - np.abs(along) / 300, 0, 1)

    rocks = np.zeros((n, n))
    # Big polar crater, slightly off the pole.
    craters = [(pole[0] + 15, pole[1] - 10, 105.0, 3500.0, 300.0, 0.2)]
    # Power-law population of smaller craters.
    n_craters = 220
    radii = (2.0 * (1 - rng.random(n_craters)) ** (-1 / 1.6)).clip(2, 60)
    for rad in radii:
        r0, c0 = rng.uniform(0, n, 2)
        depth = rad * pixel_size_m * 0.2 * rng.uniform(0.6, 1.0)
        freshness = rng.random()
        craters.append((r0, c0, rad, depth, depth * 0.15, freshness))

    for r0, c0, rad, depth, rim, fresh in craters:
        r = np.hypot(rows - r0, cols - c0)
        dem += _crater_profile(r, rad, depth, rim)
        # Fresh craters are surrounded by boulders (what Diviner sees).
        if fresh > 0.6:
            rocks += fresh * np.exp(-((r - rad) / (0.6 * rad + 1)) ** 2)

    rocks += 0.05 * ndimage.gaussian_filter(rng.random((n, n)), 2)
    rocks = np.clip(rocks / max(rocks.max(), 1e-9), 0, 1)

    return Scene(dem=dem.astype(np.float32), pixel_size_m=pixel_size_m,
                 pole_rc=pole, name="synthetic-south-pole", rocks=rocks.astype(np.float32),
                 meta={"synthetic": True, "seed": seed})


# ---------------------------------------------------------------------------
# Real data
# ---------------------------------------------------------------------------
def read_raster(path: str | Path) -> tuple[np.ndarray, float | None]:
    """Read a single-band raster. Returns (array, pixel_size_m or None).
    Uses rasterio when installed (keeps georeferencing); else Pillow."""
    path = Path(path)
    try:
        import rasterio  # type: ignore
        with rasterio.open(path) as src:
            arr = src.read(1).astype(np.float32)
            nodata = src.nodata
            if nodata is not None:
                arr[arr == nodata] = np.nan
            return arr, abs(src.transform.a)
    except ImportError:
        pass
    if path.suffix.lower() == ".npy":
        return np.load(path).astype(np.float32), None
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    return np.asarray(Image.open(path), dtype=np.float32), None


def _block_mean(arr: np.ndarray, f: int) -> np.ndarray:
    if f <= 1:
        return arr
    h, w = (arr.shape[0] // f) * f, (arr.shape[1] // f) * f
    return np.nanmean(arr[:h, :w].reshape(h // f, f, w // f, f), axis=(1, 3))


def load_scene(dem_path: str | Path, pixel_size_m: float | None = None,
               pole_rc: tuple[float, float] | None = None, downsample: int = 1,
               dem_scale: float = 1.0, rocks_path: str | Path | None = None,
               illum_path: str | Path | None = None) -> Scene:
    """Load real NASA rasters into a Scene.

    dem_scale: LOLA IMG/TIF products are often stored in km or with a scale
    factor (e.g. 0.5 m per DN); pass the factor that converts to metres.
    pole_rc: position of the pole in the *original* raster; defaults to centre.
    """
    dem, px = read_raster(dem_path)
    px = pixel_size_m or px
    if px is None:
        raise ValueError("Pixel size unknown: pass --pixel-size (metres).")
    dem = dem * dem_scale
    if np.isnan(dem).any():
        dem = np.where(np.isnan(dem), np.nanmean(dem), dem)
    h0, w0 = dem.shape
    pole = pole_rc or (h0 / 2.0, w0 / 2.0)

    dem = _block_mean(dem, downsample)
    pole = (pole[0] / downsample, pole[1] / downsample)
    scene = Scene(dem=dem.astype(np.float32), pixel_size_m=px * downsample,
                  pole_rc=pole, name=Path(dem_path).stem,
                  meta={"synthetic": False, "source": str(dem_path)})

    def _aux(p):
        a, _ = read_raster(p)
        a = _block_mean(a, downsample)[: dem.shape[0], : dem.shape[1]]
        if a.shape != dem.shape:
            raise ValueError(f"{p}: shape {a.shape} does not match DEM {dem.shape}")
        return a

    if rocks_path:
        r = _aux(rocks_path)
        scene.rocks = np.clip(r / np.nanpercentile(r, 99.5), 0, 1).astype(np.float32)
    if illum_path:
        il = _aux(illum_path)
        if np.nanmax(il) > 1.5:  # percent -> fraction
            il = il / 100.0
        scene.illumination = np.clip(il, 0, 1).astype(np.float32)
    return scene
