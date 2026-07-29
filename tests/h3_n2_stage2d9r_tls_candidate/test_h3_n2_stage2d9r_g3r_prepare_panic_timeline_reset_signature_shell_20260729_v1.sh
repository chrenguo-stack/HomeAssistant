#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
OUTPUT=$(PYTHON_BIN=python3 "$ROOT/tools/run_stage2d9r_g3r_prepare_panic_timeline_reset_signature_physical_d2_20260729_v1.sh")
printf '%s\n' "$OUTPUT" | grep -q '"authorization_created": false'
printf '%s\n' "$OUTPUT" | grep -q '"board_operation": false'
printf '%s\n' "$OUTPUT" | grep -q '"d2_request_id": "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260729-09"'
! find "$ROOT" -type f \( -iname '*authorization*09*' -o -iname '*physical-d2-authorization-09*' \) | grep -q .
