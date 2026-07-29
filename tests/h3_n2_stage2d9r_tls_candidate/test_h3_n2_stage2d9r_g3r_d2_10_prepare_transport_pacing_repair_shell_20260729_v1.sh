#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT="$(python3 "$ROOT/tools/h3_n2_stage2d9r_g3r_prepare_transport_pacing_repair_20260729_v1.py")"

python3 - "$OUTPUT" <<'PY'
import json
import sys

value = json.loads(sys.argv[1])
assert value["status"] == "SOURCE_ONLY_REQUIRES_NEW_EXACT_D2_EXECUTION_BINDING"
assert value["root_cause_code"] == "USB_SERIAL_JTAG_RX_BURST_OVERRUN_AFTER_NONBLOCKING_REPAIR"
assert value["paced_chunk_bytes"] == 64
assert value["inter_chunk_delay_ms"] == 100
for key in (
    "physical_request_created",
    "physical_authorization_created",
    "board_operation",
    "usb_enumeration",
    "serial_operation",
    "esptool_operation",
    "flash_operation",
    "network_operation",
):
    assert value[key] is False
PY
