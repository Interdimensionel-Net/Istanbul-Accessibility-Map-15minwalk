"""Offline end-to-end run: fixture stations, a synthetic walk graph, temporary dirs."""

import json
import shutil
from pathlib import Path

import networkx as nx
import pytest

from walkshed import pipeline
from walkshed.config import Config
from walkshed.isochrone import add_travel_time

FIXTURES = Path(__file__).parent / "fixtures"

LINES = {
    "source": "synthetic test data",
    "lines": [
        {
            "line": "M2",
            "name": "Test Metro",
            "mode": "subway",
            "operator": "Metro İstanbul",
            "status": "operating",
            "stations": ["Taksim", "No mode station"],
        },
        {
            "line": "B1",
            "name": "Test Rail",
            "mode": "suburban_rail",
            "operator": "TCDD Taşımacılık",
            "status": "operating",
            "stations": ["Yenikapı"],
        },
        {
            "line": "T1",
            "name": "Test Tram",
            "mode": "tram",
            "operator": "Metro İstanbul",
            "status": "operating",
            "stations": ["Kabataş"],
        },
        {
            "line": "F1",
            "name": "Test Funicular",
            "mode": "funicular",
            "operator": "Metro İstanbul",
            "status": "operating",
            "stations": ["Fun Stop"],
        },
        {
            "line": "34",
            "name": "Test BRT",
            "mode": "brt",
            "operator": "İETT",
            "status": "operating",
            "stations": ["Zincirlikuyu"],
        },
    ],
}


def _grid_graph(origins_m, cfg: Config) -> nx.MultiDiGraph:
    """A 100 m lattice of streets around every origin, integer node ids, metric CRS."""
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = cfg.crs_metric
    step, span = 100.0, 6
    ids: dict[tuple[float, float], int] = {}

    def node(x: float, y: float) -> int:
        key = (x, y)
        if key not in ids:
            ids[key] = len(ids)
            graph.add_node(ids[key], x=x, y=y)
        return ids[key]

    for x0, y0 in zip(origins_m.geometry.x, origins_m.geometry.y, strict=True):
        bx, by = int(x0 // 1000) * 1000, int(y0 // 1000) * 1000
        for i in range(-span, span + 1):
            for j in range(-span, span + 1):
                a = node(bx + i * step, by + j * step)
                for di, dj in ((1, 0), (0, 1)):
                    b = node(bx + (i + di) * step, by + (j + dj) * step)
                    graph.add_edge(a, b, length=step)
                    graph.add_edge(b, a, length=step)
    return add_travel_time(graph, cfg)


@pytest.fixture
def cfg(tmp_path, monkeypatch) -> Config:
    ref_dir = tmp_path / "reference"
    ref_dir.mkdir()
    (ref_dir / "lines.json").write_text(json.dumps(LINES, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(Config, "reference_path", property(lambda self: ref_dir / "lines.json"))
    cfg = Config(cache_dir=tmp_path / "cache", output_dir=tmp_path / "output", max_snap_m=2000.0)
    cfg.cache_dir.mkdir()
    return cfg


def test_run_offline_writes_every_output(cfg, monkeypatch):
    from walkshed.overpass import cache_path

    shutil.copyfile(FIXTURES / "overpass_small.json", cache_path(cfg))
    monkeypatch.setattr(
        pipeline, "load_or_build_graph", lambda origins, c, refresh=False: _grid_graph(origins, c)
    )
    monkeypatch.setattr(pipeline, "_graph_cache_exists", lambda origins, c: False)

    summary = pipeline.run(cfg)

    assert summary["station_count"] == 6
    assert summary["total_km2"] > 0
    prov = summary["provenance"]
    assert prov["overpass_from_cache"] is True
    assert prov["graph_from_cache"] is False
    assert len(prov["overpass_query_hash"]) == 12 and len(prov["reference_hash"]) == 12
    assert "osmnx" in prov["packages"]
    for name in ("stations.geojson", "isochrones.geojson", "coverage.geojson", "summary.json"):
        assert (cfg.output_dir / name).exists(), name
    assert cfg.map_html.exists()
    for name in ("bands.geojson", "coverage.geojson", "meta.json"):
        assert (cfg.artifact_dir / name).exists(), name
    meta = json.loads((cfg.artifact_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["bands"] == [900]
    assert meta["provenance"]["overpass_query_hash"] == prov["overpass_query_hash"]
    assert {s["sid"] for s in meta["stations"] if s["covered"]} == {1, 4, 5, 6, 8, 20}
