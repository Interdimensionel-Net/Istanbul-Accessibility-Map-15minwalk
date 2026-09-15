import geopandas as gpd
from shapely.geometry import Point

from walkshed.validate import compare, compare_loose, normalize


def test_normalize_folds_turkish_and_punctuation():
    assert normalize("Ayrılık Çeşmesi") == "ayrilikcesmesi"
    assert normalize("Kadıköy - İSKİ") == normalize("Kadikoy ISKI")


def test_compare_reports_missing():
    reference = [{"line": "M2", "operator": "x", "stations": ["Taksim", "Osmanbey", "Ghost"]}]
    stations = gpd.GeoDataFrame(
        {"name": ["Taksim", "Osmanbey Meydanı"]},
        geometry=[Point(0, 0), Point(1, 1)],
        crs="EPSG:4326",
    )
    strict = compare(reference, stations)["M2"]
    loose = compare_loose(reference, stations)["M2"]
    assert strict["matched"] == 1
    assert strict["missing_in_osm"] == ["Osmanbey", "Ghost"]
    assert loose["matched"] == 2
    assert loose["missing_in_osm"] == ["Ghost"]


def test_provenance_has_no_absolute_paths():
    from walkshed.config import Config
    from walkshed.pipeline import provenance

    config = provenance(Config(), False, False, False)["config"]
    for key, value in config.items():
        if isinstance(value, str):
            assert ":\\" not in value and not value.startswith("/"), (key, value)
    assert config["cache_dir"] == "data/cache"
