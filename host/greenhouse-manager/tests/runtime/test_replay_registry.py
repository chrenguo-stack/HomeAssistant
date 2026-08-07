from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from greenhouse_manager.runtime.replay_registry import (
    ReplayRegistry,
    ReplayRegistryUnavailable,
    validate_replay_tuple,
)

NODE_ID = "node_01hzx7aq5fj3"
BOOT_1 = "boot_0000000000000001"
BOOT_2 = "boot_0000000000000002"
BOOT_MAX = "boot_ffffffffffffffff"


def test_validate_replay_tuple_enforces_n3w_boot_session_and_seq() -> None:
    key = validate_replay_tuple(NODE_ID, BOOT_MAX, 2**32 - 1)
    assert key.boot_session == 2**64 - 1

    for invalid_boot in (
        "boot_0000000000000000",
        "boot_000000000000000G",
        "boot_01J2A6Q9T8W4",
    ):
        with pytest.raises(ValueError, match="boot_session_invalid"):
            validate_replay_tuple(NODE_ID, invalid_boot, 0)

    with pytest.raises(ValueError, match="sequence_out_of_range"):
        validate_replay_tuple(NODE_ID, BOOT_1, 2**32)
    with pytest.raises(ValueError, match="sequence_out_of_range"):
        validate_replay_tuple(NODE_ID, BOOT_1, True)


def test_inspection_is_read_only_and_commit_consumes_tuple(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"
    with ReplayRegistry(database) as registry:
        before = registry.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=7)
        after_inspect = registry.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=7)
        committed = registry.commit(node_id=NODE_ID, boot_id=BOOT_1, seq=7)
        duplicate = registry.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=7)

    assert before.status == "ready"
    assert after_inspect.status == "ready"
    assert committed.status == "accepted"
    assert committed.highest_session == 1
    assert duplicate.status == "duplicate"


def test_read_only_open_never_creates_or_consumes_state(tmp_path: Path) -> None:
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(ReplayRegistryUnavailable, match="replay_registry_unavailable"):
        ReplayRegistry(missing, read_only=True)
    assert not missing.exists()

    database = tmp_path / "replay.sqlite3"
    with ReplayRegistry(database) as registry:
        registry.commit(node_id=NODE_ID, boot_id=BOOT_1, seq=3)

    with ReplayRegistry(database, read_only=True) as registry:
        inspection = registry.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=4)
        with pytest.raises(ReplayRegistryUnavailable, match="replay_registry_read_only"):
            registry.commit(node_id=NODE_ID, boot_id=BOOT_1, seq=4)

    assert inspection.status == "ready"
    with ReplayRegistry(database) as registry:
        assert registry.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=4).status == "ready"


def test_higher_session_advances_and_lower_session_fails_closed(tmp_path: Path) -> None:
    with ReplayRegistry(tmp_path / "replay.sqlite3") as registry:
        assert registry.commit(node_id=NODE_ID, boot_id=BOOT_1, seq=5).status == "accepted"
        assert registry.commit(node_id=NODE_ID, boot_id=BOOT_2, seq=0).status == "accepted"

        stale = registry.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=6)
        stale_commit = registry.commit(node_id=NODE_ID, boot_id=BOOT_1, seq=6)
        same_session_new_seq = registry.commit(node_id=NODE_ID, boot_id=BOOT_2, seq=1)

    assert stale.status == "stale_boot_session"
    assert stale.highest_session == 2
    assert stale_commit.status == "stale_boot_session"
    assert same_session_new_seq.status == "accepted"


def test_higher_session_prunes_lower_session_replay_rows(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"
    with ReplayRegistry(database) as registry:
        registry.commit(node_id=NODE_ID, boot_id=BOOT_1, seq=1)
        registry.commit(node_id=NODE_ID, boot_id=BOOT_1, seq=2)
        registry.commit(node_id=NODE_ID, boot_id=BOOT_2, seq=0)
        audit = registry.audit()

    assert audit["replay_tuple_count"] == 1


def test_state_persists_across_manager_restart(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"
    with ReplayRegistry(database) as registry:
        registry.commit(node_id=NODE_ID, boot_id=BOOT_MAX, seq=42)

    with ReplayRegistry(database) as reopened:
        duplicate = reopened.inspect(node_id=NODE_ID, boot_id=BOOT_MAX, seq=42)
        stale = reopened.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=43)
        audit = reopened.audit()

    assert duplicate.status == "duplicate"
    assert duplicate.highest_session == 2**64 - 1
    assert stale.status == "stale_boot_session"
    assert audit["node_count"] == 1
    assert audit["replay_tuple_count"] == 1


def test_commit_rolls_back_high_water_when_replay_insert_fails(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"
    with ReplayRegistry(database) as registry:
        registry.commit(node_id=NODE_ID, boot_id=BOOT_1, seq=1)

    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TRIGGER fail_replay_insert
            BEFORE INSERT ON n3w_replay_seen
            BEGIN
                SELECT RAISE(ABORT, 'forced replay insert failure');
            END;
            """
        )

    with (
        ReplayRegistry(database) as registry,
        pytest.raises(
            ReplayRegistryUnavailable,
            match="replay_registry_unavailable",
        ),
    ):
        registry.commit(node_id=NODE_ID, boot_id=BOOT_2, seq=1)

    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER fail_replay_insert")

    with ReplayRegistry(database) as registry:
        inspection = registry.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=2)
        new_session = registry.inspect(node_id=NODE_ID, boot_id=BOOT_2, seq=1)

    assert inspection.status == "ready"
    assert inspection.highest_session == 1
    assert new_session.status == "ready"
    assert new_session.highest_session == 1


def test_concurrent_connections_serialize_same_tuple(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"
    with ReplayRegistry(database):
        pass

    def commit_once() -> str:
        with ReplayRegistry(database) as registry:
            return registry.commit(node_id=NODE_ID, boot_id=BOOT_1, seq=9).status

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(commit_once) for _ in range(2)]
        statuses = sorted(future.result() for future in futures)

    assert statuses == ["accepted", "duplicate"]


def test_closed_or_corrupt_registry_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"
    registry = ReplayRegistry(database)
    registry.close()

    with pytest.raises(ReplayRegistryUnavailable, match="replay_registry_unavailable"):
        registry.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=1)

    corrupt = tmp_path / "corrupt.sqlite3"
    corrupt.write_bytes(b"not a sqlite database")
    with pytest.raises(ReplayRegistryUnavailable):
        ReplayRegistry(corrupt)


def test_audit_detects_invalid_persisted_high_water(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"
    with ReplayRegistry(database) as registry:
        registry.commit(node_id=NODE_ID, boot_id=BOOT_1, seq=1)

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE n3w_replay_state SET highest_session_hex = 'not-valid' WHERE node_id = ?",
            (NODE_ID,),
        )

    with (
        ReplayRegistry(database) as registry,
        pytest.raises(
            ReplayRegistryUnavailable,
            match="replay_registry_corrupt",
        ),
    ):
        registry.audit()
