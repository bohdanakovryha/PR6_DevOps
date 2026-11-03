"""Application settings loaded from environment variables.

All configuration is read from the environment (12-factor style), validated once
at start-up, and stored in an immutable ``Settings`` object. Invalid values raise
``ConfigError`` so the service fails fast instead of running half-configured.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

ALLOWED_ENVIRONMENTS = ("dev", "staging", "prod")
ALLOWED_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

DEFAULT_APP_NAME = "pr6-service"
DEFAULT_PORT = 8000
DEFAULT_DATA_DIR = "/app/data"


class ConfigError(ValueError):
    """Raised when one or more environment variables are missing or invalid."""


@dataclass(frozen=True)
class Settings:
    """Validated runtime configuration of the service."""

    app_name: str
    version: str
    commit: str
    environment: str
    port: int
    log_level: str
    data_dir: Path


def _parse_port(raw: str, errors: list[str]) -> int:
    """Convert APP_PORT to int and make sure it is a valid TCP port."""
    try:
        port = int(raw)
    except ValueError:
        errors.append(f"APP_PORT must be an integer, got {raw!r}")
        return DEFAULT_PORT
    if not 1 <= port <= 65535:
        errors.append(f"APP_PORT must be in range 1..65535, got {port}")
    return port


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Build ``Settings`` from a mapping of environment variables.

    ``environ`` defaults to ``os.environ``; tests pass their own mapping or use
    ``monkeypatch`` to change the real environment.
    """
    env = os.environ if environ is None else environ
    errors: list[str] = []

    # APP_VERSION is mandatory: a deployment without a known version is not traceable.
    version = env.get("APP_VERSION", "").strip()
    if not version:
        errors.append("APP_VERSION is required and must not be empty")

    environment = env.get("APP_ENV", "dev").strip().lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        errors.append(f"APP_ENV must be one of {ALLOWED_ENVIRONMENTS}, got {environment!r}")

    log_level = env.get("LOG_LEVEL", "INFO").strip().upper()
    if log_level not in ALLOWED_LOG_LEVELS:
        errors.append(f"LOG_LEVEL must be one of {ALLOWED_LOG_LEVELS}, got {log_level!r}")

    port = _parse_port(env.get("APP_PORT", str(DEFAULT_PORT)).strip(), errors)

    if errors:
        # Report every problem at once so the operator can fix them in one go.
        raise ConfigError("; ".join(errors))

    return Settings(
        app_name=env.get("APP_NAME", DEFAULT_APP_NAME).strip() or DEFAULT_APP_NAME,
        version=version,
        commit=env.get("GIT_COMMIT", "unknown").strip() or "unknown",
        environment=environment,
        port=port,
        log_level=log_level,
        data_dir=Path(env.get("DATA_DIR", DEFAULT_DATA_DIR)),
    )
