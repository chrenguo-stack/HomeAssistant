#!/bin/sh
set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 -B -m unittest \
  tests.h3_n2_stage2d9r_tls_candidate.test_h3_n2_stage2d9r_g3r_d2_17_g05_permission_independent_shell_invoke_repair_20260730_v1
