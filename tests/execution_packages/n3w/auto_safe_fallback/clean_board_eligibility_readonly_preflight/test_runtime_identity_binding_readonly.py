from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
SCRIPT = (
    ROOT
    / "tools/execution_packages/n3w/auto_safe_fallback/"
    "clean_board_eligibility_readonly_preflight/runtime_identity_binding_readonly.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("runtime_identity_binding_readonly", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def registration_db(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE registrations(
                hardware_id TEXT PRIMARY KEY,
                current_pairing_id TEXT NOT NULL,
                pairing_epoch INTEGER NOT NULL,
                node_id TEXT,
                logical_location_id TEXT,
                repair_authorized INTEGER NOT NULL DEFAULT 0,
                retired_at TEXT,
                retirement_reason TEXT
            );
            CREATE TABLE pairing_sessions(
                pairing_id TEXT PRIMARY KEY,
                hardware_id TEXT NOT NULL,
                pairing_epoch INTEGER NOT NULL,
                state TEXT NOT NULL
            );
            CREATE TABLE registration_events(
                event_id INTEGER PRIMARY KEY,
                hardware_id TEXT,
                pairing_id TEXT,
                node_id TEXT
            );
            CREATE TABLE registration_node_history(
                history_id INTEGER PRIMARY KEY,
                hardware_id TEXT,
                node_id TEXT
            );
            CREATE TABLE node_id_leases(
                node_id TEXT PRIMARY KEY,
                hardware_id TEXT
            );
            CREATE TABLE retirement_outbox(
                retirement_id INTEGER PRIMARY KEY,
                hardware_id TEXT
            );
            """
        )


def credential_db(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE credential_assignments(
                assignment_id INTEGER PRIMARY KEY,
                hardware_id TEXT,
                node_id TEXT,
                last_node_id TEXT
            )
            """
        )


def replay_db(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE n3w_replay_state(node_id TEXT,highest_session INTEGER,highest_seq INTEGER)"
        )


def add_pending(registration: Path, hardware_id: str, pairing_id: str) -> None:
    with sqlite3.connect(registration) as connection:
        connection.execute(
            """
            INSERT INTO pairing_sessions(pairing_id,hardware_id,pairing_epoch,state)
            VALUES(?,?,1,'pending')
            """,
            (pairing_id, hardware_id),
        )
        connection.execute(
            """
            INSERT INTO registrations(
                hardware_id,current_pairing_id,pairing_epoch,node_id,
                repair_authorized,retired_at,retirement_reason
            ) VALUES(?,?,1,NULL,0,NULL,NULL)
            """,
            (hardware_id, pairing_id),
        )


def add_historical(registration: Path, credential: Path, hardware_id: str) -> None:
    pairing_id = "00000000-0000-4000-8000-000000000001"
    with sqlite3.connect(registration) as connection:
        connection.execute(
            """
            INSERT INTO pairing_sessions(pairing_id,hardware_id,pairing_epoch,state)
            VALUES(?,?,1,'approved')
            """,
            (pairing_id, hardware_id),
        )
        connection.execute(
            """
            INSERT INTO registrations(
                hardware_id,current_pairing_id,pairing_epoch,node_id,
                repair_authorized,retired_at,retirement_reason
            ) VALUES(?,?,1,'node_old',0,NULL,NULL)
            """,
            (hardware_id, pairing_id),
        )
    with sqlite3.connect(credential) as connection:
        connection.execute(
            """
            INSERT INTO credential_assignments(hardware_id,node_id,last_node_id)
            VALUES(?,?,?)
            """,
            (hardware_id, "node_old", "node_old"),
        )


def test_snapshot_contains_only_hashed_manager_identities(tmp_path: Path) -> None:
    module = load_module()
    registration = tmp_path / "registration.sqlite3"
    credential = tmp_path / "credential.sqlite3"
    registration_db(registration)
    credential_db(credential)
    historical = "ghw-c6-001122334455"
    add_historical(registration, credential, historical)

    payload = module.build_snapshot(registration, credential)

    assert payload["schema"] == module.SNAPSHOT_SCHEMA
    assert payload["hardware_id_count"] == 1
    assert payload["hardware_id_sha256"] == [module.sha256_text(historical)]
    assert historical not in str(payload)
    assert payload["read_only"] is True
    assert payload["manager_mutation"] is False


