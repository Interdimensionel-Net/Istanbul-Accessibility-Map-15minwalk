# Changelog

## Unreleased

- Phone layout on both pages: a hamburger opens the line list, basemap, theme and
  about text as a left drawer over a scrim; a slim status pill replaces the stats
  strip; the station and route sheets start at 40% and 48% of the screen and drag
  up from a grip. Deep links `#menu`, `#station/<sid>` and `#route/<code>`.
- Route panel: stop names are buttons. A click keeps the line's walksheds, outlines the
  picked stop in the focus colour and zooms to it; a second click zooms back to the line.
  Deep link `#route/<code>/<sid>`.
- FastAPI web app (`uv run walkshed-web`) that serves the precomputed artifact:
  enveloped JSON API, validated query parameters, per-route rate limits, security
  headers with a nonce-bound CSP, gzip and ETag on data files, JSON logs. Vanilla
  ES6 front end on the five-variable theme contract with 16 presets, vendored
  Leaflet, toast, modal, and keyboard support. 72 tests, 99% coverage.
- Per-node line labels from chained stop matching (`resolve_lines`). Each station node
  keeps only the lines whose ordered stop list picked it; duplicate nodes at shared
  stations and unpicked same-name nodes are dropped. Used by the pipeline and
  `scripts/render_map.py`.

## [0.1.0] - 2026-09-15

- First release: Overpass station fetch, reference-list matching, osmnx walk graph,
  5/10/15-minute isochrones, coverage summary, Folium map, offline graph build.
- Web map with official line names and colours, OSM route geometry, per-line stop
  lists, static basemap sheets, and run provenance in every summary.
