"""Pure modules: settings, artifact loading, indexes, search, envelope, limiter, security."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from pydantic import ValidationError

from walkshed_web.artifact import ArtifactError, load_artifact
from walkshed_web.datafiles import build_cache
from walkshed_web.envelope import Meta, ok, page_meta
from walkshed_web.indexes import build_indexes
from walkshed_web.limiter import Bucket, RateLimiter, bucket_for
from walkshed_web.search import normalize_tr, rank_stations
from walkshed_web.security import csp_for
from walkshed_web.settings import Settings


def test_settings_resolve_artifact_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("WALKSHED_WEB_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setenv("WALKSHED_WEB_PORT", "9001")
    s = Settings()
    assert s.artifact_dir == tmp_path.resolve()
    assert s.port == 9001
    with pytest.raises(ValidationError):
        s.port = 1  # frozen


def test_settings_reject_bad_port(monkeypatch):
    monkeypatch.setenv("WALKSHED_WEB_PORT", "70000")
    with pytest.raises(ValidationError):
        Settings()


def test_artifact_loads_fixture(artifact_dir: Path):
    art = load_artifact(artifact_dir)
    assert len(art.meta.stations) == 3
    assert art.meta.stations[0].name == "Karaköy"
    assert art.meta.stations[1].codes == ("M2", "B1")
    assert set(art.bands_by_sid) == {101, 102}
    assert art.route_count == 1
    assert art.basemap is not None and art.basemap["layers"][0]["file"] == "basemap_core.jpg"
    assert art.reference_hash == "39f925f0404f"
    assert "bands.geojson" in art.files and "basemap_core.jpg" in art.files
    with pytest.raises(FrozenInstanceError):
        art.meta = None  # frozen


def test_artifact_missing_required(artifact_dir: Path):
    (artifact_dir / "meta.json").unlink()
    with pytest.raises(ArtifactError, match="meta.json"):
        load_artifact(artifact_dir)


def test_artifact_invalid_meta(artifact_dir: Path):
    (artifact_dir / "meta.json").write_text('{"stations": "nope"}', encoding="utf-8")
    with pytest.raises(ArtifactError, match="validation"):
        load_artifact(artifact_dir)


def test_artifact_unreadable_json(artifact_dir: Path):
    (artifact_dir / "bands.geojson").write_text("{not json", encoding="utf-8")
    with pytest.raises(ArtifactError):
        load_artifact(artifact_dir)


def test_artifact_optional_files_may_be_missing(artifact_dir: Path):
    (artifact_dir / "routes.geojson").unlink()
    (artifact_dir / "basemap.json").unlink()
    art = load_artifact(artifact_dir)
    assert art.route_count == 0 and art.basemap is None
    assert "routes.geojson" not in art.files


def test_cache_gzips_only_large_text(artifact_dir: Path):
    cache = build_cache(artifact_dir, gzip_min_bytes=0)
    assert cache["bands.geojson"].gzipped is not None
    assert cache["basemap_core.jpg"].gzipped is None
    big = build_cache(artifact_dir, gzip_min_bytes=10_000_000)
    assert big["bands.geojson"].gzipped is None


def test_indexes(artifact_dir: Path):
    idx = build_indexes(load_artifact(artifact_dir).meta)
    assert idx.by_sid[102].name == "Yenikapı"
    assert {s.sid for s in idx.stations_by_code["M2"]} == {102, 103}
    assert {s.sid for s in idx.stations_by_code["B1"]} == {102}
    assert idx.operators == {"İETT", "Metro İstanbul", "TCDD Taşımacılık"}
    assert idx.line_name("M2") == "Yenikapı – Hacıosman"
    assert idx.line_name("ZZ") == "ZZ"


@pytest.mark.parametrize(
    ("raw", "key"),
    [("İETT", "iett"), ("Karaköy", "karakoy"), ("ŞİŞLİ", "sisli"), ("Yenikapı", "yenikapi")],
)
def test_normalize_tr(raw, key):
    assert normalize_tr(raw) == key


def test_rank_prefix_before_substring(artifact_dir: Path):
    stations = load_artifact(artifact_dir).meta.stations
    hits = rank_stations(stations, "kap", 10)
    assert [s.name for s in hits] == ["Yenikapı"]
    hits = rank_stations(stations, "ye", 10)
    assert hits[0].name == "Yenikapı"
    assert rank_stations(stations, "   ", 10) == ()
    assert len(rank_stations(stations, "i", 1)) == 1


def test_envelope():
    body = ok([Meta(total=1)], page_meta(total=10, offset=20, limit=10))
    assert body["success"] is True
    assert body["data"] == [{"total": 1, "page": None, "limit": None}]
    assert body["meta"] == {"total": 10, "page": 3, "limit": 10}


def test_limiter_burst_then_refill():
    now = [1000.0]
    limiter = RateLimiter(clock=lambda: now[0])
    bucket = Bucket("t", per_minute=60, burst=2)
    assert limiter.check("a", bucket).allowed
    assert limiter.check("a", bucket).allowed
    denied = limiter.check("a", bucket)
    assert not denied.allowed and denied.retry_after >= 1
    assert limiter.check("b", bucket).allowed  # independent key
    now[0] += 1.0
    assert limiter.check("a", bucket).allowed


def test_limiter_evicts_oldest_keys(monkeypatch):
    import walkshed_web.limiter as mod

    monkeypatch.setattr(mod, "MAX_KEYS", 2)
    limiter = RateLimiter(clock=lambda: 0.0)
    bucket = Bucket("t", 60, 1)
    for key in "abc":
        limiter.check(key, bucket)
    assert list(limiter._state) == ["b", "c"]


def test_bucket_for_prefix():
    a, b = Bucket("a", 1, 1), Bucket("b", 1, 1)
    assert bucket_for("/api/x", (("/api", a),), b) is a
    assert bucket_for("/other", (("/api", a),), b) is b


def test_csp_contains_nonce_and_hosts():
    policy = csp_for("abc", ("https://tile.example",))
    assert "script-src 'self' 'nonce-abc'" in policy
    assert "img-src 'self' data: blob: https://tile.example" in policy
    assert "cdnjs" not in policy
