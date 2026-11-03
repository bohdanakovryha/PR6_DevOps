# Runtime image for the PR6 service. Built in CI and tagged with the git commit SHA.

ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}

# Build metadata, passed by CI: --build-arg GIT_COMMIT=$GITHUB_SHA
ARG APP_VERSION=1.0.0
ARG GIT_COMMIT=unknown
# Allows building through a private/corporate PyPI mirror; defaults to the public index.
ARG PIP_INDEX_URL=https://pypi.org/simple

LABEL org.opencontainers.image.title="pr6-service" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_VERSION=${APP_VERSION} \
    GIT_COMMIT=${GIT_COMMIT} \
    APP_PORT=8000 \
    DATA_DIR=/app/data

WORKDIR /app

# Dedicated unprivileged user: the service must never run as root.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home \
            --home-dir /app --shell /usr/sbin/nologin app

# Dependencies first, so this layer is cached while only the code changes.
COPY requirements.txt .
RUN pip install --index-url "${PIP_INDEX_URL}" -r requirements.txt

COPY gunicorn.conf.py .
COPY app/ ./app/

# The data directory must belong to the app user, otherwise /health reports 503.
RUN mkdir -p /app/data && chown app:app /app/data

USER app

EXPOSE 8000

# Docker-level health status (shown by `docker ps`); uses Python, so no curl is needed.
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('APP_PORT', '8000'), timeout=2)"]

# Exec form: gunicorn becomes PID 1 and receives SIGTERM directly.
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app.wsgi:app"]
