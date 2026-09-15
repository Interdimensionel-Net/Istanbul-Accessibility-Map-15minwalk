# Contributing

1. Install: `uv sync`.
2. Format and lint: `uv run ruff format . && uv run ruff check .`
3. Test: `uv run pytest`. Tests must not touch the network. Use fixtures under `tests/fixtures/`.
4. Open a pull request against `main`. CI runs the three commands above.

Station list changes go in `data/reference/lines.json`, with the source named in the
pull request. Never commit `data/cache/`, `output/`, or the Metro İstanbul PDF.
