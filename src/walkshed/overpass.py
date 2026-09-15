"""Fetch rail stations, stops, and entrances from Overpass with a disk cache."""

from __future__ import annotations

import json
import logging
import random
import time
from pathlib import Path

import requests

from walkshed.config import Config
from walkshed.names import content_hash
from walkshed.reference import load_extra_node_ids

log = logging.getLogger(__name__)

RETRY_STATUSES = {429, 502, 503, 504}
REQUEST_TIMEOUT_S = 180


def _area_clause(cfg: Config) -> str:
    names = (cfg.area_name, *cfg.extra_area_names)
    parts = "".join(f'area["name"="{n}"]["admin_level"="{cfg.area_admin_level}"];' for n in names)
    return f"({parts})->.a;"


def _extra_ids_clause(cfg: Config) -> str:
    ids = load_extra_node_ids(cfg.reference_path.with_name("aliases.json"))
    if not ids:
        return ""
    joined = ",".join(str(i) for i in ids)
    return f"  node(id:{joined});\n"


def build_query(cfg: Config) -> str:
    return f"""[out:json][timeout:120];
{_area_clause(cfg)}
(
{_extra_ids_clause(cfg)}  node(area.a)["railway"="station"];
  node(area.a)["railway"="tram_stop"];
  node(area.a)["railway"="subway_entrance"];
  node(area.a)["railway"="train_station_entrance"];
  node(area.a)["aerialway"="station"];
  node(area.a)["network"~"{cfg.brt_network_regex}",i]["bus"="yes"];
);
out body;"""


def _validated_elements(payload: dict, cfg: Config) -> list[dict]:
    elements = payload.get("elements")
    if not elements:
        raise RuntimeError(
            f"Overpass returned no elements for area {cfg.area_name!r}, "
            f"admin_level {cfg.area_admin_level}. Check the area name."
        )
    if not any("lat" in e for e in elements):
        raise RuntimeError("Overpass elements carry no coordinates. Check the out mode.")
    return elements


def query_hash(cfg: Config) -> str:
    """Hash of the exact Overpass query text. Names the cache file and goes into provenance."""
    return content_hash(build_query(cfg))


def cache_path(cfg: Config) -> Path:
    return cfg.cache_dir / f"overpass_{query_hash(cfg)}.json"


def _read_cache(cfg: Config) -> list[dict] | None:
    cache = cache_path(cfg)
    if not cache.exists():
        return None
    try:
        payload = json.loads(cache.read_text(encoding="utf-8"))
        elements = _validated_elements(payload, cfg)
    except (json.JSONDecodeError, RuntimeError, OSError) as error:
        log.warning("Overpass cache unusable (%s). Refetching.", error)
        return None
    log.info("Overpass cache hit: %s", cache)
    return elements


def fetch_elements(cfg: Config, refresh: bool = False) -> list[dict]:
    """Return Overpass elements, from cache when present and valid."""
    if not refresh:
        cached = _read_cache(cfg)
        if cached is not None:
            return cached
    payload = _request_with_retry(cfg)
    elements = _validated_elements(payload, cfg)
    cache = cache_path(cfg)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return elements


def _request_with_retry(cfg: Config) -> dict:
    query = build_query(cfg)
    headers = {"User-Agent": cfg.user_agent}
    last_error: Exception | None = None
    for attempt in range(cfg.overpass_retries):
        try:
            response = requests.post(
                cfg.overpass_url,
                data={"data": query},
                headers=headers,
                timeout=REQUEST_TIMEOUT_S,
            )
            if response.status_code in RETRY_STATUSES:
                raise requests.HTTPError(f"Overpass returned {response.status_code}")
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            last_error = error
            if attempt == cfg.overpass_retries - 1:
                break
            wait = 2 ** (attempt + 1) + random.uniform(0, 1)
            log.warning("Overpass attempt %d failed: %s. Retry in %.0fs", attempt + 1, error, wait)
            time.sleep(wait)
    raise RuntimeError(f"Overpass failed after {cfg.overpass_retries} attempts: {last_error}")
