"""Bounded, allowlisted query models. Nothing unvalidated reaches a handler."""

from __future__ import annotations

from typing import Annotated

from fastapi import Path, Query
from pydantic import BaseModel, ConfigDict, Field

CODE_PATTERN = r"^[A-Za-z0-9]{1,8}$"
NAME_PATTERN = r"^[^\x00-\x1f]{0,80}$"
HASH_PATTERN = r"^[0-9a-f]{1,32}$"
MODE_PATTERN = r"^[a-z_]{1,24}$"

SidPath = Annotated[int, Path(ge=1, le=2**63 - 1)]
CodePath = Annotated[str, Path(pattern=CODE_PATTERN)]
VersionQuery = Annotated[str | None, Query(pattern=HASH_PATTERN)]


class StationQuery(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    line: str | None = Field(default=None, pattern=CODE_PATTERN)
    operator: str | None = Field(default=None, min_length=1, max_length=40)
    mode: str | None = Field(default=None, pattern=MODE_PATTERN)
    covered: bool | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0, le=100_000)


class LineQuery(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    operator: str | None = Field(default=None, min_length=1, max_length=40)
    mode: str | None = Field(default=None, pattern=MODE_PATTERN)
    include_stops: bool = False
    include_coords: bool = False


class SearchQuery(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    q: str = Field(min_length=1, max_length=80, pattern=NAME_PATTERN)
    limit: int = Field(default=7, ge=1, le=25)
