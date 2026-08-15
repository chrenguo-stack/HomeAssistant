#!/usr/bin/env python3
"""Build one private, non-executable S5 two-board package from bound inputs.

The builder is deliberately host/compile-only. It may run git read-only commands and
ESPHome ``config``/``compile`` only. It never runs/upload/logs a device, opens no
serial/USB/JTAG interface, and creates no physical-execution command sheet.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import secrets
import shutil
import sqlite3
import stat
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

PROVENANCE_REVIEW_AUTHORIZATION = (
    "D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-PRIVATE-PACKAGE-BUILDER-EXACT-HEAD-"
    "READONLY-REBASELINE-AND-PROVENANCE-REVIEW-20260815-01"
)
CONTRACT_REPAIR_AUTHORIZATION = (
    "D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-PRIVATE-PACKAGE-PROVENANCE-METADATA-"
    "AND-MINIMAL-MANAGER-SNAPSHOT-CONTRACT-REPAIR-20260815-01"
)
AUTHORIZATION = CONTRACT_REPAIR_AUTHORIZATION
PREEXISTING_IMPLEMENTATION_HEAD = "180d8dd102b6ca12a0e6adca134a821b57fd3322"
PREEXISTING_IMPLEMENTATION_ORIGIN = "PREEXISTING_REVIEWED_BASELINE"
AUTHORIZATION_START_HEAD = "15510ac3dbf3f8639f63e9dfa5146a27b52eb0d0"
ESPHOME_VERSION = "2026.4.3"
ALLOWED_ESPHOME_ACTIONS = ("config", "compile")
SOURCE_BINDING_PATHS = (
    "firmware/esphome_rc/components/greenhouse_n3w_core",
    "firmware/esphome_rc/components/greenhouse_n3w_product_core",
    "firmware/esphome_rc/components/greenhouse_n3w_product_runtime",
    "firmware/esphome_rc/components/greenhouse_n3w_s5_manager_transport",
    "firmware/esphome_rc/components/greenhouse_n3w_s5_private_runtime",
    "tools/n3w_product_s5_build_private_package.py",
)
REQUIRED_MANAGER_STATE = (
    "registration.sqlite3",
    "replay.sqlite3",
    "relay-authorization.sqlite3",
    "relay-keys",
)
_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_MAC = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
_KEY_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class PrivatePackageBuildError(RuntimeError):
    """The private package cannot be built without violating the frozen contract."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _require_private_path(path: Path, *, directory: bool, label: str) -> None:
    if path.is_symlink():
        raise PrivatePackageBuildError(f"{label}_symlink_rejected")
    try:
        info = path.stat()
    except OSError as exc:
        raise PrivatePackageBuildError(f"{label}_unavailable") from exc
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise PrivatePackageBuildError(f"{label}_not_directory")
    elif not stat.S_ISREG(info.st_mode):
        raise PrivatePackageBuildError(f"{label}_not_regular_file")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise PrivatePackageBuildError(f"{label}_permissions_invalid")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise PrivatePackageBuildError(f"{label}_owner_invalid")


