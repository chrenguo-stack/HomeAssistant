#!/bin/sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)"
PYTHONDONTWRITEBYTECODE=1 python3 -B "$ROOT/tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_17_g13_consumed_package_mode_g14_repair_20260731_v1.py"
