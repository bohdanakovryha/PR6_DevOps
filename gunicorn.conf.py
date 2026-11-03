"""Gunicorn settings.

The bind address and log level come from the same validated settings as the app,
so a bad environment variable stops the server at start-up (fail fast).
"""

import os

from app.config import load_settings

_settings = load_settings()

bind = f"0.0.0.0:{_settings.port}"
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
timeout = 30            # kill a worker that is stuck on one request for 30 s
graceful_timeout = 10   # time given to workers to finish requests on shutdown
keepalive = 5
accesslog = "-"         # access log to stdout -> visible in `docker logs`
errorlog = "-"
loglevel = _settings.log_level.lower()
