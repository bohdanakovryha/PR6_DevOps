"""Shared fixtures for unit tests."""

from pathlib import Path

import pytest

from app.config import Settings
from app.main import create_app

# Every variable the service reads; cleared before config tests so the
# developer's or CI runner's own environment cannot affect the result.
APP_ENV_VARS = (
    "APP_NAME", "APP_VERSION", "GIT_COMMIT", "APP_ENV",
    "APP_PORT", "LOG_LEVEL", "DATA_DIR",
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Valid settings whose data directory is an isolated temporary folder."""
    return Settings(
        app_name="pr6-service",
        version="1.2.3",
        commit="abc1234",
        environment="dev",
        port=8000,
        log_level="INFO",
        data_dir=tmp_path,
    )


@pytest.fixture
def client(settings: Settings):
    """Flask test client: sends requests to the app without starting a server."""
    app = create_app(settings)
    app.testing = True
    return app.test_client()


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Minimal valid environment built with monkeypatch (restored after each test)."""
    for name in APP_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_VERSION", "1.0.0")
    return monkeypatch
