#!/bin/bash
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)"
exec python3 -B "$ROOT/tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_d2_17_g17_fail_g18_semantic_digest_repair_20260801_v1.py"
