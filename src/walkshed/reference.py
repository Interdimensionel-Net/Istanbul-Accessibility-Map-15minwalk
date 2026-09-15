"""Match OSM stations to the official per-line reference list."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd

from walkshed.names import MIN_LOOSE_KEY, line_stations, load_lines, normalize

log = logging.getLogger(__name__)

LINE_SEP = "/"
COMPATIBLE_MODES = {
    "brt": {"brt"},
    "tram": {"tram", "heritage_tram"},
    "subway": {"subway"},
    "train": {"suburban_rail", "subway", "tram"},  # T6 runs on TCDD track
    "light_rail": {"funicular", "subway", "tram"},
    "funicular": {"funicular", "heritage_funicular"},
    "cable_car": {"cable_car"},
}


def load_aliases(path: Path) -> dict[str, str]:
    """Normalized OSM name -> reference name, from an optional aliases.json next to lines.json."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))["osm_name_to_reference"]
    return {normalize(k): v for k, v in raw.items()}


def load_id_overrides(path: Path) -> dict[int, str]:
    """OSM node id -> reference name: stations whose OSM name is shared by another station, plus
    the extra nodes the Overpass query fetches by id (see load_extra_node_ids)."""
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    raw = {**doc.get("extra_osm_node_ids", {}), **doc.get("osm_id_to_reference", {})}
    return {int(k): v for k, v in raw.items()}


def load_extra_node_ids(path: Path) -> tuple[int, ...]:
    """OSM node ids the station query must fetch explicitly because their tags miss the
    generic filters, for example Metrobüs platforms tagged network=İETT."""
    if not path.exists():
        return ()
    raw = json.loads(path.read_text(encoding="utf-8")).get("extra_osm_node_ids", {})
    return tuple(sorted(int(k) for k in raw))


def apply_id_overrides(stations: gpd.GeoDataFrame, overrides: dict[int, str]) -> gpd.GeoDataFrame:
    """Rename stations by OSM id before name matching."""
    if not overrides:
        return stations
    renamed = stations["osm_id"].map(overrides)
    return stations.assign(name=renamed.fillna(stations["name"]))


def station_index(lines: list[dict]) -> dict[str, list[dict]]:
    """Normalized station name -> list of {line, operator, mode} for operating lines."""
    index: dict[str, list[dict]] = {}
    for line in lines:
        if line.get("status", "operating") != "operating":
            continue
        entry = {"line": line["line"], "operator": line["operator"], "mode": line["mode"]}
        for station in line_stations(line):
            index.setdefault(normalize(station), []).append(entry)
    return index


def _prefer_compatible(entries: list[dict], osm_mode: str, strict: bool = False) -> list[dict]:
    """Entries whose mode fits the OSM mode. strict=True: no compatible entry, no match."""
    allowed = COMPATIBLE_MODES.get(osm_mode)
    if not allowed:
        return entries
    compatible = [e for e in entries if e["mode"] in allowed]
    return compatible if (compatible or strict) else entries


def _lookup(
    name: str, osm_mode: str, index: dict[str, list[dict]], aliases: dict[str, str]
) -> list[dict]:
    key = normalize(aliases.get(normalize(name), name))
    if key in index:
        return _prefer_compatible(index[key], osm_mode, strict=True)
    if len(key) < MIN_LOOSE_KEY:
        return []
    loose = [
        entries
        for k, entries in index.items()
        if len(k) >= MIN_LOOSE_KEY and (k in key or key in k)
    ]
    return _prefer_compatible(loose[0], osm_mode, strict=True) if len(loose) == 1 else []


def enrich(
    stations: gpd.GeoDataFrame, index: dict[str, list[dict]], aliases: dict[str, str] | None = None
) -> gpd.GeoDataFrame:
    """Replace line/operator/mode from the reference where matched; flag in_reference."""
    aliases = aliases or {}
    hits = [
        _lookup(n, m, index, aliases)
        for n, m in zip(stations["name"], stations["mode"], strict=True)
    ]
    matched = pd.Series([bool(h) for h in hits], index=stations.index)
    ref_lines = pd.Series(
        [LINE_SEP.join(sorted({e["line"] for e in h})) for h in hits], index=stations.index
    )
    ref_operator = pd.Series([h[0]["operator"] if h else None for h in hits], index=stations.index)
    ref_mode = pd.Series([h[0]["mode"] if h else None for h in hits], index=stations.index)
    return stations.assign(
        osm_mode=stations["mode"],
        in_reference=matched,
        line=ref_lines.where(matched, stations["line"]),
        operator=ref_operator.where(matched, stations["operator"]),
        mode=ref_mode.where(matched, stations["mode"]),
    )


def apply_reference(stations: gpd.GeoDataFrame, path: Path, require: bool) -> gpd.GeoDataFrame:
    """Enrich from the reference file; drop unmatched stations when `require` is set."""
    if not path.exists():
        log.warning("Reference file %s missing. Keeping OSM tags.", path)
        return stations.assign(in_reference=False)
    alias_file = path.with_name("aliases.json")
    aliases = load_aliases(alias_file)
    stations = apply_id_overrides(stations, load_id_overrides(alias_file))
    enriched = enrich(stations, station_index(load_lines(path)), aliases)
    unmatched = enriched[~enriched["in_reference"]]
    if len(unmatched):
        log.info("%d OSM stations not in reference: %s", len(unmatched), sorted(unmatched["name"]))
    if require:
        return enriched[enriched["in_reference"]].reset_index(drop=True)
    return enriched
