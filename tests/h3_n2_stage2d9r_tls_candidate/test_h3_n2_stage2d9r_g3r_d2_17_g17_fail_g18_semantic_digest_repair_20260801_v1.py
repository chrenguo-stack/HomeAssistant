#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g18_semantic_terminal_file_verification_20260801_v1.py"
ACCEPTANCE = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g17-raw-vs-semantic-digest-failure-20260801-v1.json"
DECISION = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g18-semantic-record-digest-successor-pending-20260801-v1.json"

spec = importlib.util.spec_from_file_location("g18", TOOL)
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def expect_code(code: str, fn) -> None:
    try:
        fn()
    except m.G18Error as exc:
        assert exc.args[0] == code
    else:
        raise AssertionError("expected " + code)


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
        "authorization_marker_fields": {
            "status": "CONSUMED_PASS",
            "terminal_result_sha256": inner,
        },
        "result_fields": {"prepare_count": 1, "verify_count": 1},
        "prepare_delivery_fields": {
            "status": "DELIVERED",
            "exact_write_confirmed": True,
            "delivery_evidence_sha256": prepare_sha,
        },
        "verify_delivery_fields": {
            "status": "DELIVERED",
            "exact_write_confirmed": True,
            "delivery_evidence_sha256": verify_sha,
        },
        "prepare_evidence_fields": {"classification": "PREPARE_PASS"},
        "panic_evidence_fields": {
            "reset_loop_count": 0,
            "post_command_reset_count": 0,
        },
        "all_physical_operation_flags_false": True,
        "g14_runtime_mutated": False,
    }
    value["terminal_record_sha256"] = m.canonical_sha256(value)
    m.G16_TERMINAL_RECORD_SHA256 = value["terminal_record_sha256"]
    return value


def test_raw_and_semantic_digest_domains_are_independent() -> None:
    terminal = synthetic_terminal()
    raw_file_sha = "a" * 64
    assert raw_file_sha != terminal["terminal_record_sha256"]
    report = m.verify_terminal_file_semantics(raw_file_sha, terminal)
    assert report["semantic_binding_valid"] is True
    assert report["raw_file_sha256"] == raw_file_sha
    assert report["semantic_record_sha256"] == terminal["terminal_record_sha256"]
    assert report["raw_equals_semantic_record"] is False
    assert report["raw_digest_role"] == "PRE_POST_IMMUTABILITY_ONLY"
    assert report["semantic_digest_role"] == "CANONICAL_JSON_SELF_BINDING"

    expect_code(
        "G16_TERMINAL_RAW_FILE_SHA256_INVALID",
        lambda: m.verify_terminal_file_semantics("bad", terminal),
    )
    broken = dict(terminal)
    broken["status"] = "FAIL"
    expect_code(
        "TERMINAL_RECORD_SHA256_SEMANTIC_MISMATCH",
        lambda: m.verify_terminal_file_semantics(raw_file_sha, broken),
    )


def test_alias_and_reconstruction() -> None:
    head = "a" * 40
    original = {"repository_head_sha": head}
    repaired = m.authorization_with_main_sha_alias(original)
    assert repaired["main_sha"] == head
    assert "main_sha" not in original
    expect_code(
        "AUTHORIZATION_MAIN_SHA_ALIAS_CONFLICT",
        lambda: m.authorization_with_main_sha_alias(
            {"repository_head_sha": head, "main_sha": "b" * 40}
        ),
    )

    terminal = synthetic_terminal()
    reconstructed = m.reconstruct_terminal(terminal)
    assert reconstructed["status"] == "PASS"
    assert reconstructed["physical_execution_outcome"] == "CONSUMED_PASS"
    assert reconstructed["physical_rerun_required"] is False
    assert reconstructed["g17_failure_root_cause"] == (
        "G17_RAW_FILE_DIGEST_COMPARED_TO_G16_SEMANTIC_RECORD_DIGEST"
    )
    digest = reconstructed.pop("terminal_record_sha256")
    assert m.canonical_sha256(reconstructed) == digest


def test_subset_bindings() -> None:
    acceptance = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
    core = {
        "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g17-failure-acceptance-binding/1",
        "decision_id": acceptance["decision_id"],
        "status": "FAIL",
        "terminal_state": acceptance["terminal_state"],
        "failure_code": acceptance["failure_code"],
        "terminal_record_sha256": acceptance["terminal_record_sha256"],
        "authorization_created": acceptance["authorization_created"],
        "authorization_claimed": acceptance["authorization_claimed"],
        "authorization_consumed": acceptance["authorization_consumed"],
        "g16_runtime_read": acceptance["g16_runtime_read"],
        "g16_runtime_mutated": acceptance["g16_runtime_mutated"],
        "all_physical_operation_flags_false": acceptance[
            "all_physical_operation_flags_false"
        ],
        "physical_rerun_required": acceptance["physical_rerun_required"],
        "replay_permitted": acceptance["replay_permitted"],
    }
    assert m.canonical_sha256(core) == acceptance["acceptance_binding_sha256"]

    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    pending_core = {
        "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g18-semantic-digest-successor-pending-binding/1",
        "g17_failure_acceptance_binding_sha256": decision[
            "g17_failure_acceptance_binding_sha256"
        ],
        "g17_terminal_record_sha256": decision["g17_terminal_record_sha256"],
        "g16_terminal_record_sha256": decision["g16_terminal_record_sha256"],
        "g16_forensic_export_sha256": decision["g16_forensic_export_sha256"],
        "g16_acceptance_binding_sha256": decision[
            "g16_acceptance_binding_sha256"
        ],
        "root_cause": decision["root_cause"],
        "repair": decision["repair"],
        "operation_scope": decision["closure_scope"],
        "board_operation_authorized": decision["board_operation_authorized"],
        "physical_rerun_authorized": decision["physical_rerun_authorized"],
        "replay_authorized": decision["physical_execution_replay_authorized"],
        "activate_authorized": decision["activate_operation_authorized"],
        "cleanup_authorized": decision["cleanup_operation_authorized"],
    }
    assert m.canonical_sha256(pending_core) == decision["pending_binding_sha256"]


def test_source_boundary() -> None:
    boundary = m.source_boundary()
    assert boundary["physical_rerun_authorized"] is False
    assert boundary["replay_permitted"] is False
    for key, value in boundary.items():
        if key.endswith("_operation") or key.endswith("_executed") or key.endswith(
            "_enumeration"
        ):
            assert value is False
    source = TOOL.read_text(encoding="utf-8")
    for forbidden in (
        "import serial",
        "import subprocess",
        "import socket",
        "esptool.main",
        "mosquitto",
    ):
        assert forbidden not in source


if __name__ == "__main__":
    test_raw_and_semantic_digest_domains_are_independent()
    test_alias_and_reconstruction()
    test_subset_bindings()
    test_source_boundary()
    print(
        json.dumps(
            {
                "status": "PASS",
                "suite": "g17-fail-g18-semantic-digest-repair",
            },
            sort_keys=True,
        )
    )
