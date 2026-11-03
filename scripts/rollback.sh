#!/usr/bin/env bash
# Manual rollback to the previous successfully deployed image (or to a given one).
#
#   scripts/rollback.sh              # previous image from .deploy/history
#   scripts/rollback.sh <image-ref>  # explicit image
set -Eeuo pipefail
cd "$(dirname "$0")/.."

STATE_DIR="${STATE_DIR:-.deploy}"
TARGET="${1:-}"

if [[ -z "$TARGET" ]]; then
  if [[ ! -s "$STATE_DIR/history" ]] || [[ "$(wc -l <"$STATE_DIR/history")" -lt 2 ]]; then
    echo "[rollback] not enough history in $STATE_DIR/history; pass the image explicitly" >&2
    exit 1
  fi
  TARGET="$(tail -n 2 "$STATE_DIR/history" | head -n 1)"
fi

echo "[rollback] rolling back to $TARGET"
# Re-use the deploy script: it starts the image and runs the same checks.
exec scripts/deploy.sh "$TARGET"
