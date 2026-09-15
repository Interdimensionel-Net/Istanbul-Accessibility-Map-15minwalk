"""Single source of configuration for the walkshed pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORRIDOR_SAFETY_FACTOR = 1.4


@dataclass(frozen=True)
class Config:
    """All tunable values. Frozen so no step can mutate shared state."""

    area_name: str = "İstanbul"
    extra_area_names: tuple[str, ...] = ("Kocaeli",)
    max_lon: float = 29.5  # Gebze is 29.43; İzmit tram starts past 29.8
    area_admin_level: str = "4"
    walk_speed_kmh: float = 4.5
    cutoff_seconds: int = 900
    bands_seconds: tuple[int, ...] = (300, 600, 900)
    web_bands: tuple[int, ...] = (900,)  # bands shipped to the web map
    entrance_match_m: float = 300.0
    edge_buffer_m: float = 25.0
    node_buffer_m: float = 50.0
    max_snap_m: float = 200.0
    corridor_simplify_m: float = 100.0
    osmnx_timeout_s: int = 600
    osmnx_overpass_url: str = "https://overpass-api.de/api"
    osmnx_max_query_area_m2: float = 120_000_000.0
    offline_graph: bool = False
    crs_geo: str = "EPSG:4326"
    crs_metric: str = "EPSG:5254"
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    user_agent: str = "istanbul-rail-walkshed/0.1 (+https://github.com/Interdimensionel-Net/Istanbul-Accessibility-Map-15minwalk)"
    verbose: bool = False
    overpass_retries: int = 4
    brt_network_regex: str = "Metrob"
    brt_line_name: str = "Metrobüs"
    require_reference: bool = True
    map_zoom: int = 11
    cache_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "cache")
    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "output")

    @property
    def walk_speed_m_per_s(self) -> float:
        """Walking speed in metres per second."""
        return self.walk_speed_kmh * 1000 / 3600

    @property
    def max_walk_m(self) -> float:
        """Network distance reachable at the cutoff, before buffers."""
        return self.walk_speed_m_per_s * self.cutoff_seconds

    @property
    def corridor_buffer_m(self) -> float:
        """Download radius around each origin. Wider than the walk reach plus buffers."""
        return self.max_walk_m * CORRIDOR_SAFETY_FACTOR + self.node_buffer_m

    @property
    def osmnx_cache_dir(self) -> Path:
        return self.cache_dir / "osmnx"

    @property
    def reference_path(self) -> Path:
        return PROJECT_ROOT / "data" / "reference" / "lines.json"

    @property
    def artifact_dir(self) -> Path:
        return self.output_dir / "artifact"

    @property
    def map_html(self) -> Path:
        return self.output_dir / "istanbul_15min_walkshed.html"


DEFAULT_CONFIG = Config()