def test_verify_binds_unique_new_pending_to_scanned_hashes(tmp_path: Path) -> None:
    module = load_module()
    registration = tmp_path / "registration.sqlite3"
    credential = tmp_path / "credential.sqlite3"
    replay = tmp_path / "replay.sqlite3"
    registration_db(registration)
    credential_db(credential)
    replay_db(replay)

    old = "ghw-c6-001122334455"
    add_historical(registration, credential, old)
    snapshot = set(module.build_snapshot(registration, credential)["hardware_id_sha256"])

    target = "ghw-c6-112233445566"
    pairing = "123e4567-e89b-42d3-a456-426614174000"
    add_pending(registration, target, pairing)

    result = module.verify_binding(
        registration,
        credential,
        replay,
        snapshot_hashes=snapshot,
        product_hardware_id_sha256=module.sha256_text(target),
        pairing_id_sha256=module.sha256_text(pairing),
    )

    assert result["status"] == "PASS"
    assert result["new_pending_identity_count"] == 1
    assert result["lcd_matches_manager_pending"] is True
    assert result["preboot_identity_absent"] is True


def test_verify_rejects_target_present_in_preboot_snapshot(tmp_path: Path) -> None:
    module = load_module()
    registration = tmp_path / "registration.sqlite3"
    credential = tmp_path / "credential.sqlite3"
    replay = tmp_path / "replay.sqlite3"
    registration_db(registration)
    credential_db(credential)
    replay_db(replay)

    target = "ghw-c6-112233445566"
    pairing = "123e4567-e89b-42d3-a456-426614174000"
    add_pending(registration, target, pairing)
    snapshot = {module.sha256_text(target)}

    with pytest.raises(module.StopExecution):
        module.verify_binding(
            registration,
            credential,
            replay,
            snapshot_hashes=snapshot,
            product_hardware_id_sha256=module.sha256_text(target),
            pairing_id_sha256=module.sha256_text(pairing),
        )


def test_verify_rejects_multiple_new_pending_identities(tmp_path: Path) -> None:
    module = load_module()
    registration = tmp_path / "registration.sqlite3"
    credential = tmp_path / "credential.sqlite3"
    replay = tmp_path / "replay.sqlite3"
    registration_db(registration)
    credential_db(credential)
    replay_db(replay)

    first = "ghw-c6-112233445566"
    first_pairing = "123e4567-e89b-42d3-a456-426614174000"
    second = "ghw-c6-aabbccddeeff"
    second_pairing = "123e4567-e89b-42d3-a456-426614174001"
    add_pending(registration, first, first_pairing)
    add_pending(registration, second, second_pairing)

    with pytest.raises(module.StopExecution):
        module.verify_binding(
            registration,
            credential,
            replay,
            snapshot_hashes=set(),
            product_hardware_id_sha256=module.sha256_text(first),
            pairing_id_sha256=module.sha256_text(first_pairing),
        )


def test_verify_rejects_pairing_identity_mismatch(tmp_path: Path) -> None:
    module = load_module()
    registration = tmp_path / "registration.sqlite3"
    credential = tmp_path / "credential.sqlite3"
    replay = tmp_path / "replay.sqlite3"
    registration_db(registration)
    credential_db(credential)
    replay_db(replay)

    target = "ghw-c6-112233445566"
    pairing = "123e4567-e89b-42d3-a456-426614174000"
    add_pending(registration, target, pairing)

    with pytest.raises(module.StopExecution):
        module.verify_binding(
            registration,
            credential,
            replay,
            snapshot_hashes=set(),
            product_hardware_id_sha256=module.sha256_text(target),
            pairing_id_sha256="0" * 64,
        )


def test_source_is_read_only() -> None:
    source = SCRIPT.read_text(encoding="utf-8").upper()
    for statement in ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP TABLE", "ALTER TABLE"):
        assert statement not in source
    assert "PRAGMA QUERY_ONLY=ON" in source
    assert "MANAGER_MUTATION" in source
    assert "MANAGER_REPLAY_MUTATION" in source
