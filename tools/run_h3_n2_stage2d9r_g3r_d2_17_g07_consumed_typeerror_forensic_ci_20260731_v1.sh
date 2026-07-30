#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
export PYTHONDONTWRITEBYTECODE=1
cd "$ROOT"
python3 -B -m unittest tests.h3_n2_stage2d9r_tls_candidate.test_h3_n2_stage2d9r_g3r_d2_17_g07_consumed_typeerror_forensic_20260731_v1
! find "$ROOT" \( -type d -name __pycache__ -o -type f -name '*.pyc' -o -type f -name '*.pyo' \) -print -quit | grep -q .
