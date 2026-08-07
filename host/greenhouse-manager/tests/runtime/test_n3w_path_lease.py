from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from greenhouse_manager.runtime.n3w_path_lease import (
    N3wPathLeaseCoordinator,
    PathLeasePolicy,
    PathOwner,
)
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

NODE_ID = "node_01hzx7aq5fj3"
BOOT_1 = "boot_0000000000000001"
BOOT_2 = "boot_0000000000000002"
DIRECT = PathOwner("direct")
RELAY_A = PathOwner("relay", "gateway_01hzx7aq5fj3")
RELAY_B = PathOwner("relay", "gateway_01hzx7aq5fj4")
NOW = datetime(2026, 8, 7, 8, 0, tzinfo=UTC)
POLICY = PathLeasePolicy(
    stability_window_s=5,
    minimum_distinct_frames=2,
    lease_ttl_s=10,
    old_path_grace_s=3,
)


def coordinator(
    database: Path,
    *,
    ingress_allowed: bool = True,
) -> tuple[ReplayRegistry, N3wPathLeaseCoordinator]:
    replay = ReplayRegistry(database)
    path = N3wPathLeaseCoordinator(
        replay_registry=replay,
        policy=POLICY,
        ingress_allowed=lambda _node_id: ingress_allowed,
    )
    return replay, path


def test_first_valid_frame_establishes_one_persistent_path_and_cursor(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"
    replay, path = coordinator(database)
    try:
        accepted = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=7,
            owner=DIRECT,
            now=NOW,
        )
        audit = path.audit()
        assert accepted.status == "accepted"
        assert accepted.active_owner == DIRECT
        assert accepted.revision == 1
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=7).status == "duplicate"
        assert audit["node_count"] == 1
    finally:
        replay.close()

    replay2, path2 = coordinator(database)
    try:
        duplicate = path2.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=7,
            owner=RELAY_A,
            now=NOW + timedelta(seconds=1),
        )
        assert duplicate.status == "duplicate"
        assert duplicate.active_owner == DIRECT
    finally:
        replay2.close()


def test_same_boot_unseen_lower_sequence_is_rejected_without_consumption(tmp_path: Path) -> None:
    replay, path = coordinator(tmp_path / "replay.sqlite3")
    try:
        assert (
            path.process(
                node_id=NODE_ID,
                boot_id=BOOT_1,
                seq=100,
                owner=DIRECT,
                now=NOW,
            ).status
            == "accepted"
        )
        stale = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=99,
            owner=DIRECT,
            now=NOW + timedelta(seconds=1),
        )
        assert stale.status == "rejected"
        assert stale.code == "stale_sequence"
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=99).status == "ready"
    finally:
        replay.close()


def test_direct_health_blocks_relay_candidate_and_does_not_consume_tuple(tmp_path: Path) -> None:
    replay, path = coordinator(tmp_path / "replay.sqlite3")
    try:
        path.process(node_id=NODE_ID, boot_id=BOOT_1, seq=1, owner=DIRECT, now=NOW)
        blocked = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=2,
            owner=RELAY_A,
            now=NOW + timedelta(seconds=5),
        )
        assert blocked.status == "rejected"
        assert blocked.code == "active_path_healthy"
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=2).status == "ready"
    finally:
        replay.close()


def test_expired_direct_switches_only_after_stable_relay_candidate(tmp_path: Path) -> None:
    replay, path = coordinator(tmp_path / "replay.sqlite3")
    try:
        path.process(node_id=NODE_ID, boot_id=BOOT_1, seq=1, owner=DIRECT, now=NOW)
        first = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=2,
            owner=RELAY_A,
            now=NOW + timedelta(seconds=11),
        )
        assert first.code == "path_candidate_pending"
        assert first.candidate_distinct_count == 1
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=2).status == "ready"

        repeated = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=2,
            owner=RELAY_A,
            now=NOW + timedelta(seconds=12),
        )
        assert repeated.code == "candidate_sequence_not_advancing"
        assert repeated.candidate_distinct_count == 1

        switched = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=3,
            owner=RELAY_A,
            now=NOW + timedelta(seconds=16),
        )
        assert switched.status == "accepted"
        assert switched.switched is True
        assert switched.active_owner == RELAY_A
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=2).status == "ready"
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=3).status == "duplicate"
    finally:
        replay.close()


