"""Testinfra connection to the running container.

The container name is taken from CONTAINER_NAME (default: pr6-app, as in compose.yaml).
"""

import os

import pytest
import testinfra

CONTAINER_NAME = os.environ.get("CONTAINER_NAME", "pr6-app")


@pytest.fixture(scope="module")
def host():
    """Testinfra host that runs every command via `docker exec` in the container."""
    return testinfra.get_host(f"docker://{CONTAINER_NAME}")
