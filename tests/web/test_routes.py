"""HTTP surface: envelope, validation, errors, headers, rate limits, data files, page."""

import gzip
import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.testclient import TestClient

from walkshed_web.app import create_app
from walkshed_web.settings import Settings

HEADERS = (
    "content-security-policy",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "cross-origin-opener-policy",
)


def test_health_and_version(client: TestClient):
    body = client.get("/api/health").json()
    assert body["success"] and body["data"]["status"] == "ok" and body["data"]["stations"] == 3
    body = client.get("/api/version").json()
    assert body["data"]["reference_hash"] == "39f925f0404f"


def test_meta_hides_provenance_by_default(client: TestClient):
    data = client.get("/api/meta").json()["data"]
    assert data["counts"] == {"stations": 3, "covered": 2, "lines": 3, "routes": 1}
    assert data["operators"] == ["Metro İstanbul", "TCDD Taşımacılık", "İETT"]
    assert data["provenance"] is None
    assert data["basemap"]["layers"][0]["file"] == "/data/basemap_core.jpg"


def test_meta_exposes_provenance_when_enabled(settings: Settings):
    cfg = settings.model_copy(update={"expose_provenance": True})
    with TestClient(create_app(cfg)) as tc:
        data = tc.get("/api/meta").json()["data"]
    assert data["provenance"]["python"] == "3.13.1"


def test_lines_list_and_detail(client: TestClient):
    body = client.get("/api/lines").json()
    assert body["meta"]["total"] == 3
    m2 = next(line for line in body["data"] if line["code"] == "M2")
    assert m2["stop_count"] == 3 and m2["station_count"] == 2
    assert m2["stops"] is None and m2["coords"] is None
    body = client.get("/api/lines", params={"operator": "İETT", "include_stops": "true"}).json()
    assert [line["code"] for line in body["data"]] == ["F2"]
    assert body["data"][0]["stops"][0]["name"] == "Karaköy"
    detail = client.get("/api/lines/M2").json()["data"]
    assert detail["stops"][2] == {"name": "Ghost", "sid": None}
    assert len(detail["coords"]) == 2


def test_lines_errors(client: TestClient):
    r = client.get("/api/lines/ZZ")
    assert r.status_code == 404 and r.json()["error"] == "Line not found."
    assert client.get("/api/lines/bad code").status_code == 422
    r = client.get("/api/lines", params={"operator": "Nobody"})
    assert r.status_code == 422 and r.json() == {
        "success": False,
        "data": None,
        "error": "Invalid request parameters.",
        "meta": None,
    }


def test_stations_filter_by_split_code(client: TestClient):
    body = client.get("/api/stations", params={"line": "B1"}).json()
    assert [s["sid"] for s in body["data"]] == [102]
    assert body["data"][0]["lines"] == ["M2", "B1"]
    body = client.get("/api/stations", params={"line": "M2", "covered": "false"}).json()
    assert [s["sid"] for s in body["data"]] == [103]


def test_stations_pagination(client: TestClient):
    body = client.get("/api/stations", params={"limit": 2, "offset": 2}).json()
    assert body["meta"] == {"total": 3, "page": 2, "limit": 2}
    assert len(body["data"]) == 1
    assert client.get("/api/stations", params={"limit": 0}).status_code == 422
    assert client.get("/api/stations", params={"limit": 501}).status_code == 422
    assert client.get("/api/stations", params={"mode": "Nope!"}).status_code == 422
    assert client.get("/api/stations", params={"mode": "rocket"}).status_code == 422
    assert client.get("/api/stations", params={"unknown": "1"}).status_code == 422


def test_station_detail_and_bands(client: TestClient):
    data = client.get("/api/stations/102").json()["data"]
    assert data["line_names"] == [
        {"code": "M2", "name": "Yenikapı – Hacıosman"},
        {"code": "B1", "name": "Halkalı – Gebze"},
    ]
    assert data["widest"] == {"band": 900, "minutes": 15, "km2": 2.1}
    data = client.get("/api/stations/103").json()["data"]
    assert data["bands"] == [] and data["widest"] is None
    geo = client.get("/api/stations/101/bands").json()["data"]
    assert geo["type"] == "FeatureCollection" and len(geo["features"]) == 1
    assert client.get("/api/stations/999").status_code == 404
    assert client.get("/api/stations/999/bands").status_code == 404
    assert client.get("/api/stations/0").status_code == 422
    assert client.get("/api/stations/abc").status_code == 422


def test_search(client: TestClient):
    hits = client.get("/api/search", params={"q": "karakoy"}).json()["data"]
    assert hits[0]["name"] == "Karaköy" and hits[0]["lines"] == ["F2"]
    hits = client.get("/api/search", params={"q": "İ"}).json()["data"]
    assert hits and hits[0]["name"] == "Şişli-Mecidiyeköy"
    assert client.get("/api/search").status_code == 422
    assert client.get("/api/search", params={"q": "x" * 81}).status_code == 422
    assert client.get("/api/search", params={"q": "a\x01b"}).status_code == 422


