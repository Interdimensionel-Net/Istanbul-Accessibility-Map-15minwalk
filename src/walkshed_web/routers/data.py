"""Raw artifact files for Leaflet. The name is a cache key, never a path."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from walkshed_web.artifact import Artifact, artifact_from_app
from walkshed_web.datafiles import etag_for, is_fresh, pick_payload
from walkshed_web.errors import ApiError
from walkshed_web.queries import FileNamePath, VersionQuery

router = APIRouter(prefix="/data", tags=["data"])
SHORT_CACHE = "public, max-age=300, must-revalidate"
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"


@router.get("/{name}")
def data_file(
    name: FileNamePath,
    request: Request,
    artifact: Annotated[Artifact, Depends(artifact_from_app)],
    v: VersionQuery = None,
) -> Response:
    cached = artifact.files.get(name)
    if cached is None:
        raise ApiError(404, "Not available.")
    versioned = v is not None and v == artifact.reference_hash
    body, encoding = pick_payload(cached, request)
    headers = {
        "ETag": etag_for(cached, encoding),
        "Last-Modified": cached.last_modified,
        "Cache-Control": IMMUTABLE_CACHE if versioned else SHORT_CACHE,
        "Vary": "Accept-Encoding",
    }
    if is_fresh(cached, request, encoding):
        return Response(status_code=304, headers=headers)
    if encoding:
        headers["Content-Encoding"] = encoding
    return Response(content=body, media_type=cached.media_type, headers=headers)
