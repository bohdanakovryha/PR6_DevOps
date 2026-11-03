"""Configuration tests: valid values, defaults and behaviour with bad settings."""

import runpy
from pathlib import Path

import pytest

from app.config import ConfigError, load_settings
from app.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_defaults_are_applied(clean_env):
    settings = load_settings()

    assert settings.version == "1.0.0"
    assert settings.environment == "dev"
    assert settings.port == 8000
    assert settings.log_level == "INFO"
    assert settings.commit == "unknown"
    assert settings.data_dir == Path("/app/data")


@pytest.mark.parametrize(
    ("name", "value", "attribute", "expected"),
    [
        ("APP_PORT", "9090", "port", 9090),
        ("APP_ENV", "PROD", "environment", "prod"),       # case-insensitive
        ("LOG_LEVEL", "debug", "log_level", "DEBUG"),
        ("GIT_COMMIT", "0a1b2c3", "commit", "0a1b2c3"),
        ("DATA_DIR", "/tmp/pr6", "data_dir", Path("/tmp/pr6")),
    ],
)
def test_valid_overrides(clean_env, name, value, attribute, expected):
    clean_env.setenv(name, value)

    assert getattr(load_settings(), attribute) == expected


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("APP_PORT", "abc", "APP_PORT must be an integer"),
        ("APP_PORT", "0", "APP_PORT must be in range"),
        ("APP_PORT", "70000", "APP_PORT must be in range"),
        ("APP_ENV", "production", "APP_ENV must be one of"),
        ("LOG_LEVEL", "LOUD", "LOG_LEVEL must be one of"),
        ("APP_VERSION", "   ", "APP_VERSION is required"),
    ],
)
def test_invalid_values_raise_config_error(clean_env, name, value, message):
    clean_env.setenv(name, value)

    with pytest.raises(ConfigError, match=message):
        load_settings()


def test_missing_version_is_rejected(clean_env):
    clean_env.delenv("APP_VERSION")

    with pytest.raises(ConfigError, match="APP_VERSION is required"):
        load_settings()


def test_all_errors_are_reported_together(clean_env):
    clean_env.setenv("APP_PORT", "abc")
    clean_env.setenv("LOG_LEVEL", "LOUD")

    with pytest.raises(ConfigError) as excinfo:
        load_settings()

    assert "APP_PORT" in str(excinfo.value)
    assert "LOG_LEVEL" in str(excinfo.value)


def test_app_does_not_start_with_bad_settings(clean_env):
    clean_env.setenv("APP_ENV", "production")

    with pytest.raises(ConfigError):
        create_app()


def test_gunicorn_binds_to_configured_port(clean_env):
    clean_env.setenv("APP_PORT", "9000")
    clean_env.setenv("LOG_LEVEL", "WARNING")

    config = runpy.run_path(str(PROJECT_ROOT / "gunicorn.conf.py"))

    assert config["bind"] == "0.0.0.0:9000"
    assert config["loglevel"] == "warning"


def test_gunicorn_refuses_to_start_with_bad_port(clean_env):
    clean_env.setenv("APP_PORT", "not-a-port")

    with pytest.raises(ConfigError):
        runpy.run_path(str(PROJECT_ROOT / "gunicorn.conf.py"))
