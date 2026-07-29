#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
LAUNCHER="$ROOT/tools/run_stage2d9r_g3r_d2_11_prepare_transport_pacing_physical_d2_20260729_v1.sh"

STATUS=$("$LAUNCHER")
printf '%s\n' "$STATUS" | grep -q '"status": "SOURCE_ONLY_REQUIRES_NEW_EXACT_D2_11_AUTHORIZATION"'
printf '%s\n' "$STATUS" | grep -q '"physical_authorization_created": false'
printf '%s\n' "$STATUS" | grep -q '"board_operation": false'
printf '%s\n' "$STATUS" | grep -q '"usb_enumeration": false'
printf '%s\n' "$STATUS" | grep -q '"serial_operation": false'
printf '%s\n' "$STATUS" | grep -q '"flash_operation": false'
printf '%s\n' "$STATUS" | grep -q '"network_operation": false'

if "$LAUNCHER" invalid >/dev/null 2>&1; then
  echo "invalid action unexpectedly succeeded" >&2
  exit 1
fi

echo "D2_11_SOURCE_ONLY_SHELL_CONTRACT=PASS"
