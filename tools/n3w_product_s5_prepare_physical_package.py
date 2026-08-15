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
RUNTIME_IMPLEMENTATION_HEAD = "e06c8bc90b08987a17783a1a113ea1aaa81b81c0"
PRIVATE_RUNTIME_COMPONENT = "greenhouse_n3w_s5_private_runtime"
ISOLATED_MANAGER_LAUNCHER_MODULE = (
    "greenhouse_manager.runtime.n3w_product_isolated_app"
)
DEFAULT_MANAGER_LAUNCHER_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "host"
    / "greenhouse-manager"
    / "src"
    / "greenhouse_manager"
    / "runtime"
    / "n3w_product_isolated_app.py"
)
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


def _load_json(path: Path, label: str, *, private: bool) -> dict[str, Any]:
    if private:
        _require_private_file(path, label)
    elif not path.is_file():
        raise ValueError(f"{label} must be a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain one JSON object")
    return value


def _load_credentials(path: Path, label: str) -> dict[str, Any]:
    value = _load_json(path, label, private=True)
    expected = {
        "system_id",
        "node_id",
        "credential_generation",
        "key_epoch",
        "application_key_hex",
        "local_mac",
    }
    if set(value) != expected:
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
    if int(value["local_mac"].split(":")[0], 16) & 0x01:
        raise ValueError(f"{label} local_mac must be unicast")
    return value


def _load_network(path: Path) -> dict[str, Any]:
    value = _load_json(path, "isolated_network", private=True)
    expected = {
        "wifi_ssid",
        "wifi_password",
        "wifi_channel",
        "mqtt_broker",
        "mqtt_port",
        "mqtt_client_id",
        "mqtt_username",
        "mqtt_password",
        "mqtt_tls",
    }
    if set(value) != expected:
        raise ValueError(f"isolated_network fields must be exactly {sorted(expected)}")
    ssid = value["wifi_ssid"]
    password = value["wifi_password"]
    if not isinstance(ssid, str) or not 1 <= len(ssid.encode("utf-8")) <= 32:
        raise ValueError("isolated_network wifi_ssid must be 1..32 UTF-8 bytes")
    if not isinstance(password, str) or (password and not 8 <= len(password) <= 63):
        raise ValueError("isolated_network wifi_password must be empty or 8..63 characters")
    channel = value["wifi_channel"]
    if not isinstance(channel, int) or isinstance(channel, bool) or not 1 <= channel <= 14:
        raise ValueError("isolated_network wifi_channel must be between 1 and 14")
    broker = value["mqtt_broker"]
    client_id = value["mqtt_client_id"]
    if not isinstance(broker, str) or not broker.strip() or len(broker) > 255:
        raise ValueError("isolated_network mqtt_broker is invalid")
    if not isinstance(client_id, str) or not client_id.strip() or len(client_id) > 128:
        raise ValueError("isolated_network mqtt_client_id is invalid")
    port = value["mqtt_port"]
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise ValueError("isolated_network mqtt_port is invalid")
    username = value["mqtt_username"]
    mqtt_password = value["mqtt_password"]
    if username is not None and not isinstance(username, str):
        raise ValueError("isolated_network mqtt_username must be string or null")
    if mqtt_password is not None and not isinstance(mqtt_password, str):
        raise ValueError("isolated_network mqtt_password must be string or null")
    if bool(username) != bool(mqtt_password):
        raise ValueError("isolated_network MQTT username/password must be configured together")
    if type(value["mqtt_tls"]) is not bool:
        raise ValueError("isolated_network mqtt_tls must be boolean")
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


def _public_network_binding(value: dict[str, Any]) -> dict[str, object]:
    return {
        "wifi_ssid_sha256": hashlib.sha256(value["wifi_ssid"].encode("utf-8")).hexdigest(),
        "wifi_channel": value["wifi_channel"],
        "mqtt_broker_sha256": hashlib.sha256(value["mqtt_broker"].encode("utf-8")).hexdigest(),
        "mqtt_port": value["mqtt_port"],
        "mqtt_client_id_sha256": hashlib.sha256(value["mqtt_client_id"].encode("utf-8")).hexdigest(),
        "mqtt_tls": value["mqtt_tls"],
        "mqtt_authentication_configured": bool(value["mqtt_username"]),
    }


