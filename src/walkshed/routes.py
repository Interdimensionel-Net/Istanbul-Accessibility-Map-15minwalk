"""Track geometry per line from OpenStreetMap route relations."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import requests

from walkshed.config import Config
from walkshed.names import content_hash

log = logging.getLogger(__name__)
REQUEST_TIMEOUT_S = 180


def load_relations(path: Path) -> dict[str, list[int]]:
    """Line code -> OSM relation ids, from data/reference/route_relations.json."""
    return json.loads(path.read_text(encoding="utf-8"))["relations"]


def build_query(relations: dict[str, list[int]]) -> str:
    ids = ",".join(str(int(i)) for codes in relations.values() for i in codes)
    return f"[out:json][timeout:120];relation(id:{ids});out geom;"


def cache_path(cfg: Config, query: str) -> Path:
    return cfg.cache_dir / f"routes_{content_hash(query)}.json"


def fetch_relations(cfg: Config, relations: dict[str, list[int]], refresh: bool = False) -> list:
    """Overpass relation elements with member geometry, cached by query hash."""
    query = build_query(relations)
    cache = cache_path(cfg, query)
    if cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))["elements"]
    response = requests.post(
        cfg.overpass_url,
        data={"data": query},
        headers={"User-Agent": cfg.user_agent},
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    payload = response.json()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload["elements"]


def _way_coords(member: dict, decimals: int) -> list[list[float]]:
    return [
        [round(p["lon"], decimals), round(p["lat"], decimals)] for p in member.get("geometry", [])
    ]


def routes_geojson(
    elements: list, relations: dict[str, list[int]], lines: list[dict], decimals: int = 5
) -> dict:
    """One MultiLineString feature per line code, from the way members of its relations."""
    by_id = {e["id"]: e for e in elements if e.get("type") == "relation"}
    info = {line["line"]: line for line in lines}
    features = []
    for code, ids in relations.items():
        parts = [
            _way_coords(m, decimals)
            for rid in ids
            for m in by_id.get(rid, {}).get("members", [])
            if m.get("type") == "way" and m.get("role", "") in ("", "forward", "backward")
        ]
        parts = [p for p in parts if len(p) >= 2]
        if not parts:
            log.warning("No track geometry for line %s (relations %s)", code, ids)
            continue
        line = info.get(code, {})
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "line": code,
                    "name": line.get("name", ""),
                    "operator": line.get("operator", ""),
                    "mode": line.get("mode", ""),
                },
                "geometry": {"type": "MultiLineString", "coordinates": parts},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def write_routes(cfg: Config, out_dir: Path, lines: list[dict], refresh: bool = False) -> int:
    """Write routes.geojson into out_dir. Returns the number of lines with geometry."""
    reference = cfg.reference_path.with_name("route_relations.json")
    if not reference.exists():
        log.warning("No route_relations.json; the web map falls back to station paths.")
        return 0
    relations = load_relations(reference)
    collection = routes_geojson(fetch_relations(cfg, relations, refresh), relations, lines)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "routes.geojson").write_text(
        json.dumps(collection, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    return len(collection["features"])
