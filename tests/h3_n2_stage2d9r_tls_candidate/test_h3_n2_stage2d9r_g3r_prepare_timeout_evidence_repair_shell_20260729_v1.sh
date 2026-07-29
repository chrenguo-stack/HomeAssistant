#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
python "$ROOT/tools/h3_n2_stage2d9r_g3r_prepare_timeout_evidence_recorder_20260729_v1.py" > /tmp/evidence-boundary.json
python - <<'PY'
import json
v=json.load(open('/tmp/evidence-boundary.json'))
assert v['state']=='SOURCE_ONLY_NO_BOARD_OR_NETWORK_OPERATION'
assert v['authorization_created'] is False
assert v['physical_request_created'] is False
assert v['board_operation'] is False
assert v['serial_operation'] is False
assert v['network_operation'] is False
PY
! find "$ROOT" -iname '*physical*d2*request*07*.json' -print -quit | grep .
! find "$ROOT" -iname '*authorization*07*.json' -print -quit | grep .
