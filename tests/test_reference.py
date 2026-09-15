import geopandas as gpd
from shapely.geometry import Point

from walkshed.reference import enrich, station_index

LINES = [
    {
        "line": "34",
        "mode": "brt",
        "operator": "İETT",
        "status": "operating",
        "stations": ["Taksim"],
    },
    {
        "line": "F3",
        "mode": "funicular",
        "operator": "Metro İstanbul",
        "status": "operating",
        "stations": ["Vadistanbul"],
    },
    {
        "line": "M2",
        "mode": "subway",
        "operator": "Metro İstanbul",
        "status": "operating",
        "stations": ["Yenikapı", "Taksim"],
        "branches": [{"from": "x", "stations": ["Seyrantepe"]}],
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


def _stations(names):
    return gpd.GeoDataFrame(
        {
            "name": names,
            "line": ["osm"] * len(names),
            "operator": ["osm"] * len(names),
            "mode": ["osm"] * len(names),
        },
        geometry=[Point(i, i) for i in range(len(names))],
        crs="EPSG:4326",
    )


def test_index_includes_branches_and_skips_construction():
    index = station_index(LINES)
    assert "seyrantepe" in index
    assert "ghost" not in index


def test_enrich_joins_lines_and_sets_operator():
    enriched = enrich(
        _stations(["Yenikapı", "Gebze", "Kabakça", "Taksim Meydanı"]), station_index(LINES)
    )
    by = enriched.set_index("name")
    assert by.loc["Yenikapı", "line"] == "B1/M2"
    assert by.loc["Gebze", "operator"] == "TCDD Taşımacılık"
    assert by.loc["Gebze", "mode"] == "suburban_rail"
    assert not by.loc["Kabakça", "in_reference"]
    assert by.loc["Kabakça", "line"] == "osm"
    assert by.loc["Taksim Meydanı", "line"] == "34/M2"


def test_enrich_prefers_compatible_mode_and_aliases():
    stations = _stations(["Taksim", "Vadi İstanbul"]).assign(mode=["brt", "light_rail"])
    enriched = enrich(stations, station_index(LINES), {"vadiistanbul": "Vadistanbul"})
    by = enriched.set_index("name")
    assert by.loc["Taksim", "line"] == "34"
    assert by.loc["Taksim", "mode"] == "brt"
    assert by.loc["Vadi İstanbul", "line"] == "F3"
