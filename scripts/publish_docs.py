"""Copy the built web map from output/artifact/ into docs/ for GitHub Pages.

docs/ is committed. It holds OpenStreetMap-derived data (ODbL) and two OSM basemap
sheets; the page credits OpenStreetMap contributors.

Usage: uv run python scripts/publish_docs.py
"""

from __future__ import annotations

import shutil
import sys

from walkshed.config import DEFAULT_CONFIG, PROJECT_ROOT

DOCS = PROJECT_ROOT / "docs"
KEEP = {".nojekyll"}


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    source = DEFAULT_CONFIG.artifact_dir
    if not (source / "index.html").exists():
        print(f"No built page in {source}. Run scripts/build_web.py first.")
        return 1
    DOCS.mkdir(exist_ok=True)
    for old in DOCS.iterdir():
        if old.name not in KEEP:
            old.unlink()
    (DOCS / ".nojekyll").touch()
    total = 0
    for item in sorted(source.iterdir()):
        if item.is_file():
            shutil.copyfile(item, DOCS / item.name)
            total += item.stat().st_size
            print(f"{item.name:20} {item.stat().st_size / 1e6:6.2f} MB")
    print(f"{'total':20} {total / 1e6:6.2f} MB -> {DOCS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
