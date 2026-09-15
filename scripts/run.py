"""Thin wrapper. Prefer `uv run walkshed`; this keeps `python scripts/run.py` working."""

from walkshed.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
