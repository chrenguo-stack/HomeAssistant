#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import ipaddress
import json
import os
import re
import sqlite3
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any
from collections.abc import Sequence

SCHEMA = "gh.n3w-t1-clean-reference-pairing-readiness-bridge/1"
PACKAGE_SCHEMA = "gh.n3w-t1-clean-reference-pairing-readiness-bridge-package/1"
TRANSACTION_SCHEMA = "gh.n3w-t1-clean-reference-pairing-readiness-bridge-transaction/1"

PRODUCT_SOURCE_HEAD = "24382caae4a1f5d459297f86e8d18f10a848ca64"
R2A_CONTROL_HEAD = "abeb6c31147bcf249361dcec7e9536eaed6106a6"
R2B_CONTROL_HEAD = "e15c64ac8f0f5f482a6c8538072031734002a559"
R3_OBSERVER_CONTROL_HEAD = "da9124fe18774cdb5822f9eb3afee40120cfb04f"
R2_REFERENCE_SHA256 = "89da2a2b2cc1ce0fa024c3c45e24a71f09ba05e0e0cadbd67dd6387291239747"

DEVICE_PROVISIONING_BLOB = "6e63d03027a251248bbe418b60175f9f241a2865"
FIRST_PAIRING_ONBOARDING_BLOB = "332a59ad083e1db1c29de174139b3f45342c5fa8"

CONFIRMATION = "CREATE CLEAN REFERENCE PAIRING READINESS: YES"
AUTHORIZATION_PREFIX = "N3W_T1_CORE_STACK_CLEAN_REFERENCE_PAIRING_READINESS_"

R2A_TRANSACTION = Path("/var/lib/n3w-t1-clean-reference-r2a/transaction.json")
R2B_TRANSACTION = Path("/var/lib/n3w-t1-clean-reference-r2b/transaction.json")

RELEASE_PATH = Path("/opt/HomeAssistant/infra/n3w-t1/production/fresh-release.json")
SYSTEM_IDENTITY_ROOT = Path("/var/lib/greenhouse-manager/identity")
SYSTEM_IDENTITY_MARKER = SYSTEM_IDENTITY_ROOT / "INITIALIZED.json"
SYSTEM_IDENTITY = SYSTEM_IDENTITY_ROOT / "system-identity.json"
MANAGER_IDENTITY = SYSTEM_IDENTITY_ROOT / "manager-identity.json"
MACHINE_ID_PATH = Path("/etc/machine-id")
SSH_HOST_PUBLIC_KEY = Path("/etc/ssh/ssh_host_ed25519_key.pub")
MANAGER_DB = Path("/var/lib/greenhouse-manager/manager/manager-state.sqlite3")
CREDENTIAL_DB = Path("/var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3")
PEER_TRUST_DB = Path("/var/lib/greenhouse-manager/n3w/system-peer-trust.sqlite3")
APPLICATION_KEY_DB = Path("/var/lib/greenhouse-manager/n3w/relay-authorization.sqlite3")

PROVISIONING_ROOT = Path("/var/lib/n3w-t1-provisioning")
FACTORY_ACCEPTED = PROVISIONING_ROOT / "FACTORY_ACCEPTED.json"
FIRST_PAIRING_TRANSACTION = PROVISIONING_ROOT / "FIRST_PAIRING_ONBOARDING.json"
SUCCESSOR_RECOVERY = PROVISIONING_ROOT / "FIRST_PAIRING_SUCCESSOR_RECOVERY.json"

BRIDGE_ROOT = Path("/var/lib/n3w-t1-clean-reference-pairing-readiness")
BRIDGE_TRANSACTION = BRIDGE_ROOT / "transaction.json"

DEVICE_PROVISIONING_TOOL = Path("/opt/HomeAssistant/tools/n3w_t1_device_provisioning_host.py")
FIRST_PAIRING_TOOL = Path("/opt/HomeAssistant/tools/n3w_t1_first_pairing_onboarding.py")

REGISTRATION_BOOTSTRAP_PORT = 47110
REGISTRATION_DISCOVERY_PORT = 47111
PRIVILEGED_PAIRING_PORT = 47112

TRUSTED_LAN_STATE = Path("/run/n3w/trusted-product-lan/state.json")
REGISTRATION_GUARD_TOOL = Path("/opt/HomeAssistant/tools/n3w_registration_ingress_guard.py")
BROKER_GUARD_TOOL = Path("/opt/HomeAssistant/tools/n3w_broker_ingress_guard.py")
REGISTRATION_GUARD_BLOB = "ef5077b6bc80c73bc8d3f35cf7a33a198ce918c7"
BROKER_GUARD_BLOB = "795903b06c7ee93a0602649e478bc070723ab8c0"

EXPECTED_SERVICES = ("broker", "homeassistant", "manager")


class BridgeError(RuntimeError):
    pass


