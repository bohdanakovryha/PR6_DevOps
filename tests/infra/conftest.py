"""Testinfra connection to the running container.

The container name is taken from CONTAINER_NAME (default: pr6-app, as in compose.yaml).
"""

import os
import subprocess
import sys

import pytest
import testinfra

CONTAINER_NAME = os.environ.get("CONTAINER_NAME", "pr6-app")


# Testinfra's docker backend runs "docker exec ..." through a POSIX shell, which
# fails on Windows ("bytes args is not allowed on Windows"). On Windows, call
# docker directly with an argument list instead (no shell, no quoting issues).
if sys.platform == "win32":
    from testinfra.backend.docker import DockerBackend

    def _run_without_host_shell(self, command, *args, **kwargs):
        cmd = self.get_command(command, *args)
        user = ["-u", self.user] if self.user else []
        proc = subprocess.run(
            ["docker", "exec", *user, self.name, "/bin/sh", "-c", cmd],
            capture_output=True,
            timeout=60,
        )
        return self.result(proc.returncode, self.encode(cmd), proc.stdout, proc.stderr)

    DockerBackend.run = _run_without_host_shell


@pytest.fixture(scope="module")
def host():
    """Testinfra host that runs every command via `docker exec` in the container."""
    return testinfra.get_host(f"docker://{CONTAINER_NAME}")