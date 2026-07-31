#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import types

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g17_main_sha_terminal_reconstruction_20260731_v1.py"
ACCEPTANCE = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g16-forensic-pass-main-sha-root-cause-20260731-v1.json"
DECISION = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g17-main-sha-terminal-reconstruction-pending-20260731-v1.json"

spec = importlib.util.spec_from_file_location("g17", TOOL)
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def expect_code(code: str, fn) -> None:
    try:
        fn()
    except m.G17Error as exc:
        assert exc.args[0] == code
    else:
        raise AssertionError("expected " + code)


def test_alias() -> None:
    head = "a" * 40
    original = {"repository_head_sha": head, "x": 1}
    repaired = m.authorization_with_main_sha_alias(original)
    assert repaired["main_sha"] == head
    assert original.get("main_sha") is None
    assert m.authorization_with_main_sha_alias({"repository_head_sha": head, "main_sha": head})["main_sha"] == head
    expect_code("AUTHORIZATION_REPOSITORY_HEAD_SHA_MISSING", lambda: m.authorization_with_main_sha_alias({}))
    expect_code("AUTHORIZATION_REPOSITORY_HEAD_SHA_INVALID", lambda: m.authorization_with_main_sha_alias({"repository_head_sha": "bad"}))
    expect_code("AUTHORIZATION_MAIN_SHA_ALIAS_CONFLICT", lambda: m.authorization_with_main_sha_alias({"repository_head_sha": head, "main_sha": "b" * 40}))

    seen = {}
    core = types.SimpleNamespace()
    def original_result_object(**kwargs):
        seen.update(kwargs)
        return {"status": "CONSUMED_PASS", "main_sha": kwargs["authorization"]["main_sha"]}
    core.result_object = original_result_object
    report = m.install_main_sha_result_alias_repair(core)
    value = core.result_object(authorization={"repository_head_sha": head})
    assert report == {
        "installed": True,
        "repair": "MAIN_SHA_AUTHORIZATION_ALIAS",
        "authorization_record_mutated": False,
        "repository_head_sha_required": True,
    }
    assert value["status"] == "CONSUMED_PASS"
    assert seen["authorization"]["main_sha"] == head


def test_subset_bindings() -> None:
    acceptance = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
    core = {
        "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g16-forensic-pass-acceptance-binding/1",
        "source_pr": acceptance["source_pr"],
        "source_head_sha": acceptance["source_head_sha"],
        "terminal_record_sha256": acceptance["terminal_record_sha256"],
        "forensic_export_sha256": acceptance["forensic_export_sha256"],
        "authorization_record_sha256": acceptance["authorization_record_sha256"],
        "authorization_marker_sha256": acceptance["authorization_marker_sha256"],
        "status": "PASS",
        "terminal_state": acceptance["g16_terminal_state"],
        "classification": acceptance["classification"],
        "secondary_failure_code": acceptance["secondary_failure_code"],
        "secondary_failure_detail": acceptance["secondary_failure_detail"],
        "g14_inner_authorization_marker_status": acceptance["g14_inner_authorization_marker_status"],
        "g14_outer_terminal_state": acceptance["g14_outer_terminal_state"],
        "g14_outer_inner_marker_relation": acceptance["g14_outer_inner_marker_relation"],
        "prepare_delivery_status": acceptance["prepare_delivery_status"],
        "verify_delivery_status": acceptance["verify_delivery_status"],
        "prepare_evidence_classification": acceptance["prepare_evidence_classification"],
        "panic_reset_loop_count": acceptance["reset_loop_count"],
        "all_physical_operation_flags_false": acceptance["all_physical_operation_flags_false"],
        "g14_runtime_mutated": acceptance["g14_runtime_mutated"],
        "g15_runtime_accessed": acceptance["g15_runtime_accessed"],
        "replay_permitted": acceptance["replay_permitted"],
    }
    assert m.canonical_sha256(core) == acceptance["acceptance_binding_sha256"]

    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    pending_core = {
        "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g17-terminal-reconstruction-pending-binding/1",
        "g16_acceptance_binding_sha256": decision["g16_acceptance_binding_sha256"],
        "g14_terminal_record_sha256": decision["g14_terminal_record_sha256"],
        "g14_inner_terminal_result_sha256": decision["g14_inner_terminal_result_sha256"],
        "g14_inner_marker_status": decision["g14_inner_marker_status"],
        "prepare_delivery_sha256": decision["prepare_delivery_evidence_sha256"],
        "verify_delivery_sha256": decision["verify_delivery_evidence_sha256"],
        "root_cause": decision["root_cause"],
        "repair": decision["repair"],
        "operation_scope": decision["closure_scope"],
        "board_operation_authorized": decision["board_operation_authorized"],
        "replay_authorized": decision["physical_execution_replay_authorized"],
        "physical_rerun_authorized": decision["physical_rerun_authorized"],
        "activate_authorized": decision["activate_operation_authorized"],
        "cleanup_authorized": decision["cleanup_operation_authorized"],
    }
    assert m.canonical_sha256(pending_core) == decision["pending_binding_sha256"]


