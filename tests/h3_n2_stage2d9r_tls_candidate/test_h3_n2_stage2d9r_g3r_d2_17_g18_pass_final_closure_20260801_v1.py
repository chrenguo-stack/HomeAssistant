#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TERMINAL = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g18-target-mac-host-only-closure-pass-20260801-v1.json"
DECISION = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-final-closure-20260801-v1.json"

EXPECTED_TERMINAL_SHA256 = "30b3a16744b1127df04133c34efa661ce4cd05cc576635a180e079e8b380c855"
EXPECTED_CLOSURE_BINDING_SHA256 = "cb7f9924941a51874af9945434d3623eb850de7b06b6b2493f0acf2bf823bf78"


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


terminal = json.loads(TERMINAL.read_text(encoding="utf-8"))
assert terminal["terminal_record_sha256"] == EXPECTED_TERMINAL_SHA256
terminal_core = dict(terminal)
terminal_core.pop("terminal_record_sha256")
assert canonical_sha256(terminal_core) == EXPECTED_TERMINAL_SHA256

assert terminal["status"] == "PASS"
assert terminal["terminal_state"] == "D2_17_TARGET_MAC_HOST_ONLY_CLOSURE_RECONSTRUCTED_CONSUMED_PASS"
assert terminal["physical_execution_outcome"] == "CONSUMED_PASS"
assert terminal["authorization_created"] is True
assert terminal["authorization_claimed"] is True
assert terminal["authorization_consumed"] is True
assert terminal["d2_17_closure_complete"] is True
assert terminal["g16_terminal_semantic_binding_valid"] is True
assert terminal["g16_terminal_raw_digest_role"] == "PRE_POST_IMMUTABILITY_ONLY"
assert terminal["g16_terminal_semantic_digest_role"] == "CANONICAL_JSON_SELF_BINDING"
assert terminal["g16_runtime_read"] is True
assert terminal["g16_runtime_mutated"] is False
assert terminal["g14_runtime_accessed"] is False
assert terminal["g15_runtime_accessed"] is False
assert terminal["all_physical_operation_flags_false"] is True
assert terminal["physical_rerun_required"] is False
assert terminal["physical_rerun_authorized"] is False
assert terminal["replay_permitted"] is False
assert terminal["automatic_retry_permitted"] is False
assert terminal["failure_code"] is None

for key in (
    "board_operation",
    "usb_enumeration",
    "serial_operation",
    "esptool_operation",
    "flash_operation",
    "physical_nvs_operation",
    "network_operation",
    "broker_started",
    "prepare_executed",
    "verify_executed",
    "recovery_executed",
    "activate_executed",
    "cleanup_executed",
    "ready",
    "merge",
    "release",
    "tag",
    "deployment",
):
    assert terminal[key] is False, key

decision = json.loads(DECISION.read_text(encoding="utf-8"))
binding_core = {
    "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g18-final-closure-binding/1",
    "source_pr": decision["source_pr"],
    "source_head_sha": decision["source_head_sha"],
    "g18_terminal_record_sha256": decision["g18_terminal_record_sha256"],
    "g18_status": decision["g18_status"],
    "g18_terminal_state": decision["g18_terminal_state"],
    "physical_execution_outcome": decision["physical_execution_outcome"],
    "authorization_consumed": decision["authorization_consumed"],
    "d2_17_closure_complete": True,
    "g16_terminal_record_sha256": decision["g16_terminal_record_sha256"],
    "g17_terminal_record_sha256": decision["g17_terminal_record_sha256"],
    "reconstructed_physical_terminal_record_sha256": decision["reconstructed_physical_terminal_record_sha256"],
    "all_physical_operation_flags_false": decision["all_physical_operation_flags_false"],
    "physical_rerun_required": decision["physical_rerun_required"],
    "replay_permitted": decision["replay_permitted"],
}
assert canonical_sha256(binding_core) == EXPECTED_CLOSURE_BINDING_SHA256
assert decision["closure_binding_sha256"] == EXPECTED_CLOSURE_BINDING_SHA256
assert decision["state"] == "CLOSED"
assert decision["ready_authorized"] is False
assert decision["merge_authorized"] is False
assert decision["release_authorized"] is False
assert decision["tag_authorized"] is False
assert decision["deployment_authorized"] is False

print(json.dumps({"status": "PASS", "suite": "g18-final-closure"}, sort_keys=True))