def prepare(args: argparse.Namespace) -> dict[str, object]:
    if not re.fullmatch(r"[0-9a-f]{40}", args.preparation_head):
        raise ValueError("preparation_head must be an exact lowercase 40-hex commit SHA")
    if args.runtime_head != RUNTIME_IMPLEMENTATION_HEAD:
        raise ValueError("runtime_head does not match the reviewed S5 private-runtime implementation")
    if not isinstance(args.espnow_channel, int) or isinstance(args.espnow_channel, bool) or not 1 <= args.espnow_channel <= 14:
        raise ValueError("espnow_channel must be between 1 and 14")

    child_path = Path(args.child_credentials).resolve()
    relay_path = Path(args.relay_credentials).resolve()
    network_path = Path(args.isolated_network).resolve()
    child_firmware = Path(args.child_firmware).resolve()
    relay_firmware = Path(args.relay_firmware).resolve()
    manager_bundle = Path(args.manager_bundle).resolve()
    launcher_source = Path(args.manager_launcher_source).resolve()
    output = Path(args.output).resolve()

    child = _load_credentials(child_path, "child_credentials")
    relay = _load_credentials(relay_path, "relay_credentials")
    network = _load_network(network_path)
    if child["system_id"] != relay["system_id"]:
        raise ValueError("Child and Relay must belong to the same system")
    if child["node_id"] == relay["node_id"]:
        raise ValueError("Child and Relay node_id values must be distinct")
    if child["local_mac"].lower() == relay["local_mac"].lower():
        raise ValueError("Child and Relay MAC addresses must be distinct")
    if network["wifi_channel"] != args.espnow_channel:
        raise ValueError("isolated Wi-Fi channel must equal the bound ESP-NOW channel")

    for path, label in (
        (child_firmware, "child_firmware"),
        (relay_firmware, "relay_firmware"),
        (manager_bundle, "isolated_manager_state_bundle"),
    ):
        _require_private_file(path, label)
    if not launcher_source.is_file():
        raise ValueError("isolated_manager_launcher_source must be a regular file")

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
    _write_private_json(output / "isolated_network.json", network)

    manifest = {
        "schema": "gh.n3w-product-s5-private-physical-e2e-package/2",
        "package_id": package_id,
        "preparation_authorization": AUTHORIZATION,
        "physical_execution_authorization": None,
        "execution_authorized": False,
        "preparation_head": args.preparation_head,
        "runtime_implementation_head": args.runtime_head,
        "private_runtime_component": PRIVATE_RUNTIME_COMPONENT,
        "isolated_manager_launcher_module": ISOLATED_MANAGER_LAUNCHER_MODULE,
        "system_id": child["system_id"],
        "child_binding": _public_credential_binding(child),
        "relay_binding": _public_credential_binding(relay),
        "network_binding": _public_network_binding(network),
        "radio_binding": {
            "espnow_channel": args.espnow_channel,
            "wifi_channel": network["wifi_channel"],
            "channels_match": True,
        },
        "composition_contract": {
            "child_consumes_only_child_post_registration_material": True,
            "relay_consumes_only_relay_post_registration_material": True,
            "factory_peer_identity_present": False,
            "pair_lmk_supplied_by_package": False,
            "manager_uses_existing_s4_peer_authorization_authority": True,
            "normal_production_manager_startup_changed": False,
        },
        "inputs": {
            "child_credentials_sha256": _sha256_file(child_path),
            "relay_credentials_sha256": _sha256_file(relay_path),
            "isolated_network_source_sha256": _sha256_file(network_path),
            "isolated_network_package_sha256": _sha256_file(output / "isolated_network.json"),
            "child_firmware_sha256": _sha256_file(child_firmware),
            "relay_firmware_sha256": _sha256_file(relay_firmware),
            "isolated_manager_state_bundle_sha256": _sha256_file(manager_bundle),
            "isolated_manager_launcher_source_sha256": _sha256_file(launcher_source),
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
            "delete_private_network_configuration",
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
        "private_runtime_component": PRIVATE_RUNTIME_COMPONENT,
        "isolated_manager_launcher_module": ISOLATED_MANAGER_LAUNCHER_MODULE,
        "network_binding": _public_network_binding(network),
        "espnow_channel": args.espnow_channel,
        "child_firmware_sha256": manifest["inputs"]["child_firmware_sha256"],
        "relay_firmware_sha256": manifest["inputs"]["relay_firmware_sha256"],
        "isolated_manager_state_bundle_sha256": manifest["inputs"]["isolated_manager_state_bundle_sha256"],
        "isolated_manager_launcher_source_sha256": manifest["inputs"]["isolated_manager_launcher_source_sha256"],
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
    value.add_argument("--isolated-network", required=True)
    value.add_argument("--espnow-channel", required=True, type=int)
    value.add_argument("--child-firmware", required=True)
    value.add_argument("--relay-firmware", required=True)
    value.add_argument("--manager-bundle", required=True)
    value.add_argument(
        "--manager-launcher-source",
        default=str(DEFAULT_MANAGER_LAUNCHER_SOURCE),
    )
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
