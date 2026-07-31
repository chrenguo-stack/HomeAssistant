#!/bin/sh
set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 -B "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_17_g10_expired_unexecuted_g11_reauthorization_20260731_v1.py"
python3 -B "tools/h3_n2_stage2d9r_g3r_d2_17_g10_expired_unexecuted_g11_reauthorization_contract_20260731_v1.py" --now "2026-07-31T06:43:12Z"
