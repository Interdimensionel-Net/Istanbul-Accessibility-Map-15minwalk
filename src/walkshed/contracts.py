"""Column checks at the boundaries between pipeline stages."""

from __future__ import annotations

import pandas as pd

STATIONS = ("osm_id", "name", "mode", "line", "operator", "geometry")
ENTRANCES = ("osm_id", "name", "geometry")
ORIGINS = (
    "osm_id",
    "name",
    "station_id",
    "station_name",
    "mode",
    "line",
    "operator",
    "origin_kind",
    "geometry",
)
ISOCHRONES = ORIGINS + ("graph_node", "band_s")


def require_columns(frame: pd.DataFrame, columns: tuple[str, ...], stage: str) -> pd.DataFrame:
    """Raise a clear error naming the stage when a required column is missing."""
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise ValueError(f"{stage}: missing columns {missing}. Present: {list(frame.columns)}")
    return frame
