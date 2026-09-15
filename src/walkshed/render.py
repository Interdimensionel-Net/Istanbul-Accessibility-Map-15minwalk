"""Folium map with coverage, per-station polygons, and station markers."""

from __future__ import annotations

import folium
import geopandas as gpd

from walkshed.config import Config

MODE_COLORS = {
    "subway": "#1f77b4",
    "suburban_rail": "#d62728",
    "train": "#d62728",
    "tram": "#2ca02c",
    "heritage_tram": "#66a61e",
    "funicular": "#9467bd",
    "heritage_funicular": "#b48ac8",
    "cable_car": "#e7298a",
    "light_rail": "#ff7f0e",
    "brt": "#e6ab02",
    "unknown": "#7f7f7f",
}
MODE_LABELS = {
    "subway": "Metro",
    "suburban_rail": "Marmaray and suburban rail",
    "train": "Marmaray and suburban rail",
    "tram": "Tram",
    "heritage_tram": "Tram",
    "funicular": "Funicular",
    "heritage_funicular": "Funicular",
    "cable_car": "Cable car",
    "brt": "Metrobüs",
}
COVERAGE_COLOR = "#1a5fb4"
TILES = "OpenStreetMap"
FOCUS_CSS = "<style>path.leaflet-interactive:focus{outline:none}</style>"


def _coverage_layer(coverage: gpd.GeoDataFrame) -> folium.FeatureGroup:
    layer = folium.FeatureGroup(name="15-min walk coverage (all rail)", show=True)
    folium.GeoJson(
        coverage.__geo_interface__,
        style_function=lambda _: {
            "fillColor": COVERAGE_COLOR,
            "color": COVERAGE_COLOR,
            "weight": 1,
            "fillOpacity": 0.35,
        },
    ).add_to(layer)
    return layer


def _widest_per_station(isochrones: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """One polygon per station: the widest band, dissolved over all its entrances."""
    subset = isochrones
    if "band_s" in subset:
        subset = subset[subset["band_s"] == subset["band_s"].max()]
    keys = ["station_id", "station_name", "line", "operator", "mode"]
    return subset[keys + ["geometry"]].dissolve(by=keys, as_index=False)


def _mode_layer(
    stations_poly: gpd.GeoDataFrame, label: str, modes: list[str]
) -> folium.FeatureGroup:
    subset = stations_poly[stations_poly["mode"].isin(modes)]
    color = MODE_COLORS.get(modes[0], MODE_COLORS["unknown"])
    layer = folium.FeatureGroup(name=f"{label} ({len(subset)} stations)", show=False)
    folium.GeoJson(
        subset[["station_name", "line", "operator", "geometry"]].__geo_interface__,
        style_function=lambda _: {
            "fillColor": color,
            "color": color,
            "weight": 0.8,
            "fillOpacity": 0.25,
        },
        highlight_function=lambda _: {"weight": 3, "color": "#222", "fillOpacity": 0.45},
        tooltip=folium.GeoJsonTooltip(
            fields=["station_name", "line", "operator"],
            aliases=["Station", "Line", "Operator"],
        ),
    ).add_to(layer)
    return layer


def _station_layer(stations: gpd.GeoDataFrame) -> folium.FeatureGroup:
    layer = folium.FeatureGroup(name="Stations", show=True)
    for row in stations.itertuples():
        folium.CircleMarker(
            location=(row.geometry.y, row.geometry.x),
            radius=3,
            color=MODE_COLORS.get(row.mode, MODE_COLORS["unknown"]),
            fill=True,
            fill_opacity=0.9,
            tooltip=f"{row.name} ({row.line}, {row.mode}, {row.operator})",
        ).add_to(layer)
    return layer


def build_map(
    stations: gpd.GeoDataFrame,
    isochrones: gpd.GeoDataFrame,
    coverage: gpd.GeoDataFrame,
    summary: dict,
    cfg: Config,
) -> folium.Map:
    """All inputs must be in EPSG:4326."""
    min_x, min_y, max_x, max_y = coverage.total_bounds
    center = ((min_y + max_y) / 2, (min_x + max_x) / 2)
    fmap = folium.Map(location=center, zoom_start=cfg.map_zoom, tiles=TILES)
    fmap.get_root().header.add_child(folium.Element(FOCUS_CSS))
    _coverage_layer(coverage).add_to(fmap)
    per_station = _widest_per_station(isochrones)
    groups: dict[str, list[str]] = {}
    for mode in per_station["mode"].unique():
        groups.setdefault(MODE_LABELS.get(mode, mode), []).append(mode)
    for label, modes in sorted(groups.items()):
        _mode_layer(per_station, label, modes).add_to(fmap)
    _station_layer(stations).add_to(fmap)
    folium.LayerControl(collapsed=False).add_to(fmap)
    title = (
        f"<div style='position:fixed;top:10px;left:50px;z-index:9999;background:white;"
        f"padding:8px 12px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.3);"
        f"font-family:sans-serif;font-size:14px'>"
        f"<b>Istanbul: 15-minute walk to rail</b><br>"
        f"{summary['station_count']} stations, {summary['origin_count']} origins "
        f"({summary['entrance_count']} entrances), {summary['total_km2']:.1f} km² covered, "
        f"{cfg.walk_speed_kmh} km/h<br><span style='font-size:11px'>"
        f"Data © OpenStreetMap contributors (ODbL)</span></div>"
    )
    fmap.get_root().html.add_child(folium.Element(title))
    return fmap
