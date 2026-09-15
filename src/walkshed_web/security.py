"""Security headers and the per-request CSP nonce."""

from __future__ import annotations

import secrets
from collections.abc import Iterable

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

NONCE_KEY = "csp_nonce"


def csp_for(nonce: str, tile_hosts: Iterable[str]) -> str:
    """Minimal policy. Leaflet writes inline `style` attributes on panes and tiles, so
    `style-src` keeps 'unsafe-inline'; scripts are nonce-bound and served from this origin only.
    """
    img_hosts = " ".join(tile_hosts)
    return "; ".join(
        [
            "default-src 'none'",
            f"script-src 'self' 'nonce-{nonce}'",
            "style-src 'self' 'unsafe-inline'",
            f"img-src 'self' data: blob: {img_hosts}".rstrip(),
            "font-src 'self'",
            "connect-src 'self'",
            "manifest-src 'self'",
            "base-uri 'none'",
            "form-action 'none'",
            "frame-ancestors 'none'",
            "object-src 'none'",
        ]
    )


class SecurityHeadersMiddleware:
    """Pure ASGI middleware so the headers also land on 404s, 429s, and static files."""

    def __init__(self, app: ASGIApp, tile_hosts: Iterable[str], enable_hsts: bool) -> None:
        self.app = app
        self.tile_hosts = tuple(tile_hosts)
        self.enable_hsts = enable_hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        nonce = secrets.token_urlsafe(16)
        scope.setdefault("state", {})[NONCE_KEY] = nonce
        secure = scope.get("scheme") == "https" or _forwarded_https(scope)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Content-Security-Policy"] = csp_for(nonce, self.tile_hosts)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Permissions-Policy"] = "geolocation=(self), microphone=(), camera=()"
                headers["Cross-Origin-Opener-Policy"] = "same-origin"
                headers["Cross-Origin-Resource-Policy"] = "same-origin"
                if self.enable_hsts and secure:
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _forwarded_https(scope: Scope) -> bool:
    for name, value in scope.get("headers", []):
        if name == b"x-forwarded-proto":
            return value.decode("latin-1").split(",")[0].strip() == "https"
    return False
