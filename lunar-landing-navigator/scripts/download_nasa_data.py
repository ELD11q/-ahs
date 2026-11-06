"""Download NASA lunar south-pole rasters (run this on your own machine).

NASA's data sites occasionally reorganise their folders, so instead of
hard-coding file URLs that may break, this script:

  1. prints the official catalogue pages for each dataset, and
  2. downloads any file URL you pass it (with resume + progress).

Usage:
    python scripts/download_nasa_data.py --list
    python scripts/download_nasa_data.py <file-url> [<file-url> ...] -o data/

Then run the navigator on it, e.g.:
    python -m lunar_nav --dem data/LDEM_85S_20M.tif --pixel-size 20 --downsample 4
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

CATALOGUE = {
    "LOLA polar DEMs (elevation, slope) – PDS Geosciences node":
        "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/",
    "LOLA high-res south-pole DEMs, illumination & Earth visibility – NASA GSFC PGDA":
        "https://pgda.gsfc.nasa.gov/products/",
    "Diviner rock abundance (polar) – PDS Geosciences node":
        "https://pds-geosciences.wustl.edu/missions/lro/diviner.htm",
    "LROC NAC images / mosaics (for YOLO crater & boulder detection)":
        "https://wms.lroc.asu.edu/lroc/rdr_product_select",
    "Artemis III candidate regions (context)":
        "https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/",
}

HINTS = """
Tips
 * Start with a ~20-80 m/px south-pole DEM (85S or 80S); 5 m/px files are many GB.
 * LOLA polar .IMG files come with a .LBL label: read SCALING_FACTOR / OFFSET and
   pass them via --dem-scale (and convert km -> m if needed).
 * GeoTIFFs keep pixel size automatically if you `pip install rasterio`.
 * Use --downsample 2..8 so the horizon ray-casting stays fast.
"""


def download(url: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / url.rstrip("/").split("/")[-1]
    have = dest.stat().st_size if dest.exists() else 0
    req = urllib.request.Request(url, headers={"User-Agent": "lunar-landing-navigator/0.1"})
    if have:
        req.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(req) as r:
        if have and r.status != 206:
            have = 0  # server ignored Range: start over
        total = int(r.headers.get("Content-Length", 0)) + have
        mode = "ab" if have else "wb"
        done = have
        with open(dest, mode) as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
                done += len(chunk)
                if total:
                    sys.stdout.write(f"\r{dest.name}: {done / 1e6:8.1f} / {total / 1e6:.1f} MB")
                    sys.stdout.flush()
    print(f"\nsaved {dest}")
    return dest


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("urls", nargs="*")
    p.add_argument("-o", "--out", default="data")
    p.add_argument("--list", action="store_true", help="show where to find each dataset")
    a = p.parse_args()
    if a.list or not a.urls:
        for k, v in CATALOGUE.items():
            print(f"- {k}\n    {v}")
        print(HINTS)
        return
    for u in a.urls:
        download(u, Path(a.out))


if __name__ == "__main__":
    main()