def _run(
    argv: Sequence[str],
    *,
    timeout: float = 60.0,
    allowed: frozenset[int] = frozenset({0}),
) -> str:
    completed = subprocess.run(
        tuple(argv),
        check=False,
        text=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout,
    )
    if completed.returncode not in allowed:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise BridgeError(
            f"command_failed:{Path(argv[0]).name}:{completed.returncode}:"
            f"{hashlib.sha256(detail.encode()).hexdigest() if detail else 'none'}"
        )
    return completed.stdout


def _sha256(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise BridgeError(f"file_invalid:{path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_blob_sha(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise BridgeError(f"source_tool_invalid:{path.name}")
    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def _read_json(path: Path, *, mode: int | None = None) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise BridgeError(f"record_unavailable:{path.name}")
    metadata = path.stat()
    if mode is not None and (
        metadata.st_uid != 0
        or metadata.st_gid != 0
        or stat.S_IMODE(metadata.st_mode) != mode
        or metadata.st_nlink != 1
    ):
        raise BridgeError(f"record_metadata_invalid:{path.name}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BridgeError(f"record_invalid:{path.name}") from error
    if not isinstance(document, dict):
        raise BridgeError(f"record_document_invalid:{path.name}")
    return document


def _require_private_root(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise BridgeError(f"private_root_invalid:{path}")
    metadata = path.stat()
    if (
        metadata.st_uid != 0
        or metadata.st_gid != 0
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise BridgeError(f"private_root_metadata_invalid:{path}")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_private_json(path: Path, document: dict[str, Any]) -> None:
    _require_private_root(path.parent)
    payload = (
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temporary = Path(raw)
    replaced = False
    try:
        os.fchmod(fd, 0o600)
        os.fchown(fd, 0, 0)
        with os.fdopen(fd, "wb", closefd=True) as stream:
            fd = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        replaced = True
        _fsync_directory(path.parent)
    finally:
        if fd >= 0:
            os.close(fd)
        if not replaced:
            temporary.unlink(missing_ok=True)


def _create_bridge_root() -> None:
    if BRIDGE_ROOT.exists() or BRIDGE_ROOT.is_symlink():
        raise BridgeError("bridge_transaction_already_claimed")
    BRIDGE_ROOT.mkdir(mode=0o700)
    os.chown(BRIDGE_ROOT, 0, 0)
    _require_private_root(BRIDGE_ROOT)
    _fsync_directory(BRIDGE_ROOT.parent)


def _package(root: Path) -> dict[str, Any]:
    manifest_path = root / "package-manifest.json"
    manifest = _read_json(manifest_path)
    if manifest.get("schema") != PACKAGE_SCHEMA:
        raise BridgeError("package_schema_invalid")
    expected = {
        "product_source_head": PRODUCT_SOURCE_HEAD,
        "r2a_control_head": R2A_CONTROL_HEAD,
        "r2b_control_head": R2B_CONTROL_HEAD,
        "r3_observer_control_head": R3_OBSERVER_CONTROL_HEAD,
        "r2_reference_sha256": R2_REFERENCE_SHA256,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise BridgeError(f"package_binding_invalid:{key}")
    control_head = manifest.get("control_plane_head")
    if not isinstance(control_head, str) or re.fullmatch(r"[0-9a-f]{40}", control_head) is None:
        raise BridgeError("package_control_head_invalid")

    expected_files = {
        "tools/n3w_t1_clean_reference_pairing_readiness_bridge.py",
        "tools/n3w_t1_clean_reference_observer.py",
    }
    records = manifest.get("files")
    if not isinstance(records, list) or {
        item.get("path") for item in records if isinstance(item, dict)
    } != expected_files:
        raise BridgeError("package_file_inventory_invalid")

    by_path: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise BridgeError("package_file_record_invalid")
        relative = record.get("path")
        if not isinstance(relative, str):
            raise BridgeError("package_file_path_invalid")
        path = root / relative
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size != record.get("size")
            or _sha256(path) != record.get("sha256")
        ):
            raise BridgeError(f"package_file_binding_invalid:{relative}")
        by_path[relative] = record

    actual = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and item != manifest_path
    }
    if actual != expected_files:
        raise BridgeError("package_file_set_invalid")

    executing = Path(os.path.abspath(__file__))
    self_relative = "tools/n3w_t1_clean_reference_pairing_readiness_bridge.py"
    self_record = by_path[self_relative]
    if (
        executing.is_symlink()
        or executing != root / self_relative
        or _sha256(executing) != self_record["sha256"]
        or executing.stat().st_size != self_record["size"]
    ):
        raise BridgeError("executing_bridge_binding_invalid")
    return manifest


def _load_observer(root: Path) -> ModuleType:
    path = root / "tools/n3w_t1_clean_reference_observer.py"
    spec = importlib.util.spec_from_file_location("n3w_clean_reference_bridge_observer", path)
    if spec is None or spec.loader is None:
        raise BridgeError("observer_import_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if getattr(module, "SCHEMA", None) != "gh.n3w-t1-clean-reference-observation/1":
        raise BridgeError("observer_schema_invalid")
    return module


def _baseline(path: Path) -> dict[str, Any]:
    if _sha256(path) != R2_REFERENCE_SHA256:
        raise BridgeError("r2_reference_sha256_invalid")
    document = _read_json(path)
    if (
        document.get("schema") != "gh.n3w-t1-clean-reference-observation/1"
        or document.get("status") != "PASS"
        or document.get("reference_label") != "R2"
        or document.get("read_only") is not True
        or document.get("network_mutation") is not False
        or document.get("board_access") is not False
        or document.get("health", {}).get("overall_pass") is not True
    ):
        raise BridgeError("r2_reference_contract_invalid")
    authority = document.get("stable_contracts", {}).get("authority", {})
    if (
        authority.get("product_source_head") != PRODUCT_SOURCE_HEAD
        or authority.get("r2a_control_head") != R2A_CONTROL_HEAD
        or authority.get("r2b_control_head") != R2B_CONTROL_HEAD
    ):
        raise BridgeError("r2_reference_authority_invalid")
    return document


def _r2_transactions() -> dict[str, str]:
    r2a = _read_json(R2A_TRANSACTION, mode=0o600)
    expected_r2a = {
        "schema": "gh.n3w-t1-clean-reference-r2a-transaction/1",
        "stage": "RUNTIME_STARTED",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "authorization_replay_allowed": False,
        "product_source_head": PRODUCT_SOURCE_HEAD,
        "control_plane_head": R2A_CONTROL_HEAD,
        "runtime_started": True,
        "production_service_start": True,
        "persistence_enabled": True,
        "certificate_timer_enabled": True,
        "pre_reboot_ready": True,
    }
    for key, value in expected_r2a.items():
        if r2a.get(key) != value:
            raise BridgeError(f"r2a_transaction_binding_invalid:{key}")

    r2b = _read_json(R2B_TRANSACTION, mode=0o600)
    expected_r2b = {
        "schema": "gh.n3w-t1-clean-reference-r2b-transaction/1",
        "stage": "REBOOT_ACCEPTED",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "authorization_replay_allowed": False,
        "product_source_head": PRODUCT_SOURCE_HEAD,
        "r2a_control_head": R2A_CONTROL_HEAD,
        "control_plane_head": R2B_CONTROL_HEAD,
        "reboot_acceptance_passed": True,
        "board_access": False,
    }
    for key, value in expected_r2b.items():
        if r2b.get(key) != value:
            raise BridgeError(f"r2b_transaction_binding_invalid:{key}")
    return {
        "r2a_transaction_sha256": _sha256(R2A_TRANSACTION),
        "r2b_transaction_sha256": _sha256(R2B_TRANSACTION),
    }


def _relevant_runtime(reference: dict[str, Any]) -> dict[str, Any]:
    runtime = reference.get("runtime_observations")
    if not isinstance(runtime, dict):
        raise BridgeError("runtime_observations_invalid")
    sqlite = runtime.get("sqlite")
    containers = runtime.get("containers")
    dynsec = runtime.get("dynsec_counts")
    registries = runtime.get("homeassistant_registry_counts")
    mqtt = runtime.get("mqtt_session")
    if not all(isinstance(value, dict) for value in (sqlite, containers, dynsec, registries, mqtt)):
        raise BridgeError("runtime_reference_shape_invalid")
    identities: dict[str, str] = {}
    for service in ("manager", "homeassistant"):
        row = mqtt.get(service)
        if not isinstance(row, dict) or not isinstance(row.get("identity_sha256"), str):
            raise BridgeError(f"mqtt_identity_invalid:{service}")
        identities[service] = row["identity_sha256"]
    return {
        "boot_id_sha256": runtime.get("boot_id_sha256"),
        "containers": containers,
        "sqlite_row_counts": {
            path: value.get("row_counts")
            for path, value in sqlite.items()
            if isinstance(value, dict)
        },
        "dynsec_counts": dynsec,
        "homeassistant_registry_counts": registries,
        "mqtt_identity_sha256": identities,
    }


def _current_reference(root: Path, baseline: dict[str, Any]) -> dict[str, Any]:
    observer = _load_observer(root)
    try:
        current = observer.collect("R2")
    except Exception as error:
        raise BridgeError(f"current_observation_failed:{type(error).__name__}") from error
    if current.get("health", {}).get("overall_pass") is not True:
        raise BridgeError("current_runtime_health_not_pass")
    if current.get("stable_contracts") != baseline.get("stable_contracts"):
        raise BridgeError("stable_contract_drift")
    if _relevant_runtime(current) != _relevant_runtime(baseline):
        raise BridgeError("pre_pairing_runtime_drift")
    return current


def _tool_binding() -> None:
    if _git_blob_sha(DEVICE_PROVISIONING_TOOL) != DEVICE_PROVISIONING_BLOB:
        raise BridgeError("device_provisioning_tool_drift")
    if _git_blob_sha(REGISTRATION_GUARD_TOOL) != REGISTRATION_GUARD_BLOB:
        raise BridgeError("registration_guard_tool_drift")
    if _git_blob_sha(BROKER_GUARD_TOOL) != BROKER_GUARD_BLOB:
        raise BridgeError("broker_guard_tool_drift")


def _release_binding() -> str:
    release = _read_json(RELEASE_PATH)
    if (
        release.get("schema") != "gh.n3w-t1-fresh-release/1"
        or release.get("source_head") != PRODUCT_SOURCE_HEAD
        or release.get("release_id") != PRODUCT_SOURCE_HEAD
        or release.get("explicit_provisioning_required") is not True
    ):
        raise BridgeError("fresh_release_identity_binding_invalid")
    return PRODUCT_SOURCE_HEAD


def _host_identity() -> dict[str, str]:
    if (
        MACHINE_ID_PATH.is_symlink()
        or not MACHINE_ID_PATH.is_file()
        or SSH_HOST_PUBLIC_KEY.is_symlink()
        or not SSH_HOST_PUBLIC_KEY.is_file()
    ):
        raise BridgeError("os_identity_material_missing")
    machine_id = MACHINE_ID_PATH.read_text(encoding="utf-8").strip()
    if re.fullmatch(r"[0-9a-f]{32}", machine_id) is None:
        raise BridgeError("machine_id_invalid")
    ssh_public = SSH_HOST_PUBLIC_KEY.read_bytes().strip()
    if not ssh_public:
        raise BridgeError("ssh_host_identity_invalid")
    digest = hashlib.sha256(
        machine_id.encode("ascii") + b"\0" + ssh_public
    ).hexdigest()
    host_instance_id = f"t1h-{digest[:24]}"
    return {
        "host_instance_id": host_instance_id,
        "host_instance_id_sha256": hashlib.sha256(
            host_instance_id.encode()
        ).hexdigest(),
    }


def _initialization_marker_digest(marker: dict[str, Any]) -> str:
    value = dict(marker)
    value.pop("manifest_sha256", None)
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _system_identity_authority() -> dict[str, str]:
    _require_private_root(SYSTEM_IDENTITY_ROOT)
    marker = _read_json(SYSTEM_IDENTITY_MARKER)
    if stat.S_IMODE(SYSTEM_IDENTITY_MARKER.stat().st_mode) != 0o600:
        raise BridgeError("system_identity_marker_metadata_invalid")
    if marker.get("schema") != "gh.h0h1.system-initialization/1":
        raise BridgeError("system_identity_marker_schema_invalid")
    manifest_sha256 = marker.get("manifest_sha256")
    if (
        not isinstance(manifest_sha256, str)
        or manifest_sha256 != _initialization_marker_digest(marker)
    ):
        raise BridgeError("system_identity_marker_self_binding_invalid")

    expected_names = {
        "system-identity.json",
        "system-root.key",
        "system-ca.pem",
        "system-ca-key.pem",
        "manager-identity.json",
    }
    files = marker.get("files")
    if not isinstance(files, dict) or set(files) != expected_names:
        raise BridgeError("system_identity_inventory_invalid")
    for name in expected_names:
        record = files.get(name)
        path = SYSTEM_IDENTITY_ROOT / name
        if (
            not isinstance(record, dict)
            or path.is_symlink()
            or not path.is_file()
            or stat.S_IMODE(path.stat().st_mode) != 0o600
            or path.stat().st_nlink != 1
            or path.stat().st_size != record.get("size")
            or _sha256(path) != record.get("sha256")
        ):
            raise BridgeError(f"system_identity_member_invalid:{name}")

    identity = _read_json(SYSTEM_IDENTITY)
    manager_identity = _read_json(MANAGER_IDENTITY)
    if identity.get("schema") != "gh.h0h1.system-identity/1":
        raise BridgeError("system_identity_schema_invalid")
    if manager_identity.get("schema") != "gh.h0h1.manager-identity/1":
        raise BridgeError("manager_identity_schema_invalid")
    system_id = identity.get("system_id")
    manager_id = manager_identity.get("manager_id")
    if (
        not isinstance(system_id, str)
        or not system_id
        or manager_identity.get("system_id") != system_id
        or marker.get("system_id") != system_id
        or not isinstance(manager_id, str)
        or not manager_id
        or marker.get("manager_id") != manager_id
    ):
        raise BridgeError("system_identity_binding_invalid")

    if MANAGER_DB.is_symlink() or not MANAGER_DB.is_file():
        raise BridgeError("manager_identity_database_invalid")
    connection = sqlite3.connect(
        f"{MANAGER_DB.resolve().as_uri()}?mode=ro",
        uri=True,
        timeout=5,
    )
    try:
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute(
            "SELECT schema, system_id_fingerprint, "
            "structured_legacy_manager_state_imported, "
            "anonymous_nodes_reconstructed "
            "FROM h0h1_legacy_adoption_provenance"
        ).fetchall()
    except sqlite3.Error as error:
        raise BridgeError("manager_identity_database_query_failed") from error
    finally:
        connection.close()
    system_id_sha256 = hashlib.sha256(system_id.encode()).hexdigest()
    if (
        len(rows) != 1
        or rows[0][0] != "gh.h0h1.legacy-adoption-provenance/1"
        or rows[0][1] != system_id_sha256[:24]
        or int(rows[0][2]) != 0
        or int(rows[0][3]) != 0
    ):
        raise BridgeError("manager_system_identity_binding_invalid")
    return {
        "system_id": system_id,
        "system_id_sha256": system_id_sha256,
        "system_identity_manifest_sha256": manifest_sha256,
    }


def _device_provisioning_state() -> str:
    try:
        report = json.loads(
            _run(
                ("python3", str(DEVICE_PROVISIONING_TOOL), "status"),
                timeout=120,
            )
        )
    except json.JSONDecodeError as error:
        raise BridgeError("device_provisioning_status_json_invalid") from error
    if (
        not isinstance(report, dict)
        or report.get("status") != "PASS"
        or report.get("state") != "UNPROVISIONED"
        or report.get("release_id") != PRODUCT_SOURCE_HEAD
        or report.get("production_service_start") is not False
        or report.get("board_access") is not False
    ):
        raise BridgeError("device_provisioning_state_invalid")
    return "UNPROVISIONED"


def _device_identity() -> dict[str, str]:
    _tool_binding()
    release_id = _release_binding()
    provisioning_state = _device_provisioning_state()
    host = _host_identity()
    system = _system_identity_authority()
    return {
        "release_id": release_id,
        "host_instance_id": host["host_instance_id"],
        "system_id": system["system_id"],
        "host_instance_id_sha256": host["host_instance_id_sha256"],
        "system_id_sha256": system["system_id_sha256"],
        "system_identity_manifest_sha256": system[
            "system_identity_manifest_sha256"
        ],
        "identity_authority": "clean_reference_runtime_identity_v1",
        "device_provisioning_state": provisioning_state,
    }

def _optional_table_count(path: Path, table: str) -> int:
    if path.is_symlink():
        raise BridgeError(f"security_database_symlink:{path.name}")
    if not path.exists():
        return 0
    if not path.is_file():
        raise BridgeError(f"security_database_invalid:{path.name}")
    connection = sqlite3.connect(
        f"{path.resolve().as_uri()}?mode=ro",
        uri=True,
        timeout=5,
    )
    try:
        connection.execute("PRAGMA query_only=ON")
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if exists is None:
            raise BridgeError(f"security_table_missing:{path.name}:{table}")
        return int(
            connection.execute(
                f'SELECT COUNT(*) FROM "{table.replace(chr(34), chr(34) * 2)}"'
            ).fetchone()[0]
        )
    finally:
        connection.close()


def _security_state_counts() -> dict[str, int]:
    credential_assignments = _optional_table_count(
        CREDENTIAL_DB,
        "credential_assignments",
    )
    peer_trust_records = _optional_table_count(
        PEER_TRUST_DB,
        "n3w_system_peer_trust",
    )

    if APPLICATION_KEY_DB.is_symlink() or not APPLICATION_KEY_DB.is_file():
        raise BridgeError("application_key_database_invalid")
    connection = sqlite3.connect(
        f"{APPLICATION_KEY_DB.resolve().as_uri()}?mode=ro",
        uri=True,
        timeout=5,
    )
    try:
        connection.execute("PRAGMA query_only=ON")
        required = {
            "n3w_relay_meta",
            "n3w_relay_nodes",
            "n3w_relay_key_epochs",
        }
        names = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if not required <= names:
            raise BridgeError("application_key_schema_invalid")
        active_nodes = int(
            connection.execute(
                "SELECT COUNT(*) FROM n3w_relay_nodes WHERE active = 1"
            ).fetchone()[0]
        )
        key_epochs = int(
            connection.execute(
                "SELECT COUNT(*) FROM n3w_relay_key_epochs"
            ).fetchone()[0]
        )
    finally:
        connection.close()

    return {
        "credential_assignments": credential_assignments,
        "peer_trust_records": peer_trust_records,
        "application_key_active_nodes": active_nodes,
        "application_key_epochs": key_epochs,
    }

def _require_clean_security_state(counts: dict[str, int]) -> None:
    expected = {
        "credential_assignments": 0,
        "peer_trust_records": 0,
        "application_key_active_nodes": 0,
        "application_key_epochs": 0,
    }
    if counts != expected:
        raise BridgeError("first_pair_security_state_not_clean")


def _pairing_records_absent() -> bool:
    if PROVISIONING_ROOT.is_symlink():
        raise BridgeError("provisioning_root_symlink_forbidden")
    if not PROVISIONING_ROOT.exists():
        return False
    _require_private_root(PROVISIONING_ROOT)
    for path in (FACTORY_ACCEPTED, FIRST_PAIRING_TRANSACTION, SUCCESSOR_RECOVERY):
        if path.exists() or path.is_symlink():
            raise BridgeError(f"pairing_record_already_present:{path.name}")
    if any(PROVISIONING_ROOT.iterdir()):
        raise BridgeError("provisioning_root_not_clean")
    return True

def _listener_count(protocol: str, port: int) -> int:
    if protocol == "tcp":
        output = _run(("ss", "-H", "-ltn"), timeout=20)
    elif protocol == "udp":
        output = _run(("ss", "-H", "-lun"), timeout=20)
    else:
        raise BridgeError("listener_protocol_invalid")
    target = f":{port}"
    return sum(
        1
        for line in output.splitlines()
        if len(line.split()) >= 5 and target in line.split()[3]
    )


def _manager_id() -> str:
    output = _run(
        (
            "docker",
            "ps",
            "--filter",
            "label=com.docker.compose.project=n3wfc4",
            "--filter",
            "label=com.docker.compose.service=manager",
            "--format",
            "{{.ID}}",
        ),
        timeout=20,
    )
    identifiers = [line.strip() for line in output.splitlines() if line.strip()]
    if len(identifiers) != 1:
        raise BridgeError("manager_container_not_unique")
    manager_id = identifiers[0]
    network_mode = _run(
        ("docker", "inspect", "-f", "{{.HostConfig.NetworkMode}}", manager_id),
        timeout=20,
    ).strip()
    if network_mode != "host":
        raise BridgeError("manager_network_mode_invalid")
    return manager_id


def _manager_runtime_flags(manager_id: str) -> None:
    raw = _run(
        ("docker", "inspect", "-f", "{{json .Config.Env}}", manager_id),
        timeout=20,
    )
    try:
        environment = json.loads(raw)
    except json.JSONDecodeError as error:
        raise BridgeError("manager_environment_invalid") from error
    if not isinstance(environment, list) or not all(
        isinstance(item, str) for item in environment
    ):
        raise BridgeError("manager_environment_invalid")
    values: dict[str, str] = {}
    for item in environment:
        key, separator, value = item.partition("=")
        if separator:
            values[key] = value
    if values.get("GH_N3W_RUNTIME_ENABLED", "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        raise BridgeError("manager_n3w_runtime_not_enabled")
    if values.get("GH_N3W_PRODUCT_PAIRING_ENABLED", "false").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
        "",
    }:
        raise BridgeError("legacy_product_pairing_runtime_enabled")


def _pairing_control_closed(manager_id: str) -> dict[str, Any]:
    try:
        report = json.loads(
            _run(
                (
                    "docker",
                    "exec",
                    manager_id,
                    "greenhouse-manager-pairing",
                    "window-status",
                ),
                timeout=20,
            )
        )
    except json.JSONDecodeError as error:
        raise BridgeError("pairing_control_status_json_invalid") from error
    expected = {
        "schema": "gh.n3w.pairing-window-control-result/1",
        "accepted": True,
        "code": "status",
        "pairing_window_state": "CLOSED",
        "raw_locator_in_output": False,
    }
    for key, value in expected.items():
        if report.get(key) != value:
            raise BridgeError(f"pairing_control_status_invalid:{key}")
    if report.get("broker_host_sha256") is not None:
        raise BridgeError("pairing_control_closed_broker_binding_present")
    return report


def _trusted_lan_authority() -> dict[str, str]:
    document = _read_json(TRUSTED_LAN_STATE)
    if (
        document.get("schema") != "gh.trusted-product-lan/1"
        or document.get("interface") != "eth0"
        or document.get("available") is not True
        or not isinstance(document.get("generation"), str)
        or not document["generation"]
        or not isinstance(document.get("subnet"), str)
    ):
        raise BridgeError("trusted_product_lan_state_invalid")
    try:
        network = ipaddress.ip_network(document["subnet"], strict=True)
    except ValueError as error:
        raise BridgeError("trusted_product_lan_subnet_invalid") from error
    if not isinstance(network, ipaddress.IPv4Network):
        raise BridgeError("trusted_product_lan_subnet_invalid")

    try:
        address_document = json.loads(
            _run(("ip", "-j", "-4", "addr", "show", "dev", "eth0"), timeout=20)
        )
    except json.JSONDecodeError as error:
        raise BridgeError("trusted_product_lan_interface_json_invalid") from error
    addresses: list[ipaddress.IPv4Address] = []
    if isinstance(address_document, list):
        for interface in address_document:
            if not isinstance(interface, dict):
                continue
            for row in interface.get("addr_info", []):
                if (
                    isinstance(row, dict)
                    and row.get("family") == "inet"
                    and row.get("scope") == "global"
                    and isinstance(row.get("local"), str)
                ):
                    try:
                        parsed = ipaddress.ip_address(row["local"])
                    except ValueError:
                        continue
                    if isinstance(parsed, ipaddress.IPv4Address):
                        addresses.append(parsed)
    if len(addresses) != 1 or addresses[0] not in network:
        raise BridgeError("trusted_product_lan_interface_binding_invalid")
    return {
        "trusted_network_sha256": hashlib.sha256(
            str(network).encode("utf-8")
        ).hexdigest(),
        "trusted_lan_generation_sha256": hashlib.sha256(
            document["generation"].encode("utf-8")
        ).hexdigest(),
    }


def _load_registration_guard() -> ModuleType:
    _tool_binding()
    tool_directory = str(REGISTRATION_GUARD_TOOL.parent)
    inserted = tool_directory not in sys.path
    if inserted:
        sys.path.insert(0, tool_directory)
    try:
        spec = importlib.util.spec_from_file_location(
            "n3w_registration_ingress_guard_readonly_probe",
            REGISTRATION_GUARD_TOOL,
        )
        if spec is None or spec.loader is None:
            raise BridgeError("registration_guard_import_invalid")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if inserted:
            sys.path.remove(tool_directory)


def _registration_guard_authority(
    trusted_network_sha256: str,
) -> dict[str, Any]:
    guard = _load_registration_guard()
    try:
        decision = guard.broker_guard.read_network_decision()
        trusted_subnet = decision.trusted_subnet
        if trusted_subnet is None:
            raise BridgeError("registration_guard_trusted_subnet_unavailable")
        observed_hash = hashlib.sha256(
            str(trusted_subnet).encode("utf-8")
        ).hexdigest()
        if observed_hash != trusted_network_sha256:
            raise BridgeError("registration_guard_trusted_subnet_mismatch")
        inventory = guard.parse_firewall_inventory(guard._save_filter_table())
        guard.validate_applied_state(inventory, trusted_subnet)
    except BridgeError:
        raise
    except Exception as error:
        raise BridgeError(
            f"registration_guard_validation_failed:{type(error).__name__}"
        ) from error
    positions = list(inventory.registration_anchor_positions)
    if positions != [2, 3, 4]:
        raise BridgeError("registration_guard_anchor_positions_invalid")
    return {
        "registration_guard_applied": True,
        "registration_guard_anchor_positions": positions,
    }


def _current_product_registration_readiness() -> dict[str, Any]:
    manager_id = _manager_id()
    _manager_runtime_flags(manager_id)
    control = _pairing_control_closed(manager_id)

    bootstrap_count = _listener_count("tcp", REGISTRATION_BOOTSTRAP_PORT)
    discovery_count = _listener_count("udp", REGISTRATION_DISCOVERY_PORT)
    privileged_count = _listener_count("tcp", PRIVILEGED_PAIRING_PORT)
    if bootstrap_count != 1:
        raise BridgeError("registration_bootstrap_listener_count_invalid")
    if discovery_count != 1:
        raise BridgeError("registration_discovery_listener_count_invalid")
    if privileged_count != 0:
        raise BridgeError("privileged_pairing_listener_present")

    trusted = _trusted_lan_authority()
    guard = _registration_guard_authority(trusted["trusted_network_sha256"])
    return {
        "registration_ready": True,
        "registration_bootstrap_listener_count": bootstrap_count,
        "registration_discovery_listener_count": discovery_count,
        "privileged_pairing_listener_count": privileged_count,
        "pairing_window_state": control["pairing_window_state"],
        **trusted,
        **guard,
    }


def _preflight(root: Path, reference_path: Path) -> dict[str, Any]:
    manifest = _package(root)
    if os.geteuid() != 0:
        raise BridgeError("root_required")
    if BRIDGE_ROOT.exists() or BRIDGE_ROOT.is_symlink():
        raise BridgeError("bridge_transaction_already_claimed")
    _pairing_records_absent()
    registration = _current_product_registration_readiness()
    transactions = _r2_transactions()
    baseline = _baseline(reference_path)
    current = _current_reference(root, baseline)
    _require_clean_security_state(_security_state_counts())
    identity = _device_identity()
    stable_authority = current["stable_contracts"]["authority"]
    if stable_authority.get("r2a_transaction_sha256") != transactions["r2a_transaction_sha256"]:
        raise BridgeError("r2a_reference_transaction_mismatch")
    if stable_authority.get("r2b_transaction_sha256") != transactions["r2b_transaction_sha256"]:
        raise BridgeError("r2b_reference_transaction_mismatch")
    return {
        "manifest": manifest,
        "transactions": transactions,
        "identity": identity,
        "registration": registration,
        "current": current,
    }


def _authorization(value: str) -> str:
    if (
        not value.startswith(AUTHORIZATION_PREFIX)
        or len(value) > 200
        or not value.replace("_", "").replace("-", "").isalnum()
    ):
        raise BridgeError("authorization_id_invalid")
    return value


def _factory_document(preflight: dict[str, Any]) -> dict[str, Any]:
    identity = preflight["identity"]
    transactions = preflight["transactions"]
    manifest = preflight["manifest"]
    return {
        "schema": "gh.n3w.t1-factory-accepted/1",
        "status": "PASS",
        "factory_accepted": True,
        "release_id": identity["release_id"],
        "host_instance_id": identity["host_instance_id"],
        "system_id": identity["system_id"],
        "system_id_sha256": identity["system_id_sha256"],
        "identity_authority": identity["identity_authority"],
        "device_provisioning_state": identity["device_provisioning_state"],
        "system_identity_manifest_sha256": identity[
            "system_identity_manifest_sha256"
        ],
        "acceptance_route": "clean_reference_r2_bridge_v2",
        "r2_reference_sha256": R2_REFERENCE_SHA256,
        "r2a_transaction_sha256": transactions["r2a_transaction_sha256"],
        "r2b_transaction_sha256": transactions["r2b_transaction_sha256"],
        "bridge_control_head": manifest["control_plane_head"],
    }


def _onboarding_inspect() -> dict[str, Any]:
    try:
        report = json.loads(
            _run(
                ("python3", str(FIRST_PAIRING_TOOL), "inspect"),
                timeout=120,
            )
        )
    except json.JSONDecodeError as error:
        raise BridgeError("first_pairing_inspect_json_invalid") from error
    expected = {
        "status": "PASS",
        "operation": "inspect",
        "factory_accepted": True,
        "transaction_present": False,
        "successor_recovery_present": False,
        "mutation": False,
        "pairing_udp_listener_count": 0,
        "pairing_http_listener_count": 0,
        "pairing_window_state": "CLOSED",
        "raw_locator_in_output": False,
    }
    for key, value in expected.items():
        if report.get(key) != value:
            raise BridgeError(f"first_pairing_inspect_invalid:{key}")
    return report


def inspect(root: Path, reference_path: Path) -> dict[str, Any]:
    preflight = _preflight(root, reference_path)
    identity = preflight["identity"]
    registration = preflight["registration"]
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "state": "CURRENT_PRODUCT_REGISTRATION_READY",
        "product_source_head": PRODUCT_SOURCE_HEAD,
        "r2a_control_head": R2A_CONTROL_HEAD,
        "r2b_control_head": R2B_CONTROL_HEAD,
        "r3_observer_control_head": R3_OBSERVER_CONTROL_HEAD,
        "bridge_control_head": preflight["manifest"]["control_plane_head"],
        "r2_reference_sha256": R2_REFERENCE_SHA256,
        "r2a_transaction_unchanged": True,
        "r2b_transaction_unchanged": True,
        "device_provisioning_state": identity["device_provisioning_state"],
        "device_provisioning_ready": False,
        "identity_authority": identity["identity_authority"],
        "system_identity_manifest_sha256": identity[
            "system_identity_manifest_sha256"
        ],
        "host_instance_id_sha256": identity["host_instance_id_sha256"],
        "system_id_sha256": identity["system_id_sha256"],
        "factory_accepted_required": False,
        "factory_accepted_present": False,
        "legacy_first_pairing_onboarding_required": False,
        "first_pairing_transaction_present": False,
        "registration_ready": registration["registration_ready"],
        "registration_bootstrap_listener_count": registration[
            "registration_bootstrap_listener_count"
        ],
        "registration_discovery_listener_count": registration[
            "registration_discovery_listener_count"
        ],
        "privileged_pairing_listener_count": registration[
            "privileged_pairing_listener_count"
        ],
        "pairing_window_state": registration["pairing_window_state"],
        "trusted_network_sha256": registration["trusted_network_sha256"],
        "trusted_lan_generation_sha256": registration[
            "trusted_lan_generation_sha256"
        ],
        "registration_guard_applied": registration["registration_guard_applied"],
        "registration_guard_anchor_positions": registration[
            "registration_guard_anchor_positions"
        ],
        "product_mutation": False,
        "network_mutation": False,
        "service_restart": False,
        "board_access": False,
    }



def status() -> dict[str, Any]:
    present = BRIDGE_TRANSACTION.is_file() and not BRIDGE_TRANSACTION.is_symlink()
    transaction = _read_json(BRIDGE_TRANSACTION, mode=0o600) if present else None
    marker_present = FACTORY_ACCEPTED.is_file() and not FACTORY_ACCEPTED.is_symlink()
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "transaction_present": present,
        "transaction_stage": transaction.get("stage") if transaction else "UNCLAIMED",
        "authorization_consumed": (
            transaction.get("authorization_consumed") if transaction else False
        ),
        "authorization_replay_allowed": (
            transaction.get("authorization_replay_allowed") if transaction else None
        ),
        "factory_accepted_present": marker_present,
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="n3w-t1-clean-reference-pairing-readiness-bridge"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--package-root", required=True)
    inspect_parser.add_argument("--r2-reference", required=True)

    sub.add_parser("status")
    return parser


def _emit(document: dict[str, Any], *, error: bool = False) -> None:
    destination = sys.stderr if error else sys.stdout
    destination.write(
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "inspect":
            report = inspect(
                Path(os.path.abspath(args.package_root)),
                Path(os.path.abspath(args.r2_reference)),
            )
        else:
            report = status()
    except (
        BridgeError,
        OSError,
        sqlite3.Error,
        subprocess.SubprocessError,
        ValueError,
        TypeError,
        KeyError,
    ) as error:
        claimed = BRIDGE_TRANSACTION.exists() or BRIDGE_TRANSACTION.is_symlink()
        _emit(
            {
                "schema": SCHEMA,
                "status": "STOP",
                "reason": str(error)[:300],
                "authorization_reusable": None if not claimed else False,
                "mutation_state": "NONE" if not claimed else "POSTCLAIM",
                "board_access": False,
            },
            error=True,
        )
        return 2
    _emit(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
