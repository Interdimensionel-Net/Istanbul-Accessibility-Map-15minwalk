"""The HTML shell, with the per-request CSP nonce stamped in."""

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from walkshed_web.security import NONCE_KEY

router = APIRouter(tags=["pages"])
INDEX_PATH = Path(__file__).resolve().parents[1] / "static" / "index.html"
NONCE_PLACEHOLDER = "{{CSP_NONCE}}"


@lru_cache
def _template() -> str:
    return INDEX_PATH.read_text(encoding="utf-8")


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request) -> HTMLResponse:
    nonce = request.scope.get("state", {}).get(NONCE_KEY, "")
    page = _template().replace(NONCE_PLACEHOLDER, nonce)
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})
