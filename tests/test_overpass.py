from walkshed.config import Config
from walkshed.overpass import build_query


def test_query_emits_coordinates():
    query = build_query(Config())
    assert query.strip().endswith("out body;")
    assert 'area["name"="İstanbul"]' in query
    assert 'area["name"="Kocaeli"]' in query
    assert '"aerialway"="station"' in query
