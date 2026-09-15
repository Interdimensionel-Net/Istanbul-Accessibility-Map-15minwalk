"""Turkish-aware station name search."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable

from walkshed_web.models import StationDoc

_TURKISH = str.maketrans({"ı": "i", "İ": "i", "I": "i"})


def normalize_tr(text: str) -> str:
    """Lowercase ASCII-ish key: dotted and dotless i fold to i, diacritics are stripped."""
    folded = text.translate(_TURKISH).lower()
    decomposed = unicodedata.normalize("NFD", folded)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).strip()


def rank_stations(stations: Iterable[StationDoc], query: str, limit: int) -> tuple[StationDoc, ...]:
    """Prefix matches first, then substring matches, in input order. Empty query -> nothing."""
    key = normalize_tr(query)
    if not key:
        return ()
    starts: list[StationDoc] = []
    within: list[StationDoc] = []
    for station in stations:
        name = normalize_tr(station.name)
        if name.startswith(key):
            starts.append(station)
        elif key in name:
            within.append(station)
    return tuple((starts + within)[:limit])