def _load_json(path: Path, label: str) -> dict[str, Any]:
    _require_private_path(path, directory=False, label=label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PrivatePackageBuildError(f"{label}_json_invalid") from exc
    if not isinstance(value, dict):
        raise PrivatePackageBuildError(f"{label}_object_required")
    return value


def _load_credentials(path: Path, label: str) -> dict[str, Any]:
    value = _load_json(path, label)
    expected = {
        "system_id",
        "node_id",
        "credential_generation",
        "key_epoch",
        "application_key_hex",
        "local_mac",
    }
    if set(value) != expected:
        raise PrivatePackageBuildError(f"{label}_fields_invalid")
    if not isinstance(value["system_id"], str) or _ID.fullmatch(value["system_id"]) is None:
        raise PrivatePackageBuildError(f"{label}_system_id_invalid")
    if not isinstance(value["node_id"], str) or _ID.fullmatch(value["node_id"]) is None:
        raise PrivatePackageBuildError(f"{label}_node_id_invalid")
    for field in ("credential_generation", "key_epoch"):
        current = value[field]
        if not isinstance(current, int) or isinstance(current, bool) or current < 1:
            raise PrivatePackageBuildError(f"{label}_{field}_invalid")
    key_hex = value["application_key_hex"]
    if not isinstance(key_hex, str) or len(key_hex) != 64:
        raise PrivatePackageBuildError(f"{label}_application_key_invalid")
    try:
        key = bytes.fromhex(key_hex)
    except ValueError as exc:
        raise PrivatePackageBuildError(f"{label}_application_key_invalid") from exc
    if not any(key):
        raise PrivatePackageBuildError(f"{label}_application_key_zero")
    mac = value["local_mac"]
    if not isinstance(mac, str) or _MAC.fullmatch(mac) is None:
        raise PrivatePackageBuildError(f"{label}_local_mac_invalid")
    if int(mac.split(":")[0], 16) & 0x01 or int(mac.replace(":", ""), 16) == 0:
        raise PrivatePackageBuildError(f"{label}_local_mac_invalid")
    value["application_key_hex"] = key_hex.lower()
    value["local_mac"] = mac.lower()
    return value


def _load_network(path: Path) -> dict[str, Any]:
    value = _load_json(path, "isolated_network")
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
        raise PrivatePackageBuildError("isolated_network_fields_invalid")
    ssid = value["wifi_ssid"]
    password = value["wifi_password"]
    if not isinstance(ssid, str) or not 1 <= len(ssid.encode("utf-8")) <= 32:
        raise PrivatePackageBuildError("isolated_network_wifi_ssid_invalid")
    if not isinstance(password, str) or (password and not 8 <= len(password) <= 63):
        raise PrivatePackageBuildError("isolated_network_wifi_password_invalid")
    channel = value["wifi_channel"]
    if not isinstance(channel, int) or isinstance(channel, bool) or not 1 <= channel <= 14:
        raise PrivatePackageBuildError("isolated_network_wifi_channel_invalid")
    if not isinstance(value["mqtt_broker"], str) or not value["mqtt_broker"].strip():
        raise PrivatePackageBuildError("isolated_network_mqtt_broker_invalid")
    port = value["mqtt_port"]
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise PrivatePackageBuildError("isolated_network_mqtt_port_invalid")
    if not isinstance(value["mqtt_client_id"], str) or not value["mqtt_client_id"].strip():
        raise PrivatePackageBuildError("isolated_network_mqtt_client_id_invalid")
    username = value["mqtt_username"]
    mqtt_password = value["mqtt_password"]
    if username is not None and not isinstance(username, str):
        raise PrivatePackageBuildError("isolated_network_mqtt_username_invalid")
    if mqtt_password is not None and not isinstance(mqtt_password, str):
        raise PrivatePackageBuildError("isolated_network_mqtt_password_invalid")
    if bool(username) != bool(mqtt_password):
        raise PrivatePackageBuildError("isolated_network_mqtt_auth_incomplete")
    if type(value["mqtt_tls"]) is not bool:
        raise PrivatePackageBuildError("isolated_network_mqtt_tls_invalid")
    if value["mqtt_tls"]:
        raise PrivatePackageBuildError("isolated_network_mqtt_tls_requires_separate_ca_contract")
    return value


def _write_private_text(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _write_private_json(path: Path, value: object) -> None:
    _write_private_text(path, json.dumps(value, sort_keys=True, indent=2) + "\n")


def _copy_private_file(source: Path, target: Path, label: str) -> None:
    _require_private_path(source, directory=False, label=label)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(target.parent, 0o700)
    with source.open("rb") as incoming:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)


def _run_git(source_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=source_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise PrivatePackageBuildError("source_git_binding_failed")
    return result


def _verify_source_binding(source_root: Path, source_head: str) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", source_head) is None:
        raise PrivatePackageBuildError("source_head_invalid")
    head = _run_git(source_root, "rev-parse", "HEAD").stdout.strip()
    if head != source_head:
        raise PrivatePackageBuildError("source_head_mismatch")
    lineage = _run_git(
        source_root,
        "merge-base",
        "--is-ancestor",
        AUTHORIZATION_START_HEAD,
        source_head,
        check=False,
    )
    if lineage.returncode != 0:
        raise PrivatePackageBuildError("source_lineage_mismatch")
    status = _run_git(source_root, "status", "--porcelain", "--", *SOURCE_BINDING_PATHS).stdout
    if status.strip():
        raise PrivatePackageBuildError("source_binding_paths_dirty")


def _yaml(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _render_child(
    *, source_root: Path, build_path: Path, credentials: dict[str, Any], pmk_hex: str, channel: int
) -> str:
    components = source_root / "firmware" / "esphome_rc" / "components"
    return f"""esphome:
  name: gh-n3w-s5-child-private
  friendly_name: N3-W Product S5 Private Child
  min_version: {ESPHOME_VERSION}
  build_path: {_yaml(build_path)}

esp32:
  board: esp32-c6-devkitm-1
  variant: ESP32C6
  flash_size: 8MB
  framework:
    type: esp-idf
    advanced:
      include_builtin_idf_components:
        - nvs_flash
        - esp_wifi

logger:
  level: INFO
  hardware_uart: USB_SERIAL_JTAG

external_components:
  - source:
      type: local
      path: {_yaml(components)}
    components:
      - greenhouse_n3w_core
      - greenhouse_n3w_product_core
      - greenhouse_n3w_product_runtime
      - greenhouse_n3w_s5_private_runtime

greenhouse_n3w_core:

greenhouse_n3w_product_core:

greenhouse_n3w_product_runtime:
  id: n3w_product_integration
  role: child
  execution_enabled: true
  pmk_hex: {_yaml(pmk_hex)}
  last_direct_channel: {channel}

greenhouse_n3w_s5_private_runtime:
  id: n3w_private_runtime_material
  product_runtime_id: n3w_product_integration
  role: child
  system_id: {_yaml(credentials['system_id'])}
  node_id: {_yaml(credentials['node_id'])}
  credential_generation: {credentials['credential_generation']}
  key_epoch: {credentials['key_epoch']}
  application_key_hex: {_yaml(credentials['application_key_hex'])}
  local_mac: {_yaml(credentials['local_mac'].replace(':', ''))}
"""


def _render_relay(
    *,
    source_root: Path,
    build_path: Path,
    credentials: dict[str, Any],
    network: dict[str, Any],
    pmk_hex: str,
) -> str:
    components = source_root / "firmware" / "esphome_rc" / "components"
    password_line = f"      password: {_yaml(network['wifi_password'])}\n" if network["wifi_password"] else ""
    mqtt_auth = ""
    if network["mqtt_username"]:
        mqtt_auth = (
            f"  username: {_yaml(network['mqtt_username'])}\n"
            f"  password: {_yaml(network['mqtt_password'])}\n"
        )
    channel = network["wifi_channel"]
    return f"""esphome:
  name: gh-n3w-s5-relay-private
  friendly_name: N3-W Product S5 Private Relay
  min_version: {ESPHOME_VERSION}
  build_path: {_yaml(build_path)}

esp32:
  board: esp32-c6-devkitm-1
  variant: ESP32C6
  flash_size: 8MB
  framework:
    type: esp-idf
    advanced:
      include_builtin_idf_components:
        - nvs_flash
        - esp_wifi

logger:
  level: INFO
  hardware_uart: USB_SERIAL_JTAG

wifi:
  networks:
    - ssid: {_yaml(network['wifi_ssid'])}
{password_line}      channel: {channel}
  fast_connect: true

mqtt:
  broker: {_yaml(network['mqtt_broker'])}
  port: {network['mqtt_port']}
  client_id: {_yaml(network['mqtt_client_id'])}
{mqtt_auth}  discovery: false

external_components:
  - source:
      type: local
      path: {_yaml(components)}
    components:
      - greenhouse_n3w_core
      - greenhouse_n3w_product_core
      - greenhouse_n3w_product_runtime
      - greenhouse_n3w_s5_manager_transport
      - greenhouse_n3w_s5_private_runtime

greenhouse_n3w_core:

greenhouse_n3w_product_core:

greenhouse_n3w_product_runtime:
  id: n3w_product_integration
  role: relay
  execution_enabled: true
  pmk_hex: {_yaml(pmk_hex)}
  last_direct_channel: {channel}

greenhouse_n3w_s5_manager_transport:
  id: n3w_product_manager_transport
  product_runtime_id: n3w_product_integration
  execution_enabled: true

greenhouse_n3w_s5_private_runtime:
  id: n3w_private_runtime_material
  product_runtime_id: n3w_product_integration
  manager_transport_id: n3w_product_manager_transport
  role: relay
  system_id: {_yaml(credentials['system_id'])}
  node_id: {_yaml(credentials['node_id'])}
  credential_generation: {credentials['credential_generation']}
  key_epoch: {credentials['key_epoch']}
  application_key_hex: {_yaml(credentials['application_key_hex'])}
  local_mac: {_yaml(credentials['local_mac'].replace(':', ''))}
  relay_capable: true
  low_battery: false
  overloaded: false
"""


def _sqlite_connection(path: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        row = connection.execute("PRAGMA quick_check").fetchone()
        if row is None or row[0] != "ok":
            raise PrivatePackageBuildError(f"manager_state_corrupt:{path.name}")
        return connection
    except sqlite3.Error as exc:
        raise PrivatePackageBuildError(f"manager_state_unavailable:{path.name}") from exc


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }


def _validate_pairing_state(path: Path, credential: dict[str, Any]) -> dict[str, object]:
    connection = _sqlite_connection(path)
    try:
        if not {"registrations", "pairing_sessions", "credential_assignments"} <= _table_names(connection):
            raise PrivatePackageBuildError("manager_registration_schema_mismatch")
        rows = connection.execute(
            """
            SELECT r.hardware_id, r.node_id, r.retired_at, s.state
            FROM registrations AS r
            JOIN pairing_sessions AS s ON s.pairing_id = r.current_pairing_id
            WHERE r.node_id = ?
            """,
            (credential["node_id"],),
        ).fetchall()
        if len(rows) != 1 or rows[0]["state"] != "approved" or rows[0]["retired_at"] is not None:
            raise PrivatePackageBuildError("manager_registration_membership_mismatch")
        lifecycle = connection.execute(
            """
            SELECT hardware_id, node_id, active_generation, state
            FROM credential_assignments
            WHERE node_id = ? AND state != 'revoked'
            """,
            (credential["node_id"],),
        ).fetchall()
        if (
            len(lifecycle) != 1
            or lifecycle[0]["hardware_id"] != rows[0]["hardware_id"]
            or lifecycle[0]["state"] != "active"
            or lifecycle[0]["active_generation"] != credential["credential_generation"]
        ):
            raise PrivatePackageBuildError("manager_credential_generation_mismatch")
        return {
            "node_id": credential["node_id"],
            "credential_generation": credential["credential_generation"],
            "active_registration": True,
        }
    except sqlite3.Error as exc:
        raise PrivatePackageBuildError("manager_registration_query_failed") from exc
    finally:
        connection.close()


def _validate_minimal_registration_snapshot(path: Path, allowed_node_ids: set[str]) -> None:
    connection = _sqlite_connection(path)
    try:
        if _table_names(connection) != {"registrations", "pairing_sessions", "credential_assignments"}:
            raise PrivatePackageBuildError("manager_snapshot_registration_not_minimal")
        registrations = connection.execute(
            "SELECT hardware_id, current_pairing_id, node_id, retired_at FROM registrations"
        ).fetchall()
        if (
            len(registrations) != 2
            or {row["node_id"] for row in registrations} != allowed_node_ids
            or any(row["retired_at"] is not None for row in registrations)
        ):
            raise PrivatePackageBuildError("manager_snapshot_registration_not_minimal")
        hardware_ids = {row["hardware_id"] for row in registrations}
        pairing_ids = {row["current_pairing_id"] for row in registrations}
        pairings = connection.execute(
            "SELECT pairing_id, hardware_id, state FROM pairing_sessions"
        ).fetchall()
        if (
            len(pairings) != 2
            or {row["pairing_id"] for row in pairings} != pairing_ids
            or {row["hardware_id"] for row in pairings} != hardware_ids
            or any(row["state"] != "approved" for row in pairings)
        ):
            raise PrivatePackageBuildError("manager_snapshot_pairing_sessions_not_minimal")
        lifecycle = connection.execute(
            "SELECT hardware_id, node_id, active_generation, state FROM credential_assignments"
        ).fetchall()
        if (
            len(lifecycle) != 2
            or {row["node_id"] for row in lifecycle} != allowed_node_ids
            or {row["hardware_id"] for row in lifecycle} != hardware_ids
            or any(row["state"] != "active" for row in lifecycle)
        ):
            raise PrivatePackageBuildError("manager_snapshot_credentials_not_minimal")
    except sqlite3.Error as exc:
        raise PrivatePackageBuildError("manager_snapshot_registration_query_failed") from exc
    finally:
        connection.close()


def _validate_replay_state(path: Path) -> dict[str, object]:
    connection = _sqlite_connection(path)
    try:
        names = {name for name in _table_names(connection) if name.startswith("n3w_replay_")}
        if names != {"n3w_replay_meta", "n3w_replay_state", "n3w_replay_seen"}:
            raise PrivatePackageBuildError("manager_replay_schema_mismatch")
        versions = connection.execute("SELECT schema_version FROM n3w_replay_meta").fetchall()
        if len(versions) != 1 or versions[0][0] != 1:
            raise PrivatePackageBuildError("manager_replay_schema_mismatch")
        return {
            "schema_version": 1,
            "state_row_count": int(connection.execute("SELECT COUNT(*) FROM n3w_replay_state").fetchone()[0]),
            "seen_row_count": int(connection.execute("SELECT COUNT(*) FROM n3w_replay_seen").fetchone()[0]),
        }
    finally:
        connection.close()


def _validate_minimal_replay_snapshot(path: Path, allowed_node_ids: set[str]) -> None:
    connection = _sqlite_connection(path)
    try:
        if _table_names(connection) != {"n3w_replay_meta", "n3w_replay_state", "n3w_replay_seen"}:
            raise PrivatePackageBuildError("manager_snapshot_replay_not_minimal")
        state_ids = {
            str(row[0]) for row in connection.execute("SELECT DISTINCT node_id FROM n3w_replay_state").fetchall()
        }
        seen_ids = {
            str(row[0]) for row in connection.execute("SELECT DISTINCT node_id FROM n3w_replay_seen").fetchall()
        }
        if not state_ids <= allowed_node_ids or not seen_ids <= allowed_node_ids:
            raise PrivatePackageBuildError("manager_snapshot_replay_contains_other_node")
    except sqlite3.Error as exc:
        raise PrivatePackageBuildError("manager_snapshot_replay_query_failed") from exc
    finally:
        connection.close()


def _validate_application_key(
    connection: sqlite3.Connection,
    key_dir: Path,
    credential: dict[str, Any],
    schema_version: int,
) -> dict[str, object]:
    node = connection.execute(
        "SELECT active FROM n3w_relay_nodes WHERE node_id = ?", (credential["node_id"],)
    ).fetchone()
    if node is None or node["active"] != 1:
        raise PrivatePackageBuildError("manager_application_key_node_inactive")
    if schema_version == 1:
        epoch = connection.execute(
            "SELECT key_file, enabled FROM n3w_relay_key_epochs WHERE node_id = ? AND key_epoch = ?",
            (credential["node_id"], credential["key_epoch"]),
        ).fetchone()
        accepted = epoch is not None and epoch["enabled"] == 1
        expected_hash = None
    else:
        epoch = connection.execute(
            """
            SELECT key_file, enabled, state, key_sha256
            FROM n3w_relay_key_epochs
            WHERE node_id = ? AND key_epoch = ?
            """,
            (credential["node_id"], credential["key_epoch"]),
        ).fetchone()
        accepted = (
            epoch is not None
            and epoch["enabled"] == 1
            and epoch["state"] in {"ACTIVE", "GRACE"}
        )
        expected_hash = epoch["key_sha256"] if epoch is not None else None
    if not accepted or epoch is None:
        raise PrivatePackageBuildError("manager_application_key_epoch_mismatch")
    key_file = epoch["key_file"]
    if not isinstance(key_file, str) or _KEY_FILE.fullmatch(key_file) is None:
        raise PrivatePackageBuildError("manager_application_key_file_invalid")
    path = key_dir / key_file
    _require_private_path(path, directory=False, label="manager_application_key_file")
    key = path.read_bytes()
    if len(key) != 32 or key != bytes.fromhex(credential["application_key_hex"]):
        raise PrivatePackageBuildError("manager_application_key_material_mismatch")
    actual_hash = hashlib.sha256(key).hexdigest()
    if expected_hash is not None and (not isinstance(expected_hash, str) or expected_hash != actual_hash):
        raise PrivatePackageBuildError("manager_application_key_hash_mismatch")
    return {
        "node_id": credential["node_id"],
        "key_epoch": credential["key_epoch"],
        "key_file": key_file,
        "application_key_sha256": actual_hash,
    }


def _validate_relay_authorization_state(
    path: Path, key_dir: Path, child: dict[str, Any], relay: dict[str, Any]
) -> dict[str, object]:
    connection = _sqlite_connection(path)
    try:
        names = {name for name in _table_names(connection) if name.startswith("n3w_relay_")}
        if "n3w_relay_meta" not in names:
            raise PrivatePackageBuildError("manager_relay_authorization_schema_mismatch")
        versions = connection.execute("SELECT schema_version FROM n3w_relay_meta").fetchall()
        if len(versions) != 1 or versions[0][0] not in {1, 2}:
            raise PrivatePackageBuildError("manager_relay_authorization_schema_mismatch")
        version = int(versions[0][0])
        expected = {
            "n3w_relay_meta",
            "n3w_relay_nodes",
            "n3w_relay_gateway_nodes",
            "n3w_relay_key_epochs",
        }
        if version == 2:
            expected.add("n3w_relay_operations")
        if names != expected:
            raise PrivatePackageBuildError("manager_relay_authorization_schema_mismatch")

        allowed_node_ids = {str(child["node_id"]), str(relay["node_id"])}
        node_rows = connection.execute("SELECT node_id, active FROM n3w_relay_nodes").fetchall()
        if (
            len(node_rows) != 2
            or {str(row["node_id"]) for row in node_rows} != allowed_node_ids
            or any(row["active"] != 1 for row in node_rows)
        ):
            raise PrivatePackageBuildError("manager_snapshot_relay_nodes_not_minimal")

        if version == 1:
            epoch_rows = connection.execute(
                "SELECT node_id, key_epoch, key_file, enabled FROM n3w_relay_key_epochs"
            ).fetchall()
        else:
            epoch_rows = connection.execute(
                "SELECT node_id, key_epoch, key_file, enabled, state FROM n3w_relay_key_epochs"
            ).fetchall()
        expected_epochs = {
            str(child["node_id"]): int(child["key_epoch"]),
            str(relay["node_id"]): int(relay["key_epoch"]),
        }
        if len(epoch_rows) != 2 or {str(row["node_id"]) for row in epoch_rows} != allowed_node_ids:
            raise PrivatePackageBuildError("manager_snapshot_key_epochs_not_minimal")
        for row in epoch_rows:
            node_id = str(row["node_id"])
            if row["key_epoch"] != expected_epochs[node_id] or row["enabled"] != 1:
                raise PrivatePackageBuildError("manager_snapshot_key_epochs_not_minimal")
            if version == 2 and row["state"] not in {"ACTIVE", "GRACE"}:
                raise PrivatePackageBuildError("manager_snapshot_key_epochs_not_minimal")

        gateway_rows = int(connection.execute("SELECT COUNT(*) FROM n3w_relay_gateway_nodes").fetchone()[0])
        if gateway_rows != 0:
            raise PrivatePackageBuildError("manager_snapshot_gateway_relation_present")
        if version == 2:
            operation_rows = int(connection.execute("SELECT COUNT(*) FROM n3w_relay_operations").fetchone()[0])
            if operation_rows != 0:
                raise PrivatePackageBuildError("manager_snapshot_relay_operations_not_minimal")

        child_binding = _validate_application_key(connection, key_dir, child, version)
        relay_binding = _validate_application_key(connection, key_dir, relay, version)
        key_files = {str(child_binding["key_file"]), str(relay_binding["key_file"])}
        if len(key_files) != 2:
            raise PrivatePackageBuildError("manager_snapshot_relay_key_file_collision")
        return {
            "schema_version": version,
            "child": child_binding,
            "relay": relay_binding,
            "required_key_files": sorted(key_files),
            "enabled_gateway_grant_count": 0,
            "gateway_relation_row_count": 0,
            "dynamic_ingress_authority_persisted": False,
        }
    except sqlite3.Error as exc:
        raise PrivatePackageBuildError("manager_relay_authorization_query_failed") from exc
    finally:
        connection.close()


def _validate_minimal_manager_snapshot_source(
    source: Path, child: dict[str, Any], relay: dict[str, Any]
) -> dict[str, object]:
    _require_private_path(source, directory=True, label="manager_state_root")
    actual_top_level = {entry.name for entry in source.iterdir()}
    if actual_top_level != set(REQUIRED_MANAGER_STATE):
        raise PrivatePackageBuildError("manager_snapshot_top_level_not_minimal")
    for sidecar in source.glob("*.sqlite3-*"):
        if sidecar.name.endswith(("-wal", "-shm", "-journal")):
            raise PrivatePackageBuildError("manager_state_not_quiescent")
    for name in REQUIRED_MANAGER_STATE:
        if not (source / name).exists():
            raise PrivatePackageBuildError(f"manager_state_missing:{name}")

    allowed_node_ids = {str(child["node_id"]), str(relay["node_id"])}
    _validate_minimal_registration_snapshot(source / "registration.sqlite3", allowed_node_ids)
    _validate_minimal_replay_snapshot(source / "replay.sqlite3", allowed_node_ids)

    source_keys = source / "relay-keys"
    _require_private_path(source_keys, directory=True, label="manager_relay_key_dir")
    for entry in source_keys.iterdir():
        if not entry.is_file() or entry.is_symlink():
            raise PrivatePackageBuildError("manager_relay_key_dir_entry_invalid")
    relay_auth = _validate_relay_authorization_state(
        source / "relay-authorization.sqlite3", source_keys, child, relay
    )
    actual_key_files = {entry.name for entry in source_keys.iterdir()}
    expected_key_files = set(relay_auth["required_key_files"])
    if actual_key_files != expected_key_files:
        raise PrivatePackageBuildError("manager_snapshot_relay_keys_not_minimal")

    return {
        "minimal_snapshot_verified": True,
        "target_node_ids": sorted(allowed_node_ids),
        "required_key_files": sorted(expected_key_files),
        "top_level_entries": sorted(actual_top_level),
    }


def _copy_and_validate_manager_state(
    source: Path, target: Path, child: dict[str, Any], relay: dict[str, Any]
) -> dict[str, object]:
    minimal_source = _validate_minimal_manager_snapshot_source(source, child, relay)

    target.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name in REQUIRED_MANAGER_STATE[:3]:
        _copy_private_file(source / name, target / name, f"manager_state_{name}")
    source_keys = source / "relay-keys"
    target_keys = target / "relay-keys"
    target_keys.mkdir(mode=0o700)
    for key_file in minimal_source["required_key_files"]:
        _copy_private_file(source_keys / str(key_file), target_keys / str(key_file), "manager_application_key_file")

    registration = _validate_pairing_state(target / "registration.sqlite3", child)
    relay_registration = _validate_pairing_state(target / "registration.sqlite3", relay)
    replay = _validate_replay_state(target / "replay.sqlite3")
    relay_auth = _validate_relay_authorization_state(
        target / "relay-authorization.sqlite3", target_keys, child, relay
    )
    file_hashes: dict[str, str] = {}
    for path in sorted(target.rglob("*")):
        if path.is_file():
            file_hashes[str(path.relative_to(target))] = _sha256_file(path)
    return {
        "registration": {"child": registration, "relay": relay_registration},
        "replay": replay,
        "relay_authorization": relay_auth,
        "minimal_snapshot": minimal_source,
        "file_sha256": file_hashes,
        "quiescent_snapshot_required": True,
    }


def _run_esphome(action: str, config: Path, log: Path, source_root: Path) -> None:
    if action not in ALLOWED_ESPHOME_ACTIONS:
        raise PrivatePackageBuildError("esphome_action_not_allowed")
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        result = subprocess.run(
            [sys.executable, "-m", "esphome", action, str(config)],
            cwd=source_root,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            env=os.environ.copy(),
        )
    if result.returncode != 0:
        raise PrivatePackageBuildError(f"esphome_{action}_failed_private_log:{log.name}")


def _locate_firmware(build_path: Path, role: str) -> Path:
    candidates = [path for path in build_path.rglob("firmware.bin") if path.is_file()]
    if len(candidates) != 1:
        raise PrivatePackageBuildError(f"{role}_firmware_artifact_ambiguous")
    return candidates[0]


def _public_credential_binding(value: dict[str, Any]) -> dict[str, object]:
    return {
        "system_id": value["system_id"],
        "node_id": value["node_id"],
        "credential_generation": value["credential_generation"],
        "key_epoch": value["key_epoch"],
        "local_mac_sha256": hashlib.sha256(value["local_mac"].encode("ascii")).hexdigest(),
        "application_key_sha256": hashlib.sha256(bytes.fromhex(value["application_key_hex"])).hexdigest(),
    }


def _public_network_binding(value: dict[str, Any]) -> dict[str, object]:
    return {
        "wifi_ssid_sha256": hashlib.sha256(value["wifi_ssid"].encode()).hexdigest(),
        "wifi_channel": value["wifi_channel"],
        "mqtt_broker_sha256": hashlib.sha256(value["mqtt_broker"].encode()).hexdigest(),
        "mqtt_port": value["mqtt_port"],
        "mqtt_client_id_sha256": hashlib.sha256(value["mqtt_client_id"].encode()).hexdigest(),
        "mqtt_tls": value["mqtt_tls"],
        "mqtt_authentication_configured": bool(value["mqtt_username"]),
    }


def build(args: argparse.Namespace) -> dict[str, object]:
    os.umask(0o077)
    source_root = Path(args.source_root).resolve()
    if not source_root.is_dir():
        raise PrivatePackageBuildError("source_root_invalid")
    _verify_source_binding(source_root, args.source_head)
    try:
        installed_esphome = importlib.metadata.version("esphome")
    except importlib.metadata.PackageNotFoundError as exc:
        raise PrivatePackageBuildError("esphome_not_installed") from exc
    if installed_esphome != ESPHOME_VERSION:
        raise PrivatePackageBuildError("esphome_version_mismatch")

    child_path = Path(args.child_credentials).resolve()
    relay_path = Path(args.relay_credentials).resolve()
    network_path = Path(args.isolated_network).resolve()
    manager_state = Path(args.manager_state_root).resolve()
    output = Path(args.output).resolve()
    for private_path in (child_path, relay_path, network_path, manager_state, output):
        if _inside(private_path, source_root):
            raise PrivatePackageBuildError("private_material_inside_source_tree_rejected")
    if output.exists():
        raise PrivatePackageBuildError("output_already_exists")

    child = _load_credentials(child_path, "child_credentials")
    relay = _load_credentials(relay_path, "relay_credentials")
    network = _load_network(network_path)
    if child["system_id"] != relay["system_id"]:
        raise PrivatePackageBuildError("cross_system_pair_rejected")
    if child["node_id"] == relay["node_id"] or child["local_mac"] == relay["local_mac"]:
        raise PrivatePackageBuildError("child_relay_identity_collision")

    # Validate the upstream snapshot before creating any package output. This prevents
    # unrelated node material from ever being copied into a failed package attempt.
    _validate_minimal_manager_snapshot_source(manager_state, child, relay)

    output.mkdir(mode=0o700, parents=False)
    for name in ("inputs", "rendered", "artifacts", "build_logs", ".work"):
        (output / name).mkdir(mode=0o700)

    package_id = f"S5-E2E-{uuid.uuid4()}"
    pmk = secrets.token_bytes(16)
    if len(pmk) != 16 or not any(pmk):
        raise PrivatePackageBuildError("fresh_pmk_generation_failed")
    pmk_hex = pmk.hex()
    _write_private_json(
        output / "private_secrets.json",
        {
            "schema": "gh.n3w-product-s5-private-package-secrets/2",
            "package_id": package_id,
            "espnow_pmk_hex": pmk_hex,
            "physical_execution_authorization": None,
            "execution_authorized": False,
        },
    )
    _copy_private_file(child_path, output / "inputs" / "child_credentials.json", "child_credentials")
    _copy_private_file(relay_path, output / "inputs" / "relay_credentials.json", "relay_credentials")
    _copy_private_file(network_path, output / "inputs" / "isolated_network.json", "isolated_network")
    manager_binding = _copy_and_validate_manager_state(
        manager_state, output / "manager_state", child, relay
    )

    child_yaml = _render_child(
        source_root=source_root,
        build_path=output / ".work" / "child",
        credentials=child,
        pmk_hex=pmk_hex,
        channel=network["wifi_channel"],
    )
    relay_yaml = _render_relay(
        source_root=source_root,
        build_path=output / ".work" / "relay",
        credentials=relay,
        network=network,
        pmk_hex=pmk_hex,
    )
    if child_yaml.count(pmk_hex) != 1 or relay_yaml.count(pmk_hex) != 1:
        raise PrivatePackageBuildError("pmk_render_binding_failed")
    child_config = output / "rendered" / "child.yml"
    relay_config = output / "rendered" / "relay.yml"
    _write_private_text(child_config, child_yaml)
    _write_private_text(relay_config, relay_yaml)

    for role, config in (("child", child_config), ("relay", relay_config)):
        _run_esphome("config", config, output / "build_logs" / f"{role}-config.log", source_root)
        _run_esphome("compile", config, output / "build_logs" / f"{role}-compile.log", source_root)

    shutil.rmtree(output / "rendered" / ".esphome", ignore_errors=True)
    child_fw = _locate_firmware(output / ".work" / "child", "child")
    relay_fw = _locate_firmware(output / ".work" / "relay", "relay")
    _copy_private_file(child_fw, output / "artifacts" / "child_firmware.bin", "child_firmware")
    _copy_private_file(relay_fw, output / "artifacts" / "relay_firmware.bin", "relay_firmware")
    shutil.rmtree(output / ".work")

    manifest = {
        "schema": "gh.n3w-product-s5-private-physical-e2e-package/3",
        "package_id": package_id,
        "implementation_provenance": {
            "origin": PREEXISTING_IMPLEMENTATION_ORIGIN,
            "preexisting_implementation_head": PREEXISTING_IMPLEMENTATION_HEAD,
            "provenance_review_authorization": PROVENANCE_REVIEW_AUTHORIZATION,
            "contract_repair_authorization": CONTRACT_REPAIR_AUTHORIZATION,
            "retroactive_legacy_authorization_attribution": False,
        },
        "authorization_start_head": AUTHORIZATION_START_HEAD,
        "source_head": args.source_head,
        "esphome_version": ESPHOME_VERSION,
        "physical_execution_authorization": None,
        "execution_authorized": False,
        "system_id": child["system_id"],
        "child_binding": _public_credential_binding(child),
        "relay_binding": _public_credential_binding(relay),
        "network_binding": _public_network_binding(network),
        "radio_binding": {
            "espnow_channel": network["wifi_channel"],
            "wifi_channel": network["wifi_channel"],
            "channels_match": True,
            "fresh_pmk_sha256": hashlib.sha256(pmk).hexdigest(),
            "same_fresh_pmk_rendered_into_both_firmware_configs": True,
        },
        "build_provenance": {
            "source_tree_exact_head_verified": True,
            "source_binding_paths_clean": True,
            "allowed_esphome_actions": list(ALLOWED_ESPHOME_ACTIONS),
            "minimal_manager_snapshot_verified": True,
            "child_rendered_yaml_sha256": _sha256_file(child_config),
            "relay_rendered_yaml_sha256": _sha256_file(relay_config),
            "child_firmware_sha256": _sha256_file(output / "artifacts" / "child_firmware.bin"),
            "relay_firmware_sha256": _sha256_file(output / "artifacts" / "relay_firmware.bin"),
        },
        "input_sha256": {
            "child_credentials": _sha256_file(output / "inputs" / "child_credentials.json"),
            "relay_credentials": _sha256_file(output / "inputs" / "relay_credentials.json"),
            "isolated_network": _sha256_file(output / "inputs" / "isolated_network.json"),
        },
        "manager_state_binding": manager_binding,
        "composition_contract": {
            "child_consumes_only_own_post_registration_material": True,
            "relay_consumes_only_own_post_registration_material": True,
            "manager_snapshot_contains_only_target_child_and_relay": True,
            "relay_key_directory_exact_target_closure": True,
            "factory_peer_identity_present": False,
            "static_gateway_child_preseed_present": False,
            "pair_lmk_supplied_by_package": False,
            "manager_generates_pair_lmk": False,
            "dynamic_ingress_authority_is_ram_only": True,
        },
        "ready_for_readonly_binding_review": True,
        "production_access_allowed": False,
        "n3l_allowed": False,
    }
    _write_private_json(output / "manifest.json", manifest)
    _write_private_json(
        output / "cleanup_contract.json",
        {
            "schema": "gh.n3w-product-s5-private-cleanup-contract/2",
            "package_id": package_id,
            "required": [
                "stop_test_applications_and_espnow_rf",
                "return_both_boards_to_rom_bootloader_no_reset",
                "freeze_sanitized_evidence_before_private_deletion",
                "delete_entire_private_package_root",
            ],
        },
    )
    _write_private_text(
        output / "READ_ONLY_GATE.txt",
        "PRIVATE S5 PACKAGE\n"
        f"package_id={package_id}\n"
        "execution_authorized=false\n"
        "A separate explicit physical-execution authorization is mandatory.\n"
        "No device command sheet is present in this package.\n",
    )
    return {
        "package_id": package_id,
        "source_head": args.source_head,
        "child_firmware_sha256": manifest["build_provenance"]["child_firmware_sha256"],
        "relay_firmware_sha256": manifest["build_provenance"]["relay_firmware_sha256"],
        "manager_state_file_count": len(manager_binding["file_sha256"]),
        "minimal_manager_snapshot_verified": True,
        "execution_authorized": False,
        "ready_for_readonly_binding_review": True,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--source-root", required=True)
    value.add_argument("--source-head", required=True)
    value.add_argument("--child-credentials", required=True)
    value.add_argument("--relay-credentials", required=True)
    value.add_argument("--isolated-network", required=True)
    value.add_argument("--manager-state-root", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        result = build(parser().parse_args())
    except (OSError, PrivatePackageBuildError) as exc:
        print(f"PRIVATE_PACKAGE_BUILD=FAIL reason={exc}")
        return 2
    print("PRIVATE_PACKAGE_BUILD=PASS")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())