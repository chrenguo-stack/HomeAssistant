#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
export PYTHONDONTWRITEBYTECODE=1
python3 -B -m unittest tests.h3_n2_stage2d9r_tls_candidate.test_h3_n2_stage2d9r_g3r_d2_17_g07_target_mac_static_check_acceptance_20260731_v1
python3 -B "$ROOT/tools/h3_n2_stage2d9r_g3r_d2_17_g07_target_mac_static_check_acceptance_contract_20260731_v1.py"
! grep -R --line-number --fixed-strings '/Users/' "$ROOT/docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g07-target-mac-static-check-pass-20260731-v1.json" "$ROOT/docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g07-physical-execution-pending-20260731-v1.json" "$ROOT/docs/development/h3-n2-stage2d9r-g3r-d2-17-g07-target-mac-static-check-acceptance-contract-20260731-v1.md"
! find "$ROOT" \( -type d -name __pycache__ -o -type f -name '*.pyc' \) -print -quit | grep -q .
