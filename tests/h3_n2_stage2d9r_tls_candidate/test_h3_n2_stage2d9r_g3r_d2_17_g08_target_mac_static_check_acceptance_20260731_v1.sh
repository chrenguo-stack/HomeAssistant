#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT"

PYTHONDONTWRITEBYTECODE=1 python3 -B \
  tools/h3_n2_stage2d9r_g3r_d2_17_g08_target_mac_static_check_acceptance_contract_20260731_v1.py
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_17_g08_target_mac_static_check_acceptance_20260731_v1.py

test -z "$(find . -type d -name __pycache__ -o -type f -name '*.pyc')"
