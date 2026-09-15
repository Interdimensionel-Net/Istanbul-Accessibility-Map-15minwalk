# Changelog

## Unreleased

- Per-node line labels from chained stop matching (`resolve_lines`). Each station node
  keeps only the lines whose ordered stop list picked it; duplicate nodes at shared
  stations and unpicked same-name nodes are dropped. Used by the pipeline and
  `scripts/render_map.py`.

## [0.1.0] - 2026-09-15

- First release: Overpass station fetch, reference-list matching, osmnx walk graph,
  5/10/15-minute isochrones, coverage summary, Folium map, offline graph build.
- Web map with official line names and colours, OSM route geometry, per-line stop
  lists, static basemap sheets, and run provenance in every summary.
