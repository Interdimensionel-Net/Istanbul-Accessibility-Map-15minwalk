"""Assemble the publishable map page in output/artifact/.

Inlines the Leaflet stylesheet (the artifact host blocks external CSS from cdnjs) and copies
the province outline next to the data files written by the pipeline.

Usage: uv run python scripts/build_web.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import requests

from walkshed.config import DEFAULT_CONFIG, PROJECT_ROOT

LEAFLET_CSS_URL = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css"
PLACEHOLDER = "/* __LEAFLET_CSS__ */"
BUILD_PLACEHOLDER = "__BUILD__"


def leaflet_css(cache: Path) -> str:
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    response = requests.get(LEAFLET_CSS_URL, timeout=60)
    response.raise_for_status()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(response.text, encoding="utf-8")
    return response.text


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    cfg = DEFAULT_CONFIG
    out = cfg.artifact_dir
    if not (out / "meta.json").exists():
        print(f"No pipeline output in {out}. Run `uv run walkshed` first.")
        return 1
    source = (PROJECT_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    if PLACEHOLDER not in source:
        print("web/index.html has no Leaflet CSS placeholder.")
        return 1
    page = source.replace(PLACEHOLDER, leaflet_css(cfg.cache_dir / "leaflet-1.9.4.css"))
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    stamp = str(meta.get("provenance", {}).get("run_at", ""))[:19].replace(":", "") or "dev"
    page = page.replace(BUILD_PLACEHOLDER, stamp)
    (out / "index.html").write_text(page, encoding="utf-8")
    shutil.copyfile(
        PROJECT_ROOT / "data" / "reference" / "provinces.geojson", out / "provinces.geojson"
    )
    sizes = {p.name: p.stat().st_size for p in sorted(out.iterdir())}
    total = sum(sizes.values())
    for name, size in sizes.items():
        print(f"{name:20} {size / 1e6:6.2f} MB")
    print(f"{'total':20} {total / 1e6:6.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
