"""Load the pipeline artifact once and expose it as an immutable object."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from pydantic import ValidationError
from starlette.requests import Request

from walkshed_web.datafiles import CachedFile, build_cache
from walkshed_web.models import MetaDoc

log = logging.getLogger(__name__)

REQUIRED_FILES = ("meta.json", "bands.geojson")


class ArtifactError(RuntimeError):
    """The artifact directory is missing or unreadable."""


@dataclass(frozen=True, slots=True)
class Artifact:
    directory: Path
    meta: MetaDoc
    bands_by_sid: Mapping[int, tuple[dict[str, Any], ...]]
    route_count: int
    basemap: Mapping[str, Any] | None
    files: Mapping[str, CachedFile]

    @property
    def generated_at(self) -> str | None:
        return self.meta.provenance.run_at

    @property
    def reference_hash(self) -> str | None:
        return self.meta.provenance.reference_hash


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.error("cannot read %s: %s", path.name, exc)
        raise ArtifactError(f"cannot read {path.name}") from exc


def _group_bands(collection: Any) -> Mapping[int, tuple[dict[str, Any], ...]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for feature in collection.get("features", []):
        sid = feature.get("properties", {}).get("sid")
        if isinstance(sid, int):
            grouped.setdefault(sid, []).append(feature)
    return MappingProxyType({sid: tuple(fs) for sid, fs in grouped.items()})


def _optional_json(path: Path) -> Any | None:
    if not path.is_file():
        log.warning("optional artifact file missing: %s", path.name)
        return None
    return _read_json(path)


def load_artifact(directory: Path, gzip_min_bytes: int = 1024) -> Artifact:
    """Read and validate the artifact. Raise ArtifactError with a clear message on failure."""
    missing = [name for name in REQUIRED_FILES if not (directory / name).is_file()]
    if missing:
        raise ArtifactError(
            f"artifact directory {directory} lacks {', '.join(missing)}. Run `uv run walkshed`."
        )
    try:
        meta = MetaDoc.model_validate(_read_json(directory / "meta.json"))
    except ValidationError as exc:
        log.error("meta.json failed validation: %s", exc)
        raise ArtifactError("meta.json failed validation") from exc
    routes = _optional_json(directory / "routes.geojson")
    basemap = _optional_json(directory / "basemap.json")
    return Artifact(
        directory=directory,
        meta=meta,
        bands_by_sid=_group_bands(_read_json(directory / "bands.geojson")),
        route_count=len(routes.get("features", [])) if isinstance(routes, dict) else 0,
        basemap=MappingProxyType(basemap) if isinstance(basemap, dict) else None,
        files=build_cache(directory, gzip_min_bytes),
    )


def artifact_from_app(request: Request) -> Artifact:
    """FastAPI dependency: the artifact loaded in the lifespan."""
    return request.app.state.artifact
