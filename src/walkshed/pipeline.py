"""End-to-end run: stations -> network -> isochrones -> coverage -> map."""

from __future__ import annotations

import json
import logging
import platform
from pathlib import Path
from dataclasses import asdict
from datetime import UTC, datetime
from importlib.metadata import version

import geopandas as gpd
import networkx as nx
import osmnx as ox

from walkshed.config import PROJECT_ROOT, Config
from walkshed.contracts import ENTRANCES, ISOCHRONES, ORIGINS, STATIONS, require_columns
from walkshed.coverage import dissolve_coverage, summarize
from walkshed.export import resolve_lines, write_artifact_data
from walkshed.isochrone import reachable_bands
from walkshed.names import content_hash, load_lines
from walkshed.network import load_or_build_graph
from walkshed.overpass import cache_path, fetch_elements, query_hash
from walkshed.reference import apply_reference, load_aliases
from walkshed.render import build_map
from walkshed.stations import build_origins, parse_elements

log = logging.getLogger(__name__)
PROGRESS_EVERY = 50


def _snap_to_graph(
    origins_m: gpd.GeoDataFrame, graph: nx.MultiDiGraph, cfg: Config
) -> tuple[gpd.GeoDataFrame, list]:
    """Nearest graph node per origin. Origins beyond max_snap_m from the network are dropped."""
    if origins_m.empty:
        raise RuntimeError("No origins to snap. The station set is empty.")
    nearest, dist = ox.distance.nearest_nodes(
        graph, X=origins_m.geometry.x.to_list(), Y=origins_m.geometry.y.to_list(), return_dist=True
    )
    keep = [d <= cfg.max_snap_m for d in dist]
    dropped = origins_m[[not k for k in keep]]
    if len(dropped):
        log.warning(
            "%d origins are more than %.0f m from the network and are skipped: %s",
            len(dropped),
            cfg.max_snap_m,
            sorted(set(dropped["station_name"])),
        )
    kept_nodes = [n for n, k in zip(nearest, keep, strict=True) if k]
    return origins_m[keep].reset_index(drop=True), kept_nodes


def compute_isochrones(
    origins_m: gpd.GeoDataFrame, graph: nx.MultiDiGraph, cfg: Config
) -> gpd.GeoDataFrame:
    """One row per origin and band, in the metric CRS. Column `band_s` holds the cutoff."""
    origins_m, nearest = _snap_to_graph(origins_m, graph, cfg)
    attrs = origins_m.drop(columns="geometry").assign(graph_node=nearest)
    rows = []
    for i, (record, node) in enumerate(
        zip(attrs.to_dict("records"), nearest, strict=True), start=1
    ):
        for band, polygon in reachable_bands(graph, node, cfg).items():
            rows.append({**record, "band_s": band, "geometry": polygon})
        if i % PROGRESS_EVERY == 0:
            log.info("Isochrones: %d / %d", i, len(nearest))
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=cfg.crs_metric)


def _write_outputs(
    stations: gpd.GeoDataFrame,
    isochrones_m: gpd.GeoDataFrame,
    coverage_m: gpd.GeoDataFrame,
    summary: dict,
    cfg: Config,
) -> None:
    out = cfg.output_dir
    out.mkdir(parents=True, exist_ok=True)
    isochrones = isochrones_m.to_crs(cfg.crs_geo)
    coverage = coverage_m.to_crs(cfg.crs_geo)
    stations.to_file(out / "stations.geojson", driver="GeoJSON")
    isochrones.to_file(out / "isochrones.geojson", driver="GeoJSON")
    coverage.to_file(out / "coverage.geojson", driver="GeoJSON")
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    build_map(stations, isochrones, coverage, summary, cfg).save(str(cfg.map_html))
    log.info("Wrote outputs to %s", out)


PACKAGES = ("osmnx", "geopandas", "networkx", "shapely", "folium")


def provenance(cfg: Config, refresh: bool, overpass_cached: bool, graph_cached: bool) -> dict:
    """What produced this run: inputs, their hashes, versions, and the effective configuration."""
    overpass = cache_path(cfg)
    retrieved = (
        datetime.fromtimestamp(overpass.stat().st_mtime, tz=UTC).isoformat()
        if overpass.exists()
        else None
    )
    reference = cfg.reference_path
    return {
        "run_at": datetime.now(tz=UTC).isoformat(),
        "overpass_query_hash": query_hash(cfg),
        "overpass_retrieved_at": retrieved,
        "overpass_from_cache": overpass_cached,
        "reference_hash": content_hash(reference.read_text(encoding="utf-8"))
        if reference.exists()
        else None,
        "graph_from_cache": graph_cached,
        "refresh": refresh,
        "python": platform.python_version(),
        "packages": {p: version(p) for p in PACKAGES},
        "config": {k: _public_value(v) for k, v in asdict(cfg).items()},
    }


def _public_value(value: object) -> object:
    """Config values as published: paths relative to the project, never the machine's layout."""
    if isinstance(value, Path):
        try:
            return value.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            return value.name
    if isinstance(value, int | float | bool | str | tuple):
        return value
    return str(value)


def run(cfg: Config, refresh: bool = False) -> dict:
    overpass_cached = cache_path(cfg).exists() and not refresh
    elements = fetch_elements(cfg, refresh=refresh)
    raw_stations, entrances = parse_elements(elements, cfg)
    require_columns(raw_stations, STATIONS, "parse_elements stations")
    require_columns(entrances, ENTRANCES, "parse_elements entrances")
    stations = apply_reference(raw_stations, cfg.reference_path, cfg.require_reference)
    if cfg.require_reference and cfg.reference_path.exists():
        stations = resolve_lines(
            stations,
            load_lines(cfg.reference_path),
            load_aliases(cfg.reference_path.with_name("aliases.json")),
        )
    origins_m = require_columns(build_origins(stations, entrances, cfg), ORIGINS, "build_origins")
    log.info("%d stations, %d entrances, %d origins", len(stations), len(entrances), len(origins_m))
    graph_cached = not refresh and _graph_cache_exists(origins_m, cfg)
    graph = load_or_build_graph(origins_m, cfg, refresh=refresh)
    isochrones_m = require_columns(
        compute_isochrones(origins_m, graph, cfg), ISOCHRONES, "compute_isochrones"
    )
    widest = isochrones_m[isochrones_m["band_s"] == max(cfg.bands_seconds)]
    coverage_m = dissolve_coverage(widest)
    summary = {
        **summarize(widest, coverage_m),
        "provenance": provenance(cfg, refresh, overpass_cached, graph_cached),
    }
    _write_outputs(stations, isochrones_m, coverage_m, summary, cfg)
    write_artifact_data(
        stations, isochrones_m, coverage_m, cfg, cfg.artifact_dir, provenance=summary["provenance"]
    )
    return summary


def _graph_cache_exists(origins_m: gpd.GeoDataFrame, cfg: Config) -> bool:
    from walkshed.network import corridor_polygon, graph_cache_path

    return graph_cache_path(corridor_polygon(origins_m, cfg), cfg).exists()
