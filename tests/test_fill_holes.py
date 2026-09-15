import pytest
from shapely.geometry import Polygon, box

from walkshed.isochrone import fill_holes


def test_fill_holes_keeps_every_part():
    ring = Polygon(box(0, 0, 10, 10).exterior.coords, [box(4, 4, 6, 6).exterior.coords])
    multi = ring.union(box(20, 0, 30, 10))
    filled = fill_holes(multi)
    assert filled.geom_type == "MultiPolygon"
    assert filled.area == pytest.approx(200.0)
