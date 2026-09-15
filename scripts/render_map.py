"""Re-render the Folium map and the web data from files already in output/.

No isochrones are recomputed.

Usage: uv run python scripts/render_map.py
"""

from __future__ import annotations

import json
import sys

import geopandas as gpd

from walkshed.config import DEFAULT_CONFIG
from walkshed.coverage import dissolve_coverage, summarize
from walkshed.export import resolve_lines, write_artifact_data
from walkshed.names import load_lines
from walkshed.overpass import cache_path
from walkshed.pipeline import provenance
from walkshed.reference import load_aliases
from walkshed.render import build_map


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    cfg = DEFAULT_CONFIG
    out = cfg.output_dir
    stations = resolve_lines(
        gpd.read_file(out / "stations.geojson"),
        load_lines(cfg.reference_path),
        load_aliases(cfg.reference_path.with_name("aliases.json")),
    )
    labels = stations.set_index("osm_id")[["line", "operator", "mode"]]
    isochrones = gpd.read_file(out / "isochrones.geojson")
    isochrones = isochrones[isochrones["station_id"].isin(labels.index)].copy()
    for column in ("line", "operator", "mode"):
        isochrones[column] = isochrones["station_id"].map(labels[column])
    widest = isochrones[isochrones["band_s"] == isochrones["band_s"].max()]
    coverage = dissolve_coverage(widest.to_crs(cfg.crs_metric)).to_crs(cfg.crs_geo)
    summary = summarize(widest.to_crs(cfg.crs_metric), coverage.to_crs(cfg.crs_metric))
    # stations.geojson and isochrones.geojson are pipeline outputs and stay untouched here:
    # a narrower label resolution must never delete computed walksheds from disk.
    coverage.to_file(out / "coverage.geojson", driver="GeoJSON")
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
