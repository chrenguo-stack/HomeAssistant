#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
export PYTHONDONTWRITEBYTECODE=1
python3 -B -m unittest tests.h3_n2_stage2d9r_tls_candidate.test_h3_n2_stage2d9r_g3r_d2_17_g06_nested_launcher_permission_independent_handoff_repair_20260730_v1
! find "$ROOT" \( -type d -name __pycache__ -o -type f -name '*.pyc' \) -print -quit | grep -q .
