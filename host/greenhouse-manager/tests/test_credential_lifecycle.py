from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from greenhouse_manager.credential_lifecycle import (
    CredentialLifecycleConflict,
    CredentialLifecycleStore,
    CredentialState,
)

HARDWARE_ID = "ghw-c6-98a316a9f2f8"
NODE_ID = "gh-n1-a9f2f8"
NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


def test_records_secret_free_active_generation(tmp_path: Path) -> None:
    database = tmp_path / "registration.sqlite3"
    with CredentialLifecycleStore(database) as store:
        record = store.activate(
            hardware_id=HARDWARE_ID, node_id=NODE_ID, generation=1, now=NOW
        )

    assert record.state is CredentialState.ACTIVE
    assert record.active_generation == 1
    assert record.pending_generation is None
    serialized = json.dumps(asdict(record), default=str)
    assert "password" not in serialized
    assert "secret" not in serialized


def test_rotation_commit_is_monotonic_and_persistent(tmp_path: Path) -> None:
    database = tmp_path / "registration.sqlite3"
    with CredentialLifecycleStore(database) as store:
        store.activate(hardware_id=HARDWARE_ID, node_id=NODE_ID, generation=1, now=NOW)
        rotating = store.begin_rotation(
            HARDWARE_ID, generation=2, now=NOW + timedelta(seconds=1)
        )
        committed = store.commit_rotation(
            HARDWARE_ID, now=NOW + timedelta(seconds=2)
        )

    with CredentialLifecycleStore(database) as restored:
        persisted = restored.get(HARDWARE_ID)

    assert rotating.state is CredentialState.ROTATING
    assert rotating.active_generation == 1
    assert rotating.pending_generation == 2
    assert committed.active_generation == 2
    assert committed.pending_generation is None
    assert persisted == committed


def test_rotation_rollback_preserves_active_generation(tmp_path: Path) -> None:
    database = tmp_path / "registration.sqlite3"
    with CredentialLifecycleStore(database) as store:
        store.activate(hardware_id=HARDWARE_ID, node_id=NODE_ID, generation=7, now=NOW)
        store.begin_rotation(HARDWARE_ID, generation=8, now=NOW)
        restored = store.roll_back_rotation(HARDWARE_ID, now=NOW)

    assert restored.state is CredentialState.ACTIVE
    assert restored.active_generation == 7
    assert restored.pending_generation is None
    assert restored.reason == "candidate_verification_failed"


def test_rejects_generation_rollback_and_parallel_rotation(tmp_path: Path) -> None:
    with CredentialLifecycleStore(tmp_path / "registration.sqlite3") as store:
        store.activate(hardware_id=HARDWARE_ID, node_id=NODE_ID, generation=3, now=NOW)
        with pytest.raises(CredentialLifecycleConflict, match="generation must increase"):
            store.begin_rotation(HARDWARE_ID, generation=3, now=NOW)
        store.begin_rotation(HARDWARE_ID, generation=4, now=NOW)
        with pytest.raises(CredentialLifecycleConflict, match="rotating state"):
            store.begin_rotation(HARDWARE_ID, generation=5, now=NOW)


def test_revoke_and_recovery_clear_pending_generation(tmp_path: Path) -> None:
    first_database = tmp_path / "revoke.sqlite3"
    with CredentialLifecycleStore(first_database) as store:
        store.activate(hardware_id=HARDWARE_ID, node_id=NODE_ID, generation=1, now=NOW)
        store.begin_rotation(HARDWARE_ID, generation=2, now=NOW)
        revoked = store.revoke(HARDWARE_ID, now=NOW)

    second_database = tmp_path / "recovery.sqlite3"
    with CredentialLifecycleStore(second_database) as store:
        store.activate(hardware_id=HARDWARE_ID, node_id=NODE_ID, generation=1, now=NOW)
        recovery = store.require_recovery(
            HARDWARE_ID, reason="backup_integrity_failed", now=NOW
        )

    assert revoked.state is CredentialState.REVOKED
    assert revoked.pending_generation is None
    assert recovery.state is CredentialState.RECOVERY_REQUIRED
    assert recovery.reason == "backup_integrity_failed"
