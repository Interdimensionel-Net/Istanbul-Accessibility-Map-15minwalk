"""Token-bucket rate limiting, in process, keyed by a hashed client address."""

from __future__ import annotations

import hashlib
import secrets
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from walkshed_web.envelope import fail

MAX_KEYS = 20_000
_SALT = secrets.token_bytes(16)


@dataclass(frozen=True, slots=True)
class Decision:
    allowed: bool
    retry_after: int


@dataclass(frozen=True, slots=True)
class Bucket:
    """Requests per minute and burst size for one route family."""

    name: str
    per_minute: int
    burst: int


class RateLimiter:
    """One bucket per key. `check` refills by elapsed time and spends one token."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._state: OrderedDict[str, tuple[float, float]] = OrderedDict()

    def check(self, key: str, bucket: Bucket) -> Decision:
        now = self._clock()
        rate = bucket.per_minute / 60.0
        tokens, last = self._state.get(key, (float(bucket.burst), now))
        tokens = min(float(bucket.burst), tokens + (now - last) * rate)
        if tokens >= 1.0:
            self._store(key, tokens - 1.0, now)
            return Decision(True, 0)
        self._store(key, tokens, now)
        return Decision(False, max(1, int((1.0 - tokens) / rate + 0.999)))

    def _store(self, key: str, tokens: float, now: float) -> None:
        self._state[key] = (tokens, now)
        self._state.move_to_end(key)
        while len(self._state) > MAX_KEYS:
            self._state.popitem(last=False)


def client_hash(scope: Scope) -> str:
    """Stable, salted, non-reversible id for the client address. Never log the raw address."""
    client = scope.get("client")
    host = client[0] if client else "unknown"
    return hashlib.sha256(_SALT + host.encode("utf-8")).hexdigest()[:12]


def bucket_for(path: str, buckets: tuple[tuple[str, Bucket], ...], default: Bucket) -> Bucket:
    for prefix, bucket in buckets:
        if path.startswith(prefix):
            return bucket
    return default


class RateLimitMiddleware:
    """Pure ASGI middleware. Rejects with 429 and Retry-After when a bucket is empty."""

    def __init__(
        self,
        app: ASGIApp,
        limiter: RateLimiter,
        buckets: tuple[tuple[str, Bucket], ...],
        default: Bucket,
    ) -> None:
        self.app = app
        self.limiter = limiter
        self.buckets = buckets
        self.default = default

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        bucket = bucket_for(scope["path"], self.buckets, self.default)
        decision = self.limiter.check(f"{bucket.name}:{client_hash(scope)}", bucket)
        if decision.allowed:
            await self.app(scope, receive, send)
            return
        response: Response = fail(
            "Too many requests.", 429, {"Retry-After": str(decision.retry_after)}
        )
        await response(scope, receive, send)


def limiter_from_app(request: Request) -> RateLimiter:
    return request.app.state.limiter
