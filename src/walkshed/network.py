"""Build or load the pedestrian graph around the rail corridors."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import geopandas as gpd
import networkx as nx
import osmnx as ox
import shapely
from shapely.geometry.base import BaseGeometry

from walkshed.config import Config
from walkshed.isochrone import add_travel_time
from walkshed.names import content_hash

log = logging.getLogger(__name__)
GRAPH_KEY_GRID_DEG = 0.0001  # about 10 m grid; absorbs float noise, not station changes


def corridor_polygon(origins_m: gpd.GeoDataFrame, cfg: Config) -> BaseGeometry:
    """Union of buffers around all origins (metric CRS in), returned in EPSG:4326."""
    buffered = origins_m.buffer(cfg.corridor_buffer_m)
    outline = buffered.union_all().simplify(cfg.corridor_simplify_m).buffer(cfg.corridor_simplify_m)
    merged = gpd.GeoSeries([outline], crs=cfg.crs_metric)
    return merged.to_crs(cfg.crs_geo).iloc[0]


def graph_cache_path(polygon: BaseGeometry, cfg: Config) -> Path:
    """Cache file keyed on the corridor shape, so a station change changes the key."""
    shape = shapely.set_precision(polygon, GRAPH_KEY_GRID_DEG).wkb.hex()
    key = content_hash(f"{shape}|{cfg.crs_metric}|walk")
    return cfg.cache_dir / f"walk_graph_{key}.graphml"


def _configure_osmnx(cfg: Config) -> None:
    ox.settings.log_console = cfg.verbose
    ox.settings.requests_timeout = cfg.osmnx_timeout_s
    ox.settings.overpass_url = cfg.osmnx_overpass_url
    ox.settings.overpass_rate_limit = "overpass-api.de" in cfg.osmnx_overpass_url
    ox.settings.cache_folder = str(cfg.osmnx_cache_dir)
    ox.settings.max_query_area_size = cfg.osmnx_max_query_area_m2


def _download_graph(polygon: BaseGeometry, cfg: Config) -> nx.MultiDiGraph:
    log.info("Downloading walk network for the corridor polygon")
    return ox.graph_from_polygon(polygon, network_type="walk", simplify=True)


def _graph_from_cached_responses(polygon: BaseGeometry, cfg: Config) -> nx.MultiDiGraph:
    """Rebuild the walk graph from Overpass responses already on disk. No network access."""
    from osmnx.graph import _create_graph

    files = sorted(cfg.osmnx_cache_dir.glob("*.json"))
    if not files:
        raise RuntimeError(f"offline_graph is set but {cfg.osmnx_cache_dir} holds no responses")
    log.info("Building graph offline from %d cached responses", len(files))
    responses = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    raw = _create_graph(responses, bidirectional=True)
    clipped = ox.truncate.truncate_graph_polygon(raw, polygon, truncate_by_edge=True)
    return ox.simplify_graph(clipped)


def _covering_cache(polygon: BaseGeometry, cfg: Config) -> Path | None:
    """A cached graph whose stored corridor contains the requested corridor, if any."""
    for wkt_file in sorted(cfg.cache_dir.glob("walk_graph_*.corridor.wkt")):
        graph_file = wkt_file.with_name(wkt_file.name.replace(".corridor.wkt", ".graphml"))
        if not graph_file.exists():
            continue
        stored = shapely.from_wkt(wkt_file.read_text(encoding="utf-8"))
        if stored.buffer(GRAPH_KEY_GRID_DEG).contains(polygon):
            return graph_file
    return None


def load_or_build_graph(
    origins_m: gpd.GeoDataFrame, cfg: Config, refresh: bool = False
) -> nx.MultiDiGraph:
    """Projected walk graph with a `time` attribute on every edge."""
    polygon = corridor_polygon(origins_m, cfg)
    cache = graph_cache_path(polygon, cfg)
    covering = None if refresh or cache.exists() else _covering_cache(polygon, cfg)
    if covering is not None:
        log.info("Graph cache covers the corridor: %s", covering)
        graph = ox.load_graphml(covering)
    elif cache.exists() and not refresh:
        log.info("Graph cache hit: %s", cache)
        graph = ox.load_graphml(cache)
    else:
        _configure_osmnx(cfg)
        builder = _graph_from_cached_responses if cfg.offline_graph else _download_graph
        graph = ox.project_graph(builder(polygon, cfg), to_crs=cfg.crs_metric)
        cache.parent.mkdir(parents=True, exist_ok=True)
        ox.save_graphml(graph, cache)
        cache.with_name(cache.name.replace(".graphml", ".corridor.wkt")).write_text(
            polygon.wkt, encoding="utf-8"
        )
    log.info("Graph: %d nodes, %d edges", graph.number_of_nodes(), graph.number_of_edges())
    return add_travel_time(graph, cfg)
