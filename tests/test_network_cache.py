import geopandas as gpd
from shapely.geometry import Point

from walkshed.config import Config
from walkshed.network import corridor_polygon, graph_cache_path


def _origins(points):
    return gpd.GeoDataFrame(
        {"osm_id": range(len(points))}, geometry=[Point(*p) for p in points], crs="EPSG:5254"
    )


def test_cache_key_follows_corridor_shape():
    cfg = Config()
    a = graph_cache_path(corridor_polygon(_origins([(500000, 4540000)]), cfg), cfg)
    b = graph_cache_path(
        corridor_polygon(_origins([(500000, 4540000), (520000, 4540000)]), cfg), cfg
    )
    same = graph_cache_path(corridor_polygon(_origins([(500000, 4540000)]), cfg), cfg)
    assert a != b
    assert a == same
