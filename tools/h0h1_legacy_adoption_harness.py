from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from greenhouse_manager.bootstrap.legacy_adoption import (
    CLASSIFICATION_DECISION_ID,
    CLASSIFICATION_RESULT_SHA256,
    CLASSIFICATION_SCHEMA,
    CLASSIFIED_ARTIFACT_ID,
    CLASSIFIED_ARTIFACT_SHA256,
    CLASSIFIED_BASELINE_RESULT_SHA256,
    CLASSIFIED_BASELINE_SCRIPT_SHA256,
    CLASSIFIED_BASE_SHA,
    CLASSIFIED_SOURCE_HEAD_SHA,
    CLASSIFIED_SOURCE_PR,
    build_legacy_adoption_plan,
    system_id_fingerprint,
)
from greenhouse_manager.bootstrap.portable_restore import (
    CREATE_CONFIRMATION,
    RESTORE_CONFIRMATION,
    create_portable_backup,
    restore_portable_backup,
    verify_portable_backup,
)
from greenhouse_manager.bootstrap.system_init import (
    EXPECTED_FILES,
    IDENTITY_SCHEMA,
    INITIALIZATION_SCHEMA,
    MANAGER_IDENTITY_NAME,
    MANAGER_IDENTITY_SCHEMA,
    MARKER_NAME,
    SYSTEM_CA_CERTIFICATE_NAME,
    SYSTEM_CA_PRIVATE_KEY_NAME,
    SYSTEM_IDENTITY_NAME,
    SYSTEM_ROOT_KEY_NAME,
    _canonical_json,
    _generate_ca,
    _marker_digest,
    _sha256_file,
    _write_atomic,
    verify_initialization,
)
from greenhouse_manager.runtime.credential_lifecycle import CredentialLifecycleStore
from greenhouse_manager.runtime.registration import RegistrationRegistry

SCHEMA = "gh.h0h1.legacy-system-id-adoption-host-only-result/1"
PROVENANCE_SCHEMA = "gh.h0h1.legacy-adoption-provenance/1"
SYNTHETIC_SYSTEM_ID = "greenhouse-host-only-legacy"
ARCHIVE_PHRASE = "host-only synthetic archive phrase 20260802"
BUSINESS_TABLES = (
    "registrations",
    "pairing_sessions",
    "registration_events",
    "registration_node_history",
    "node_id_leases",
    "retirement_outbox",
    "credential_assignments",
)


def _private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def _private_file(path: Path, payload: bytes) -> None:
    _private_directory(path.parent)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)


def _classification() -> dict[str, Any]:
    fingerprint = system_id_fingerprint(SYNTHETIC_SYSTEM_ID)
    return {
        "schema": CLASSIFICATION_SCHEMA,
        "status": "PASS",
        "decision_id": CLASSIFICATION_DECISION_ID,
        "classification": "LEGACY_RUNTIME_OR_CONFIGURATION_STATE_PRESENT",
        "runtime_hidden_state_classified": True,
        "legacy_import_or_adoption_required": True,
        "new_system_initialization_permitted_by_this_decision": False,
        "candidate_root_preparation_permitted_by_this_decision": False,
        "real_backup_permitted_by_this_decision": False,
        "restore_permitted_by_this_decision": False,
        "anonymous_closure_permitted_by_this_decision": False,
        "deployment_permitted_by_this_decision": False,
        "baseline_drift": [],
        "blocked_reasons": ["EXPLICIT_LEGACY_ADOPTION_OR_IMPORT_REQUIRED"],
        "binding": {
            "source_pr": CLASSIFIED_SOURCE_PR,
            "base_sha": CLASSIFIED_BASE_SHA,
            "source_head_sha": CLASSIFIED_SOURCE_HEAD_SHA,
            "artifact_id": CLASSIFIED_ARTIFACT_ID,
            "artifact_sha256": CLASSIFIED_ARTIFACT_SHA256,
            "baseline_result_sha256": CLASSIFIED_BASELINE_RESULT_SHA256,
            "baseline_script_sha256": CLASSIFIED_BASELINE_SCRIPT_SHA256,
        },
        "operation_flags": {
            "read_only": True,
            "anonymous_closure_executed": False,
            "backup_created": False,
            "board_operation": False,
            "broker_modified": False,
            "candidate_root_created": False,
            "container_created": False,
            "container_modified": False,
            "container_restarted": False,
            "docker_cp_executed": False,
            "file_created_on_t1": False,
            "file_modified_on_t1": False,
            "flash_nvs_operation": False,
            "home_assistant_modified": False,
            "identity_generated": False,
            "manager_modified": False,
            "merge_executed": False,
            "network_probe_executed": False,
            "ready_executed": False,
            "release_tag_deployment": False,
            "restore_executed": False,
            "usb_serial_operation": False,
        },
        "evidence": {
            "container_state_scan": {
                "available": True,
                "scan_complete": True,
                "candidate_count": 0,
                "identity_document_count": 0,
                "recognized_manager_row_count": 0,
                "scanned_file_count": 0,
                "errors": [],
                "open_state_fds": [],
            },
            "container_writable_layer": {
                "available": True,
                "state_related_entries": [],
                "truncated": False,
            },
            "log_signals": {
                "signal_counts": {
                    "accepted_telemetry": 3,
                    "pairing": 0,
                    "registration": 0,
                    "credential": 0,
                    "retirement": 0,
                    "outbox": 0,
                }
            },
            "manager_container": {
                "running": True,
                "state": "running",
                "version": "0.4.64",
                "mounts": [],
                "environment": {
                    "state_related_keys": ["GH_SYSTEM_ID"],
                    "secret_bearing_value_count": 0,
                    "non_secret_state_values": {
                        "GH_SYSTEM_ID": {
                            "present": True,
                            "fingerprint": fingerprint,
                        }
                    },
                },
            },
        },
    }


