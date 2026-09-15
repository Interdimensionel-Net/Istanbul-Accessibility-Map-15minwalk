"""Turn Overpass elements into station and origin GeoDataFrames."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from walkshed.config import Config
from walkshed.names import normalize

STATION_RAILWAY = {"station", "tram_stop", "brt_station", "aerialway_station"}
DUPLICATE_PLATFORM = "duplicate_platform"
ENTRANCE_RAILWAY = {"subway_entrance", "train_station_entrance", "brt_platform", DUPLICATE_PLATFORM}
PLATFORM_MERGE_M = 80.0
MODE_BY_STATION_TAG = {"subway": "subway", "light_rail": "light_rail", "funicular": "funicular"}
UNKNOWN = "unknown"
OPERATOR_TCDD = "TCDD Taşımacılık"
OPERATOR_METRO = "Metro İstanbul"
NATIONAL_MODES = {"train"}
OPERATOR_IETT = "İETT"
MODE_BRT = "brt"
BRT_STATION = "brt_station"
BRT_PLATFORM = "brt_platform"


def _is_brt(tags: dict) -> bool:
    return tags.get("bus") == "yes" and "railway" not in tags


def _mode(tags: dict) -> str:
    if _is_brt(tags):
        return MODE_BRT
    if tags.get("aerialway") == "station":
        return "cable_car"
    if tags.get("railway") == "tram_stop":
        return "tram"
    station_tag = tags.get("station", "")
    if station_tag in MODE_BY_STATION_TAG:
        return MODE_BY_STATION_TAG[station_tag]
    if tags.get("train") == "yes":
        return "train"
    if tags.get("subway") == "yes":
        return "subway"
    return UNKNOWN


def _operator(tags: dict, mode: str) -> str:
    """OSM operator tag, else infer: Marmaray and TCDD are national, the rest is Metro İstanbul."""
    tagged = tags.get("operator", "")
    if "TCDD" in tagged.upper():
        return OPERATOR_TCDD
    if tagged:
        return tagged
    if mode == MODE_BRT:
        return OPERATOR_IETT
    return OPERATOR_TCDD if mode in NATIONAL_MODES else OPERATOR_METRO


def _line(tags: dict, mode: str, cfg: Config) -> str:
    if mode == MODE_BRT:
        return cfg.brt_line_name
    return tags.get("line") or tags.get("network") or UNKNOWN


def _railway_fallback(mode: str) -> str:
    if mode == MODE_BRT:
        return BRT_PLATFORM
    if mode == "cable_car":
        return "aerialway_station"
    return ""


def _record(element: dict, cfg: Config) -> dict:
    tags = element.get("tags", {})
    mode = _mode(tags)
    return {
        "osm_id": element["id"],
        "name": tags.get("name", f"osm-{element['id']}"),
        "mode": mode,
        "operator": _operator(tags, mode),
        "line": _line(tags, mode, cfg),
        "railway": tags.get("railway", _railway_fallback(mode)),
        "geometry": Point(element["lon"], element["lat"]),
    }


def _promote_brt_stations(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """One BRT node per stop name becomes the station; the rest stay platforms (entrances)."""
    is_brt = frame["mode"] == MODE_BRT
    first_per_name = is_brt & ~frame[is_brt]["name"].duplicated().reindex(
        frame.index, fill_value=False
    )
    railway = frame["railway"].where(~first_per_name, BRT_STATION)
    return frame.assign(railway=railway)


def _merge_close_platforms(frame: gpd.GeoDataFrame, cfg: Config) -> gpd.GeoDataFrame:
    """Same name, same mode, within PLATFORM_MERGE_M: one node stays the station and the others
    become entrances. OSM maps many tram stops as one stop_position per direction; without this,
    two lines can each pick a different platform of the same stop (Sirkeci: T1 and T6)."""
    is_station = frame["railway"].isin(STATION_RAILWAY)
    if is_station.sum() < 2:
        return frame
    metric = frame.to_crs(cfg.crs_metric)
    railway = frame["railway"].copy()
    keys = frame["name"].map(normalize) + "|" + frame["mode"]
    for _, idx in frame[is_station].groupby(keys[is_station]).groups.items():
        idx = sorted(idx, key=lambda i: int(frame.at[i, "osm_id"]))
        kept: list[int] = []
        for i in idx:
            near = any(
                metric.geometry[i].distance(metric.geometry[k]) <= PLATFORM_MERGE_M for k in kept
            )
            if near:
                railway.at[i] = DUPLICATE_PLATFORM
            else:
                kept.append(i)
    return frame.assign(railway=railway)


def parse_elements(
    elements: list[dict], cfg: Config | None = None
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Split Overpass nodes into (stations, entrances) in EPSG:4326."""
    cfg = cfg or Config()
    records = [
        _record(e, cfg)
        for e in elements
        if e.get("type") == "node" and "lat" in e and e["lon"] <= cfg.max_lon
    ]
    frame = _promote_brt_stations(gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326"))
    frame = _merge_close_platforms(frame, cfg)
    stations = frame[frame["railway"].isin(STATION_RAILWAY)].reset_index(drop=True)
    entrances = frame[frame["railway"].isin(ENTRANCE_RAILWAY)].reset_index(drop=True)
    return stations, entrances


def _entrance_origins(matched: gpd.GeoDataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "osm_id": matched["osm_id_ent"],
            "name": matched["name_ent"],
            "station_id": matched["osm_id_st"],
            "station_name": matched["name_st"],
            "mode": matched["mode_st"],
            "line": matched["line_st"],
            "operator": matched["operator_st"],
            "origin_kind": "entrance",
            "geometry": matched.geometry,
        }
    )


def _station_origins(lone: gpd.GeoDataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "osm_id": lone["osm_id"],
            "name": lone["name"],
            "station_id": lone["osm_id"],
            "station_name": lone["name"],
            "mode": lone["mode"],
            "line": lone["line"],
            "operator": lone["operator"],
            "origin_kind": "station",
            "geometry": lone.geometry,
        }
    )


def build_origins(
    stations: gpd.GeoDataFrame, entrances: gpd.GeoDataFrame, cfg: Config
) -> gpd.GeoDataFrame:
    """One origin per matched entrance; lone stations are their own origin. Metric CRS out."""
    stations_m = stations.to_crs(cfg.crs_metric)
    entrances_m = entrances.to_crs(cfg.crs_metric)
    matched = gpd.sjoin_nearest(
        entrances_m,
        stations_m[["osm_id", "name", "mode", "line", "operator", "geometry"]],
        how="inner",
        max_distance=cfg.entrance_match_m,
        lsuffix="ent",
        rsuffix="st",
        distance_col="match_m",
    )
    covered = set(matched["osm_id_st"])
    lone = stations_m[~stations_m["osm_id"].isin(covered)]
    combined = pd.concat([_entrance_origins(matched), _station_origins(lone)], ignore_index=True)
    return gpd.GeoDataFrame(combined, geometry="geometry", crs=cfg.crs_metric)
