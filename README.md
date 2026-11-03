# PR6 DevOps — automated testing and deployment of a Python service

A small Flask service with two routes and a complete DevOps process around it:
pytest tests → Docker image build tagged with the commit hash → deployment with Docker Compose →
Testinfra and HTTP `/health` checks → automatic rollback to the previous image on failure.

| Route | Response |
|---|---|
| `GET /health`  | `200 {"status":"ok", ...}` or `503 {"status":"error", ...}` if the data directory is not writable |
| `GET /version` | `{"name", "version", "commit", "environment"}` — shows exactly which image is running |

## Layout

```
app/                       service code (config.py — settings from environment variables)
gunicorn.conf.py           WSGI server settings
Dockerfile, compose.yaml, .env.example
tests/unit/                pytest: API, settings, monkeypatch, parametrize, fixtures
tests/infra/               Testinfra: files, processes, port, non-root user
scripts/http_check.py      readiness wait with timeouts
scripts/deploy.sh          deploy + checks + automatic rollback
scripts/rollback.sh        manual rollback
scripts/local_pipeline.sh  the same stages as CI, for a training Linux machine
.github/workflows/ci-cd.yml  GitHub Actions
```

## Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `APP_VERSION` | — (required, baked into the image) | application version |
| `GIT_COMMIT` | `unknown` (commit SHA in the image) | commit hash |
| `APP_ENV` | `dev` | `dev` / `staging` / `prod` |
| `APP_PORT` | `8000` | port inside the container (1..65535) |
| `LOG_LEVEL` | `INFO` | log level |
| `DATA_DIR` | `/app/data` | directory checked by `/health` |
| `HOST_PORT` | `8080` | port published on the host |
| `HEALTH_TIMEOUT` | `60` | seconds to wait for readiness after a deployment |

An invalid value (for example `APP_PORT=abc`) stops the service at start-up with `ConfigError`.

## Run

```bash
cp .env.example .env
docker compose up -d --build          # build and start
curl -s localhost:8080/health
curl -s localhost:8080/version
docker compose logs -f app            # logs
docker compose down                   # stop
```

## Check

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt

pytest -v                              # unit tests (tests/unit)
pytest tests/infra -v                  # Testinfra against the running container pr6-app
python scripts/http_check.py --url http://127.0.0.1:8080/health --timeout 30
```

## Deploy and roll back

```bash
# full local pipeline: pytest -> docker build (tag = commit hash) -> deploy
scripts/local_pipeline.sh

# deploy a specific image (automatic rollback on failure)
scripts/deploy.sh pr6-devops:<commit-sha>

# manual rollback to the previous successful version (history in .deploy/history)
scripts/rollback.sh
# or to a specific image
scripts/rollback.sh ghcr.io/bohdanakovryha/pr6_devops:<commit-sha>
```

`deploy.sh` exit codes: `0` — success, `1` — deployment failed (rolled back, or nothing to roll back to),
`2` — both the deployment and the rollback failed.

## CI/CD (GitHub Actions)

| Event | test | build | deploy |
|---|---|---|---|
| Pull request to `main` | pytest + JUnit report | build image `:<sha>` | — |
| Push / merge to `main` | pytest | build + push to GHCR `:<sha>` | deploy, Testinfra, HTTP `/health` and `/version`, promote to `:stable` |

* `build` depends on `test`, `deploy` depends on both: a red test blocks the deployment.
* The deployed image is exactly the one built and checked in `build` (tag — full commit SHA).
* `:stable` is the last image that passed all checks. On a fresh GitHub VM it is started first,
  so a failed deployment always has a version to roll back to.
* Test reports and container logs are uploaded as artifacts with `if: always()` — even when a stage fails.
* Timeouts: `timeout-minutes` for every job, a timeout for each HTTP request and an overall readiness deadline.
* To deploy to your own Linux machine, install a self-hosted runner and set the repository variable
  `DEPLOY_RUNNER=self-hosted`.

It is recommended to protect the `main` branch (Settings → Branches): "Require status checks to pass" for
`Unit tests (pytest)` and `Build image` — then a PR with a red test cannot be merged.

## Failure experiments

1. **Broken test.** Branch `experiment/broken-test`: an expected value in a test is changed. The `test` stage is red,
   `build` and `deploy` are skipped, the previous version keeps running in the training environment.
2. **Broken `/health`.** Branch `experiment/broken-health`: `chown app:app /app/data` is removed from the `Dockerfile`.
   Unit tests and the build pass, but inside the container the `app` user cannot write to `/app/data`, so `/health`
   returns `503`. `deploy.sh` saves the logs, starts the previous image again, re-checks it and exits with code `1` —
   the deployment stays marked as failed.
