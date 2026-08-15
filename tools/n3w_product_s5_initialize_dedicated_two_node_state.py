#!/usr/bin/env python3
"""Create one synthetic-only S5 dedicated two-node state closure.

This host-only initializer is intentionally unable to materialize real private
state. It accepts only an explicit synthetic fixture document, creates no PMK,
opens no network or device interface, and writes only a disposable two-node
Manager snapshot plus matching synthetic Child/Relay credential files.

Real private-state materialization requires a separate authorization and tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import stat
from pathlib import Path
from typing import Any

AUTHORIZATION = (
    "D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-DEDICATED-TWO-NODE-STATE-"
    "INITIALIZER-HOSTONLY-CONTRACT-AND-SYNTHETIC-VALIDATION-20260815-01"
)
INPUT_SCHEMA = "gh.n3w-product-s5-dedicated-two-node-state-synthetic/1"
SYNTHETIC_MARKER = "S5-SYNTHETIC-ONLY-NOT-REAL-CREDENTIALS"
RELAY_CAPABILITY = "n3w-product-relay"

_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_HARDWARE_ID = re.compile(r"^ghw-[a-z0-9]+-[0-9a-f]{12}$")
_PAIRING_ID = re.compile(r"^[A-Za-z0-9_-]{3,96}$")
_MAC = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


class SyntheticStateError(RuntimeError):
    """Synthetic state input or output violates the frozen S5 contract."""


def _private_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(path, 0o700)


def _private_text(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)


def _private_json(path: Path, value: object) -> None:
    _private_text(path, json.dumps(value, sort_keys=True, indent=2) + "\n")


def _validate_key_hex(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise SyntheticStateError(f"{label}_application_key_invalid")
    try:
        raw = bytes.fromhex(value)
    except ValueError as exc:
        raise SyntheticStateError(f"{label}_application_key_invalid") from exc
    if not any(raw):
        raise SyntheticStateError(f"{label}_application_key_zero")
    return value.lower()


def _validate_mac(value: object, label: str) -> str:
    if not isinstance(value, str) or _MAC.fullmatch(value) is None:
        raise SyntheticStateError(f"{label}_local_mac_invalid")
    normalized = value.lower()
    if int(normalized.split(":")[0], 16) & 0x01:
        raise SyntheticStateError(f"{label}_local_mac_multicast")
    if int(normalized.replace(":", ""), 16) == 0:
        raise SyntheticStateError(f"{label}_local_mac_zero")
    return normalized


def _validate_node(value: object, role: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SyntheticStateError(f"{role}_object_required")
    expected = {
        "role",
        "hardware_id",
        "pairing_id",
        "pairing_epoch",
        "node_id",
        "credential_generation",
        "key_epoch",
        "application_key_hex",
        "local_mac",
        "capabilities",
    }
    if set(value) != expected:
        raise SyntheticStateError(f"{role}_fields_invalid")
    if value["role"] != role:
        raise SyntheticStateError(f"{role}_role_invalid")
    if not isinstance(value["hardware_id"], str) or _HARDWARE_ID.fullmatch(value["hardware_id"]) is None:
        raise SyntheticStateError(f"{role}_hardware_id_invalid")
    if not isinstance(value["pairing_id"], str) or _PAIRING_ID.fullmatch(value["pairing_id"]) is None:
        raise SyntheticStateError(f"{role}_pairing_id_invalid")
    if not isinstance(value["node_id"], str) or _ID.fullmatch(value["node_id"]) is None:
        raise SyntheticStateError(f"{role}_node_id_invalid")
    for field in ("pairing_epoch", "credential_generation", "key_epoch"):
        current = value[field]
        if not isinstance(current, int) or isinstance(current, bool) or current < 1:
            raise SyntheticStateError(f"{role}_{field}_invalid")
    if value["credential_generation"] != value["pairing_epoch"]:
        raise SyntheticStateError(f"{role}_credential_generation_pairing_epoch_mismatch")
    capabilities = value["capabilities"]
    if (
        not isinstance(capabilities, list)
        or any(not isinstance(item, str) or not item for item in capabilities)
        or len(set(capabilities)) != len(capabilities)
    ):
        raise SyntheticStateError(f"{role}_capabilities_invalid")
    if RELAY_CAPABILITY not in capabilities:
        raise SyntheticStateError(f"{role}_relay_capability_missing")

    normalized = dict(value)
    normalized["application_key_hex"] = _validate_key_hex(value["application_key_hex"], role)
    normalized["local_mac"] = _validate_mac(value["local_mac"], role)
    if not value["hardware_id"].endswith(normalized["local_mac"].replace(":", "")):
        raise SyntheticStateError(f"{role}_hardware_mac_binding_mismatch")
    normalized["capabilities"] = list(capabilities)
    return normalized


def load_fixture(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise SyntheticStateError("fixture_unavailable")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyntheticStateError("fixture_json_invalid") from exc
    if not isinstance(value, dict):
        raise SyntheticStateError("fixture_object_required")
    if set(value) != {"schema", "synthetic_only", "synthetic_marker", "system_id", "child", "relay"}:
        raise SyntheticStateError("fixture_fields_invalid")
    if value["schema"] != INPUT_SCHEMA:
        raise SyntheticStateError("fixture_schema_invalid")
    if value["synthetic_only"] is not True or value["synthetic_marker"] != SYNTHETIC_MARKER:
        raise SyntheticStateError("real_materialization_rejected")
    if not isinstance(value["system_id"], str) or _ID.fullmatch(value["system_id"]) is None:
        raise SyntheticStateError("system_id_invalid")
    child = _validate_node(value["child"], "child")
    relay = _validate_node(value["relay"], "relay")
    for field in ("hardware_id", "pairing_id", "node_id", "local_mac", "application_key_hex"):
        if child[field] == relay[field]:
            raise SyntheticStateError(f"child_relay_{field}_collision")
    return {
        "schema": value["schema"],
        "synthetic_only": True,
        "synthetic_marker": value["synthetic_marker"],
        "system_id": value["system_id"],
        "child": child,
        "relay": relay,
    }


def _credential_document(system_id: str, node: dict[str, Any]) -> dict[str, object]:
    return {
        "system_id": system_id,
        "node_id": node["node_id"],
        "credential_generation": node["credential_generation"],
        "key_epoch": node["key_epoch"],
        "application_key_hex": node["application_key_hex"],
        "local_mac": node["local_mac"],
    }


def _create_registration(path: Path, fixture: dict[str, Any]) -> None:
    db = sqlite3.connect(path)
    try:
        db.executescript(
            """
            CREATE TABLE pairing_sessions (
                pairing_id TEXT PRIMARY KEY,
                hardware_id TEXT NOT NULL,
                pairing_epoch INTEGER NOT NULL,
                state TEXT NOT NULL,
                capabilities_json TEXT NOT NULL
            );
            CREATE TABLE registrations (
                hardware_id TEXT PRIMARY KEY,
                current_pairing_id TEXT NOT NULL,
                pairing_epoch INTEGER NOT NULL,
                node_id TEXT UNIQUE NOT NULL,
                retired_at TEXT
            );
            CREATE TABLE credential_assignments (
                hardware_id TEXT NOT NULL UNIQUE,
                pairing_id TEXT NOT NULL,
                node_id TEXT UNIQUE NOT NULL,
                active_generation INTEGER NOT NULL,
                pending_generation INTEGER,
                state TEXT NOT NULL
            );
            """
        )
        for role in ("child", "relay"):
            node = fixture[role]
            db.execute(
                """
                INSERT INTO pairing_sessions(
                    pairing_id, hardware_id, pairing_epoch, state, capabilities_json
                ) VALUES (?, ?, ?, 'approved', ?)
                """,
                (
                    node["pairing_id"],
                    node["hardware_id"],
                    node["pairing_epoch"],
                    json.dumps(node["capabilities"], separators=(",", ":")),
                ),
            )
            db.execute(
                """
                INSERT INTO registrations(
                    hardware_id, current_pairing_id, pairing_epoch, node_id, retired_at
                ) VALUES (?, ?, ?, ?, NULL)
                """,
                (
                    node["hardware_id"],
                    node["pairing_id"],
                    node["pairing_epoch"],
                    node["node_id"],
                ),
            )
            db.execute(
                """
                INSERT INTO credential_assignments(
                    hardware_id, pairing_id, node_id, active_generation,
                    pending_generation, state
                ) VALUES (?, ?, ?, ?, NULL, 'active')
                """,
                (
                    node["hardware_id"],
                    node["pairing_id"],
                    node["node_id"],
                    node["credential_generation"],
                ),
            )
        db.commit()
    finally:
        db.close()
    os.chmod(path, 0o600)


def _create_replay(path: Path) -> None:
    db = sqlite3.connect(path)
    try:
        db.executescript(
            """
            CREATE TABLE n3w_replay_meta (schema_version INTEGER NOT NULL);
            INSERT INTO n3w_replay_meta(schema_version) VALUES (1);
            CREATE TABLE n3w_replay_state (
                node_id TEXT PRIMARY KEY,
                highest_session_hex TEXT NOT NULL
            );
            CREATE TABLE n3w_replay_seen (
                node_id TEXT NOT NULL,
                boot_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                committed_at TEXT NOT NULL,
                PRIMARY KEY(node_id, boot_id, seq)
            );
            """
        )
        db.commit()
    finally:
        db.close()
    os.chmod(path, 0o600)


def _create_relay_authorization(path: Path, key_dir: Path, fixture: dict[str, Any]) -> None:
    db = sqlite3.connect(path)
    try:
        db.executescript(
            """
            CREATE TABLE n3w_relay_meta (schema_version INTEGER NOT NULL);
            INSERT INTO n3w_relay_meta(schema_version) VALUES (2);
            CREATE TABLE n3w_relay_nodes (
                node_id TEXT PRIMARY KEY,
                active INTEGER NOT NULL
            );
            CREATE TABLE n3w_relay_gateway_nodes (
                gateway_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                enabled INTEGER NOT NULL
            );
            CREATE TABLE n3w_relay_key_epochs (
                node_id TEXT NOT NULL,
                key_epoch INTEGER NOT NULL,
                key_file TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                state TEXT NOT NULL,
                key_sha256 TEXT
            );
            CREATE TABLE n3w_relay_operations (
                operation_key TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                node_id TEXT NOT NULL,
                gateway_id TEXT,
                key_epoch INTEGER,
                status TEXT NOT NULL
            );
            """
        )
        for role in ("child", "relay"):
            node = fixture[role]
            key_name = f"{role}.key"
            key = bytes.fromhex(node["application_key_hex"])
            key_path = key_dir / key_name
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(key)
            db.execute(
                "INSERT INTO n3w_relay_nodes(node_id, active) VALUES (?, 1)",
                (node["node_id"],),
            )
            db.execute(
                """
                INSERT INTO n3w_relay_key_epochs(
                    node_id, key_epoch, key_file, enabled, state, key_sha256
                ) VALUES (?, ?, ?, 1, 'ACTIVE', ?)
                """,
                (
                    node["node_id"],
                    node["key_epoch"],
                    key_name,
                    hashlib.sha256(key).hexdigest(),
                ),
            )
        db.commit()
    finally:
        db.close()
    os.chmod(path, 0o600)


def _assert_output_contract(root: Path, fixture: dict[str, Any]) -> dict[str, object]:
    state = root / "manager_state"
    credentials = root / "credentials"
    expected_root = {"manager_state", "credentials", "synthetic_manifest.json"}
    if {entry.name for entry in root.iterdir()} != expected_root:
        raise SyntheticStateError("output_root_not_minimal")
    expected_state = {
        "registration.sqlite3",
        "replay.sqlite3",
        "relay-authorization.sqlite3",
        "relay-keys",
    }
    if {entry.name for entry in state.iterdir()} != expected_state:
        raise SyntheticStateError("manager_state_not_minimal")
    if {entry.name for entry in (state / "relay-keys").iterdir()} != {"child.key", "relay.key"}:
        raise SyntheticStateError("relay_key_closure_not_exact")
    if {entry.name for entry in credentials.iterdir()} != {"child.json", "relay.json"}:
        raise SyntheticStateError("credential_closure_not_exact")

    reg = sqlite3.connect(state / "registration.sqlite3")
    reg.row_factory = sqlite3.Row
    try:
        tables = {
            row[0]
            for row in reg.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            if not str(row[0]).startswith("sqlite_")
        }
        if tables != {"pairing_sessions", "registrations", "credential_assignments"}:
            raise SyntheticStateError("registration_tables_not_minimal")
        rows = reg.execute(
            "SELECT hardware_id, current_pairing_id, pairing_epoch, node_id, retired_at FROM registrations"
        ).fetchall()
        if len(rows) != 2 or {row["node_id"] for row in rows} != {
            fixture["child"]["node_id"],
            fixture["relay"]["node_id"],
        }:
            raise SyntheticStateError("registration_membership_invalid")
        lifecycle = reg.execute(
            "SELECT node_id, active_generation, pending_generation, state FROM credential_assignments"
        ).fetchall()
        if len(lifecycle) != 2 or any(
            row["state"] != "active" or row["pending_generation"] is not None
            for row in lifecycle
        ):
            raise SyntheticStateError("credential_lifecycle_invalid")
    finally:
        reg.close()

    replay = sqlite3.connect(state / "replay.sqlite3")
    try:
        if replay.execute("SELECT COUNT(*) FROM n3w_replay_state").fetchone()[0] != 0:
            raise SyntheticStateError("replay_state_not_blank")
        if replay.execute("SELECT COUNT(*) FROM n3w_replay_seen").fetchone()[0] != 0:
            raise SyntheticStateError("replay_seen_not_blank")
    finally:
        replay.close()

    auth = sqlite3.connect(state / "relay-authorization.sqlite3")
    try:
        if auth.execute("SELECT COUNT(*) FROM n3w_relay_gateway_nodes").fetchone()[0] != 0:
            raise SyntheticStateError("static_gateway_relation_present")
        if auth.execute("SELECT COUNT(*) FROM n3w_relay_operations").fetchone()[0] != 0:
            raise SyntheticStateError("relay_operation_history_not_blank")
        if auth.execute("SELECT COUNT(*) FROM n3w_relay_nodes").fetchone()[0] != 2:
            raise SyntheticStateError("relay_node_membership_invalid")
        if auth.execute("SELECT COUNT(*) FROM n3w_relay_key_epochs").fetchone()[0] != 2:
            raise SyntheticStateError("relay_key_epoch_closure_invalid")
    finally:
        auth.close()

    for path in root.rglob("*"):
        mode = stat.S_IMODE(path.stat().st_mode)
        expected = 0o700 if path.is_dir() else 0o600
        if mode != expected:
            raise SyntheticStateError(f"output_permissions_invalid:{path.name}")

    return {
        "synthetic_only": True,
        "target_node_count": 2,
        "gateway_relation_row_count": 0,
        "relay_operation_row_count": 0,
        "replay_state_row_count": 0,
        "replay_seen_row_count": 0,
        "credential_generation_equals_pairing_epoch": True,
        "pair_lmk_present": False,
        "pmk_present": False,
    }


def initialize(fixture_path: Path, output: Path) -> dict[str, object]:
    os.umask(0o077)
    fixture = load_fixture(fixture_path)
    if output.exists():
        raise SyntheticStateError("output_already_exists")

    _private_dir(output)
    state = output / "manager_state"
    credentials = output / "credentials"
    _private_dir(state)
    _private_dir(credentials)
    key_dir = state / "relay-keys"
    _private_dir(key_dir)

    _create_registration(state / "registration.sqlite3", fixture)
    _create_replay(state / "replay.sqlite3")
    _create_relay_authorization(
        state / "relay-authorization.sqlite3",
        key_dir,
        fixture,
    )
    _private_json(
        credentials / "child.json",
        _credential_document(fixture["system_id"], fixture["child"]),
    )
    _private_json(
        credentials / "relay.json",
        _credential_document(fixture["system_id"], fixture["relay"]),
    )
    manifest = {
        "schema": "gh.n3w-product-s5-dedicated-two-node-state-synthetic-result/1",
        "authorization": AUTHORIZATION,
        "synthetic_only": True,
        "real_private_state_materialized": False,
        "system_id_sha256": hashlib.sha256(
            fixture["system_id"].encode("utf-8")
        ).hexdigest(),
        "child_node_id_sha256": hashlib.sha256(
            fixture["child"]["node_id"].encode("utf-8")
        ).hexdigest(),
        "relay_node_id_sha256": hashlib.sha256(
            fixture["relay"]["node_id"].encode("utf-8")
        ).hexdigest(),
        "static_gateway_relation_present": False,
        "pair_lmk_present": False,
        "pmk_present": False,
    }
    _private_json(output / "synthetic_manifest.json", manifest)

    result = _assert_output_contract(output, fixture)
    result["authorization"] = AUTHORIZATION
    result["output_contract_verified"] = True
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--fixture", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        result = initialize(Path(args.fixture).resolve(), Path(args.output).resolve())
    except (OSError, sqlite3.Error, SyntheticStateError) as exc:
        print(f"S5_SYNTHETIC_TWO_NODE_STATE_INITIALIZER=FAIL reason={exc}")
        return 2
    print("S5_SYNTHETIC_TWO_NODE_STATE_INITIALIZER=PASS")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