def _materialize_identity(candidate: Path) -> tuple[str, str]:
    _private_directory(candidate)
    now = datetime.now(UTC)
    created_at = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    manager_id = f"ghm-{secrets.token_hex(8)}"
    root_key = secrets.token_bytes(32)
    ca_private_key, ca_certificate = _generate_ca(SYNTHETIC_SYSTEM_ID, now=now)
    fingerprint = system_id_fingerprint(SYNTHETIC_SYSTEM_ID)
    identity = {
        "schema": IDENTITY_SCHEMA,
        "system_id": SYNTHETIC_SYSTEM_ID,
        "created_at": created_at,
        "generation": 1,
        "legacy_system_id_adopted": True,
        "source_system_id_fingerprint": fingerprint,
        "classification_result_sha256": CLASSIFICATION_RESULT_SHA256,
    }
    manager_identity = {
        "schema": MANAGER_IDENTITY_SCHEMA,
        "system_id": SYNTHETIC_SYSTEM_ID,
        "manager_id": manager_id,
        "created_at": created_at,
        "generation": 1,
        "identity_origin": "legacy_system_id_adoption",
        "classification_result_sha256": CLASSIFICATION_RESULT_SHA256,
    }
    payloads = {
        SYSTEM_IDENTITY_NAME: _canonical_json(identity) + b"\n",
        SYSTEM_ROOT_KEY_NAME: root_key,
        SYSTEM_CA_CERTIFICATE_NAME: ca_certificate,
        SYSTEM_CA_PRIVATE_KEY_NAME: ca_private_key,
        MANAGER_IDENTITY_NAME: _canonical_json(manager_identity) + b"\n",
    }
    for name in EXPECTED_FILES:
        _write_atomic(candidate / name, payloads[name])
    files = {}
    for name in EXPECTED_FILES:
        path = candidate / name
        stat = path.stat()
        files[name] = {
            "sha256": _sha256_file(path),
            "size": stat.st_size,
            "mode": stat.st_mode & 0o777,
        }
    marker: dict[str, Any] = {
        "schema": INITIALIZATION_SCHEMA,
        "system_id": SYNTHETIC_SYSTEM_ID,
        "manager_id": manager_id,
        "created_at": created_at,
        "generation": 1,
        "files": files,
        "marker_last": True,
        "legacy_system_id_adopted": True,
        "source_system_id_fingerprint": fingerprint,
        "classification_result_sha256": CLASSIFICATION_RESULT_SHA256,
        "structured_legacy_manager_state_imported": False,
        "anonymous_nodes_reconstructed": False,
        "production_services_modified": False,
        "network_operation": False,
        "subprocess_operation": False,
    }
    marker["manifest_sha256"] = _marker_digest(marker)
    _write_atomic(candidate / MARKER_NAME, _canonical_json(marker) + b"\n")
    verified = verify_initialization(candidate)
    if verified.system_id != SYNTHETIC_SYSTEM_ID:
        raise RuntimeError("synthetic legacy SYSTEM_ID was not preserved")
    return fingerprint, manager_id


