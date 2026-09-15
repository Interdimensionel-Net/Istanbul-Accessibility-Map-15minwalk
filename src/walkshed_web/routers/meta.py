from typing import Annotated

from fastapi import APIRouter, Depends, Request

from walkshed_web.artifact import Artifact, artifact_from_app
from walkshed_web.envelope import ok
from walkshed_web.indexes import Indexes, indexes_from_app
from walkshed_web.models import BasemapOut, CountsOut, MetaOut

router = APIRouter(prefix="/api", tags=["meta"])
ATTRIBUTION = "© OpenStreetMap contributors, ODbL"


def _basemap(artifact: Artifact) -> BasemapOut | None:
    if artifact.basemap is None:
        return None
    layers = tuple(
        {**layer, "file": f"/data/{layer['file']}"}
        for layer in artifact.basemap.get("layers", [])
        if isinstance(layer, dict) and layer.get("file") in artifact.files
    )
    return BasemapOut(attribution=str(artifact.basemap.get("attribution", "")), layers=layers)


@router.get("/meta")
def meta(
    request: Request,
    artifact: Annotated[Artifact, Depends(artifact_from_app)],
    indexes: Annotated[Indexes, Depends(indexes_from_app)],
) -> dict:
    doc = artifact.meta
    expose = request.app.state.settings.expose_provenance
    return ok(
        MetaOut(
            bands=doc.bands,
            walk_speed_kmh=doc.walk_speed_kmh,
            total_km2=doc.total_km2,
            band_km2=doc.band_km2,
            counts=CountsOut(
                stations=len(doc.stations),
                covered=sum(1 for s in doc.stations if s.covered),
                lines=len(doc.lines),
                routes=artifact.route_count,
            ),
            operators=tuple(sorted(indexes.operators)),
            modes=tuple(sorted(indexes.modes)),
            generated_at=artifact.generated_at,
            reference_hash=artifact.reference_hash,
            attribution=ATTRIBUTION,
            basemap=_basemap(artifact),
            provenance=doc.provenance if expose else None,
        )
    )
