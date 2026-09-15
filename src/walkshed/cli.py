"""Command line entry point, installed as `walkshed`."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace

from walkshed.config import DEFAULT_CONFIG
from walkshed.pipeline import run


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Istanbul 15-minute rail walkshed")
    parser.add_argument("--refresh", action="store_true", help="ignore caches and refetch")
    parser.add_argument(
        "--offline", action="store_true", help="build the graph from cached Overpass responses"
    )
    parser.add_argument("--verbose", action="store_true", help="show osmnx download logging")
    parser.add_argument("--overpass-url", default=None, help="Overpass base URL for osmnx")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the full pipeline. Returns a process exit code."""
    _utf8_console()
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    overrides = {"offline_graph": args.offline, "verbose": args.verbose}
    if args.overpass_url:
        overrides["osmnx_overpass_url"] = args.overpass_url
    try:
        summary = run(replace(DEFAULT_CONFIG, **overrides), refresh=args.refresh)
    except Exception:
        logging.getLogger("walkshed").exception("Pipeline failed")
        return 1
    print(f"Done. {summary['station_count']} stations, {summary['total_km2']:.1f} km2 covered.")
    return 0
