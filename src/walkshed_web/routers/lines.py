from typing import Annotated

from fastapi import APIRouter, Depends, Query

from walkshed_web.artifact import Artifact, artifact_from_app
from walkshed_web.envelope import Meta, ok
from walkshed_web.errors import ApiError
from walkshed_web.indexes import Indexes, indexes_from_app
from walkshed_web.models import LineDoc, LineOut, LineStopOut
from walkshed_web.queries import CodePath, LineQuery

router = APIRouter(prefix="/api/lines", tags=["lines"])


def _line_out(line: LineDoc, indexes: Indexes, has_geometry: bool, query: LineQuery) -> LineOut:
    return LineOut(
        code=line.line,
        name=line.name,
        mode=line.mode,
        operator=line.operator,
        stop_count=len(line.stations),
        station_count=len(indexes.stations_by_code.get(line.line, ())),
        has_route_geometry=has_geometry,
        stops=tuple(LineStopOut(name=s.name, sid=s.sid) for s in line.stations)
        if query.include_stops
        else None,
        coords=line.coords if query.include_coords else None,
    )


def _check_filters(query: LineQuery, indexes: Indexes) -> None:
    if query.operator is not None and query.operator not in indexes.operators:
        raise ApiError(422)
    if query.mode is not None and query.mode not in indexes.modes:
        raise ApiError(422)


@router.get("")
def list_lines(
    query: Annotated[LineQuery, Query()],
    artifact: Annotated[Artifact, Depends(artifact_from_app)],
    indexes: Annotated[Indexes, Depends(indexes_from_app)],
) -> dict:
    _check_filters(query, indexes)
    has_geometry = artifact.route_count > 0
    lines = [
        _line_out(line, indexes, has_geometry, query)
        for line in artifact.meta.lines
        if (query.operator is None or line.operator == query.operator)
        and (query.mode is None or line.mode == query.mode)
    ]
    return ok(lines, Meta(total=len(lines), page=1, limit=len(lines) or 1))


@router.get("/{code}")
def get_line(
    code: CodePath,
    artifact: Annotated[Artifact, Depends(artifact_from_app)],
    indexes: Annotated[Indexes, Depends(indexes_from_app)],
) -> dict:
    line = indexes.by_code.get(code)
    if line is None:
        raise ApiError(404, "Line not found.")
    full = LineQuery(include_stops=True, include_coords=True)
    return ok(_line_out(line, indexes, artifact.route_count > 0, full))
