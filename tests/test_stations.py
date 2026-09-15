import json
from pathlib import Path

import pytest

from walkshed.config import Config
from walkshed.stations import build_origins, parse_elements

# Synthetic fixture with invented ids and names. Not OpenStreetMap data.
FIXTURE = Path(__file__).parent / "fixtures" / "overpass_small.json"


@pytest.fixture
def elements() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["elements"]


def test_parse_splits_stations_and_entrances(elements):
    stations, entrances = parse_elements(elements)
    assert len(stations) == 6
    assert len(entrances) == 4


def test_parse_assigns_mode_and_line(elements):
    stations, _ = parse_elements(elements)
    by_name = stations.set_index("name")
    assert by_name.loc["Taksim", "mode"] == "subway"
    assert by_name.loc["Taksim", "line"] == "M2"
    assert by_name.loc["Yenikapı", "mode"] == "train"
    assert by_name.loc["Yenikapı", "line"] == "Marmaray"
    assert by_name.loc["Kabataş", "mode"] == "tram"
    assert by_name.loc["Fun Stop", "mode"] == "funicular"
    assert by_name.loc["No mode station", "mode"] == "unknown"
    assert by_name.loc["No mode station", "line"] == "unknown"


def test_origins_use_entrances_when_present(elements):
    stations, entrances = parse_elements(elements)
    origins = build_origins(stations, entrances, Config())
    taksim = origins[origins["station_name"] == "Taksim"]
    assert len(taksim) == 2
    assert set(taksim["origin_kind"]) == {"entrance"}


def test_origins_fall_back_to_station_node(elements):
    stations, entrances = parse_elements(elements)
    origins = build_origins(stations, entrances, Config())
    yenikapi = origins[origins["station_name"] == "Yenikapı"]
    assert len(yenikapi) == 1
    assert yenikapi.iloc[0]["origin_kind"] == "station"


def test_orphan_entrance_is_dropped(elements):
    stations, entrances = parse_elements(elements)
    origins = build_origins(stations, entrances, Config())
    assert "Orphan entrance" not in set(origins["name"])
    assert len(origins) == 7
    assert origins.crs.to_string() == Config().crs_metric


def test_operator_marmaray_is_national(elements):
    stations, _ = parse_elements(elements)
    by_name = stations.set_index("name")
    assert by_name.loc["Yenikapı", "operator"] == "TCDD Taşımacılık"
    assert by_name.loc["Taksim", "operator"] == "Metro İstanbul"
    assert by_name.loc["Kabataş", "operator"] == "Metro İstanbul"


def test_brt_stop_dedupes_by_name(elements):
    stations, entrances = parse_elements(elements)
    brt = stations[stations["mode"] == "brt"]
    assert len(brt) == 1
    assert brt.iloc[0]["line"] == "Metrobüs"
    assert brt.iloc[0]["operator"] == "İETT"
    origins = build_origins(stations, entrances, Config())
    assert len(origins[origins["station_name"] == "Zincirlikuyu"]) == 1


def test_stations_east_of_max_lon_are_dropped(elements):
    far_east = [
        {
            "type": "node",
            "id": 99,
            "lat": 40.76,
            "lon": 29.93,
            "tags": {"railway": "tram_stop", "name": "Otogar"},
        }
    ]
    stations, _ = parse_elements(elements + far_east, Config())
    assert "Otogar" not in set(stations["name"])
