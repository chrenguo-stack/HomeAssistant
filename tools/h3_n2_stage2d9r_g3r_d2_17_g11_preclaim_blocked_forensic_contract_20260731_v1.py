#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPOSITION = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g11-preclaim-blocked-disposition-20260731-v1.json"
PENDING = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g11-read-only-preclaim-forensic-export-pending-20260731-v1.json"


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def verify_binding(value: dict[str, object], field: str, expected: str) -> None:
    observed = value.get(field)
    core = dict(value)
    core.pop(field)
    assert observed == expected
    assert canonical(core) == expected


def main() -> int:
    disposition = load(DISPOSITION)
    pending = load(PENDING)
    verify_binding(disposition, "disposition_binding_sha256", "101f96fc0c09f71ccf022e931fcaf07b0e962b09fdd8b76f86008e75e28c4bb9")
    verify_binding(pending, "pending_binding_sha256", "307112236b4bb5d668e7be3d9ef41d3fb904cd5b04a362c4de4831c7730078b4")
    assert disposition["terminal_record_sha256"] == "a413862a6bd769d20687a5f4d5b2ebd16a855486c270d22d5a1eeb15d174ddc3"
    assert disposition["authorization_claimed"] is False
    assert disposition["authorization_consumed"] is False
    assert disposition["replay_permitted"] is False
    assert disposition["automatic_retry_permitted"] is False
    assert disposition["board_operation"] is True
    assert disposition["usb_enumeration"] is True
    assert disposition["serial_operation"] is True
    assert disposition["esptool_operation"] is True
    assert disposition["physical_nvs_operation"] is True
    for field in ("flash_operation", "network_operation", "broker_started", "prepare_executed", "verify_executed", "recovery_executed", "activate_executed", "cleanup_executed"):
        assert disposition[field] is False
    for field in ("board_operation_authorized", "usb_enumeration_authorized", "serial_operation_authorized", "esptool_operation_authorized", "physical_nvs_operation_authorized", "flash_operation_authorized", "network_operation_authorized", "broker_start_authorized", "prepare_authorized", "verify_authorized", "recovery_authorized", "activate_authorized", "cleanup_authorized", "runtime_mutation_authorized"):
        assert pending[field] is False
    assert pending["g11_disposition_binding_sha256"] == disposition["disposition_binding_sha256"]
    print(json.dumps({"status": "PASS", "physical_operation": False, "disposition_binding_sha256": disposition["disposition_binding_sha256"], "pending_binding_sha256": pending["pending_binding_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
