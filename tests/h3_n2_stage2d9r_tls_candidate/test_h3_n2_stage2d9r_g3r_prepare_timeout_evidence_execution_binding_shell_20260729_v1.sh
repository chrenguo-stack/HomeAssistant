#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
OUTPUT=$(PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/tools/h3_n2_stage2d9r_g3r_prepare_timeout_evidence_physical_d2_wrapper_20260729_v1.py")
printf '%s\n' "$OUTPUT" | grep -q 'SOURCE_ONLY_REQUIRES_NEW_EXACT_PHYSICAL_D2_AUTHORIZATION'
printf '%s\n' "$OUTPUT" | grep -q '"authorization_created": false'
printf '%s\n' "$OUTPUT" | grep -q '"board_operation": false'
printf '%s\n' "$OUTPUT" | grep -q '"network_operation": false'
test ! -e "$ROOT/PHYSICAL_D2_AUTHORIZATION_07.json"
test ! -e "$ROOT/physical-d2-authorization-07.json"
test ! -e "$ROOT/tools/PHYSICAL_D2_AUTHORIZATION_07.json"
test ! -e "$ROOT/tools/physical-d2-authorization-07.json"
