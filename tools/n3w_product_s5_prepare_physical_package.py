#!/usr/bin/env python3
"""Prepare a private, non-executable S5 two-board physical E2E package.

This helper performs local validation, hashing and fresh PMK materialization only.
It does not access boards, serial ports, USB/JTAG, Wi-Fi, MQTT, ESP-NOW RF or
production services, and it intentionally emits no physical execution commands.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import stat
import uuid
from pathlib import Path
from typing import Any

AUTHORIZATION = (
    "D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-FULL-TWO-BOARD-ISOLATED-"
    "PHYSICAL-E2E-PREPARATION-20260814-01"
)
RUNTIME_IMPLEMENTATION_HEAD = "660acf72b701d9ff8e3a881e97e5d15357286786"
_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_MAC = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")

MATRIX = [
    "relay_advertisement_untrusted_hint",
    "manager_negative_authorization_matrix",
    "both_endpoint_grants_verified",
    "same_nonzero_pair_specific_16_byte_lmk",
    "automatic_encrypted_peer_install",
    "child_to_relay_to_isolated_manager_telemetry",
    "node_boot_seq_dedup_ha_identity_continuity",
    "grant_expiry_peer_removal",
    "exact_authorization_id_revoke",
    "duplicate_replay_stale_credential_negatives",
    "child_restart_cleanup_and_recovery",
    "relay_restart_cleanup_and_recovery",
    "gateway_bound_retry_cache_not_rehomed",
    "private_artifact_cleanup",
    "final_rom_bootloader_rf_stopped",
]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_private_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"{label} must be a regular file")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise ValueError(f"{label} permissions must not expose group/other bits")


def _load_credentials(path: Path, label: str) -> dict[str, Any]:
    _require_private_file(path, label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid UTF-8 JSON") from exc
    expected = {
        "system_id",
        "node_id",
        "credential_generation",
        "key_epoch",
        "application_key_hex",
        "local_mac",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{label} fields must be exactly {sorted(expected)}")
    if _ID.fullmatch(value["system_id"]) is None or _ID.fullmatch(value["node_id"]) is None:
        raise ValueError(f"{label} identity is invalid")
    for field in ("credential_generation", "key_epoch"):
        if not isinstance(value[field], int) or isinstance(value[field], bool) or value[field] < 1:
            raise ValueError(f"{label} {field} must be a positive integer")
    key_hex = value["application_key_hex"]
    if not isinstance(key_hex, str) or len(key_hex) != 64:
        raise ValueError(f"{label} application_key_hex must encode 32 bytes")
    try:
        key = bytes.fromhex(key_hex)
    except ValueError as exc:
        raise ValueError(f"{label} application_key_hex is invalid") from exc
    if not any(key):
        raise ValueError(f"{label} application key must be nonzero")
    if not isinstance(value["local_mac"], str) or _MAC.fullmatch(value["local_mac"]) is None:
        raise ValueError(f"{label} local_mac is invalid")
    return value


def _write_private_json(path: Path, value: object) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, indent=2)
            handle.write("\n")
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _public_credential_binding(value: dict[str, Any]) -> dict[str, object]:
    return {
        "system_id": value["system_id"],
        "node_id": value["node_id"],
        "credential_generation": value["credential_generation"],
        "key_epoch": value["key_epoch"],
        "local_mac_sha256": hashlib.sha256(value["local_mac"].lower().encode("ascii")).hexdigest(),
        "application_key_sha256": hashlib.sha256(bytes.fromhex(value["application_key_hex"])).hexdigest(),
    }


def prepare(args: argparse.Namespace) -> dict[str, object]:
    if not re.fullmatch(r"[0-9a-f]{40}", args.preparation_head):
        raise ValueError("preparation_head must be an exact lowercase 40-hex commit SHA")
    if args.runtime_head != RUNTIME_IMPLEMENTATION_HEAD:
        raise ValueError("runtime_head does not match the frozen S5-D implementation")

    child_path = Path(args.child_credentials).resolve()
    relay_path = Path(args.relay_credentials).resolve()
    child_firmware = Path(args.child_firmware).resolve()
    relay_firmware = Path(args.relay_firmware).resolve()
    manager_bundle = Path(args.manager_bundle).resolve()
    output = Path(args.output).resolve()

    child = _load_credentials(child_path, "child_credentials")
    relay = _load_credentials(relay_path, "relay_credentials")
    if child["system_id"] != relay["system_id"]:
        raise ValueError("Child and Relay must belong to the same system")
    if child["node_id"] == relay["node_id"]:
        raise ValueError("Child and Relay node_id values must be distinct")
    if child["local_mac"].lower() == relay["local_mac"].lower():
        raise ValueError("Child and Relay MAC addresses must be distinct")

    for path, label in (
        (child_firmware, "child_firmware"),
        (relay_firmware, "relay_firmware"),
        (manager_bundle, "isolated_manager_state_bundle"),
    ):
        _require_private_file(path, label)

    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(output, 0o700)

    package_id = f"S5-E2E-{uuid.uuid4()}"
    pmk = secrets.token_bytes(16)
    if not any(pmk):
        raise RuntimeError("fresh PMK generation failed")

    secret_document = {
        "schema": "gh.n3w-product-s5-private-package-secrets/1",
        "package_id": package_id,
        "espnow_pmk_hex": pmk.hex(),
        "physical_execution_authorization": None,
        "execution_authorized": False,
    }
    _write_private_json(output / "private_secrets.json", secret_document)

    manifest = {
        "schema": "gh.n3w-product-s5-private-physical-e2e-package/1",
        "package_id": package_id,
        "preparation_authorization": AUTHORIZATION,
        "physical_execution_authorization": None,
        "execution_authorized": False,
        "preparation_head": args.preparation_head,
        "runtime_implementation_head": args.runtime_head,
        "system_id": child["system_id"],
        "child_binding": _public_credential_binding(child),
        "relay_binding": _public_credential_binding(relay),
        "inputs": {
            "child_credentials_sha256": _sha256_file(child_path),
            "relay_credentials_sha256": _sha256_file(relay_path),
            "child_firmware_sha256": _sha256_file(child_firmware),
            "relay_firmware_sha256": _sha256_file(relay_firmware),
            "isolated_manager_state_bundle_sha256": _sha256_file(manager_bundle),
            "private_secrets_sha256": _sha256_file(output / "private_secrets.json"),
        },
        "physical_acceptance_matrix": MATRIX,
        "required_final_state": {
            "child": "ROM_BOOTLOADER_NO_RESET",
            "relay": "ROM_BOOTLOADER_NO_RESET",
            "espnow_rf_active": False,
        },
        "production_access_allowed": False,
        "n3l_allowed": False,
    }
    _write_private_json(output / "manifest.json", manifest)

    cleanup = {
        "schema": "gh.n3w-product-s5-private-cleanup-contract/1",
        "package_id": package_id,
        "required": [
            "stop_test_applications_and_espnow_rf",
            "return_both_boards_to_rom_bootloader_no_reset",
            "freeze_sanitized_evidence_before_private_deletion",
            "delete_private_credentials_copies",
            "delete_pmk_and_runtime_lmk_material",
            "delete_manager_state_copy",
            "delete_private_firmware_package_and_raw_serial_logs",
        ],
    }
    _write_private_json(output / "cleanup_contract.json", cleanup)

    checklist = (
        "PRIVATE S5 TWO-BOARD PHYSICAL E2E PACKAGE\n"
        f"package_id={package_id}\n"
        "execution_authorized=false\n"
        "A separate explicit physical-execution authorization is mandatory.\n"
        "This package contains no executable physical-operation command sheet.\n"
        "Do not reuse this package after any terminal physical attempt.\n"
    )
    checklist_path = output / "READ_ONLY_GATE.txt"
    fd = os.open(checklist_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(checklist)

    sanitized = {
        "package_id": package_id,
        "preparation_head": args.preparation_head,
        "runtime_implementation_head": args.runtime_head,
        "child_firmware_sha256": manifest["inputs"]["child_firmware_sha256"],
        "relay_firmware_sha256": manifest["inputs"]["relay_firmware_sha256"],
        "isolated_manager_state_bundle_sha256": manifest["inputs"]["isolated_manager_state_bundle_sha256"],
        "private_manifest_sha256": _sha256_file(output / "manifest.json"),
        "execution_authorized": False,
        "ready_for_readonly_binding_review": True,
    }
    return sanitized


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--preparation-head", required=True)
    value.add_argument("--runtime-head", default=RUNTIME_IMPLEMENTATION_HEAD)
    value.add_argument("--child-credentials", required=True)
    value.add_argument("--relay-credentials", required=True)
    value.add_argument("--child-firmware", required=True)
    value.add_argument("--relay-firmware", required=True)
    value.add_argument("--manager-bundle", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        result = prepare(args)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"PREPARATION=FAIL reason={exc}")
        return 2
    print("PREPARATION=PASS")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
