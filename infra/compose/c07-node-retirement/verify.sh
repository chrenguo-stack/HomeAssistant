#!/usr/bin/env bash
set -euo pipefail

compose_file="infra/compose/c07-node-retirement/docker-compose.yml"
source_dir="infra/compose/c07-node-retirement/homeassistant"
ha_config="$(mktemp -d /tmp/c07-homeassistant-XXXXXX)"
project_name="c07-node-retirement-${GITHUB_RUN_ID:-local}-${RANDOM}"

export C07_HA_CONFIG="$ha_config"
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
  rm -rf -- "$ha_config"
  exit "$status"
}
trap cleanup EXIT

mkdir -p "$ha_config/.storage" "$ha_config/custom_components"
cp "$source_dir/configuration.yaml" "$ha_config/configuration.yaml"
cp \
  "$source_dir/core.config_entries.json" \
  "$ha_config/.storage/core.config_entries"
cp -R \
  "$source_dir/custom_components/c07_retirement_probe" \
  "$ha_config/custom_components/c07_retirement_probe"
chmod 700 "$ha_config" "$ha_config/.storage"
chmod 600 "$ha_config/.storage/core.config_entries"

docker compose -f "$compose_file" config --quiet
docker compose -f "$compose_file" build tester
docker compose -f "$compose_file" up \
  --detach \
  --wait \
  --wait-timeout 180 \
  broker \
  homeassistant
docker compose -f "$compose_file" run --rm --no-deps tester
