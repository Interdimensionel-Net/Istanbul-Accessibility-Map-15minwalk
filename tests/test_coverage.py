import geopandas as gpd
import pytest
from shapely.geometry import box

from walkshed.coverage import dissolve_coverage, summarize


@pytest.fixture
def squares() -> gpd.GeoDataFrame:
    """Two 1 km squares with 0.5 km overlap, plus a disjoint square. Metric CRS."""
    return gpd.GeoDataFrame(
        {
            "station_name": ["A", "B", "C"],
            "mode": ["subway", "subway", "tram"],
            "line": ["M1", "M1", "T1"],
        },
        geometry=[box(0, 0, 1000, 1000), box(500, 0, 1500, 1000), box(5000, 0, 6000, 1000)],
        crs="EPSG:32635",
    )


def test_dissolve_merges_overlap(squares):
    coverage = dissolve_coverage(squares)
    assert len(coverage) == 1
    assert coverage.geometry.iloc[0].area == pytest.approx(2.5e6)


def test_summary_reports_km2(squares):
    summary = summarize(squares, dissolve_coverage(squares))
    assert summary["origin_count"] == 3
    assert summary["total_km2"] == pytest.approx(2.5)
    assert summary["by_mode_km2"]["subway"] == pytest.approx(1.5)
    assert summary["by_mode_km2"]["tram"] == pytest.approx(1.0)
    assert summary["by_line_km2"]["M1"] == pytest.approx(1.5)
