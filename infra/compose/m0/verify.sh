#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

export GH_MQTT_PORT_EXTERNAL="${GH_MQTT_PORT_EXTERNAL:-18884}"
export GH_SIM_INITIAL_DELAY_S="${GH_SIM_INITIAL_DELAY_S:-1}"
export GH_SIM_INTERVAL_S="${GH_SIM_INTERVAL_S:-0.5}"
export GH_SIM_DUPLICATE_EVERY="${GH_SIM_DUPLICATE_EVERY:-2}"
export GH_SIM_INVALID_EVERY="${GH_SIM_INVALID_EVERY:-3}"

compose() {
  docker compose -f docker-compose.yml "$@"
}

cleanup() {
  local status=$?
  if (( status != 0 )); then
    echo "M0 verification failed; service logs follow:" >&2
    compose logs --no-color >&2 || true
  fi
  compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  exit "${status}"
}
trap cleanup EXIT

wait_for_topic() {
  local topic="$1"
  local attempts="${2:-30}"
  local output

  for ((i = 1; i <= attempts; i++)); do
    if output="$(compose exec -T mosquitto \
      mosquitto_sub -h 127.0.0.1 -t "${topic}" -C 1 -W 2 2>/dev/null)"; then
      if [[ -n "${output}" ]]; then
        printf '%s' "${output}"
        return 0
      fi
    fi
    sleep 1
  done

  echo "Timed out waiting for retained topic: ${topic}" >&2
  return 1
}

compose down --volumes --remove-orphans >/dev/null 2>&1 || true
compose up --detach --build mosquitto manager simulator

node_id="node_01HZX7AQ5FJ3"
base="gh/v1/devsystem/state/${node_id}"

canonical="$(wait_for_topic "${base}/telemetry")"
availability="$(wait_for_topic "${base}/availability")"
diagnostic="$(wait_for_topic "${base}/diagnostic")"

CANONICAL="${canonical}" AVAILABILITY="${availability}" DIAGNOSTIC="${diagnostic}" \
python3 - <<'PY'
import json
import os

canonical = json.loads(os.environ["CANONICAL"])
availability = json.loads(os.environ["AVAILABILITY"])
diagnostic = json.loads(os.environ["DIAGNOSTIC"])

assert canonical["schema"] == "gh.telemetry/1"
assert canonical["node_id"] == "node_01HZX7AQ5FJ3"
assert canonical["measurements"]["air_humidity_pct"] <= 100
assert canonical["received_at"].endswith("Z")

assert availability["schema"] == "gh.availability/1"
assert availability["node_id"] == canonical["node_id"]
assert availability["state"] == "online"

assert diagnostic["schema"] == "gh.diagnostic/1"
assert diagnostic["node_id"] == canonical["node_id"]
assert diagnostic["state"] == "invalid_telemetry"
assert "schema validation failed" in diagnostic["message"]
PY

echo "M0 vertical slice verified: telemetry, availability and diagnostics are correct."
