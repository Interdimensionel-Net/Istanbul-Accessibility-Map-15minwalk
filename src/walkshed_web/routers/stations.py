from typing import Annotated

from fastapi import APIRouter, Depends, Query

from walkshed_web.artifact import Artifact, artifact_from_app
from walkshed_web.envelope import ok, page_meta
from walkshed_web.errors import ApiError
from walkshed_web.indexes import Indexes, indexes_from_app
from walkshed_web.models import BandOut, LineRefOut, StationDetailOut, StationDoc, StationOut
from walkshed_web.queries import SidPath, StationQuery

router = APIRouter(prefix="/api/stations", tags=["stations"])
ArtifactDep = Annotated[Artifact, Depends(artifact_from_app)]
IndexesDep = Annotated[Indexes, Depends(indexes_from_app)]


def station_out(station: StationDoc) -> StationOut:
    return StationOut(
        sid=station.sid,
        name=station.name,
        lines=station.codes,
        mode=station.mode,
        operator=station.operator,
        lon=station.lon,
        lat=station.lat,
        km2=station.km2,
        covered=station.covered,
    )


def _matches(station: StationDoc, query: StationQuery) -> bool:
    return (
        (query.line is None or query.line in station.codes)
        and (query.operator is None or station.operator == query.operator)
        and (query.mode is None or station.mode == query.mode)
        and (query.covered is None or station.covered == query.covered)
    )


@router.get("")
def list_stations(
    query: Annotated[StationQuery, Query()], artifact: ArtifactDep, indexes: IndexesDep
) -> dict:
    if not indexes.filters_are_known(query.operator, query.mode):
        raise ApiError(422)
    matched = [s for s in artifact.meta.stations if _matches(s, query)]
    page = matched[query.offset : query.offset + query.limit]
    return ok([station_out(s) for s in page], page_meta(len(matched), query.offset, query.limit))


def _bands(artifact: Artifact, sid: int) -> tuple[BandOut, ...]:
    features = artifact.bands_by_sid.get(sid, ())
    rows = sorted(
        (
            (int(f["properties"]["band"]), float(f["properties"].get("km2", 0.0)))
            for f in features
            if "band" in f.get("properties", {})
        ),
        key=lambda r: r[0],
    )
    return tuple(BandOut(band=b, minutes=b // 60, km2=k) for b, k in rows)


@router.get("/{sid}")
def get_station(sid: SidPath, artifact: ArtifactDep, indexes: IndexesDep) -> dict:
    station = indexes.by_sid.get(sid)
    if station is None:
        raise ApiError(404, "Station not found.")
    bands = _bands(artifact, sid)
    base = station_out(station)
    return ok(
        StationDetailOut(
            **base.model_dump(),
            line_names=tuple(LineRefOut(code=c, name=indexes.line_name(c)) for c in station.codes),
            bands=bands,
            widest=bands[-1] if bands else None,
        )
    )


@router.get("/{sid}/bands")
def get_station_bands(sid: SidPath, artifact: ArtifactDep, indexes: IndexesDep) -> dict:
    if sid not in indexes.by_sid:
        raise ApiError(404, "Station not found.")
    features = list(artifact.bands_by_sid.get(sid, ()))
    return ok({"type": "FeatureCollection", "features": features})
