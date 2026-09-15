import geopandas as gpd
from shapely.geometry import Point

from walkshed.export import resolve_lines

LINES = [
    {
        "line": "M2",
        "mode": "subway",
        "operator": "Metro İstanbul",
        "status": "operating",
        "stations": ["Yenikapı", "Taksim", "Levent"],
    },
    {
        "line": "M6",
        "mode": "subway",
        "operator": "Metro İstanbul",
        "status": "operating",
        "stations": ["Levent", "Etiler"],
    },
    {
        "line": "B1",
        "mode": "suburban_rail",
        "operator": "TCDD Taşımacılık",
        "status": "operating",
        "stations": ["Yenikapı", "Gebze"],
    },
    {
        "line": "M12",
        "mode": "subway",
        "operator": "Metro İstanbul",
        "status": "under_construction",
        "stations": ["Ghost"],
    },
]


def _stations(rows):
    """rows: (osm_id, name, osm_mode, x, y)."""
    return gpd.GeoDataFrame(
        {
            "osm_id": [r[0] for r in rows],
            "name": [r[1] for r in rows],
            "osm_mode": [r[2] for r in rows],
            "line": ["osm"] * len(rows),
            "operator": ["osm"] * len(rows),
            "mode": ["osm"] * len(rows),
        },
        geometry=[Point(r[3], r[4]) for r in rows],
        crs="EPSG:4326",
    )


def test_shared_station_gets_every_line_that_picked_it():
    stations = _stations(
        [
            (1, "Yenikapı", "subway", 0, 0),
            (2, "Taksim", "subway", 0, 1),
            (3, "Levent", "subway", 0, 2),
            (4, "Etiler", "subway", 0, 3),
            (5, "Gebze", "suburban_rail", 5, 0),
        ]
    )
    out = resolve_lines(stations, LINES).set_index("osm_id")
    assert out.loc[1, "line"] == "B1/M2"
    assert out.loc[1, "operator"] == "TCDD Taşımacılık"
    assert out.loc[3, "line"] == "M2/M6"
    assert out.loc[5, "line"] == "B1"
    assert out.loc[5, "mode"] == "suburban_rail"


def test_unpicked_and_construction_nodes_are_dropped():
    stations = _stations(
        [
            (1, "Yenikapı", "subway", 0, 0),
            (2, "Taksim", "subway", 0, 1),
            (3, "Levent", "subway", 0, 2),
            (9, "Ghost", "subway", 9, 9),
            (10, "Nowhere", "subway", 8, 8),
        ]
    )
    out = resolve_lines(stations, LINES)
    assert sorted(out["osm_id"]) == [1, 2, 3]


def test_duplicate_name_resolves_to_node_nearest_previous_stop():
    stations = _stations(
        [
            (1, "Yenikapı", "subway", 0, 0),
            (2, "Taksim", "subway", 0, 1),
            (3, "Levent", "subway", 0, 2),
            (30, "Levent", "subway", 50, 50),
        ]
    )
    out = resolve_lines(stations, LINES)
    assert 3 in set(out["osm_id"])
    assert 30 not in set(out["osm_id"])


def test_alias_maps_osm_spelling_to_reference_name():
    stations = _stations(
        [
            (1, "Yenikapi Istasyonu", "subway", 0, 0),
            (2, "Taksim", "subway", 0, 1),
            (3, "Levent", "subway", 0, 2),
        ]
    )
    aliases = {"yenikapiistasyonu": "Yenikapı"}
    out = resolve_lines(stations, LINES, aliases).set_index("osm_id")
    assert out.loc[1, "line"] == "B1/M2"


def test_input_frame_is_not_mutated():
    stations = _stations([(1, "Yenikapı", "subway", 0, 0), (2, "Taksim", "subway", 0, 1)])
    before = stations.copy()
    resolve_lines(stations, LINES)
    assert stations.equals(before)
