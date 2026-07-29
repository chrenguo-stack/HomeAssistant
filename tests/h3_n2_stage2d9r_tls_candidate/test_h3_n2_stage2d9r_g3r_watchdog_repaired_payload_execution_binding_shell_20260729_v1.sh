#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
OUTPUT=$(PYTHON_BIN=python3 sh "$ROOT/tools/run_stage2d9r_g3r_watchdog_repaired_payload_physical_d2_20260729_v1.sh")
printf '%s\n' "$OUTPUT" | grep -q '"authorization_created": false'
printf '%s\n' "$OUTPUT" | grep -q '"board_operation": false'
printf '%s\n' "$OUTPUT" | grep -q '"repository_head_enforced": false'
printf '%s\n' "$OUTPUT" | grep -q '"execution_closure_role": "BLOCKING"'
printf '%s\n' "$OUTPUT" | grep -q '"d2_request_id": "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260729-10"'
! find "$ROOT" -type f \( -iname '*authorization*10*.json' -o -iname '*physical-d2-authorization-10*.json' \) | grep -q .
