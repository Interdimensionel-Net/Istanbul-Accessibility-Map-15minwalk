import networkx as nx
import pytest
from shapely.geometry import Point

from walkshed.config import Config
from walkshed.isochrone import add_travel_time, reachable_bands, reachable_polygon


@pytest.fixture
def line_graph() -> nx.MultiDiGraph:
    """Five nodes in a straight line, 100 m apart, in a metric CRS."""
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:32635"
    for i in range(5):
        graph.add_node(i, x=float(i * 100), y=0.0)
    for i in range(4):
        graph.add_edge(i, i + 1, key=0, length=100.0)
        graph.add_edge(i + 1, i, key=0, length=100.0)
    return graph


def test_add_travel_time_is_pure(line_graph):
    cfg = Config(walk_speed_kmh=3.6)  # 1 m/s
    timed = add_travel_time(line_graph, cfg)
    assert "time" not in line_graph.edges[0, 1, 0]
    assert timed.edges[0, 1, 0]["time"] == pytest.approx(100.0)


def test_reachable_polygon_respects_cutoff(line_graph):
    cfg = Config(walk_speed_kmh=3.6, cutoff_seconds=250, edge_buffer_m=5, node_buffer_m=5)
    timed = add_travel_time(line_graph, cfg)
    poly = reachable_polygon(timed, center_node=0, cfg=cfg)
    assert poly.contains(Point(200, 0))
    assert not poly.contains(Point(400, 0))
    assert poly.area > 0


def test_reachable_polygon_has_no_holes(line_graph):
    cfg = Config(walk_speed_kmh=3.6, cutoff_seconds=1000, edge_buffer_m=5, node_buffer_m=5)
    timed = add_travel_time(line_graph, cfg)
    poly = reachable_polygon(timed, center_node=2, cfg=cfg)
    assert poly.geom_type == "Polygon"
    assert len(poly.interiors) == 0


def test_reachable_bands_are_nested(line_graph):
    cfg = Config(
        walk_speed_kmh=3.6, bands_seconds=(150, 250, 1000), edge_buffer_m=5, node_buffer_m=5
    )
    bands = reachable_bands(add_travel_time(line_graph, cfg), center_node=0, cfg=cfg)
    assert list(bands) == [150, 250, 1000]
    assert bands[150].area < bands[250].area < bands[1000].area
    assert bands[1000].contains(bands[250])
    assert bands[150].contains(Point(100, 0)) and not bands[150].contains(Point(200, 0))
