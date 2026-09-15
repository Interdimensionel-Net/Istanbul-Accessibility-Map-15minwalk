"""Exception handlers. Every error reaches the client as a generic envelope, never a detail."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from walkshed_web.envelope import fail

log = logging.getLogger(__name__)

GENERIC = {
    400: "Bad request.",
    404: "Not found.",
    405: "Method not allowed.",
    422: "Invalid request parameters.",
    429: "Too many requests.",
    500: "Internal error.",
}


class ApiError(Exception):
    """An error whose public message is safe to show."""

    def __init__(self, status: int, public_message: str | None = None) -> None:
        super().__init__(public_message or GENERIC.get(status, "Request failed."))
        self.status = status
        self.public_message = public_message or GENERIC.get(status, "Request failed.")


async def _api_error(_: Request, exc: Exception) -> Response:
    assert isinstance(exc, ApiError)
    return fail(exc.public_message, exc.status)


async def _validation(request: Request, exc: Exception) -> Response:
    log.info("validation failed on %s", request.scope.get("path", "?"))
    return fail(GENERIC[422], 422)


async def _http(_: Request, exc: Exception) -> Response:
    assert isinstance(exc, HTTPException)
    headers = dict(exc.headers or {})
    return fail(GENERIC.get(exc.status_code, "Request failed."), exc.status_code, headers)


async def _unhandled(request: Request, exc: Exception) -> Response:
    log.exception("unhandled error on %s", request.scope.get("path", "?"))
    return fail(GENERIC[500], 500)


def install_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(RequestValidationError, _validation)
    app.add_exception_handler(HTTPException, _http)
    app.add_exception_handler(Exception, _unhandled)
