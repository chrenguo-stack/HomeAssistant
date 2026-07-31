#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
g16 = importlib.import_module(
    "h3_n2_stage2d9r_g3r_d2_17_g16_marker_state_tolerant_forensic_export_20260731_v1"
)
g15 = importlib.import_module(
    "h3_n2_stage2d9r_g3r_d2_17_g15_post_verify_terminalization_forensic_export_20260731_v1"
)


def canonical(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o600)


def build_runtime(root: Path, marker_status: str) -> tuple[Path, Path]:
    physical = root / "D2_17_G14_PHYSICAL_EXECUTION_20260731_01"
    physical.mkdir(parents=True, mode=0o700)
    result = {
        "schema": "synthetic-result/1",
        "status": "CONSUMED_FAILED",
        "terminal_state": "CONSUMED_FAILED",
        "failure_code": "POST_CLAIM_EXECUTION_FAILED",
        "primary_failure_code": "POST_CLAIM_EXECUTION_FAILED",
        "secondary_failure_code": "KeyError",
        "secondary_failure_detail": "repository_head_sha",
        "terminalization_fallback_used": True,
        "prepare_count": 1,
        "verify_count": 1,
        "terminal_result_sha256": "a" * 64,
    }
    result_path = physical / "D2_17_G14_PHYSICAL_RESULT.json"
    write_json(result_path, result)
    g15.G14_PHYSICAL_RESULT_SHA256 = g15.sha(result_path)

    marker_name = hashlib.sha256(g15.D2_REQUEST_ID.encode()).hexdigest() + ".json"
    marker_path = root / "authorization-state-g14" / marker_name
    marker = {
        "schema": "synthetic-marker/1",
        "status": marker_status,
        "terminal_result_sha256": "a" * 64,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
    }
    write_json(marker_path, marker)
    g15.G14_AUTHORIZATION_MARKER_SHA256 = g15.sha(marker_path)

    terminal_core = {
        "decision_id": g15.G14_DECISION_ID,
        "d2_request_id": g15.D2_REQUEST_ID,
        "status": "FAIL",
        "terminal_state": "CONSUMED_FAILED",
        "failure_code": "POST_CLAIM_EXECUTION_FAILED",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "physical_result_sha256": g15.G14_PHYSICAL_RESULT_SHA256,
        "authorization_marker_sha256": g15.G14_AUTHORIZATION_MARKER_SHA256,
        "authorization_record_sha256": g15.G14_AUTHORIZATION_RECORD_SHA256,
        "flash_operation": True,
        "prepare_executed": True,
        "verify_executed": True,
        "recovery_executed": False,
        "activate_executed": False,
        "cleanup_executed": False,
    }
    terminal = dict(terminal_core)
    terminal["terminal_record_sha256"] = canonical(terminal_core)
    terminal_path = physical / "D2_17_G14_PHYSICAL_DECISION_TERMINAL.json"
    write_json(terminal_path, terminal)
    g15.G14_TERMINAL_SHA256 = terminal["terminal_record_sha256"]
    return root, terminal_path


def test_consumed_pass_marker_is_exported() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        runtime, terminal = build_runtime(Path(temporary), "CONSUMED_PASS")
        value = g16.export(runtime, terminal)
        assert value["status"] == "PASS"
        assert value["g14_inner_authorization_marker_status"] == "CONSUMED_PASS"
        assert value["g14_outer_inner_marker_relation"] == (
            "INNER_EXECUTION_PASS_OUTER_TERMINALIZATION_FAILED"
        )
        assert value["secondary_failure_code"] == "KeyError"
        assert value["secondary_failure_detail"] == "repository_head_sha"
        observed = value["forensic_export_sha256"]
        core = dict(value)
        core.pop("forensic_export_sha256")
        assert canonical(core) == observed
        for key in (
            "board_operation", "usb_enumeration", "serial_operation",
            "esptool_operation", "flash_operation", "physical_nvs_operation",
            "network_operation", "broker_started", "prepare_executed",
            "verify_executed", "recovery_executed", "activate_executed",
            "cleanup_executed", "g14_runtime_mutated",
        ):
            assert value[key] is False


def test_consumed_failed_marker_remains_supported() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        runtime, terminal = build_runtime(Path(temporary), "CONSUMED_FAILED")
        value = g16.export(runtime, terminal)
        assert value["g14_outer_inner_marker_relation"] == (
            "INNER_AND_OUTER_CONSUMED_FAILED"
        )


def test_unknown_marker_state_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        runtime, terminal = build_runtime(Path(temporary), "UNKNOWN")
        try:
            g16.export(runtime, terminal)
        except g16.G16ForensicError as exc:
            assert exc.args[0] == "G14_AUTHORIZATION_MARKER_STATE_UNSUPPORTED"
        else:
            raise AssertionError("unknown marker state accepted")


if __name__ == "__main__":
    test_consumed_pass_marker_is_exported()
    test_consumed_failed_marker_remains_supported()
    test_unknown_marker_state_fails_closed()
    print("PASS")
