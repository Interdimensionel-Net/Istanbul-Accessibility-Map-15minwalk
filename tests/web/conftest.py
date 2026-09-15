import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from walkshed_web.app import create_app
from walkshed_web.settings import Settings, get_settings

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "artifact"


@pytest.fixture
def artifact_dir(tmp_path: Path) -> Path:
    """A private copy of the fixture, so tests may delete files from it."""
    target = tmp_path / "artifact"
    shutil.copytree(FIXTURE_DIR, target)
    return target


@pytest.fixture
def settings(artifact_dir: Path) -> Settings:
    return Settings(artifact_dir=artifact_dir, enable_docs=False)


@pytest.fixture
def client(settings: Settings) -> TestClient:
    get_settings.cache_clear()
    with TestClient(create_app(settings), raise_server_exceptions=False) as tc:
        yield tc
    get_settings.cache_clear()
