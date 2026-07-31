#!/usr/bin/env python3
"""Host-only G16 repair for G15's exact-marker state assumption."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import h3_n2_stage2d9r_g3r_d2_17_g15_post_verify_terminalization_forensic_export_20260731_v1 as predecessor

G15_TERMINAL_RECORD_SHA256 = '865f2955e26115bebacd13792e420ffb4166359ae525acb0cc854fd7ff6c0d05'
G15_AUTHORIZATION_RECORD_SHA256 = '9307e9c122611c9242b23aec4ed5ef92d8d5f0e63fee02d5a16a81589308eb17'
G15_AUTHORIZATION_MARKER_SHA256 = '0e8c9e3750dcb15443fcd0e1c9a2d4874eb5e3a6fc39086af4ae04ff1c9d86bf'
G15_PRIVATE_DELIVERY_BINDING_SHA256 = '7c59c984d513ff034dc669339d430b0cfb948db9e5cee8fbcc6cb91fd12e2bcd'
G15_DISPOSITION_BINDING_SHA256 = '7bd04cf01416ce3a886c873a1a6054b2ab426f19edac38dfc88a9879e4cdd124'
G16_PENDING_BINDING_SHA256 = '6f772b70af1137c08480eeb1ae7af994f203a6fd2e4c665393aad22d02e73d54'
ACCEPTED_MARKER_STATES = frozenset({"CLAIMED", "CONSUMED_PASS", "CONSUMED_FAILED"})


class G16ForensicError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise G16ForensicError(code)


def canonical(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def marker_path(runtime_root: Path) -> Path:
    name = hashlib.sha256(predecessor.D2_REQUEST_ID.encode()).hexdigest() + ".json"
    return runtime_root / "authorization-state-g14" / name


def relation(marker_status: str, outer_state: str) -> str:
    mapping = {
        ("CONSUMED_PASS", "CONSUMED_FAILED"): "INNER_EXECUTION_PASS_OUTER_TERMINALIZATION_FAILED",
        ("CONSUMED_FAILED", "CONSUMED_FAILED"): "INNER_AND_OUTER_CONSUMED_FAILED",
        ("CLAIMED", "CONSUMED_FAILED"): "INNER_MARKER_LEFT_CLAIMED_OUTER_TERMINALIZATION_FAILED",
    }
    return mapping.get((marker_status, outer_state), "UNEXPECTED_OUTER_INNER_STATE_RELATION")


def export(runtime_root: Path, outer_terminal: Path) -> dict[str, Any]:
    runtime_root = runtime_root.expanduser().resolve(strict=True)
    require(runtime_root.is_dir() and not runtime_root.is_symlink(), "G14_RUNTIME_ROOT_INVALID")

    original_require = predecessor.require

    def marker_state_tolerant_require(condition: bool, code: str) -> None:
        if code == "G14_AUTHORIZATION_MARKER_STATE_DRIFT":
            return
        original_require(condition, code)

    predecessor.require = marker_state_tolerant_require
    try:
        value = predecessor.export(runtime_root, outer_terminal)
    finally:
        predecessor.require = original_require

    path = marker_path(runtime_root)
    marker = predecessor.load_json(path, "G14_AUTHORIZATION_MARKER_INVALID")
    require(
        predecessor.sha(path) == predecessor.G14_AUTHORIZATION_MARKER_SHA256,
        "G14_AUTHORIZATION_MARKER_DIGEST_DRIFT",
    )
    status = marker.get("status")
    require(
        isinstance(status, str) and status in ACCEPTED_MARKER_STATES,
        "G14_AUTHORIZATION_MARKER_STATE_UNSUPPORTED",
    )

    outer = predecessor.load_json(outer_terminal.expanduser().resolve(strict=True), "G14_OUTER_TERMINAL_INVALID")
    value["schema"] = "gh.h3.n2.stage2d9r-g3r-d2-17-g16-marker-state-tolerant-post-verify-forensic-export/1"
    value["terminal_state"] = "G14_CONSUMED_POST_VERIFY_MARKER_STATE_TOLERANT_FORENSIC_EXPORT_COMPLETE"
    value["g15_terminal_record_sha256"] = G15_TERMINAL_RECORD_SHA256
    value["g15_authorization_record_sha256"] = G15_AUTHORIZATION_RECORD_SHA256
    value["g15_authorization_marker_sha256"] = G15_AUTHORIZATION_MARKER_SHA256
    value["g15_private_delivery_binding_sha256"] = G15_PRIVATE_DELIVERY_BINDING_SHA256
    value["g15_disposition_binding_sha256"] = G15_DISPOSITION_BINDING_SHA256
    value["g16_pending_binding_sha256"] = G16_PENDING_BINDING_SHA256
    value["g14_inner_authorization_marker_status"] = status
    value["g14_outer_terminal_state"] = outer.get("terminal_state")
    value["g14_outer_inner_marker_relation"] = relation(status, str(outer.get("terminal_state")))
    value["authorization_marker_fields"] = predecessor.pick(
        marker,
        (
            "schema", "status", "failure_code", "terminal_result_sha256",
            "recovery_attempted", "one_shot", "replay_permitted",
            "automatic_retry_permitted",
        ),
    )
    value["g14_runtime_mutated"] = False
    value.pop("forensic_export_sha256", None)
    value["forensic_export_sha256"] = canonical(value)
    return value


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
        descriptor = os.open(output, flags, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", closefd=False) as handle:
                json.dump(value, handle, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(descriptor)
        print(json.dumps(value, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        code = exc.args[0] if exc.args and isinstance(exc.args[0], str) else type(exc).__name__
        value = {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g16-marker-state-tolerant-post-verify-forensic-export/1",
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
            "g14_runtime_mutated": False,
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
