# Istanbul 15-minute rail walkshed

Isochrone map of every area within a 15-minute walk of an Istanbul rapid transit
station: metro, Marmaray, suburban rail, tram, funicular, cable car, and the
Metrobüs BRT. Routing runs on the OpenStreetMap pedestrian network with osmnx.
No API key is needed.

Operators are kept apart: Metro İstanbul (İBB), TCDD Taşımacılık (Marmaray B1,
B2, M11, T6), and İETT (Metrobüs, T2, F2).

## Requirements

Python 3.13, [uv](https://docs.astral.sh/uv/), about 500 MB of disk for
`data/cache/`, and access to an Overpass API server. No API key.

## Run

```
uv sync
uv run pytest
uv run walkshed
```

Open `output/istanbul_15min_walkshed.html`.

The first run downloads the walk network (10 to 20 minutes) and caches it in
`data/cache/`. Cache files are named by a hash of their inputs: the Overpass
query text for stations, the corridor shape for the graph. A change to the
query or to the station set produces a new file; stale caches are never reused.
`output/summary.json` and `output/artifact/meta.json` carry a `provenance`
block with input hashes, retrieval time, package versions, and the effective
configuration.

| Flag | Effect |
|---|---|
| `--refresh` | Ignore the caches and refetch stations and network. |
| `--offline` | Rebuild the walk graph from Overpass responses already in `data/cache/osmnx/`. No network request. Use it after a partial download or when Overpass is down. |
| `--overpass-url URL` | Overpass base URL for the network download, for example `https://overpass.kumi.systems/api`. |
| `--verbose` | Show osmnx request logging. |

## Known issues

- The public Overpass server returns HTTP 504 or drops connections when busy.
  The station query retries four times with back-off. The network download
  resumes from the osmnx cache on the next run.
- The first run takes 10 to 20 minutes for the download and about 10 minutes
  for 800 origins.
- OSM entrance coverage is uneven. A station without a mapped entrance uses
  its station node as the origin.
- The reference list is a July 2026 snapshot. Lines that open or close later
  need an edit to `data/reference/lines.json`.
- Walking speed is flat at 4.5 km/h. Slopes are not modelled.

## Outputs

| File | Content |
|---|---|
| `output/stations.geojson` | Station and stop points |
| `output/isochrones.geojson` | One polygon per entrance or station |
| `output/coverage.geojson` | Dissolved coverage |
| `output/summary.json` | Counts and km² per mode and line |
| `output/istanbul_15min_walkshed.html` | Interactive map |

## Reference data

`data/reference/lines.json` holds the official station list per line, taken from
the Metro İstanbul network map (v.3 rev.20.1, July 2026) and Wikipedia. It is the
authority for line membership, operator, and which stations are in service.
OSM stations that are not on the list (under construction, rural TCDD stops,
Kocaeli tram) are dropped. `data/reference/aliases.json` maps OSM spellings to
official names. `data/reference/route_relations.json` lists one OpenStreetMap
route relation per line; its track geometry draws the lines on the web map.
Run `uv run python scripts/validate_lines.py` after a pipeline run to see the
match report.

## Method

1. Overpass query for `railway=station`, `tram_stop`, `subway_entrance`,
   `aerialway=station`, and Metrobüs stops in İstanbul and Kocaeli provinces.
2. Each OSM station matches the reference list by normalized name. The reference
   supplies line, operator, and mode.
3. Entrances match their nearest station within 300 m. Stations with no entrance are origins.
4. Walk graph from osmnx, clipped to 1.5 km corridors around origins, projected to EPSG:5254 (TUREF TM30).
5. Per origin: `nx.ego_graph` with a 900 s cutoff at 4.5 km/h, then buffer edges (25 m)
   and nodes (50 m), union, fill holes.
6. Dissolve all polygons for total coverage.

All parameters live in `src/walkshed/config.py`.

## Web map

`web/index.html` is a standalone Leaflet page: pick lines, operators, and walk
times, search a station, and see the merged 5, 10 and 15 minute reach. It
loads the compact data the pipeline writes to `output/artifact/`.

```
uv run walkshed
uv run python scripts/build_web.py
```

`build_web.py` inlines the Leaflet stylesheet and writes the finished page and
its data files to `output/artifact/`. Host that folder on any static server or
a GitHub Pages branch. The page uses live OpenStreetMap tiles when it can reach
them. For hosts that block tile servers, `scripts/build_basemap.py` stitches
two static OpenStreetMap sheets (about 4 MB) that the page shows underneath;
without them it falls back to a drawn province outline.

### Publish on GitHub Pages

```
uv run python scripts/build_basemap.py   # once: static OSM sheets, about 4 MB
uv run python scripts/build_web.py
uv run python scripts/publish_docs.py    # copies the page and data into docs/
git add docs && git commit -m "docs: publish web map"
```

Enable Pages for the repository with source "GitHub Actions". The workflow in
`.github/workflows/pages.yml` deploys `docs/` on every push that changes it.
The hosted page uses live OpenStreetMap tiles, so the static sheets are only a
fallback there.

`scripts/render_map.py` rebuilds the Folium map in `output/` from saved results
without recomputing isochrones. `scripts/validate_lines.py` reports which
official stations have no OpenStreetMap match.

## License and attribution

The code is released under the MIT License. See `LICENSE`.

Station, entrance, and pedestrian network data come from OpenStreetMap,
© OpenStreetMap contributors, under the Open Database License (ODbL). Any
GeoJSON or GraphML this pipeline produces is a derivative database and is also
under ODbL. The rendered HTML map is a produced work and carries the credit.
Neither `output/` nor `data/cache/` is committed.

The station list in `data/reference/lines.json` was transcribed from the
Metro İstanbul network map (v.3 rev.20.1, July 2026) and Wikipedia line
articles (CC BY-SA). Station names and line membership are factual data.
Province outlines in `data/reference/provinces.geojson` come from OpenStreetMap
via Nominatim (ODbL).
