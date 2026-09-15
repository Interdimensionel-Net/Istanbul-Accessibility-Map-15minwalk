"""Stitch OpenStreetMap tiles into static basemap images for hosts that block tile servers.

Writes output/artifact/basemap_wide.jpg, basemap_core.jpg and basemap.json (their bounds).
Tiles © OpenStreetMap contributors, ODbL. Keep the request volume small and the
User-Agent honest, per the OSM tile usage policy.

Usage: uv run python scripts/build_basemap.py
"""

from __future__ import annotations

import io
import json
import math
import sys
import time
from pathlib import Path

import requests
from PIL import Image

from walkshed.config import DEFAULT_CONFIG

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
TILE = 256
LAYERS = {
    # name: (zoom, west, south, east, north)
    "wide": (12, 28.05, 40.78, 29.45, 41.30),
    "core": (14, 28.82, 40.96, 29.20, 41.14),
}
PAUSE_S = 0.15


def _tile_x(lon: float, z: int) -> int:
    return int((lon + 180) / 360 * 2**z)


def _tile_y(lat: float, z: int) -> int:
    rad = math.radians(lat)
    return int((1 - math.log(math.tan(rad) + 1 / math.cos(rad)) / math.pi) / 2 * 2**z)


def _tile_lon(x: int, z: int) -> float:
    return x / 2**z * 360 - 180


def _tile_lat(y: int, z: int) -> float:
    n = math.pi - 2 * math.pi * y / 2**z
    return math.degrees(math.atan(math.sinh(n)))


def _fetch(session: requests.Session, z: int, x: int, y: int, cache: Path) -> Image.Image:
    path = cache / f"{z}_{x}_{y}.png"
    if not path.exists():
        response = session.get(TILE_URL.format(z=z, x=x, y=y), timeout=60)
        response.raise_for_status()
        path.write_bytes(response.content)
        time.sleep(PAUSE_S)
    return Image.open(io.BytesIO(path.read_bytes())).convert("RGB")


def build_layer(name: str, spec: tuple, out: Path, cache: Path, session: requests.Session) -> dict:
    z, west, south, east, north = spec
    x0, x1 = _tile_x(west, z), _tile_x(east, z)
    y0, y1 = _tile_y(north, z), _tile_y(south, z)
    cols, rows = x1 - x0 + 1, y1 - y0 + 1
    print(f"{name}: zoom {z}, {cols}x{rows} = {cols * rows} tiles")
    sheet = Image.new("RGB", (cols * TILE, rows * TILE))
    for j, y in enumerate(range(y0, y1 + 1)):
        for i, x in enumerate(range(x0, x1 + 1)):
            sheet.paste(_fetch(session, z, x, y, cache), (i * TILE, j * TILE))
    target = out / f"basemap_{name}.jpg"
    sheet.save(target, "JPEG", quality=72, optimize=True, progressive=True)
    print(f"  wrote {target.name}: {target.stat().st_size / 1e6:.2f} MB")
    return {
        "file": target.name,
        "zoom": z,
        "bounds": [
            [_tile_lat(y1 + 1, z), _tile_lon(x0, z)],
            [_tile_lat(y0, z), _tile_lon(x1 + 1, z)],
        ],
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    cfg = DEFAULT_CONFIG
    out = cfg.artifact_dir
    out.mkdir(parents=True, exist_ok=True)
    cache = cfg.cache_dir / "tiles"
    cache.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = cfg.user_agent
    layers = [build_layer(name, spec, out, cache, session) for name, spec in LAYERS.items()]
    (out / "basemap.json").write_text(
        json.dumps({"attribution": "© OpenStreetMap contributors", "layers": layers}),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
