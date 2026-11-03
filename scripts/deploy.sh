#!/usr/bin/env bash
# Deploy an image to the training environment and roll back automatically on failure.
#
#   scripts/deploy.sh <image-ref>        e.g. ghcr.io/user/pr6_devops:<commit-sha>
#
# Steps:
#   1. remember the image that is running now (rollback target);
#   2. start the new image with docker compose;
#   3. verify it: HTTP check of /health (with timeouts) + Testinfra tests;
#   4. on failure: save logs, start the previous image again, verify it again.
#
# Exit codes: 0 - deployed; 1 - deployment failed (rolled back or nothing to roll
# back to); 2 - deployment AND rollback failed. A rollback never turns a failed
# deployment into a success: the CI job stays red.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

NEW_IMAGE="${1:?usage: scripts/deploy.sh <image-ref>}"

# Settings from .env (same file docker compose uses). Like compose, variables
# already set in the shell win over the file; then defaults are applied.
if [[ -f .env ]]; then
  while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    if [[ -z "${!key+x}" ]]; then export "$key=$value"; fi
  done < .env
fi
CONTAINER_NAME="${CONTAINER_NAME:-pr6-app}"
HOST_PORT="${HOST_PORT:-8080}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-60}"
REPORT_DIR="${REPORT_DIR:-reports}"
STATE_DIR="${STATE_DIR:-.deploy}"
HEALTH_URL="http://127.0.0.1:${HOST_PORT}/health"
export CONTAINER_NAME APP_PORT="${APP_PORT:-8000}"
mkdir -p "$REPORT_DIR" "$STATE_DIR"

log() { printf '[deploy %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }

running_image() {
  docker inspect --format '{{.Config.Image}}' "$CONTAINER_NAME" 2>/dev/null || true
}

start() {
  log "starting $1"
  APP_IMAGE="$1" timeout 120 docker compose up -d --no-build --force-recreate --remove-orphans
}

verify() {  # $1 - label used in report file names
  log "HTTP check $HEALTH_URL (deadline ${HEALTH_TIMEOUT}s)"
  python3 scripts/http_check.py --url "$HEALTH_URL" --timeout "$HEALTH_TIMEOUT" \
          --interval 2 --request-timeout 3 || return 1
  log "Testinfra checks"
  timeout 180 python3 -m pytest tests/infra -q -p no:cacheprovider \
          --junitxml="$REPORT_DIR/infra-$1.xml" || return 1
}

save_logs() {  # keep the logs before the container is replaced
  docker logs --timestamps "$CONTAINER_NAME" >"$REPORT_DIR/container-$1.log" 2>&1 || true
  docker inspect --format '{{json .State}}' "$CONTAINER_NAME" >"$REPORT_DIR/state-$1.json" 2>/dev/null || true
}

PREVIOUS_IMAGE="$(running_image)"
if [[ -z "$PREVIOUS_IMAGE" && -s "$STATE_DIR/history" ]]; then
  PREVIOUS_IMAGE="$(tail -n 1 "$STATE_DIR/history")"
fi
log "current image : ${PREVIOUS_IMAGE:-<none>}"
log "new image     : $NEW_IMAGE"

if start "$NEW_IMAGE" && verify deploy; then
  save_logs deploy
  echo "$NEW_IMAGE" >>"$STATE_DIR/history"
  log "SUCCESS: $NEW_IMAGE is deployed and healthy"
  exit 0
fi

save_logs failed
log "FAILED: $NEW_IMAGE did not pass the checks (logs: $REPORT_DIR/container-failed.log)"

if [[ -z "$PREVIOUS_IMAGE" || "$PREVIOUS_IMAGE" == "$NEW_IMAGE" ]]; then
  log "no previous image to roll back to"
  exit 1
fi

log "ROLLBACK to $PREVIOUS_IMAGE"
if start "$PREVIOUS_IMAGE" && verify rollback; then
  save_logs rollback
  log "rollback finished, service is healthy again on $PREVIOUS_IMAGE"
  log "deployment of $NEW_IMAGE is marked as FAILED"
  exit 1
fi

save_logs rollback-failed
log "ROLLBACK FAILED - manual intervention required"
exit 2
