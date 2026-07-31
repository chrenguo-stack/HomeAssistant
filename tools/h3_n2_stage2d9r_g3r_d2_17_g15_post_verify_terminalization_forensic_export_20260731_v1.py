#!/usr/bin/env python3
"""Host-only G15 forensic export for a consumed G14 post-VERIFY terminalization failure.

The tool reads only allow-listed JSON evidence from an already retired G14 runtime.
It never enumerates USB/serial, invokes esptool, accesses Flash/NVS, starts a broker,
or executes PREPARE/VERIFY/recovery. It emits no private paths, raw logs, commands,
credentials, or secret values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

G14_DECISION_ID = "D1-H3N2-STAGE2D9R-G3R-D2-17-G14-PHYSICAL-EXECUTION-20260731-01"
D2_REQUEST_ID = "D2-H3N2-STAGE2D9R-G3R-EXECUTION-IDENTITY-FROZEN-PREFLIGHT-STABILIZED-PHYSICAL-20260730-17"
G14_TERMINAL_SHA256 = "45b1aa3438257be87170e68c4308af697f5d6bde468248318fded4fd2e3c97c1"
G14_PHYSICAL_RESULT_SHA256 = "81dc50c77be871c26b5030cd85bd27c07acd7886a3cd642875a6ab2450c99735"
G14_AUTHORIZATION_MARKER_SHA256 = "223e4549c3f86c9a02e270f9672ccd056797b2e58175610e1d391ec46693a4f8"
G14_AUTHORIZATION_RECORD_SHA256 = "47bd58b60acb94ccf3d9e470359936fd8b610987dba99cc81adcddaf09ce1b29"
G14_DISPOSITION_BINDING_SHA256 = "23692fe5e7a9a21f8fdaf804cb5b90cc219496f9ac834487f58bf58e35e2d869"

class ForensicError(RuntimeError):
    pass

def require(ok: bool, code: str) -> None:
    if not ok:
        raise ForensicError(code)

def canonical(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def mode(path: Path) -> str:
    return format(path.stat().st_mode & 0o7777, "04o")

def load_json(path: Path, code: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), code)
    require(mode(path) == "0600", code + "_MODE")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ForensicError(code) from exc
    require(isinstance(value, dict), code)
    return value

def verify_self_binding(value: dict[str, Any], field: str, expected: str, code: str) -> None:
    require(value.get(field) == expected, code + "_EXPECTED")
    core = dict(value)
    core.pop(field, None)
    require(canonical(core) == expected, code + "_SEMANTIC")

def pick(value: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: value.get(key) for key in keys if key in value}

def optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return load_json(path, "OPTIONAL_EVIDENCE_INVALID_" + path.name.upper().replace(".", "_").replace("-", "_"))

def classify(result: dict[str, Any], guard: dict[str, Any] | None) -> dict[str, Any]:
    fallback = result.get("terminalization_fallback_used") is True
    primary = result.get("primary_failure_code") or result.get("failure_code")
    secondary = (
        result.get("secondary_failure_detail")
        or result.get("post_result_terminalization_failure_code")
        or (guard or {}).get("failure_code")
    )
    secondary_class = result.get("secondary_failure_code")
    exact = isinstance(secondary, str) and bool(secondary)
    if fallback and primary == "POST_CLAIM_EXECUTION_FAILED":
        classification = "POST_VERIFY_RESULT_GENERATOR_FAILURE_HIDDEN_BY_GENERIC_FALLBACK"
    elif fallback:
        classification = "POST_CLAIM_TERMINALIZATION_FALLBACK"
    else:
        classification = "NON_FALLBACK_POST_CLAIM_FAILURE"
    return {
        "classification": classification,
        "terminalization_fallback_used": fallback,
        "primary_failure_code": primary,
        "secondary_failure_code": secondary_class,
        "secondary_failure_detail": secondary,
        "exact_secondary_failure_available": exact,
    }

def export(runtime_root: Path, outer_terminal_path: Path) -> dict[str, Any]:
    runtime_root = runtime_root.expanduser().resolve(strict=True)
    require(runtime_root.is_dir() and not runtime_root.is_symlink(), "G14_RUNTIME_ROOT_INVALID")
    outer_terminal_path = outer_terminal_path.expanduser().resolve(strict=True)
    terminal = load_json(outer_terminal_path, "G14_OUTER_TERMINAL_INVALID")
    verify_self_binding(terminal, "terminal_record_sha256", G14_TERMINAL_SHA256, "G14_OUTER_TERMINAL")
    exact = {
        "decision_id": G14_DECISION_ID,
        "d2_request_id": D2_REQUEST_ID,
        "status": "FAIL",
        "terminal_state": "CONSUMED_FAILED",
        "failure_code": "POST_CLAIM_EXECUTION_FAILED",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "physical_result_sha256": G14_PHYSICAL_RESULT_SHA256,
        "authorization_marker_sha256": G14_AUTHORIZATION_MARKER_SHA256,
        "authorization_record_sha256": G14_AUTHORIZATION_RECORD_SHA256,
        "flash_operation": True,
        "prepare_executed": True,
        "verify_executed": True,
        "recovery_executed": False,
        "activate_executed": False,
        "cleanup_executed": False,
    }
    for key, expected in exact.items():
        require(terminal.get(key) == expected, "G14_OUTER_TERMINAL_FIELD_DRIFT_" + key.upper())

    physical = runtime_root / "D2_17_G14_PHYSICAL_EXECUTION_20260731_01"
    require(physical.is_dir() and not physical.is_symlink(), "G14_PHYSICAL_ROOT_INVALID")
    result_path = physical / "D2_17_G14_PHYSICAL_RESULT.json"
    result = load_json(result_path, "G14_PHYSICAL_RESULT_INVALID")
    require(sha(result_path) == G14_PHYSICAL_RESULT_SHA256, "G14_PHYSICAL_RESULT_DIGEST_DRIFT")

    marker_name = hashlib.sha256(D2_REQUEST_ID.encode()).hexdigest() + ".json"
    marker_path = runtime_root / "authorization-state-g14" / marker_name
    marker = load_json(marker_path, "G14_AUTHORIZATION_MARKER_INVALID")
    require(sha(marker_path) == G14_AUTHORIZATION_MARKER_SHA256, "G14_AUTHORIZATION_MARKER_DIGEST_DRIFT")
    require(marker.get("status") == "CONSUMED_FAILED", "G14_AUTHORIZATION_MARKER_STATE_DRIFT")

    terminalization = physical / "terminalization-evidence"
    guard = optional_json(terminalization / "terminalization-guard.json")
    recovery = optional_json(terminalization / "locked-recovery-terminal.json")
    prepare_manifest = optional_json(physical / "prepare-evidence" / "prepare-evidence-manifest.json")
    panic_manifest = optional_json(physical / "prepare-evidence" / "prepare-panic-evidence-manifest.json")
    prepare_delivery = optional_json(physical / "delivery-evidence" / "prepare-transport-delivery.json")
    verify_delivery = optional_json(physical / "delivery-evidence" / "verify-transport-delivery.json")

    diagnosis = classify(result, guard)
    summary: dict[str, Any] = {
        "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g15-post-verify-terminalization-forensic-export/1",
        "status": "PASS",
        "terminal_state": "G14_CONSUMED_POST_VERIFY_FORENSIC_EXPORT_COMPLETE",
        "decision_id": G14_DECISION_ID,
        "d2_request_id": D2_REQUEST_ID,
        "g14_terminal_record_sha256": G14_TERMINAL_SHA256,
        "g14_physical_result_sha256": G14_PHYSICAL_RESULT_SHA256,
        "g14_authorization_marker_sha256": G14_AUTHORIZATION_MARKER_SHA256,
        "g14_authorization_record_sha256": G14_AUTHORIZATION_RECORD_SHA256,
        "g14_disposition_binding_sha256": G14_DISPOSITION_BINDING_SHA256,
        **diagnosis,
        "result_fields": pick(result, (
            "schema", "status", "terminal_state", "failure_code",
            "primary_failure_code", "secondary_failure_code", "secondary_failure_detail",
            "terminalization_fallback_used", "post_result_terminalization_failure_code",
            "prepare_count", "verify_count", "prepare_transport_delivery_status",
            "verify_transport_delivery_status", "recovery_attempted", "recovery_succeeded",
            "recovery_failure_code", "prepare_evidence_classification",
            "panic_timeline_classification", "reset_loop_count", "post_command_reset_count",
            "terminal_result_sha256",
        )),
        "terminalization_guard_fields": pick(guard or {}, (
            "schema", "status", "failure_code", "terminal_result_sha256",
            "replay_permitted", "automatic_retry_permitted",
        )),
        "recovery_terminal_fields": pick(recovery or {}, (
            "schema", "status", "attempt_count", "scope", "succeeded", "failure_code",
        )),
        "prepare_evidence_fields": pick(prepare_manifest or {}, (
            "classification", "terminal", "serial_evidence_sha256",
            "broker_evidence_sha256", "timeline_sha256",
        )),
        "panic_evidence_fields": pick(panic_manifest or {}, (
            "classification", "terminal", "realtime_serial_sha256",
            "reset_signatures_sha256", "realtime_timeline_sha256",
            "reset_loop_count", "post_command_reset_count", "manifest_file_sha256",
        )),
        "prepare_delivery_fields": pick(prepare_delivery or {}, (
            "schema", "phase", "status", "failure_code",
            "attempted_chunk_count", "completed_chunk_count",
            "exact_write_confirmed", "delivery_evidence_sha256",
        )),
        "verify_delivery_fields": pick(verify_delivery or {}, (
            "schema", "phase", "status", "failure_code",
            "attempted_chunk_count", "completed_chunk_count",
            "exact_write_confirmed", "delivery_evidence_sha256",
        )),
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
        "private_paths_included": False,
        "raw_logs_included": False,
        "command_material_included": False,
        "secret_values_included": False,
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
    }
    summary["forensic_export_sha256"] = canonical(summary)
    return summary

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--outer-terminal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        value = export(args.runtime_root, args.outer_terminal)
        output = args.output.expanduser().resolve(strict=False)
        require(not output.exists(), "FORENSIC_OUTPUT_ALREADY_EXISTS")
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(output.parent, 0o700)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(output, flags, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", closefd=False) as handle:
                json.dump(value, handle, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(fd)
        print(json.dumps(value, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        code = exc.args[0] if exc.args and isinstance(exc.args[0], str) else type(exc).__name__
        value = {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g15-post-verify-terminalization-forensic-export/1",
            "status": "FAIL",
            "failure_code": code,
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
            "private_paths_included": False,
            "raw_logs_included": False,
            "command_material_included": False,
            "secret_values_included": False,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
        }
        print(json.dumps(value, sort_keys=True, separators=(",", ":")))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
