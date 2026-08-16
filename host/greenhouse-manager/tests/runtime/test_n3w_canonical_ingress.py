from datetime import UTC, datetime

from greenhouse_manager.runtime.n3w_canonical_ingress import N3wCanonicalIngressCoordinator
from greenhouse_manager.runtime.n3w_path_lease import (
    N3wPathLeaseCoordinator,
    PathLeasePolicy,
    PathOwner,
)
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
NODE_ID = "node_child01"


def boot(value: int) -> str:
    return f"boot_{value:016x}"


def test_multi_ingress_latest_valid_wins_without_path_owner(tmp_path) -> None:
    with ReplayRegistry(tmp_path / "replay.sqlite3") as replay:
        canonical = N3wCanonicalIngressCoordinator(
            replay_registry=replay,
            ingress_allowed=lambda _node_id: True,
        )
        assert canonical.process(
            node_id=NODE_ID,
            boot_id=boot(1),
            seq=100,
            source="direct",
            now=NOW,
        ).status == "accepted"
        assert canonical.process(
            node_id=NODE_ID,
            boot_id=boot(1),
            seq=100,
            source="relay",
            gateway_id="node_relay01",
            now=NOW,
        ).status == "duplicate"
        assert canonical.process(
            node_id=NODE_ID,
            boot_id=boot(1),
            seq=101,
            source="relay",
            gateway_id="node_relay02",
            now=NOW,
        ).status == "accepted"
        stale = canonical.process(
            node_id=NODE_ID,
            boot_id=boot(1),
            seq=100,
            source="direct",
            now=NOW,
        )
        assert stale.status == "rejected"
        assert stale.code == "stale_sequence"
        assert canonical.process(
            node_id=NODE_ID,
            boot_id=boot(1),
            seq=102,
            source="direct",
            now=NOW,
        ).status == "accepted"
        snapshot = canonical.snapshot(NODE_ID)
        audit = canonical.audit()

    assert snapshot.seq == 102
    assert snapshot.last_source == "direct"
    assert audit["path_lease_dependency"] is False
    assert audit["candidate_path_state"] is False


def test_new_boot_accepts_sequence_reset_and_old_boot_is_stale(tmp_path) -> None:
    with ReplayRegistry(tmp_path / "replay.sqlite3") as replay:
        canonical = N3wCanonicalIngressCoordinator(
            replay_registry=replay,
            ingress_allowed=lambda _node_id: True,
        )
        assert canonical.process(
            node_id=NODE_ID,
            boot_id=boot(7),
            seq=900,
            source="direct",
            now=NOW,
        ).status == "accepted"
        assert canonical.process(
            node_id=NODE_ID,
            boot_id=boot(8),
            seq=0,
            source="relay",
            gateway_id="node_relay01",
            now=NOW,
        ).status == "accepted"
        stale = canonical.process(
            node_id=NODE_ID,
            boot_id=boot(7),
            seq=901,
            source="direct",
            now=NOW,
        )

    assert stale.status == "rejected"
    assert stale.code == "stale_boot_session"


def test_missing_periodic_sample_recovers_on_next_sequence(tmp_path) -> None:
    with ReplayRegistry(tmp_path / "replay.sqlite3") as replay:
        canonical = N3wCanonicalIngressCoordinator(
            replay_registry=replay,
            ingress_allowed=lambda _node_id: True,
        )
        assert canonical.process(
            node_id=NODE_ID,
            boot_id=boot(3),
            seq=40,
            source="direct",
            now=NOW,
        ).status == "accepted"
        assert canonical.process(
            node_id=NODE_ID,
            boot_id=boot(3),
            seq=42,
            source="relay",
            gateway_id="node_relay01",
            now=NOW,
        ).status == "accepted"


def test_initialization_imports_legacy_path_high_water_before_path_removal(tmp_path) -> None:
    with ReplayRegistry(tmp_path / "replay.sqlite3") as replay:
        legacy = N3wPathLeaseCoordinator(
            replay_registry=replay,
            policy=PathLeasePolicy(
                stability_window_s=0,
                minimum_distinct_frames=1,
                lease_ttl_s=30,
                old_path_grace_s=0,
            ),
            ingress_allowed=lambda _node_id: True,
        )
        assert legacy.process(
            node_id=NODE_ID,
            boot_id=boot(9),
            seq=100,
            owner=PathOwner("direct"),
            now=NOW,
        ).status == "accepted"

        canonical = N3wCanonicalIngressCoordinator(
            replay_registry=replay,
            ingress_allowed=lambda _node_id: True,
        )
        assert canonical.snapshot(NODE_ID).seq == 100
        stale = canonical.process(
            node_id=NODE_ID,
            boot_id=boot(9),
            seq=99,
            source="relay",
            gateway_id="node_relay01",
            now=NOW,
        )
        advanced = canonical.process(
            node_id=NODE_ID,
            boot_id=boot(9),
            seq=101,
            source="relay",
            gateway_id="node_relay01",
            now=NOW,
        )

    assert stale.status == "rejected"
    assert stale.code == "stale_sequence"
    assert advanced.status == "accepted"
