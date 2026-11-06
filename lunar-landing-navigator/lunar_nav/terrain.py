"""Terrain derivatives computed from the LOLA DEM: slope, roughness, hillshade."""
import numpy as np
from scipy import ndimage


def slope_deg(dem: np.ndarray, pixel_size_m: float) -> np.ndarray:
    """Surface slope in degrees (central differences, like LOLA slope maps)."""
    gy, gx = np.gradient(dem.astype(np.float64), pixel_size_m)
    return np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)


def roughness(dem: np.ndarray, window: int = 5) -> np.ndarray:
    """Local relief after removing the trend: std-dev of the detrended DEM."""
    d = dem.astype(np.float64)
    detrended = d - ndimage.uniform_filter(d, window)
    var = ndimage.uniform_filter(detrended**2, window)
    return np.sqrt(np.maximum(var, 0)).astype(np.float32)


def hillshade(dem: np.ndarray, pixel_size_m: float, azimuth_deg=315.0,
              altitude_deg=35.0, z_factor=2.0) -> np.ndarray:
    gy, gx = np.gradient(dem.astype(np.float64) * z_factor, pixel_size_m)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = np.radians(azimuth_deg), np.radians(altitude_deg)
    hs = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    return np.clip(hs, 0, 1).astype(np.float32)
