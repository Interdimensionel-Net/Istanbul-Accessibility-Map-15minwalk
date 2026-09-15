"""`uv run walkshed-web`: serve the precomputed artifact."""

from __future__ import annotations

import argparse
import os
import sys

from walkshed_web.settings import DEFAULT_ARTIFACT_DIR


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="walkshed-web", description="Serve the precomputed walkshed map over HTTP."
    )
    parser.add_argument("--host", default=None, help="Bind address (default 127.0.0.1).")
    parser.add_argument("--port", type=int, default=None, help="Port (default 8000).")
    parser.add_argument(
        "--artifact-dir", default=None, help=f"Artifact folder (default {DEFAULT_ARTIFACT_DIR})."
    )
    parser.add_argument("--log-level", default=None, choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--reload", action="store_true", help="Development auto-reload.")
    return parser


def apply_env(args: argparse.Namespace) -> None:
    """Command-line flags become WALKSHED_WEB_ variables so settings see one source."""
    for flag, key in (
        ("host", "WALKSHED_WEB_HOST"),
        ("port", "WALKSHED_WEB_PORT"),
        ("artifact_dir", "WALKSHED_WEB_ARTIFACT_DIR"),
        ("log_level", "WALKSHED_WEB_LOG_LEVEL"),
    ):
        value = getattr(args, flag)
        if value is not None:
            os.environ[key] = str(value)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    apply_env(args)

    import uvicorn

    from walkshed_web.artifact import ArtifactError, load_artifact
    from walkshed_web.logging_config import configure_logging
    from walkshed_web.settings import get_settings

    get_settings.cache_clear()
    cfg = get_settings()
    configure_logging(cfg.log_level)
    try:
        load_artifact(cfg.artifact_dir, cfg.gzip_min_bytes)
    except ArtifactError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    uvicorn.run(
        "walkshed_web.app:create_app",
        factory=True,
        host=cfg.host,
        port=cfg.port,
        reload=args.reload,
        log_config=None,
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
