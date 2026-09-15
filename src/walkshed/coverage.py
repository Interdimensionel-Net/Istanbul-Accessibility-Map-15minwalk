"""Dissolve station polygons and compute area statistics."""

from __future__ import annotations

import geopandas as gpd

M2_PER_KM2 = 1_000_000


def dissolve_coverage(isochrones: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Single-row frame holding the union of all polygons, same CRS as input."""
    merged = isochrones.geometry.union_all()
    return gpd.GeoDataFrame({"layer": ["coverage"]}, geometry=[merged], crs=isochrones.crs)


def _group_km2(isochrones: gpd.GeoDataFrame, column: str) -> dict[str, float]:
    """Area per group. Groups overlap each other, so values do not sum to the total."""
    grouped = isochrones[[column, "geometry"]].dissolve(by=column)
    return {str(k): float(a) / M2_PER_KM2 for k, a in grouped.geometry.area.items()}


def _count_kind(isochrones: gpd.GeoDataFrame, kind: str) -> int:
    if "origin_kind" not in isochrones:
        return 0
    return int((isochrones["origin_kind"] == kind).sum())


def summarize(isochrones: gpd.GeoDataFrame, coverage: gpd.GeoDataFrame) -> dict:
    """Area statistics. Both frames must share a metric CRS."""
    station_key = "station_id" if "station_id" in isochrones else "station_name"
    return {
        "origin_count": len(isochrones),
        "entrance_count": _count_kind(isochrones, "entrance"),
        "station_count": int(isochrones[station_key].nunique()),
        "total_km2": float(coverage.geometry.area.sum()) / M2_PER_KM2,
        "by_mode_km2": _group_km2(isochrones, "mode"),
        "by_line_km2": _group_km2(isochrones, "line"),
        "by_operator_km2": _group_km2(isochrones, "operator") if "operator" in isochrones else {},
    }
