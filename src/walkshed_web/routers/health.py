from typing import Annotated

from fastapi import APIRouter, Depends

from walkshed_web import __version__
from walkshed_web.artifact import Artifact, artifact_from_app
<br>from walkshed_web.envelope import ok
from walkshed_web.models import HealthOut, VersionOut

router = APIRouter(prefix="/api", tags=["health"])
ArtifactDep = Annotated[Artifact, Depends(artifact_from_app)]


@router.get("/health")
def health(artifact: ArtifactDep) -> dict:
    return ok(
        HealthOut(
            status="ok",
            stations=len(artifact.meta.stations),
            generated_at=artifact.generated_at,
        )
    )


@router.get("/version")
def version(artifact: ArtifactDep) -> dict:
    return ok(
        VersionOut(
            version=__version__,
            generated_at=artifact.generated_at,
            reference_hash=artifact.reference_hash,
        )
    )
