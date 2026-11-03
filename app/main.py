"""Flask application with two operational endpoints: /health and /version."""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path

from flask import Flask, jsonify

from app.config import Settings, load_settings

logger = logging.getLogger(__name__)


def check_storage(data_dir: Path) -> tuple[bool, str]:
    """Readiness probe: the service must be able to write into its data directory.

    A temporary file is created and removed immediately. Any OS error
    (missing directory, wrong owner, read-only filesystem) marks the check as failed.
    """
    try:
        with tempfile.NamedTemporaryFile(dir=data_dir, prefix=".health-") as probe:
            probe.write(b"ok")
            probe.flush()
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc.strerror or exc}"
    return True, "writable"


def create_app(settings: Settings | None = None) -> Flask:
    """Application factory. Settings are validated before any route is registered."""
    settings = settings or load_settings()

    app = Flask(__name__)
    app.config["SETTINGS"] = settings
    app.json.sort_keys = False
    logging.basicConfig(level=settings.log_level)
    started_at = time.monotonic()

    @app.get("/health")
    def health():
        """Return 200 when all internal checks pass, otherwise 503."""
        storage_ok, storage_detail = check_storage(settings.data_dir)
        checks = {"storage": {"ok": storage_ok, "detail": storage_detail}}
        healthy = all(check["ok"] for check in checks.values())
        if not healthy:
            logger.error("health check failed: %s", checks)
        body = {
            "status": "ok" if healthy else "error",
            "checks": checks,
            "uptime_seconds": round(time.monotonic() - started_at, 1),
        }
        return jsonify(body), 200 if healthy else 503

    @app.get("/version")
    def version():
        """Return build information so we can see exactly which image is running."""
        return jsonify(
            name=settings.app_name,
            version=settings.version,
            commit=settings.commit,
            environment=settings.environment,
        )

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(status="error", message="not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify(status="error", message="method not allowed"), 405

    logger.info("%s %s (%s) configured for %s", settings.app_name, settings.version,
                settings.commit, settings.environment)
    return app
