#!/bin/sh
set -eu
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest \
  tests.h3_n2_stage2d9r_tls_candidate.test_h3_n2_stage2d9r_g3r_d2_17_terminal_record_semantic_digest_repair_20260730_v1
find tools tests -type f \( -name '*.pyc' -o -name '*.pyo' \) -print -quit | grep -q . && exit 1 || true
printf '%s\n' 'D2_17_TERMINAL_RECORD_SEMANTIC_DIGEST_REPAIR_SHELL_PASS'
