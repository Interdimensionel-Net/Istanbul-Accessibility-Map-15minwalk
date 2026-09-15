"""Immutable lookups built once from the artifact."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from starlette.requests import Request

from walkshed_web.models import LineDoc, MetaDoc, StationDoc


@dataclass(frozen=True, slots=True)
class Indexes:
    by_sid: Mapping[int, StationDoc]
    by_code: Mapping[str, LineDoc]
    stations_by_code: Mapping[str, tuple[StationDoc, ...]]
    operators: frozenset[str]
    modes: frozenset[str]

    def line_name(self, code: str) -> str:
        line = self.by_code.get(code)
        return line.name if line else code


def build_indexes(meta: MetaDoc) -> Indexes:
    stations_by_code: dict[str, list[StationDoc]] = {}
    for station in meta.stations:
        for code in station.codes:
            stations_by_code.setdefault(code, []).append(station)
    return Indexes(
        by_sid=MappingProxyType({s.sid: s for s in meta.stations}),
        by_code=MappingProxyType({line.line: line for line in meta.lines}),
        stations_by_code=MappingProxyType({c: tuple(v) for c, v in stations_by_code.items()}),
        operators=frozenset(s.operator for s in meta.stations)
        | frozenset(line.operator for line in meta.lines),
        modes=frozenset(s.mode for s in meta.stations) | frozenset(line.mode for line in meta.lines),
    )


def indexes_from_app(request: Request) -> Indexes:
    """FastAPI dependency: the indexes built in the lifespan."""
    return request.app.state.indexes
