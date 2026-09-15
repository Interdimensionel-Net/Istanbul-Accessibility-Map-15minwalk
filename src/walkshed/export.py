"""Compact data files for the interactive map artifact."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import geopandas as gpd
from shapely.geometry import mapping

from walkshed.config import Config
from walkshed.names import MIN_LOOSE_KEY, line_stations, load_lines, normalize
from walkshed.reference import COMPATIBLE_MODES, load_aliases
from walkshed.routes import write_routes

log = logging.getLogger(__name__)
M2_PER_KM2 = 1_000_000


def _round_geometry(geometry, decimals: int) -> dict:
    """GeoJSON mapping with rounded coordinates."""
    raw = mapping(geometry)

    def rnd(coords):
        if isinstance(coords[0], (int, float)):
            return [round(coords[0], decimals), round(coords[1], decimals)]
        return [rnd(c) for c in coords]

    return {"type": raw["type"], "coordinates": rnd(raw["coordinates"])}


def station_bands(
    isochrones_m: gpd.GeoDataFrame, cfg: Config, simplify_m: float
) -> gpd.GeoDataFrame:
    """Union the origin polygons of each station per band, simplified, in the metric CRS."""
    keys = ["station_id", "station_name", "line", "mode", "operator", "band_s"]
    merged = isochrones_m.dissolve(by=keys, as_index=False)[keys + ["geometry"]]
    return merged.assign(
        geometry=merged.geometry.simplify(simplify_m, preserve_topology=True),
        km2=merged.geometry.area / M2_PER_KM2,
    )


def _station_lookup(
    stations: gpd.GeoDataFrame, aliases: dict[str, str]
) -> dict[str, list[tuple[int, float, float, str]]]:
    """Normalized reference name -> every matching (osm_id, lon, lat, osm_mode)."""
    lookup: dict[str, list[tuple[int, float, float, str]]] = {}
    modes = stations["osm_mode"] if "osm_mode" in stations else stations["mode"]
    for osm_id, name, mode, geom in zip(
        stations["osm_id"], stations["name"], modes, stations.geometry, strict=True
    ):
        key = normalize(aliases.get(normalize(name), name))
        lookup.setdefault(key, []).append((int(osm_id), geom.x, geom.y, str(mode)))
    return lookup


def _candidates(name: str, lookup: dict, official: set[str]) -> list[tuple[int, float, float, str]]:
    """Exact key first; else a unique loose match that is not itself another official name."""
    key = normalize(name)
    if key in lookup:
        return lookup[key]
    if len(key) < MIN_LOOSE_KEY:
        return []
    loose = [
        v
        for k, v in lookup.items()
        if len(k) >= MIN_LOOSE_KEY and (k in key or key in k) and k not in official
    ]
    return loose[0] if len(loose) == 1 else []


def _pick(
    candidates: list[tuple[int, float, float, str]], line_mode: str, anchor: tuple | None
) -> tuple[int, float, float, str] | None:
    """Prefer a mode-compatible node; among several, the one nearest the previous stop."""
    if not candidates:
        return None
    fitting = [c for c in candidates if line_mode in COMPATIBLE_MODES.get(c[3], {line_mode})]
    pool = fitting or candidates
    if anchor is None or len(pool) == 1:
        return pool[0]
    return min(pool, key=lambda c: (c[1] - anchor[1]) ** 2 + (c[2] - anchor[2]) ** 2)


def _resolve_stops(line: dict, lookup: dict, official: set[str]) -> list[tuple[str, tuple | None]]:
    """(stop name, chosen node) for every stop on the line, in order, chaining by proximity."""
    found: list[tuple[str, tuple | None]] = []
    anchor = None
    for stop in line_stations(line):
        hit = _pick(_candidates(stop, lookup, official - {normalize(stop)}), line["mode"], anchor)
        found.append((stop, hit))
        anchor = hit or anchor
    return found


def _operating(lines: list[dict]) -> list[dict]:
    return [line for line in lines if line.get("status", "operating") == "operating"]


def line_paths(
    stations: gpd.GeoDataFrame, lines: list[dict], aliases: dict[str, str] | None = None
) -> list[dict]:
    """Per operating line: station-to-station polyline and the ordered station list with ids."""
    lookup = _station_lookup(stations, aliases or {})
    official = {normalize(s) for line in lines for s in line_stations(line)}
    paths = []
    for line in _operating(lines):
        found = _resolve_stops(line, lookup, official)
        matched = [hit for _, hit in found if hit]
        if len(matched) < 2:
            continue
        paths.append(
            {
                "line": line["line"],
                "name": line["name"],
                "mode": line["mode"],
                "operator": line["operator"],
                "coords": [[round(x, 5), round(y, 5)] for _, x, y, _ in matched],
                "stations": [{"name": s, "sid": hit[0] if hit else None} for s, hit in found],
            }
        )
    return paths


def resolve_lines(
    stations: gpd.GeoDataFrame, lines: list[dict], aliases: dict[str, str] | None = None
) -> gpd.GeoDataFrame:
    """Authoritative per-node line labels from the chained stop matching.

    Each node keeps only the lines whose ordered stop list picked it; nodes no line picked are
    dropped. This removes duplicate nodes at shared stations and same-name stations elsewhere.
    """
    info = {line["line"]: line for line in lines}
    lookup = _station_lookup(stations, aliases or {})
    official = {normalize(s) for line in lines for s in line_stations(line)}
    picked: dict[int, list[str]] = {}
    for line in _operating(lines):
        for _, hit in _resolve_stops(line, lookup, official):
            if hit is not None:
                picked.setdefault(hit[0], []).append(line["line"])
    kept = stations[stations["osm_id"].isin(picked)].copy()
    codes = kept["osm_id"].map(lambda i: sorted(set(picked[int(i)])))
    return kept.assign(
        line=codes.map("/".join),
        operator=codes.map(lambda c: info[c[0]]["operator"]),
        mode=codes.map(lambda c: info[c[0]]["mode"]),
    )


def write_artifact_data(
    stations: gpd.GeoDataFrame,
    isochrones_m: gpd.GeoDataFrame,
    coverage_m: gpd.GeoDataFrame,
    cfg: Config,
    out_dir: Path,
    simplify_m: float = 8.0,
    decimals: int = 5,
    provenance: dict | None = None,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    shipped = isochrones_m[isochrones_m["band_s"].isin(cfg.web_bands)]
    bands_m = station_bands(shipped, cfg, simplify_m)
    bands = bands_m.to_crs(cfg.crs_geo)
    features = [
        {
            "type": "Feature",
            "properties": {
                "sid": int(r.station_id),
                "band": int(r.band_s),
                "km2": round(float(r.km2), 3),
            },
            "geometry": _round_geometry(r.geometry, decimals),
        }
        for r in bands.itertuples()
    ]
    (out_dir / "bands.geojson").write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": features},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    widest = bands_m[bands_m["band_s"] == bands_m["band_s"].max()].set_index("station_id")["km2"]
    covered = set(bands_m["station_id"])
    station_rows = [
        {
            "sid": int(r.osm_id),
            "name": r.name,
            "line": r.line,
            "mode": r.mode,
            "operator": r.operator,
            "lon": round(r.geometry.x, 5),
            "lat": round(r.geometry.y, 5),
            "km2": round(float(widest.get(r.osm_id, 0.0)), 3),
            "covered": r.osm_id in covered,
        }
        for r in stations.to_crs(cfg.crs_geo).itertuples()
    ]
    coverage = (
        coverage_m.to_crs(cfg.crs_geo).geometry.simplify(0.0001, preserve_topology=True).iloc[0]
    )
    (out_dir / "coverage.geojson").write_text(
        json.dumps(
            {"type": "Feature", "properties": {}, "geometry": _round_geometry(coverage, decimals)},
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    lines = load_lines(cfg.reference_path)
    try:
        route_count = write_routes(cfg, out_dir, lines)
    except Exception as error:  # noqa: BLE001 - the web map falls back to station paths
        route_count = 0
        log.warning("Route geometry unavailable (%s); station paths will be used.", error)
    meta = {
        "stations": station_rows,
        "lines": line_paths(
            stations, lines, load_aliases(cfg.reference_path.with_name("aliases.json"))
        ),
        "routes": route_count,
        "bands": sorted(int(b) for b in bands_m["band_s"].unique()),
        "walk_speed_kmh": cfg.walk_speed_kmh,
        "total_km2": round(float(coverage_m.geometry.area.sum()) / M2_PER_KM2, 1),
        "provenance": provenance or {},
        "band_km2": {
            int(b): round(float(g.geometry.union_all().area) / M2_PER_KM2, 1)
            for b, g in bands_m.groupby("band_s")
        },
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    return meta
