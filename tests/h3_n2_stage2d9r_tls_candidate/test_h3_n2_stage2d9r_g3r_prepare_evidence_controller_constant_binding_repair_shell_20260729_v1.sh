#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
OUTPUT=$(PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/tools/h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_physical_d2_wrapper_20260729_v1.py")
printf '%s\n' "$OUTPUT" | grep -q 'SOURCE_ONLY_REQUIRES_NEW_EXACT_PHYSICAL_D2_AUTHORIZATION'
printf '%s\n' "$OUTPUT" | grep -q '"d2_request_id": "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260729-08"'
printf '%s\n' "$OUTPUT" | grep -q '"authorization_created": false'
printf '%s\n' "$OUTPUT" | grep -q '"board_operation": false'
test ! -e "$ROOT/physical-d2-authorization-08.json"
test ! -e "$ROOT/PHYSICAL_D2_AUTHORIZATION_08.json"
