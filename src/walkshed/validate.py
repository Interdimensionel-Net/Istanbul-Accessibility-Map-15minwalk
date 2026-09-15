"""Compare OSM station names against the official per-line reference list."""

from __future__ import annotations

import geopandas as gpd

from walkshed.names import MIN_LOOSE_KEY, line_stations, load_lines, normalize

load_reference = load_lines


def compare(reference: list[dict], stations: gpd.GeoDataFrame) -> dict:
    """Per line: official stations with and without an OSM name match."""
    osm_keys = {normalize(n) for n in stations["name"]}
    report = {}
    for line in reference:
        stations_on_line = line_stations(line)
        missing = [s for s in stations_on_line if normalize(s) not in osm_keys]
        report[line["line"]] = {
            "operator": line.get("operator", ""),
            "official": len(stations_on_line),
            "matched": len(stations_on_line) - len(missing),
            "missing_in_osm": missing,
        }
    return report


def _contains_match(name: str, osm_keys: set[str]) -> bool:
    key = normalize(name)
    if len(key) < MIN_LOOSE_KEY:
        return False
    return any(key in k or k in key for k in osm_keys)


def compare_loose(reference: list[dict], stations: gpd.GeoDataFrame) -> dict:
    """Same as compare, but a substring match counts. Catches 'Taksim' vs 'Taksim Meydanı'."""
    osm_keys = {normalize(n) for n in stations["name"]}
    report = {}
    for line in reference:
        stations_on_line = line_stations(line)
        missing = [s for s in stations_on_line if not _contains_match(s, osm_keys)]
        report[line["line"]] = {
            "official": len(stations_on_line),
            "matched": len(stations_on_line) - len(missing),
            "missing_in_osm": missing,
        }
    return report
