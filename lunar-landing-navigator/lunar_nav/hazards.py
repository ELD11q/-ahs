"""Crater and boulder hazards.

Two detectors share one output format (a list of craters + a hazard mask):

* `detect_craters_classic` – no ML needed: finds bowl-shaped depressions in
  the DEM. Good enough at LOLA resolution (tens of metres per pixel).
* `detect_hazards_yolo` – runs a YOLO model (ultralytics) over LROC NAC
  imagery to find small craters and boulders that the DEM cannot resolve.
  Train it on a labelled crater/boulder set (e.g. the Robbins crater
  database or a hand-labelled NAC set) and pass the weights file.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage


@dataclass
class Crater:
    row: float
    col: float
    diameter_m: float
    depth_m: float
    source: str = "dem"


def detect_craters_classic(dem: np.ndarray, pixel_size_m: float,
                           min_diameter_m: float = 300.0,
                           scales_px=(4, 10, 25)) -> tuple[list[Crater], np.ndarray]:
    craters: list[Crater] = []
    mask = np.zeros(dem.shape, dtype=bool)
    d = dem.astype(np.float64)
    for s in scales_px:
        residual = d - ndimage.gaussian_filter(d, s * 1.5)
        thr = -1.5 * residual.std()
        cand = residual < thr
        labels, n = ndimage.label(cand)
        if n == 0:
            continue
        idx = np.arange(1, n + 1)
        areas = ndimage.sum(cand, labels, idx)
        depths = -ndimage.minimum(residual, labels, idx)
        centers = ndimage.center_of_mass(cand, labels, idx)
        for a, dep, (r, c), lab in zip(areas, depths, centers, idx):
            diam = 2 * np.sqrt(a / np.pi) * pixel_size_m
            if diam < min_diameter_m:
                continue
            craters.append(Crater(r, c, diam, float(dep)))
        mask |= ndimage.binary_dilation(cand, iterations=1)
    return craters, mask


def detect_hazards_yolo(image: np.ndarray, weights: str, conf: float = 0.25,
                        image_pixel_size_m: float = 1.0,
                        out_shape: tuple[int, int] | None = None):
    """Detect craters/boulders in an orbital image with a YOLO model.

    image: 2-D grayscale (e.g. LROC NAC mosaic) co-registered with the DEM.
    Returns (craters, hazard_mask) where the mask is resampled to out_shape.
    """
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError as e:  # pragma: no cover - optional dependency
        raise ImportError("pip install ultralytics  # needed for YOLO detection") from e

    img = image.astype(np.float32)
    img = (255 * (img - img.min()) / (np.ptp(img) + 1e-9)).astype(np.uint8)
    rgb = np.stack([img] * 3, axis=-1)
    model = YOLO(weights)
    res = model.predict(rgb, conf=conf, verbose=False)[0]

    h, w = img.shape
    mask = np.zeros((h, w), dtype=bool)
    craters = []
    for (x0, y0, x1, y1), cls in zip(res.boxes.xyxy.cpu().numpy(), res.boxes.cls.cpu().numpy()):
        r0, r1 = int(max(y0, 0)), int(min(y1, h))
        c0, c1 = int(max(x0, 0)), int(min(x1, w))
        mask[r0:r1, c0:c1] = True
        name = res.names.get(int(cls), str(int(cls)))
        craters.append(Crater((y0 + y1) / 2, (x0 + x1) / 2,
                              max(x1 - x0, y1 - y0) * image_pixel_size_m, 0.0, f"yolo:{name}"))
    if out_shape and out_shape != mask.shape:
        zoom = (out_shape[0] / h, out_shape[1] / w)
        mask = ndimage.zoom(mask.astype(np.float32), zoom, order=1) > 0.25
        for c in craters:
            c.row, c.col = c.row * zoom[0], c.col * zoom[1]
    return craters, mask


def hazard_map(rocks: np.ndarray | None, crater_mask: np.ndarray,
               roughness: np.ndarray) -> np.ndarray:
    """Combine rock abundance, crater interiors and roughness into 0..1."""
    rough = roughness / (np.percentile(roughness, 99) + 1e-9)
    base = np.clip(rough, 0, 1) * 0.5
    if rocks is not None:
        base = np.maximum(base, rocks)
    return np.clip(np.maximum(base, crater_mask * 0.7), 0, 1).astype(np.float32)
