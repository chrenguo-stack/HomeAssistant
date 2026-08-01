#!/usr/bin/env python3
"""Source-only G18 semantic terminal verification and host-only reconstruction.

This module is inert unless called by a separately authorized host-only package. It
never enumerates hardware or performs serial, esptool, Flash/NVS, network, Broker,
PREPARE, VERIFY, recovery, ACTIVATE, or CLEANUP operations.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

G16_TERMINAL_RECORD_SHA256 = "d212129fae86d79428216d51a01e41e6a824db6e08106c6832e6ebc17c463567"
G16_FORENSIC_EXPORT_SHA256 = "7b35c067180ef9766f25b550a4a5fab1f55e00ba26836772e6b5e9ec19ba6810"
G16_ACCEPTANCE_BINDING_SHA256 = "9be11c054d84fb7db1a0a23eddc3f5735d5d660c6e1d2b1263634629938c0714"
G17_TERMINAL_RECORD_SHA256 = "8825449a87b36a606be635fff12518f47744324c6dcb36ae28f939128e7baa42"
G17_FAILURE_ACCEPTANCE_BINDING_SHA256 = "ba8815349a7c7f76398618f59dd6f68ff4439607f1ac2da43a58e5cbe5cc858d"
G18_PENDING_BINDING_SHA256 = "dcf06f640a51f0cc7f9316f43c26ce6dd01b0d9c8eb9506f7dcc7d1638e1d4b4"
G14_TERMINAL_RECORD_SHA256 = "45b1aa3438257be87170e68c4308af697f5d6bde468248318fded4fd2e3c97c1"
G14_INNER_TERMINAL_RESULT_SHA256 = "73ca46c31ee7a43dfdcc196d8834292cd96decbf26a1828f0cf4437e1ce00d92"
PREPARE_DELIVERY_EVIDENCE_SHA256 = "3e77a1a149a057af20046171a6b15fcd29c9e6c05867748537638e9822a0e64b"
VERIFY_DELIVERY_EVIDENCE_SHA256 = "550a278b483dae9c60405ab9d27b1765268dbdeebb783b2b3a9b5783d200c943"


class G18Error(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise G18Error(code)


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_self_binding(value: dict[str, Any], field: str, expected: str) -> None:
    require(value.get(field) == expected, field.upper() + "_EXPECTED_MISMATCH")
    core = dict(value)
    core.pop(field, None)
    require(canonical_sha256(core) == expected, field.upper() + "_SEMANTIC_MISMATCH")


def verify_terminal_file_semantics(
    raw_file_sha256: str,
    terminal: dict[str, Any],
) -> dict[str, Any]:
    """Verify the semantic record independently from the raw file-byte digest.

    The raw digest is deliberately not compared with terminal_record_sha256. The
    former binds exact file bytes; the latter binds the canonical JSON object after
    removing its self-binding field. The raw digest is returned only for a caller's
    pre/post immutability check.
    """
    require(isinstance(raw_file_sha256, str) and HEX64.fullmatch(raw_file_sha256) is not None,
            "G16_TERMINAL_RAW_FILE_SHA256_INVALID")
    require(isinstance(terminal, dict), "G16_TERMINAL_NOT_MAPPING")
    verify_self_binding(terminal, "terminal_record_sha256", G16_TERMINAL_RECORD_SHA256)
    return {
        "semantic_binding_valid": True,
        "semantic_record_sha256": G16_TERMINAL_RECORD_SHA256,
        "raw_file_sha256": raw_file_sha256,
        "raw_equals_semantic_record": raw_file_sha256 == G16_TERMINAL_RECORD_SHA256,
        "raw_digest_role": "PRE_POST_IMMUTABILITY_ONLY",
        "semantic_digest_role": "CANONICAL_JSON_SELF_BINDING",
    }


def authorization_with_main_sha_alias(authorization: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with the legacy main_sha alias safely populated."""
    require(isinstance(authorization, dict), "AUTHORIZATION_NOT_MAPPING")
    repository_head = authorization.get("repository_head_sha")
    main_sha = authorization.get("main_sha")

    if main_sha is not None:
        require(
            isinstance(main_sha, str) and HEX40.fullmatch(main_sha) is not None,
            "AUTHORIZATION_MAIN_SHA_INVALID",
        )
    if repository_head is not None:
        require(
            isinstance(repository_head, str)
            and HEX40.fullmatch(repository_head) is not None,
            "AUTHORIZATION_REPOSITORY_HEAD_SHA_INVALID",
        )

    if main_sha is None:
        require(repository_head is not None, "AUTHORIZATION_REPOSITORY_HEAD_SHA_MISSING")
        main_sha = repository_head
    elif repository_head is not None:
        require(main_sha == repository_head, "AUTHORIZATION_MAIN_SHA_ALIAS_CONFLICT")

    repaired = dict(authorization)
    repaired["main_sha"] = main_sha
    return repaired


