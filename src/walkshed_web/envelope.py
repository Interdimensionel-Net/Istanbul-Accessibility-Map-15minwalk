"""The {success, data, error, meta} response envelope."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict


class Meta(BaseModel):
    model_config = ConfigDict(frozen=True)
    total: int | None = None
    page: int | None = None
    limit: int | None = None


def _dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list | tuple):
        return [_dump(v) for v in value]
    return value


def ok(data: Any, meta: Meta | None = None) -> dict[str, Any]:
    return {
        "success": True,
        "data": _dump(data),
        "error": None,
        "meta": meta.model_dump() if meta else None,
    }


def fail(message: str, status: int, headers: dict[str, str] | None = None) -> JSONResponse:
    body = {"success": False, "data": None, "error": message, "meta": None}
    return JSONResponse(body, status_code=status, headers=headers)


def page_meta(total: int, offset: int, limit: int) -> Meta:
    return Meta(total=total, page=offset // limit + 1, limit=limit)
