"""Check OSM station coverage against data/reference/lines.json.

Usage: uv run python scripts/validate_lines.py
"""

from __future__ import annotations

import json
import sys

import geopandas as gpd

from walkshed.config import DEFAULT_CONFIG, PROJECT_ROOT
from walkshed.validate import compare, compare_loose, load_reference

REFERENCE = PROJECT_ROOT / "data" / "reference" / "lines.json"


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    stations_path = DEFAULT_CONFIG.output_dir / "stations.geojson"
    if not REFERENCE.exists() or not stations_path.exists():
        print(f"Need both {REFERENCE} and {stations_path}.")
        return 1
    reference = load_reference(REFERENCE)
    stations = gpd.read_file(stations_path)
    strict = compare(reference, stations)
    loose = compare_loose(reference, stations)
    print(f"{'line':10} {'official':>8} {'exact':>6} {'loose':>6}  missing (loose)")
    for line, row in strict.items():
        loose_row = loose[line]
        missing = ", ".join(loose_row["missing_in_osm"])
        print(
            f"{line:10} {row['official']:>8} {row['matched']:>6} "
            f"{loose_row['matched']:>6}  {missing}"
        )
    out = DEFAULT_CONFIG.output_dir / "line_validation.json"
    out.write_text(
        json.dumps({"strict": strict, "loose": loose}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
