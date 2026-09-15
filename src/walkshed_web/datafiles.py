"""In-memory byte cache for the artifact files that Leaflet consumes directly.

Every file is read and gzipped once at startup. A request never touches the filesystem and
never joins user input to a path: the file name is a key into this cache.
"""

from __future__ import annotations

import gzip
import hashlib
import logging
from dataclasses import dataclass
from email.utils import formatdate
from pathlib import Path
from types import MappingProxyType
from typing import Final

from starlette.requests import Request

log = logging.getLogger(__name__)

MEDIA_TYPES: Final[dict[str, str]] = {
    "bands.geojson": "application/geo+json",
    "routes.geojson": "application/geo+json",
    "coverage.geojson": "application/geo+json",
    "provinces.geojson": "application/geo+json",
    "basemap.json": "application/json",
    "basemap_wide.jpg": "image/jpeg",
    "basemap_core.jpg": "image/jpeg",
}
ARTIFACT_FILES: Final[frozenset[str]] = frozenset(MEDIA_TYPES)
COMPRESSIBLE: Final[frozenset[str]] = frozenset(
    n for n, t in MEDIA_TYPES.items() if not t.startswith("image/")
)
GZIP_LEVEL = 6


@dataclass(frozen=True, slots=True)
class CachedFile:
    name: str
    media_type: str
    raw: bytes
    gzipped: bytes | None
    etag: str
    last_modified: str

    @property
    def raw_size(self) -> int:
        return len(self.raw)


def _cache_one(path: Path, gzip_min_bytes: int) -> CachedFile:
    raw = path.read_bytes()
    compress = path.name in COMPRESSIBLE and len(raw) >= gzip_min_bytes
    return CachedFile(
        name=path.name,
        media_type=MEDIA_TYPES[path.name],
        raw=raw,
        gzipped=gzip.compress(raw, GZIP_LEVEL) if compress else None,
        etag='"' + hashlib.sha256(raw).hexdigest()[:32] + '"',
        last_modified=formatdate(path.stat().st_mtime, usegmt=True),
    )


def build_cache(directory: Path, gzip_min_bytes: int) -> MappingProxyType[str, CachedFile]:
    """Read every known artifact file that exists. Missing files are logged, not fatal."""
    cache: dict[str, CachedFile] = {}
    for name in sorted(ARTIFACT_FILES):
        path = directory / name
        if not path.is_file():
            log.warning("artifact file missing: %s", name)
            continue
        cached = _cache_one(path, gzip_min_bytes)
        cache[name] = cached
        log.info(
            "cached %s raw=%d gzip=%s",
            name,
            cached.raw_size,
            len(cached.gzipped) if cached.gzipped else "-",
        )
    return MappingProxyType(cache)


def accepts_gzip(request: Request) -> bool:
    header = request.headers.get("accept-encoding", "")
    return any(token.strip().split(";")[0] == "gzip" for token in header.split(","))


def pick_payload(cached: CachedFile, request: Request) -> tuple[bytes, str | None]:
    """The body to send and its Content-Encoding, after negotiation."""
    if cached.gzipped is not None and accepts_gzip(request):
        return cached.gzipped, "gzip"
    return cached.raw, None


def etag_for(cached: CachedFile, encoding: str | None) -> str:
    """Each representation gets its own validator: the gzip body is not the identity body."""
    return cached.etag if not encoding else f'{cached.etag[:-1]}-{encoding}"'


def _strip_weak(tag: str) -> str:
    tag = tag.strip()
    return tag[2:] if tag.startswith("W/") else tag


def is_fresh(cached: CachedFile, request: Request, encoding: str | None = None) -> bool:
    """True when the client's validators match and a 304 is the right answer."""
    inm = request.headers.get("if-none-match")
    if inm:
        tags = {_strip_weak(t) for t in inm.split(",")}
        return etag_for(cached, encoding) in tags or "*" in tags
    ims = request.headers.get("if-modified-since")
    return bool(ims) and ims == cached.last_modified
