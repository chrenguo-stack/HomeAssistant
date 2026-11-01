#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "${ROOT_DIR}/secrets.yaml" ]]; then
  echo "Missing ${ROOT_DIR}/secrets.yaml" >&2
  echo "Copy secrets.n1.example.yaml to secrets.yaml and set n1_mqtt_broker to the T1 LAN IP." >&2
  exit 1
fi

export RC2_CONFIG="f1_0_rc2_n1.yml"
exec bash "${ROOT_DIR}/tools/rc2.sh" "$@"
