"""Reachable-area polygons on a projected pedestrian graph."""

from __future__ import annotations

from dataclasses import replace

import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry

from walkshed.config import Config


def add_travel_time(graph: nx.MultiDiGraph, cfg: Config) -> nx.MultiDiGraph:
    """Return a copy of the graph with `time` in seconds on every edge."""
    timed = graph.copy()
    speed = cfg.walk_speed_m_per_s
    times = {
        (u, v, k): float(data["length"]) / speed
        for u, v, k, data in timed.edges(keys=True, data=True)
    }
    nx.set_edge_attributes(timed, times, "time")
    return timed


def fill_holes(geometry: BaseGeometry) -> BaseGeometry:
    """Drop interior rings but keep every disjoint part."""
    if geometry.geom_type == "Polygon":
        return Polygon(geometry.exterior)
    if geometry.geom_type == "MultiPolygon":
        return MultiPolygon([Polygon(p.exterior) for p in geometry.geoms])
    return geometry


def _buffer_union(
    graph: nx.MultiDiGraph, node_ids: list[int], cfg: Config, crs: str | None
) -> BaseGeometry:
    sub = graph.subgraph(node_ids)
    nodes = gpd.GeoSeries({n: Point(d["x"], d["y"]) for n, d in sub.nodes(data=True)}, crs=crs)
    edge_lines = [
        data.get("geometry", LineString([nodes.loc[u], nodes.loc[v]]))
        for u, v, data in sub.edges(data=True)
    ]
    buffers = list(nodes.buffer(cfg.node_buffer_m))
    if edge_lines:
        buffers = buffers + list(gpd.GeoSeries(edge_lines, crs=crs).buffer(cfg.edge_buffer_m))
    return fill_holes(gpd.GeoSeries(buffers, crs=crs).union_all())


def reachable_bands(
    graph: nx.MultiDiGraph, center_node: int, cfg: Config
) -> dict[int, BaseGeometry]:
    """One polygon per band in cfg.bands_seconds, from a single shortest-path pass."""
    limit = max(cfg.bands_seconds)
    times = nx.single_source_dijkstra_path_length(graph, center_node, cutoff=limit, weight="time")
    crs = graph.graph.get("crs")
    return {
        band: _buffer_union(graph, [n for n, t in times.items() if t <= band], cfg, crs)
        for band in sorted(cfg.bands_seconds)
    }


def reachable_polygon(graph: nx.MultiDiGraph, center_node: int, cfg: Config) -> BaseGeometry:
    """Polygon of everything reachable within cfg.cutoff_seconds from center_node."""
    single = replace(cfg, bands_seconds=(cfg.cutoff_seconds,))
    return reachable_bands(graph, center_node, single)[cfg.cutoff_seconds]
