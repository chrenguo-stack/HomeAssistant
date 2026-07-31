#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
TOOL = REPO / "tools/h3_n2_stage2d9r_g3r_d2_17_g15_post_verify_terminalization_forensic_export_20260731_v1.py"

def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)

spec = importlib.util.spec_from_file_location("g15", TOOL)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

with tempfile.TemporaryDirectory(prefix="g15-forensic-test-") as td:
    root = Path(td) / "runtime"
    root.mkdir(mode=0o700)
    physical = root / "D2_17_G14_PHYSICAL_EXECUTION_20260731_01"
    physical.mkdir(mode=0o700)

    result = {
        "schema": "synthetic-result/1",
        "status": "CONSUMED_FAILED",
        "terminal_state": "CONSUMED_FAILED",
        "failure_code": "POST_CLAIM_EXECUTION_FAILED",
        "primary_failure_code": "POST_CLAIM_EXECUTION_FAILED",
        "secondary_failure_code": "RuntimeError",
        "secondary_failure_detail": "RESULT_EVIDENCE_FINALIZATION_FAILED",
        "terminalization_fallback_used": True,
        "prepare_count": 1,
        "verify_count": 1,
        "prepare_transport_delivery_status": "DELIVERED",
        "verify_transport_delivery_status": "DELIVERED",
        "recovery_attempted": False,
        "recovery_succeeded": False,
        "terminal_result_sha256": "a" * 64,
    }
    result_path = physical / "D2_17_G14_PHYSICAL_RESULT.json"
    write_json(result_path, result)
    module.G14_PHYSICAL_RESULT_SHA256 = module.sha(result_path)

    marker = {"schema": "synthetic-marker/1", "status": "CONSUMED_FAILED"}
    marker_name = hashlib.sha256(module.D2_REQUEST_ID.encode()).hexdigest() + ".json"
    marker_path = root / "authorization-state-g14" / marker_name
    write_json(marker_path, marker)
    module.G14_AUTHORIZATION_MARKER_SHA256 = module.sha(marker_path)

    guard = {
        "schema": "synthetic-guard/1",
        "status": "TERMINALIZED",
        "failure_code": "RESULT_EVIDENCE_FINALIZATION_FAILED",
        "terminal_result_sha256": "a" * 64,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
    }
    write_json(physical / "terminalization-evidence" / "terminalization-guard.json", guard)
    write_json(physical / "delivery-evidence" / "prepare-transport-delivery.json", {
        "schema": "delivery/1", "phase": "prepare", "status": "DELIVERED",
        "failure_code": None, "attempted_chunk_count": 2, "completed_chunk_count": 2,
        "exact_write_confirmed": True, "delivery_evidence_sha256": "b" * 64,
    })
    write_json(physical / "delivery-evidence" / "verify-transport-delivery.json", {
        "schema": "delivery/1", "phase": "verify", "status": "DELIVERED",
        "failure_code": None, "attempted_chunk_count": 2, "completed_chunk_count": 2,
        "exact_write_confirmed": True, "delivery_evidence_sha256": "c" * 64,
    })

    terminal = {
        "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g14-physical-decision-terminal/1",
        "status": "FAIL",
        "terminal_state": "CONSUMED_FAILED",
        "failure_code": "POST_CLAIM_EXECUTION_FAILED",
        "failure_stage": None,
        "decision_id": module.G14_DECISION_ID,
        "d2_request_id": module.D2_REQUEST_ID,
        "authorization_claimed": True,
        "authorization_consumed": True,
        "authorization_record_sha256": module.G14_AUTHORIZATION_RECORD_SHA256,
        "physical_result_sha256": module.G14_PHYSICAL_RESULT_SHA256,
        "authorization_marker_sha256": module.G14_AUTHORIZATION_MARKER_SHA256,
        "flash_operation": True,
        "prepare_executed": True,
        "verify_executed": True,
        "recovery_executed": False,
        "activate_executed": False,
        "cleanup_executed": False,
    }
    terminal["terminal_record_sha256"] = canonical(terminal)
    module.G14_TERMINAL_SHA256 = terminal["terminal_record_sha256"]
    terminal_path = Path(td) / "outer-terminal.json"
    write_json(terminal_path, terminal)

    summary = module.export(root, terminal_path)
    assert summary["status"] == "PASS"
    assert summary["classification"] == "POST_VERIFY_RESULT_GENERATOR_FAILURE_HIDDEN_BY_GENERIC_FALLBACK"
    assert summary["exact_secondary_failure_available"] is True
    assert summary["secondary_failure_detail"] == "RESULT_EVIDENCE_FINALIZATION_FAILED"
    assert summary["prepare_delivery_fields"]["status"] == "DELIVERED"
    assert summary["verify_delivery_fields"]["status"] == "DELIVERED"
    assert summary["board_operation"] is False
    assert summary["flash_operation"] is False
    assert summary["private_paths_included"] is False
    assert summary["raw_logs_included"] is False
    assert summary["command_material_included"] is False
    assert summary["secret_values_included"] is False

print(json.dumps({
    "status": "PASS",
    "g14_generic_fallback_classified": True,
    "secondary_failure_preserved": True,
    "allowlisted_json_only": True,
    "all_physical_operation_flags_false": True,
}, sort_keys=True))
