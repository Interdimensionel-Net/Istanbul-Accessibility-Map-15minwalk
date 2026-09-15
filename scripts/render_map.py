"""Re-render the Folium map and the web data from files already in output/.

No isochrones are recomputed.

Usage: uv run python scripts/render_map.py
"""

from __future__ import annotations

import json
import sys

import geopandas as gpd

from walkshed.config import DEFAULT_CONFIG
from walkshed.export import write_artifact_data
from walkshed.overpass import cache_path
from walkshed.pipeline import provenance
from walkshed.render import build_map


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    cfg = DEFAULT_CONFIG
    out = cfg.output_dir
    stations = gpd.read_file(out / "stations.geojson")
    isochrones = gpd.read_file(out / "isochrones.geojson")
    coverage = gpd.read_file(out / "coverage.geojson")
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    summary = {
        **summary,
        "provenance": provenance(cfg, False, cache_path(cfg).exists(), True),
    }
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    build_map(stations, isochrones, coverage, summary, cfg).save(str(cfg.map_html))
    write_artifact_data(
        stations,
        isochrones.to_crs(cfg.crs_metric),
        coverage.to_crs(cfg.crs_metric),
        cfg,
        cfg.artifact_dir,
        provenance=summary["provenance"],
    )
    print(f"Wrote {cfg.map_html} and {cfg.artifact_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
