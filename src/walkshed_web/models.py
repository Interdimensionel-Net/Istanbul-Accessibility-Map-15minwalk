"""Frozen Pydantic models: the artifact document on the way in, API shapes on the way out."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

FROZEN = ConfigDict(frozen=True, extra="ignore")


class StationDoc(BaseModel):
    model_config = FROZEN
    sid: int
    name: str
    line: str
    mode: str
    operator: str
    lon: float
    lat: float
    km2: float = 0.0
    covered: bool = False

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(c for c in self.line.split("/") if c)


class LineStopDoc(BaseModel):
    model_config = FROZEN
    name: str
    sid: int | None = None


class LineDoc(BaseModel):
    model_config = FROZEN
    line: str
    name: str
    mode: str
    operator: str
    coords: tuple[tuple[float, float], ...] = ()
    stations: tuple[LineStopDoc, ...] = ()
    km2: float | None = None
    length_km: float | None = None


class ProvenanceDoc(BaseModel):
    model_config = FROZEN
    run_at: str | None = None
    reference_hash: str | None = None
    overpass_query_hash: str | None = None
    overpass_retrieved_at: str | None = None
    python: str | None = None
    packages: dict[str, str] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)


class MetaDoc(BaseModel):
    """The validated meta.json."""

    model_config = FROZEN
    stations: tuple[StationDoc, ...]
    lines: tuple[LineDoc, ...]
    bands: tuple[int, ...] = (900,)
    walk_speed_kmh: float = 4.5
    total_km2: float = 0.0
    band_km2: dict[str, float] = Field(default_factory=dict)
    provenance: ProvenanceDoc = Field(default_factory=ProvenanceDoc)


# --- API output shapes -------------------------------------------------------


class StationOut(BaseModel):
    model_config = FROZEN
    sid: int
    name: str
    lines: tuple[str, ...]
    mode: str
    operator: str
    lon: float
    lat: float
    km2: float
    covered: bool


class BandOut(BaseModel):
    model_config = FROZEN
    band: int
    minutes: int
    km2: float


class LineRefOut(BaseModel):
    model_config = FROZEN
    code: str
    name: str


class StationDetailOut(StationOut):
    line_names: tuple[LineRefOut, ...]
    bands: tuple[BandOut, ...]
    widest: BandOut | None


class LineStopOut(BaseModel):
    model_config = FROZEN
    name: str
    sid: int | None


class LineOut(BaseModel):
    model_config = FROZEN
    code: str
    name: str
    mode: str
    operator: str
    stop_count: int
    station_count: int
    has_route_geometry: bool
    km2: float | None = None
    length_km: float | None = None
    stops: tuple[LineStopOut, ...] | None = None
    coords: tuple[tuple[float, float], ...] | None = None


class SearchHitOut(BaseModel):
    model_config = FROZEN
    sid: int
    name: str
    lines: tuple[str, ...]
    operator: str
    lon: float
    lat: float


class CountsOut(BaseModel):
    model_config = FROZEN
    stations: int
    covered: int
    lines: int
    routes: int


class BasemapOut(BaseModel):
    model_config = FROZEN
    attribution: str = ""
    layers: tuple[dict[str, Any], ...] = ()


class MetaOut(BaseModel):
    model_config = FROZEN
    bands: tuple[int, ...]
    walk_speed_kmh: float
    total_km2: float
    band_km2: dict[str, float]
    counts: CountsOut
    operators: tuple[str, ...]
    modes: tuple[str, ...]
    generated_at: str | None
    reference_hash: str | None
    attribution: str
    basemap: BasemapOut | None
    provenance: ProvenanceDoc | None = None


class HealthOut(BaseModel):
    model_config = FROZEN
    status: str
    stations: int
    generated_at: str | None


class VersionOut(BaseModel):
    model_config = FROZEN
    version: str
    generated_at: str | None
    reference_hash: str | None
