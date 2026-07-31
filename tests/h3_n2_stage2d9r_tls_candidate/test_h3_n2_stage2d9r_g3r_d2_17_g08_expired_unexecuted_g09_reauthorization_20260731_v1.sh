#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
PYTHONDONTWRITEBYTECODE=1 python3 -B "$ROOT/tools/h3_n2_stage2d9r_g3r_d2_17_g08_expired_unexecuted_g09_reauthorization_contract_20260731_v1.py"
PYTHONDONTWRITEBYTECODE=1 python3 -B "$ROOT/tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_17_g08_expired_unexecuted_g09_reauthorization_20260731_v1.py"