def test_security_headers_everywhere(client: TestClient):
    for path in ("/api/health", "/nope", "/api/stations/999", "/static/js/app.js"):
        r = client.get(path)
        for h in HEADERS:
            assert h in r.headers, (path, h)
        assert "strict-transport-security" not in r.headers  # plain http
    r = client.get("/api/health", headers={"x-forwarded-proto": "https"})
    assert r.headers["strict-transport-security"].startswith("max-age=31536000")


def test_hsts_can_be_disabled(settings: Settings):
    with TestClient(create_app(settings.model_copy(update={"enable_hsts": False}))) as tc:
        r = tc.get("/api/health", headers={"x-forwarded-proto": "https"})
    assert "strict-transport-security" not in r.headers


def test_unknown_path_is_enveloped(client: TestClient):
    r = client.get("/nope")
    assert r.status_code == 404 and r.json()["error"] == "Not found."
    r = client.post("/api/health")
    assert r.status_code == 405 and r.json()["success"] is False


def test_unhandled_error_never_leaks(settings: Settings):
    app = create_app(settings)
    boom = APIRouter()

    @boom.get("/api/boom")
    def _boom() -> None:
        raise ValueError("secret-detail")

    app.include_router(boom)
    with TestClient(app, raise_server_exceptions=False) as tc:
        r = tc.get("/api/boom")
    assert r.status_code == 500
    assert r.json() == {"success": False, "data": None, "error": "Internal error.", "meta": None}
    assert "secret-detail" not in r.text


def test_rate_limit_returns_429_with_retry_after(settings: Settings):
    cfg = settings.model_copy(update={"rate_limit_per_minute": 60, "rate_limit_burst": 2})
    with TestClient(create_app(cfg)) as tc:
        assert tc.get("/api/meta").status_code == 200
        assert tc.get("/api/meta").status_code == 200
        r = tc.get("/api/meta")
        assert r.status_code == 429
        assert r.headers["retry-after"].isdigit()
        assert r.json()["error"] == "Too many requests."
        assert "content-security-policy" in r.headers
        # separate bucket families are independent
        assert tc.get("/api/search", params={"q": "k"}).status_code == 200


def test_data_file_headers_and_gzip(client: TestClient, artifact_dir: Path):
    r = client.get("/data/bands.geojson", headers={"accept-encoding": "identity"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/geo+json")
    assert r.headers["vary"] == "Accept-Encoding"
    assert r.headers["cache-control"] == "public, max-age=300, must-revalidate"
    assert "content-encoding" not in r.headers
    assert r.json() == json.loads((artifact_dir / "bands.geojson").read_text(encoding="utf-8"))
    etag = r.headers["etag"]
    r304 = client.get("/data/bands.geojson", headers={"if-none-match": etag})
    assert r304.status_code == 304 and r304.content == b""
    r304 = client.get("/data/bands.geojson", headers={"if-modified-since": r.headers["last-modified"]})
    assert r304.status_code == 304


def test_data_file_gzip_negotiation(settings: Settings, artifact_dir: Path):
    cfg = settings.model_copy(update={"gzip_min_bytes": 0})
    with TestClient(create_app(cfg)) as tc:
        r = tc.get("/data/bands.geojson", headers={"accept-encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip"
    # The test client transparently decompresses; the raw stream must still be valid gzip.
    raw = gzip.compress(r.content) if r.content[:2] != b"\x1f\x8b" else r.content
    assert json.loads(gzip.decompress(raw)) == json.loads(
        (artifact_dir / "bands.geojson").read_text(encoding="utf-8")
    )


def test_data_versioned_cache_and_images(client: TestClient):
    r = client.get("/data/bands.geojson", params={"v": "39f925f0404f"})
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
    r = client.get("/data/bands.geojson", params={"v": "deadbeef"})
    assert r.headers["cache-control"].startswith("public, max-age=300")
    assert client.get("/data/bands.geojson", params={"v": "NOT-HEX"}).status_code == 422
    r = client.get("/data/basemap_core.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.content[:2] == b"\xff\xd8"


def test_data_rejects_traversal_and_unknown_names(client: TestClient):
    for name in (
        "..%2Fmeta.json",
        "..%5C..%5Cpyproject.toml",
        "meta.json%3Astream",
        "C%3A%5CWindows%5Cwin.ini",
        "bands.geojson%00",
        "BANDS.geojson",
        "meta.json",
        "basemap_wide.jpg",
    ):
        r = client.get(f"/data/{name}")
        assert r.status_code == 404, name
        assert r.json()["error"] in ("Not available.", "Not found.")
    assert client.get("/data/").status_code == 404


def test_page_carries_matching_nonce(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert r.headers["cache-control"] == "no-store"
    csp = r.headers["content-security-policy"]
    nonce = csp.split("'nonce-")[1].split("'")[0]
    assert f'nonce="{nonce}"' in r.text
    assert "{{CSP_NONCE}}" not in r.text
    other = client.get("/").headers["content-security-policy"]
    assert other != csp


def test_static_assets(client: TestClient):
    r = client.get("/static/js/app.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert client.get("/static/vendor/leaflet/leaflet.js").status_code == 200
    assert client.get("/static/../pyproject.toml").status_code == 404


def test_docs_disabled_by_default(client: TestClient):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
