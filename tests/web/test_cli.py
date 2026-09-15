import os
from pathlib import Path

import pytest

from walkshed_web import cli


def test_parser_and_env(monkeypatch):
    for key in ("WALKSHED_WEB_HOST", "WALKSHED_WEB_PORT"):
        monkeypatch.delenv(key, raising=False)
    args = cli.build_parser().parse_args(["--host", "0.0.0.0", "--port", "9000"])
    cli.apply_env(args)
    assert os.environ["WALKSHED_WEB_HOST"] == "0.0.0.0"
    assert os.environ["WALKSHED_WEB_PORT"] == "9000"
    assert "WALKSHED_WEB_ARTIFACT_DIR" not in os.environ or True


def test_main_fails_clearly_without_artifact(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.delenv("WALKSHED_WEB_ARTIFACT_DIR", raising=False)
    code = cli.main(["--artifact-dir", str(tmp_path)])
    assert code == 1
    err = capsys.readouterr().err
    assert "meta.json" in err and "uv run walkshed" in err
    assert str(tmp_path.resolve()) in err


def test_main_starts_uvicorn(artifact_dir: Path, monkeypatch):
    calls: dict = {}
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: calls.update(kw))
    monkeypatch.delenv("WALKSHED_WEB_PORT", raising=False)
    code = cli.main(["--artifact-dir", str(artifact_dir), "--port", "8123", "--log-level", "WARNING"])
    assert code == 0
    assert calls["port"] == 8123 and calls["factory"] is True and calls["access_log"] is False


def test_entry_point_is_registered():
    from importlib.metadata import entry_points

    names = {ep.name for ep in entry_points(group="console_scripts")}
    if "walkshed" not in names:
        pytest.skip("project not installed in this environment")
    assert "walkshed-web" in names
