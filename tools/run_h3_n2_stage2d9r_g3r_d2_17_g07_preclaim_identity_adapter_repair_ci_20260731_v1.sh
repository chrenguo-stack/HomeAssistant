#!/bin/sh
set -eu
: "${D2_17_EXECUTION_ROOT:?D2_17_EXECUTION_ROOT required}"
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest \
  tests.h3_n2_stage2d9r_tls_candidate.test_h3_n2_stage2d9r_g3r_d2_17_g07_preclaim_identity_adapter_repair_20260731_v1
test -z "$(find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -print -quit)"
