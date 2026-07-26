#!/usr/bin/env bash
set -euo pipefail

compose_file="infra/compose/c07-node-retirement/docker-compose.yml"
project_name="c07-node-retirement-${GITHUB_RUN_ID:-local}-${RANDOM}"

export COMPOSE_PROJECT_NAME="$project_name"
export GH_DYNSEC_ADMIN_PASSWORD
GH_DYNSEC_ADMIN_PASSWORD="$(openssl rand -hex 24)"

cleanup() {
  status=$?
  trap - EXIT
  set +e
  if [[ "$status" -ne 0 ]]; then
    docker compose -f "$compose_file" logs --no-color broker homeassistant tester
  fi
  docker compose -f "$compose_file" down --volumes --remove-orphans
  exit "$status"
}
trap cleanup EXIT

docker compose -f "$compose_file" config --quiet
docker compose -f "$compose_file" build tester
docker compose -f "$compose_file" up \
  --detach \
  --wait \
  --wait-timeout 180 \
  broker \
  homeassistant
docker compose -f "$compose_file" run --rm --no-deps tester
