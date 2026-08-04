#!/usr/bin/env bash
set -euo pipefail

compose_file="infra/compose/c06b2c-history-projection-e2e/docker-compose.yml"
artifact_dir="artifacts/c06b2c"
project_name="c06b2c-history-${GITHUB_RUN_ID:-local}-${RANDOM}"

export COMPOSE_PROJECT_NAME="$project_name"
export C06B2C_MANAGER_IMAGE="c06b2c-manager-${GITHUB_RUN_ID:-local}-${RANDOM}:test"
export GH_MANAGER_MQTT_PASSWORD
export GH_HA_MQTT_PASSWORD
export GH_TESTER_MQTT_PASSWORD
GH_MANAGER_MQTT_PASSWORD="$(openssl rand -hex 24)"
GH_HA_MQTT_PASSWORD="$(openssl rand -hex 24)"
GH_TESTER_MQTT_PASSWORD="$(openssl rand -hex 24)"

mkdir -p "$artifact_dir"
find "$artifact_dir" -mindepth 1 -maxdepth 1 -type f -delete

current_stage="initialize"
cleanup_done=false

write_execution() {
  local status="$1"
  local exit_code="$2"
  C06B2C_EXECUTION_STATUS="$status" \
  C06B2C_EXECUTION_EXIT_CODE="$exit_code" \
  C06B2C_EXECUTION_STAGE="$current_stage" \
  C06B2C_PROJECT_NAME="$project_name" \
  python - <<'PY'
import json
import os
from pathlib import Path

path = Path("artifacts/c06b2c/execution.json")
path.write_text(
    json.dumps(
        {
            "schema": "gh.c06b2c.execution/1",
            "status": os.environ["C06B2C_EXECUTION_STATUS"],
            "exit_code": int(os.environ["C06B2C_EXECUTION_EXIT_CODE"]),
            "last_stage": os.environ["C06B2C_EXECUTION_STAGE"],
            "compose_project": os.environ["C06B2C_PROJECT_NAME"],
            "isolated_github_runner": True,
            "host_ports_requested": False,
            "production_state_modified": False,
            "secret_values_included": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    ),
    encoding="utf-8",
)
PY
}

write_cleanup() {
  local host_ports="$1"
  local containers volumes networks
  containers="$(docker ps -a --filter "name=${project_name}" --format '{{.ID}}' | wc -l | tr -d ' ')"
  volumes="$(docker volume ls --filter "name=${project_name}" --format '{{.Name}}' | wc -l | tr -d ' ')"
  networks="$(docker network ls --filter "name=${project_name}" --format '{{.Name}}' | wc -l | tr -d ' ')"
  C06B2C_REMAINING_CONTAINERS="$containers" \
  C06B2C_REMAINING_VOLUMES="$volumes" \
  C06B2C_REMAINING_NETWORKS="$networks" \
  C06B2C_HOST_PORTS="$host_ports" \
  python - <<'PY'
import json
import os
from pathlib import Path

values = {
    "remaining_test_containers": int(os.environ["C06B2C_REMAINING_CONTAINERS"]),
    "remaining_test_volumes": int(os.environ["C06B2C_REMAINING_VOLUMES"]),
    "remaining_test_networks": int(os.environ["C06B2C_REMAINING_NETWORKS"]),
    "host_ports_published": int(os.environ["C06B2C_HOST_PORTS"]),
}
path = Path("artifacts/c06b2c/cleanup.json")
path.write_text(
    json.dumps(
        {
            "schema": "gh.c06b2c.cleanup/1",
            **values,
            "cleanup_complete": all(value == 0 for value in values.values()),
            "production_services_modified": False,
            "secret_values_included": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    ),
    encoding="utf-8",
)
PY
}

published_port_count() {
  local ids=()
  mapfile -t ids < <(docker compose -f "$compose_file" ps -q)
  if [[ "${#ids[@]}" -eq 0 ]]; then
    printf '0\n'
    return
  fi
  docker inspect "${ids[@]}" | python -c '
import json, sys
containers = json.load(sys.stdin)
count = 0
for container in containers:
    ports = container.get("NetworkSettings", {}).get("Ports", {}) or {}
    for bindings in ports.values():
        if bindings:
            count += len(bindings)
print(count)
'
}

cleanup() {
  local status=$?
  trap - EXIT
  set +e
  local host_ports=0
  if [[ "$cleanup_done" != true ]]; then
    host_ports="$(published_port_count 2>/dev/null || printf '0')"
    if [[ "$status" -ne 0 ]]; then
      docker compose -f "$compose_file" logs --no-color \
        broker homeassistant manager observer >"$artifact_dir/failure-raw.log" 2>&1
      sed \
        -e "s/${GH_MANAGER_MQTT_PASSWORD}/[REDACTED]/g" \
        -e "s/${GH_HA_MQTT_PASSWORD}/[REDACTED]/g" \
        -e "s/${GH_TESTER_MQTT_PASSWORD}/[REDACTED]/g" \
        "$artifact_dir/failure-raw.log" >"$artifact_dir/failure.log"
      rm -f "$artifact_dir/failure-raw.log"
    fi
    docker compose -f "$compose_file" down --volumes --remove-orphans >/dev/null 2>&1
    write_cleanup "$host_ports"
  fi
  if [[ "$status" -eq 0 ]]; then
    write_execution passed 0
  else
    write_execution failed "$status"
  fi
  exit "$status"
}
trap cleanup EXIT

current_stage="validate-compose"
docker compose -f "$compose_file" config --quiet

current_stage="pull-images"
docker compose -f "$compose_file" pull broker ha-config-init homeassistant

current_stage="build-manager-image"
docker compose -f "$compose_file" build manager

current_stage="record-image-identities"
export C06B2C_MOSQUITTO_IMAGE_ID
export C06B2C_MOSQUITTO_REPO_DIGESTS
export C06B2C_HA_IMAGE_ID
export C06B2C_HA_REPO_DIGESTS
export C06B2C_MANAGER_IMAGE_ID
C06B2C_MOSQUITTO_IMAGE_ID="$(docker image inspect eclipse-mosquitto:2.0.22 --format '{{.Id}}')"
C06B2C_MOSQUITTO_REPO_DIGESTS="$(docker image inspect eclipse-mosquitto:2.0.22 --format '{{json .RepoDigests}}')"
C06B2C_HA_IMAGE_ID="$(docker image inspect ghcr.io/home-assistant/home-assistant:2026.7.1 --format '{{.Id}}')"
C06B2C_HA_REPO_DIGESTS="$(docker image inspect ghcr.io/home-assistant/home-assistant:2026.7.1 --format '{{json .RepoDigests}}')"
C06B2C_MANAGER_IMAGE_ID="$(docker image inspect "$C06B2C_MANAGER_IMAGE" --format '{{.Id}}')"
python - <<'PY'
import json
import os
from pathlib import Path

path = Path("artifacts/c06b2c/images.json")
path.write_text(
    json.dumps(
        {
            "schema": "gh.c06b2c.images/1",
            "mosquitto": {
                "reference": "eclipse-mosquitto:2.0.22",
                "image_id": os.environ["C06B2C_MOSQUITTO_IMAGE_ID"],
                "repo_digests": json.loads(os.environ["C06B2C_MOSQUITTO_REPO_DIGESTS"]),
            },
            "homeassistant": {
                "reference": "ghcr.io/home-assistant/home-assistant:2026.7.1",
                "image_id": os.environ["C06B2C_HA_IMAGE_ID"],
                "repo_digests": json.loads(os.environ["C06B2C_HA_REPO_DIGESTS"]),
            },
            "manager": {
                "reference": os.environ["C06B2C_MANAGER_IMAGE"],
                "image_id": os.environ["C06B2C_MANAGER_IMAGE_ID"],
                "built_from_repository_head": True,
            },
            "secret_values_included": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    ),
    encoding="utf-8",
)
PY

current_stage="start-broker-and-homeassistant"
docker compose -f "$compose_file" up \
  --detach \
  --wait \
  --wait-timeout 240 \
  broker \
  homeassistant

current_stage="prepare-mqtt-target-entities"
docker compose -f "$compose_file" run --rm --no-deps \
  -e GH_C06B2C_PHASE=prepare \
  tester

current_stage="initialize-manager-database"
docker compose -f "$compose_file" run --rm --no-deps manager-db-init

current_stage="start-mqtt-observer"
docker compose -f "$compose_file" up --detach observer
for _ in $(seq 1 120); do
  [[ -s "$artifact_dir/observer-ready.json" ]] && break
  sleep 0.5
done
test -s "$artifact_dir/observer-ready.json"

current_stage="start-real-manager-runtime"
docker compose -f "$compose_file" up --detach manager

current_stage="wait-for-initial-mqtt-result"
docker compose -f "$compose_file" wait observer

test -s "$artifact_dir/mqtt-capture.json"
current_stage="classify-initial-mqtt-result"
python - <<'PY'
import json
from pathlib import Path

capture = json.loads(Path("artifacts/c06b2c/mqtt-capture.json").read_text(encoding="utf-8"))
result = capture["result"]
print(
    "C06B2C_INITIAL_RESULT="
    + json.dumps(
        {
            "status": result.get("status"),
            "code": result.get("code"),
            "detail": result.get("detail"),
            "request_id": result.get("request_id"),
            "projection_hash": result.get("projection_hash"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
)
if result.get("status") != "verified":
    raise SystemExit(42)
PY

current_stage="verify-initial-end-to-end-closure"
docker compose -f "$compose_file" run --rm --no-deps \
  -e GH_C06B2C_PHASE=initial \
  tester

current_stage="verify-monotonic-and-idempotent-rules"
docker compose -f "$compose_file" run --rm --no-deps \
  -e GH_C06B2C_PHASE=monotonic \
  tester

current_stage="restart-homeassistant"
docker compose -f "$compose_file" restart homeassistant

current_stage="verify-restart-persistence"
docker compose -f "$compose_file" run --rm --no-deps \
  -e GH_C06B2C_PHASE=restart \
  tester

current_stage="verify-no-host-ports"
host_ports="$(published_port_count)"
test "$host_ports" = "0"

current_stage="destroy-isolated-stack"
docker compose -f "$compose_file" down --volumes --remove-orphans
write_cleanup "$host_ports"
cleanup_done=true

current_stage="complete"
write_execution passed 0
trap - EXIT
