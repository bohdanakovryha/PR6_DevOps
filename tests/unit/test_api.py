"""HTTP API tests for /health and /version."""

from dataclasses import replace

import pytest

from app.main import create_app


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["checks"]["storage"]["ok"] is True


def test_version_returns_build_info(client):
    response = client.get("/version")

    assert response.status_code == 200
    assert response.get_json() == {
        "name": "pr6-service",
        "version": "1.2.3",
        "commit": "abc1234",
        "environment": "dev",
    }


@pytest.mark.parametrize("path", ["/health", "/version"])
def test_endpoints_return_json(client, path):
    response = client.get(path)

    assert response.is_json
    assert response.mimetype == "application/json"


@pytest.mark.parametrize(
    ("method", "path", "expected_status"),
    [
        ("post", "/health", 405),
        ("delete", "/version", 405),
        ("get", "/does-not-exist", 404),
    ],
)
def test_wrong_requests_return_json_errors(client, method, path, expected_status):
    response = getattr(client, method)(path)

    assert response.status_code == expected_status
    assert response.get_json()["status"] == "error"


def test_health_is_503_when_data_dir_is_missing(settings, tmp_path):
    broken = replace(settings, data_dir=tmp_path / "missing")
    client = create_app(broken).test_client()

    response = client.get("/health")

    assert response.status_code == 503
    body = response.get_json()
    assert body["status"] == "error"
    assert body["checks"]["storage"]["ok"] is False
    assert "FileNotFoundError" in body["checks"]["storage"]["detail"]


def test_health_is_503_when_data_dir_is_not_writable(client, monkeypatch):
    # Simulate "wrong owner / read-only volume" without depending on the
    # user that runs the tests (root ignores file permissions).
    def deny(*_args, **_kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr("app.main.tempfile.NamedTemporaryFile", deny)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.get_json()["checks"]["storage"]["detail"] == "PermissionError: Permission denied"