def test_stable_direct_preempts_relay_without_waiting_for_relay_lease_expiry(tmp_path: Path) -> None:
    replay, path = coordinator(tmp_path / "replay.sqlite3")
    try:
        path.process(node_id=NODE_ID, boot_id=BOOT_1, seq=1, owner=RELAY_A, now=NOW)
        first = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=2,
            owner=DIRECT,
            now=NOW + timedelta(seconds=1),
        )
        assert first.code == "path_candidate_pending"

        path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=3,
            owner=RELAY_A,
            now=NOW + timedelta(seconds=2),
        )
        switched = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=4,
            owner=DIRECT,
            now=NOW + timedelta(seconds=6),
        )
        assert switched.status == "accepted"
        assert switched.switched is True
        assert switched.active_owner == DIRECT
    finally:
        replay.close()


def test_candidate_state_survives_restart_without_consuming_candidate_tuple(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"
    replay, path = coordinator(database)
    path.process(node_id=NODE_ID, boot_id=BOOT_1, seq=1, owner=DIRECT, now=NOW)
    pending = path.process(
        node_id=NODE_ID,
        boot_id=BOOT_1,
        seq=2,
        owner=RELAY_A,
        now=NOW + timedelta(seconds=11),
    )
    assert pending.code == "path_candidate_pending"
    replay.close()

    replay2, path2 = coordinator(database)
    try:
        assert replay2.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=2).status == "ready"
        switched = path2.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=3,
            owner=RELAY_A,
            now=NOW + timedelta(seconds=16),
        )
        assert switched.status == "accepted"
        assert switched.switched is True
    finally:
        replay2.close()


def test_old_path_grace_never_consumes_or_canonicalizes_new_old_path_tuple(tmp_path: Path) -> None:
    replay, path = coordinator(tmp_path / "replay.sqlite3")
    try:
        path.process(node_id=NODE_ID, boot_id=BOOT_1, seq=1, owner=DIRECT, now=NOW)
        path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=2,
            owner=RELAY_A,
            now=NOW + timedelta(seconds=11),
        )
        path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=3,
            owner=RELAY_A,
            now=NOW + timedelta(seconds=16),
        )
        grace = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=4,
            owner=DIRECT,
            now=NOW + timedelta(seconds=17),
        )
        assert grace.status == "rejected"
        assert grace.code == "old_path_grace"
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=4).status == "ready"
    finally:
        replay.close()


def test_higher_session_advances_on_accept_and_lower_session_fails_across_path(tmp_path: Path) -> None:
    replay, path = coordinator(tmp_path / "replay.sqlite3")
    try:
        path.process(node_id=NODE_ID, boot_id=BOOT_1, seq=9, owner=DIRECT, now=NOW)
        higher = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_2,
            seq=0,
            owner=DIRECT,
            now=NOW + timedelta(seconds=1),
        )
        stale = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=99,
            owner=RELAY_A,
            now=NOW + timedelta(seconds=2),
        )
        assert higher.status == "accepted"
        assert stale.status == "rejected"
        assert stale.code == "stale_boot_session"
    finally:
        replay.close()


def test_lifecycle_denial_happens_before_any_path_or_replay_mutation(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"
    replay, path = coordinator(database, ingress_allowed=False)
    try:
        denied = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=1,
            owner=DIRECT,
            now=NOW,
        )
        assert denied.status == "rejected"
        assert denied.code == "node_ingress_not_allowed"
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=1).status == "ready"
        assert path.audit()["node_count"] == 0
    finally:
        replay.close()


