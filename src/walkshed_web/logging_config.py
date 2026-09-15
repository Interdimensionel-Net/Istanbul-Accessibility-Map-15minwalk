"""Structured JSON logging and the per-request access log line."""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from walkshed_web.limiter import client_hash

access_log = logging.getLogger("walkshed_web.access")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            line.update(extra)
        if record.exc_info:
            line["exc"] = self.formatException(record.exc_info)
        return json.dumps(line, ensure_ascii=False)


class StderrHandler(logging.StreamHandler):
    """Writes to whatever sys.stderr is at emit time, so a replaced stream is never stale."""

    @property
    def stream(self):  # type: ignore[override]
        return sys.stderr

    @stream.setter
    def stream(self, value) -> None:
        pass


def configure_logging(level: str) -> None:
    """Install one JSON handler on the root logger. Safe to call more than once."""
    root = logging.getLogger()
    if not any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        handler = StderrHandler()
        handler.setFormatter(JsonFormatter())
        root.handlers = [handler]
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True


class RequestLogMiddleware:
    """One JSON line per request: id, method, path, status, duration, hashed client.

    The query string is never logged, so search terms never land in the log.
    """

    def __init__(self, app: ASGIApp, trust_forwarded_for: bool = False) -> None:
        self.app = app
        self.trust_forwarded_for = trust_forwarded_for

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        status = {"code": 0}

        async def send_tracking(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_tracking)
        finally:
            access_log.info(
                "request",
                extra={
                    "fields": {
                        "request_id": request_id,
                        "method": scope.get("method"),
                        "path": scope.get("path"),
                        "status": status["code"],
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                        "client_hash": client_hash(scope, self.trust_forwarded_for),
                    }
                },
            )