def reconstruct_terminal(g16_terminal: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct the physical outcome from authenticated G16 evidence."""
    require(isinstance(g16_terminal, dict), "G16_TERMINAL_NOT_MAPPING")
    verify_self_binding(
        g16_terminal,
        "terminal_record_sha256",
        G16_TERMINAL_RECORD_SHA256,
    )
    require(g16_terminal.get("status") == "PASS", "G16_TERMINAL_NOT_PASS")
    require(
        g16_terminal.get("forensic_export_sha256") == G16_FORENSIC_EXPORT_SHA256,
        "G16_FORENSIC_EXPORT_BINDING_DRIFT",
    )
    require(
        g16_terminal.get("classification")
        == "POST_VERIFY_RESULT_GENERATOR_FAILURE_HIDDEN_BY_GENERIC_FALLBACK",
        "G16_CLASSIFICATION_DRIFT",
    )
    require(g16_terminal.get("secondary_failure_code") == "KeyError",
            "G16_SECONDARY_FAILURE_CLASS_DRIFT")
    require(g16_terminal.get("secondary_failure_detail") == "main_sha",
            "G16_SECONDARY_FAILURE_DETAIL_DRIFT")
    require(
        g16_terminal.get("g14_inner_authorization_marker_status") == "CONSUMED_PASS",
        "G14_INNER_MARKER_NOT_PASS",
    )
    require(g16_terminal.get("g14_outer_terminal_state") == "CONSUMED_FAILED",
            "G14_OUTER_TERMINAL_STATE_DRIFT")
    require(
        g16_terminal.get("g14_outer_inner_marker_relation")
        == "INNER_EXECUTION_PASS_OUTER_TERMINALIZATION_FAILED",
        "G14_OUTER_INNER_RELATION_DRIFT",
    )

    marker = g16_terminal.get("authorization_marker_fields")
    result = g16_terminal.get("result_fields")
    prepare = g16_terminal.get("prepare_delivery_fields")
    verify = g16_terminal.get("verify_delivery_fields")
    evidence = g16_terminal.get("prepare_evidence_fields")
    panic = g16_terminal.get("panic_evidence_fields")
    for name, value in (
        ("MARKER", marker),
        ("RESULT", result),
        ("PREPARE_DELIVERY", prepare),
        ("VERIFY_DELIVERY", verify),
        ("PREPARE_EVIDENCE", evidence),
        ("PANIC_EVIDENCE", panic),
    ):
        require(isinstance(value, dict), "G16_" + name + "_MISSING")

    require(marker.get("status") == "CONSUMED_PASS", "G14_MARKER_STATUS_DRIFT")
    require(
        marker.get("terminal_result_sha256") == G14_INNER_TERMINAL_RESULT_SHA256,
        "G14_INNER_TERMINAL_RESULT_DRIFT",
    )
    require(result.get("prepare_count") == 1, "G14_PREPARE_COUNT_DRIFT")
    require(result.get("verify_count") == 1, "G14_VERIFY_COUNT_DRIFT")
    require(prepare.get("status") == "DELIVERED", "PREPARE_NOT_DELIVERED")
    require(prepare.get("exact_write_confirmed") is True,
            "PREPARE_EXACT_WRITE_NOT_CONFIRMED")
    require(
        prepare.get("delivery_evidence_sha256") == PREPARE_DELIVERY_EVIDENCE_SHA256,
        "PREPARE_DELIVERY_EVIDENCE_DRIFT",
    )
    require(verify.get("status") == "DELIVERED", "VERIFY_NOT_DELIVERED")
    require(verify.get("exact_write_confirmed") is True,
            "VERIFY_EXACT_WRITE_NOT_CONFIRMED")
    require(
        verify.get("delivery_evidence_sha256") == VERIFY_DELIVERY_EVIDENCE_SHA256,
        "VERIFY_DELIVERY_EVIDENCE_DRIFT",
    )
    require(evidence.get("classification") == "PREPARE_PASS",
            "PREPARE_EVIDENCE_NOT_PASS")
    require(panic.get("reset_loop_count") == 0, "RESET_LOOP_OBSERVED")
    require(panic.get("post_command_reset_count") == 0,
            "POST_COMMAND_RESET_OBSERVED")
    require(g16_terminal.get("all_physical_operation_flags_false") is True,
            "G16_HOST_ONLY_BOUNDARY_DRIFT")
    require(g16_terminal.get("g14_runtime_mutated") is False,
            "G14_RUNTIME_MUTATION_OBSERVED")

    value: dict[str, Any] = {
        "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g18-reconstructed-physical-terminal/1",
        "status": "PASS",
        "terminal_state": "D2_17_PHYSICAL_EXECUTION_RECONSTRUCTED_CONSUMED_PASS",
        "physical_execution_outcome": "CONSUMED_PASS",
        "g14_inner_terminal_result_sha256": G14_INNER_TERMINAL_RESULT_SHA256,
        "g14_outer_terminal_record_sha256": G14_TERMINAL_RECORD_SHA256,
        "g16_terminal_record_sha256": G16_TERMINAL_RECORD_SHA256,
        "g16_forensic_export_sha256": G16_FORENSIC_EXPORT_SHA256,
        "g16_acceptance_binding_sha256": G16_ACCEPTANCE_BINDING_SHA256,
        "g17_terminal_record_sha256": G17_TERMINAL_RECORD_SHA256,
        "g17_failure_acceptance_binding_sha256": G17_FAILURE_ACCEPTANCE_BINDING_SHA256,
        "g18_pending_binding_sha256": G18_PENDING_BINDING_SHA256,
        "root_cause": "RESULT_GENERATOR_EXPECTED_MAIN_SHA_ALIAS_MISSING",
        "g17_failure_root_cause": "G17_RAW_FILE_DIGEST_COMPARED_TO_G16_SEMANTIC_RECORD_DIGEST",
        "repair": "VERIFY_G16_SEMANTIC_SELF_BINDING_AFTER_JSON_LOAD_AND_USE_RAW_DIGEST_ONLY_FOR_PRE_POST_IMMUTABILITY",
        "outer_terminalization_defect_only": True,
        "prepare_delivered": True,
        "verify_delivered": True,
        "prepare_pass": True,
        "reset_loop_count": 0,
        "post_command_reset_count": 0,
        "physical_rerun_required": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
        "recovery_executed": False,
        "activate_executed": False,
        "cleanup_executed": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "private_paths_included": False,
        "raw_logs_included": False,
        "command_material_included": False,
        "secret_values_included": False,
    }
    value["terminal_record_sha256"] = canonical_sha256(value)
    return value


def source_boundary() -> dict[str, Any]:
    return {
        "state": "SOURCE_ONLY_REQUIRES_EXACT_G18_HOST_ONLY_CLOSURE_AUTHORIZATION",
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
        "recovery_executed": False,
        "activate_executed": False,
        "cleanup_executed": False,
        "physical_rerun_authorized": False,
        "replay_permitted": False,
    }


if __name__ == "__main__":
    print(json.dumps(source_boundary(), sort_keys=True))
