"""Station name normalization and reference loading, shared by matching and validation."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

TURKISH_MAP = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
SEPARATORS = re.compile(r"[\s\-–—/().,']+")
MIN_LOOSE_KEY = 4


def normalize(name: str) -> str:
    """Lowercase ASCII key that survives Turkish letters and punctuation differences."""
    folded = name.translate(TURKISH_MAP)
    ascii_only = unicodedata.normalize("NFKD", folded).encode("ascii", "ignore").decode()
    return SEPARATORS.sub("", ascii_only).lower()


def load_lines(path: Path) -> list[dict]:
    """The `lines` array of a reference file such as data/reference/lines.json."""
    return json.loads(path.read_text(encoding="utf-8"))["lines"]


def line_stations(line: dict) -> list[str]:
    """Every station on a line: the main list plus any branch lists."""
    branches = line.get("branches") or []
    return list(line["stations"]) + [s for b in branches for s in b.get("stations", [])]


def content_hash(text: str, length: int = 12) -> str:
    """Short, stable SHA-256 prefix of a string. Used for cache names and provenance."""
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]