def _materialize_empty_manager_state(candidate: Path, fingerprint: str) -> Path:
    state = candidate / "manager" / "manager-state.sqlite3"
    _private_directory(state.parent)
    with RegistrationRegistry(state):
        pass
    with CredentialLifecycleStore(state):
        pass
    with closing(sqlite3.connect(state)) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE h0h1_legacy_adoption_provenance (
                    schema TEXT NOT NULL,
                    classification_result_sha256 TEXT NOT NULL,
                    system_id_fingerprint TEXT NOT NULL,
                    structured_legacy_manager_state_imported INTEGER NOT NULL,
                    anonymous_nodes_reconstructed INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO h0h1_legacy_adoption_provenance
                VALUES (?, ?, ?, 0, 0)
                """,
                (PROVENANCE_SCHEMA, CLASSIFICATION_RESULT_SHA256, fingerprint),
            )
    state.chmod(0o600)
    return state


def _business_row_count(state: Path) -> int:
    with closing(sqlite3.connect(f"file:{state}?mode=ro&immutable=1", uri=True)) as connection:
        connection.execute("PRAGMA query_only = ON")
        return sum(
            int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in BUSINESS_TABLES
        )


def run_harness() -> dict[str, object]:
    plan = build_legacy_adoption_plan(
        _classification(),
        source_sha256=CLASSIFICATION_RESULT_SHA256,
    )
    with tempfile.TemporaryDirectory(prefix="gh-h0h1-legacy-adoption-") as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        candidate = root / "candidate"
        fingerprint, manager_id = _materialize_identity(candidate)
        state = _materialize_empty_manager_state(candidate, fingerprint)
        _private_file(
            candidate / "broker" / "dynamic-security.json",
            b'{"schema":"synthetic-dynamic-security","clients":[]}\n',
        )
        _private_file(candidate / "broker" / "mosquitto.db", b"synthetic-broker-state")

        archive = root / "portable.ghpr"
        created = create_portable_backup(
            candidate,
            plan.role_inventory,
            archive,
            passphrase=ARCHIVE_PHRASE,
            enable=True,
            confirmation=CREATE_CONFIRMATION,
        )
        verified = verify_portable_backup(archive, passphrase=ARCHIVE_PHRASE)
        restored_root = root / "restored"
        restored = restore_portable_backup(
            archive,
            restored_root,
            passphrase=ARCHIVE_PHRASE,
            expected_system_id=SYNTHETIC_SYSTEM_ID,
            enable=True,
            confirmation=RESTORE_CONFIRMATION,
        )
        restored_identity = json.loads(
            (restored_root / SYSTEM_IDENTITY_NAME).read_text(encoding="utf-8")
        )
        restored_state = restored_root / "manager" / "manager-state.sqlite3"
        inventory_paths = {candidate / relative for relative in plan.role_inventory.values()}
        member_modes = {path.stat().st_mode & 0o777 for path in inventory_paths}

        return {
            "schema": SCHEMA,
            "status": "PASS",
            "classification_contract_valid": plan.status == "CONTRACT_COMPLETE_EXECUTION_BLOCKED",
            "source_system_id_fingerprint": fingerprint,
            "existing_system_id_preserved": restored_identity["system_id"] == SYNTHETIC_SYSTEM_ID,
            "new_system_id_generated": False,
            "new_manager_identity_generated": manager_id.startswith("ghm-"),
            "empty_formal_manager_state_materialized": (
                _business_row_count(state) == 0 and _business_row_count(restored_state) == 0
            ),
            "legacy_business_rows_reconstructed": False,
            "anonymous_nodes_reconstructed": False,
            "complete_role_inventory": len(plan.role_inventory) == 10,
            "candidate_root_private": candidate.stat().st_mode & 0o777 == 0o700,
            "candidate_members_private": member_modes == {0o600},
            "portable_backup_encrypted": created.encrypted,
            "portable_backup_verified": verified.envelope_sha256 == created.envelope_sha256,
            "portable_restore_round_trip": (
                restored.system_id == SYNTHETIC_SYSTEM_ID
                and restored.activation_enabled is False
            ),
            "payload_fingerprint": hashlib.sha256(
                json.dumps(sorted(plan.role_inventory.items())).encode("utf-8")
            ).hexdigest()[:16],
            "production_services_modified": False,
            "network_operation": False,
            "subprocess_operation": False,
            "t1_operation": False,
            "board_operation": False,
            "live_apply_enabled": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run_harness()
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
