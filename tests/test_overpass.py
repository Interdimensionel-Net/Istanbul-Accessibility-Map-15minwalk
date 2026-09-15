from pathlib import Path

from walkshed.config import Config
from walkshed.overpass import build_query


def test_query_emits_coordinates():
    query = build_query(Config())
    assert query.strip().endswith("out body;")
    assert 'area["name"="İstanbul"]' in query
    assert 'area["name"="Kocaeli"]' in query
    assert '"aerialway"="station"' in query


def test_query_fetches_extra_node_ids(tmp_path: Path, monkeypatch):
    (tmp_path / "lines.json").write_text('{"lines": []}', encoding="utf-8")
    (tmp_path / "aliases.json").write_text(
        '{"osm_name_to_reference": {}, "extra_osm_node_ids": {"42": "A", "7": "B"}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(Config, "reference_path", property(lambda self: tmp_path / "lines.json"))
    assert "node(id:7,42);" in build_query(Config())


def test_query_without_extra_ids_has_no_id_clause(tmp_path: Path, monkeypatch):
    (tmp_path / "lines.json").write_text('{"lines": []}', encoding="utf-8")
    monkeypatch.setattr(Config, "reference_path", property(lambda self: tmp_path / "lines.json"))
    assert "node(id:" not in build_query(Config())
