"""Infrastructure tests for the deployed container (run with Testinfra).

The slim base image has no `ps` or `ss`, so processes and sockets are read
directly from /proc instead of installing extra packages into the image.
"""

import os

import pytest

APP_USER = "app"
APP_PORT = int(os.environ.get("APP_PORT", "8000"))
TCP_LISTEN = "0A"  # socket state code for LISTEN in /proc/net/tcp


def _uid_of(host, pid: str) -> int:
    """Real UID of a process, taken from /proc/<pid>/status."""
    for line in host.file(f"/proc/{pid}/status").content_string.splitlines():
        if line.startswith("Uid:"):
            return int(line.split()[1])
    raise AssertionError(f"no Uid line for pid {pid}")


def _cmdline(host, pid: str) -> str:
    return host.file(f"/proc/{pid}/cmdline").content_string.replace("\x00", " ").strip()


def _gunicorn_pids(host) -> list[str]:
    # One grep over all cmdline files. The pattern "gunicor[n]" does not match
    # grep's own command line; short-lived processes may vanish while grep runs
    # (rc=2), which is fine.
    result = host.run("grep -ls 'gunicor[n]' /proc/[0-9]*/cmdline")
    assert result.rc in (0, 2), result.stderr
    return [line.split("/")[2] for line in result.stdout.split()]


@pytest.mark.parametrize(
    "path",
    [
        "/app/app/__init__.py",
        "/app/app/config.py",
        "/app/app/main.py",
        "/app/app/wsgi.py",
        "/app/gunicorn.conf.py",
        "/app/requirements.txt",
    ],
)
def test_application_files_exist(host, path):
    file = host.file(path)
    assert file.exists
    assert file.is_file


def test_data_directory_belongs_to_app_user(host):
    data_dir = host.file("/app/data")
    assert data_dir.is_directory
    assert data_dir.user == APP_USER


def test_app_user_is_not_root(host):
    user = host.user(APP_USER)
    assert user.exists
    assert user.uid != 0


def test_gunicorn_is_pid_1(host):
    assert "gunicorn" in _cmdline(host, "1")


def test_gunicorn_workers_are_running(host):
    # One master + at least one worker process.
    assert len(_gunicorn_pids(host)) >= 2


def test_application_processes_do_not_run_as_root(host):
    pids = _gunicorn_pids(host)
    assert pids, "gunicorn is not running"
    for pid in pids:
        assert _uid_of(host, pid) != 0, f"process {pid} runs as root"


def test_port_is_listening(host):
    expected = f"{APP_PORT:04X}"
    listening = set()
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        file = host.file(table)
        if not file.exists:
            continue
        for row in file.content_string.splitlines()[1:]:
            fields = row.split()
            local_port = fields[1].rsplit(":", 1)[1]
            if fields[3] == TCP_LISTEN:
                listening.add(local_port)
    assert expected in listening, f"port {APP_PORT} is not listening"


def test_health_endpoint_inside_container(host):
    cmd = host.run(
        "python -c \"import urllib.request; "
        f"print(urllib.request.urlopen('http://127.0.0.1:{APP_PORT}/health', timeout=3).status)\""
    )
    assert cmd.rc == 0, cmd.stderr
    assert cmd.stdout.strip() == "200"
