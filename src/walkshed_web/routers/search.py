from typing import Annotated

from fastapi import APIRouter, Depends, Query

from walkshed_web.artifact import Artifact, artifact_from_app
from walkshed_web.envelope import Meta, ok
from walkshed_web.models import SearchHitOut
from walkshed_web.queries import SearchQuery
from walkshed_web.search import rank_stations

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def search(
    query: Annotated[SearchQuery, Query()],
    artifact: Annotated[Artifact, Depends(artifact_from_app)],
) -> dict:
    hits = rank_stations(artifact.meta.stations, query.q, query.limit)
    return ok(
        [
            SearchHitOut(
                sid=s.sid, name=s.name, lines=s.codes, operator=s.operator, lon=s.lon, lat=s.lat
            )
            for s in hits
        ],
        Meta(total=len(hits), page=1, limit=query.limit),
    )
