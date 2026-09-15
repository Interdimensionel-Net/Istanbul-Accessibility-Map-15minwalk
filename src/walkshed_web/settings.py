"""Runtime settings, read from the environment with the WALKSHED_WEB_ prefix."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_DIR = PROJECT_ROOT / "output" / "artifact"
DEFAULT_TILE_HOSTS: tuple[str, ...] = (
    "https://tile.openstreetmap.org",
    "https://*.tile.opentopomap.org",
    "https://server.arcgisonline.com",
)
TILE_HOST = re.compile(r"^https://[A-Za-z0-9.*-]+$")


class Settings(BaseSettings):
    """Every knob of the web app. Values are immutable after construction."""

    model_config = SettingsConfigDict(
        env_prefix="WALKSHED_WEB_", env_file=".env", extra="ignore", frozen=True
    )

    artifact_dir: Path = DEFAULT_ARTIFACT_DIR
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    rate_limit_per_minute: int = Field(default=120, ge=1, le=100_000)
    rate_limit_burst: int = Field(default=30, ge=1, le=10_000)
    enable_hsts: bool = True
    trust_forwarded_for: bool = False
    enable_docs: bool = False
    expose_provenance: bool = False
    tile_hosts: tuple[str, ...] = DEFAULT_TILE_HOSTS
    gzip_min_bytes: int = Field(default=1024, ge=0)

    @field_validator("tile_hosts")
    @classmethod
    def _hosts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        bad = [h for h in value if not TILE_HOST.match(h)]
        if bad:
            raise ValueError(f"tile host not allowed: {bad[0]!r}")
        return value

    @field_validator("artifact_dir", mode="before")
    @classmethod
    def _expand(cls, value: object) -> object:
        if isinstance(value, str | Path):
            return Path(value).expanduser().resolve()
        return value


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings. Tests clear the cache to inject overrides."""
    return Settings()