def synthetic_terminal() -> dict:
    forensic = "f" * 64
    inner = "1" * 64
    prepare_sha = "2" * 64
    verify_sha = "3" * 64
    m.G16_FORENSIC_EXPORT_SHA256 = forensic
    m.G14_INNER_TERMINAL_RESULT_SHA256 = inner
    m.PREPARE_DELIVERY_EVIDENCE_SHA256 = prepare_sha
    m.VERIFY_DELIVERY_EVIDENCE_SHA256 = verify_sha
    value = {
        "status": "PASS",
        "forensic_export_sha256": forensic,
        "classification": "POST_VERIFY_RESULT_GENERATOR_FAILURE_HIDDEN_BY_GENERIC_FALLBACK",
        "secondary_failure_code": "KeyError",
        "secondary_failure_detail": "main_sha",
        "g14_inner_authorization_marker_status": "CONSUMED_PASS",
        "g14_outer_terminal_state": "CONSUMED_FAILED",
        "g14_outer_inner_marker_relation": "INNER_EXECUTION_PASS_OUTER_TERMINALIZATION_FAILED",
        "authorization_marker_fields": {"status": "CONSUMED_PASS", "terminal_result_sha256": inner},
        "result_fields": {"prepare_count": 1, "verify_count": 1},
        "prepare_delivery_fields": {"status": "DELIVERED", "exact_write_confirmed": True, "delivery_evidence_sha256": prepare_sha},
        "verify_delivery_fields": {"status": "DELIVERED", "exact_write_confirmed": True, "delivery_evidence_sha256": verify_sha},
        "prepare_evidence_fields": {"classification": "PREPARE_PASS"},
        "panic_evidence_fields": {"reset_loop_count": 0, "post_command_reset_count": 0},
        "all_physical_operation_flags_false": True,
        "g14_runtime_mutated": False,
    }
    value["terminal_record_sha256"] = m.canonical_sha256(value)
    m.G16_TERMINAL_RECORD_SHA256 = value["terminal_record_sha256"]
    return value


def test_reconstruction() -> None:
    terminal = synthetic_terminal()
    reconstructed = m.reconstruct_terminal(terminal)
    assert reconstructed["status"] == "PASS"
    assert reconstructed["physical_execution_outcome"] == "CONSUMED_PASS"
    assert reconstructed["physical_rerun_required"] is False
    assert reconstructed["outer_terminalization_defect_only"] is True
    digest = reconstructed.pop("terminal_record_sha256")
    assert m.canonical_sha256(reconstructed) == digest

    terminal = synthetic_terminal()
    terminal["panic_evidence_fields"]["reset_loop_count"] = 1
    terminal["terminal_record_sha256"] = m.canonical_sha256({k: v for k, v in terminal.items() if k != "terminal_record_sha256"})
    m.G16_TERMINAL_RECORD_SHA256 = terminal["terminal_record_sha256"]
    expect_code("RESET_LOOP_OBSERVED", lambda: m.reconstruct_terminal(terminal))


def test_source_boundary() -> None:
    boundary = m.source_boundary()
    assert boundary["physical_rerun_authorized"] is False
    assert boundary["replay_permitted"] is False
    for key, value in boundary.items():
        if key.endswith("_operation") or key.endswith("_executed") or key.endswith("_enumeration"):
            assert value is False
    source = TOOL.read_text(encoding="utf-8")
    for forbidden in ("import serial", "import subprocess", "import socket", "esptool.main", "mosquitto"):
        assert forbidden not in source


if __name__ == "__main__":
    test_alias()
    test_subset_bindings()
    test_reconstruction()
    test_source_boundary()
    print(json.dumps({"status": "PASS", "suite": "g16-pass-g17-main-sha-terminal-reconstruction"}, sort_keys=True))
