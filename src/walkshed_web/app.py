"""Application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from walkshed_web import __version__
from walkshed_web.artifact import load_artifact
from walkshed_web.errors import install_handlers
from walkshed_web.indexes import build_indexes
from walkshed_web.limiter import Bucket, RateLimiter, RateLimitMiddleware
from walkshed_web.logging_config import RequestLogMiddleware
from walkshed_web.routers import ALL_ROUTERS
from walkshed_web.security import SecurityHeadersMiddleware
from walkshed_web.settings import Settings, get_settings

log = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"


def rate_buckets(settings: Settings) -> tuple[tuple[str, Bucket], ...]:
    """Route-family buckets. Order matters: the first matching prefix wins."""
    base, burst = settings.rate_limit_per_minute, settings.rate_limit_burst
    return (
        ("/static/", Bucket("static", base * 5, burst * 10)),
        ("/api/search", Bucket("search", base * 2, burst * 2)),
        ("/api/health", Bucket("health", max(1, base // 2), burst)),
        ("/api/version", Bucket("health", max(1, base // 2), burst)),
        ("/api/", Bucket("read", base, burst)),
        ("/data/", Bucket("data", max(1, base // 4), burst)),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        artifact = load_artifact(cfg.artifact_dir, cfg.gzip_min_bytes)
        app.state.artifact = artifact
        app.state.indexes = build_indexes(artifact.meta)
        log.info("artifact loaded: %d stations", len(artifact.meta.stations))
        yield

    app = FastAPI(
        title="Istanbul 15-minute walkshed",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if cfg.enable_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if cfg.enable_docs else None,
    )
    app.state.settings = cfg
    app.state.limiter = RateLimiter()
    install_handlers(app)
    for router in ALL_ROUTERS:
        app.include_router(router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # Starlette wraps in reverse order: the last added middleware is the outermost.
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        RateLimitMiddleware,
        limiter=app.state.limiter,
        buckets=rate_buckets(cfg),
        default=Bucket("page", max(1, cfg.rate_limit_per_minute // 2), cfg.rate_limit_burst),
    )
    app.add_middleware(RequestLogMiddleware)
    app.add_middleware(
        SecurityHeadersMiddleware, tile_hosts=cfg.tile_hosts, enable_hsts=cfg.enable_hsts
    )
    return app
