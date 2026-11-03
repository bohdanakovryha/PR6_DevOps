#!/usr/bin/env bash
# Run the same stages as the CI/CD pipeline on a local / training Linux machine:
#   1. unit tests (pytest)  2. image build tagged with the commit SHA  3. deploy + checks
# Any failing stage stops the pipeline, so a red test blocks the deployment.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

REPORT_DIR="${REPORT_DIR:-reports}"
IMAGE_REPO="${IMAGE_REPO:-pr6-devops}"
COMMIT="$(git rev-parse --short HEAD)"
IMAGE="$IMAGE_REPO:$COMMIT"
mkdir -p "$REPORT_DIR"

stage() { printf '\n========== %s ==========\n' "$*"; }
trap 'printf "\n[pipeline] FAILED at stage: %s\n" "$CURRENT_STAGE"' ERR

CURRENT_STAGE="test"
stage "1/3 test: pytest"
python3 -m pytest -q -p no:cacheprovider --junitxml="$REPORT_DIR/unit-tests.xml"

CURRENT_STAGE="build"
stage "2/3 build: $IMAGE"
# DOCKER_BUILD_FLAGS may add e.g. a PyPI mirror: --build-arg PIP_INDEX_URL=...
# shellcheck disable=SC2086
docker build -q ${DOCKER_BUILD_FLAGS:-} \
  --build-arg APP_VERSION="${APP_VERSION:-1.0.0}" \
  --build-arg GIT_COMMIT="$COMMIT" \
  -t "$IMAGE" .

CURRENT_STAGE="deploy"
stage "3/3 deploy: $IMAGE"
scripts/deploy.sh "$IMAGE"

printf '\n[pipeline] SUCCESS: %s deployed\n' "$IMAGE"