def test_clock_rollback_fails_closed_without_consuming_tuple(tmp_path: Path) -> None:
    replay, path = coordinator(tmp_path / "replay.sqlite3")
    try:
        path.process(node_id=NODE_ID, boot_id=BOOT_1, seq=1, owner=DIRECT, now=NOW)
        rollback = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=2,
            owner=DIRECT,
            now=NOW - timedelta(seconds=1),
        )
        assert rollback.status == "rejected"
        assert rollback.code == "clock_rollback"
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=2).status == "ready"
    finally:
        replay.close()


def test_path_update_failure_rolls_back_replay_and_cursor(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"
    replay, path = coordinator(database)
    path.process(node_id=NODE_ID, boot_id=BOOT_1, seq=1, owner=DIRECT, now=NOW)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TRIGGER fail_path_update
            BEFORE UPDATE ON n3w_path_leases
            BEGIN
                SELECT RAISE(ABORT, 'forced path failure');
            END;
            """
        )

    failed = path.process(
        node_id=NODE_ID,
        boot_id=BOOT_1,
        seq=2,
        owner=DIRECT,
        now=NOW + timedelta(seconds=1),
    )
    assert failed.status == "rejected"

    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER fail_path_update")
    assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=2).status == "ready"
    recovered = path.process(
        node_id=NODE_ID,
        boot_id=BOOT_1,
        seq=2,
        owner=DIRECT,
        now=NOW + timedelta(seconds=1),
    )
    assert recovered.status == "accepted"
    replay.close()


def test_replay_insert_failure_rolls_back_switch_candidate_and_owner(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"
    replay, path = coordinator(database)
    path.process(node_id=NODE_ID, boot_id=BOOT_1, seq=1, owner=DIRECT, now=NOW)
    path.process(
        node_id=NODE_ID,
        boot_id=BOOT_1,
        seq=2,
        owner=RELAY_A,
        now=NOW + timedelta(seconds=11),
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TRIGGER fail_replay_insert
            BEFORE INSERT ON n3w_replay_seen
            BEGIN
                SELECT RAISE(ABORT, 'forced replay failure');
            END;
            """
        )

    failed = path.process(
        node_id=NODE_ID,
        boot_id=BOOT_1,
        seq=3,
        owner=RELAY_A,
        now=NOW + timedelta(seconds=16),
    )
    assert failed.status == "rejected"

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT active_transport, candidate_distinct_count FROM n3w_path_leases WHERE node_id = ?",
            (NODE_ID,),
        ).fetchone()
        connection.execute("DROP TRIGGER fail_replay_insert")
    assert row == ("direct", 1)
    assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=3).status == "ready"
    replay.close()


def test_concurrent_relay_gateways_serialize_to_one_durable_owner(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"
    replay, path = coordinator(database)
    path.process(node_id=NODE_ID, boot_id=BOOT_1, seq=1, owner=DIRECT, now=NOW)
    path.process(
        node_id=NODE_ID,
        boot_id=BOOT_1,
        seq=2,
        owner=RELAY_A,
        now=NOW + timedelta(seconds=11),
    )
    path.process(
        node_id=NODE_ID,
        boot_id=BOOT_1,
        seq=3,
        owner=RELAY_A,
        now=NOW + timedelta(seconds=16),
    )
    replay.close()

    def compete(owner: PathOwner, seq: int) -> str:
        local_replay = ReplayRegistry(database)
        local_path = N3wPathLeaseCoordinator(
            replay_registry=local_replay,
            policy=PathLeasePolicy(
                stability_window_s=0,
                minimum_distinct_frames=1,
                lease_ttl_s=1,
                old_path_grace_s=0,
            ),
            ingress_allowed=lambda _node_id: True,
        )
        try:
            return local_path.process(
                node_id=NODE_ID,
                boot_id=BOOT_1,
                seq=seq,
                owner=owner,
                now=NOW + timedelta(seconds=30),
            ).status
        finally:
            local_replay.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = [
            future.result()
            for future in (
                executor.submit(compete, RELAY_A, 4),
                executor.submit(compete, RELAY_B, 5),
            )
        ]
    assert statuses.count("accepted") == 1
