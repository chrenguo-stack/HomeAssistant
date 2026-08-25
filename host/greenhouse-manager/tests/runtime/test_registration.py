from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from greenhouse_manager.runtime.credential_lifecycle import CredentialLifecycleStore
from greenhouse_manager.runtime.registration import (
    HelloValidationError,
    RegistrationConflict,
    RegistrationRegistry,
    RegistrationState,
)

NOW = datetime(2026, 7, 11, 10, 0, tzinfo=UTC)
HARDWARE_ID = "ghw-c6-98a316a9f2f8"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
NODE_ID = "gh-n1-a9f2f8"
LOGICAL_LOCATION_ID = "greenhouse-bed-01"


def valid_hello(*, pairing_id: str = PAIRING_ID, epoch: int = 3) -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": pairing_id,
        "pairing_epoch": epoch,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "F1.0-RC2-N2.0",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials", "lcd-pairing-qr"],
        "sent_at_ms": 120345,
    }


@pytest.fixture
def registry(tmp_path: Path) -> RegistrationRegistry:
    instance = RegistrationRegistry(tmp_path / "registration.sqlite3", pending_ttl_s=120)
    yield instance
    instance.close()


def test_strictly_validates_untrusted_hello(registry: RegistrationRegistry) -> None:
    invalid = valid_hello()
    invalid["pairing_pop"] = "must-never-cross-mqtt"

    with pytest.raises(HelloValidationError, match="Additional properties"):
        registry.observe_hello(invalid, now=NOW)

    invalid = valid_hello()
    invalid["node_nonce"] = "too-short"
    with pytest.raises(HelloValidationError, match="node_nonce"):
        registry.observe_hello(invalid, now=NOW)


def test_creates_pending_and_deduplicates_same_session(registry: RegistrationRegistry) -> None:
    created = registry.observe_hello(valid_hello(), now=NOW)
    duplicate = registry.observe_hello(valid_hello(), now=NOW + timedelta(seconds=10))

    assert created.status == "created"
    assert created.record.state == RegistrationState.PENDING
    assert created.record.expires_at == NOW + timedelta(seconds=120)
    assert duplicate.status == "duplicate"
    assert duplicate.record.first_seen_at == NOW
    assert duplicate.record.last_seen_at == NOW + timedelta(seconds=10)


def test_approved_device_requires_bound_repair_intent_and_preserves_node_id(
    registry: RegistrationRegistry,
) -> None:
    registry.observe_hello(valid_hello(), now=NOW)
    approved = registry.approve(
        HARDWARE_ID,
        PAIRING_ID,
        node_id=NODE_ID,
        now=NOW,
    )

    next_pairing_id = "ca3e468d-fcdd-413d-b834-a8ac0cbe889e"

    blocked = registry.observe_hello(
        valid_hello(pairing_id=next_pairing_id, epoch=4),
        now=NOW + timedelta(seconds=18),
    )

    still_current = registry.get(HARDWARE_ID)

    assert blocked.status == "rejected"
    assert blocked.reason == "repair_intent_required"
    assert still_current.pairing_id == PAIRING_ID
    assert still_current.state is RegistrationState.APPROVED
    assert still_current.node_id == NODE_ID

    registry.authorize_repair(
        HARDWARE_ID,
        next_pairing_id,
        now=NOW + timedelta(seconds=19),
    )

    superseded = registry.observe_hello(
        valid_hello(pairing_id=next_pairing_id, epoch=4),
        now=NOW + timedelta(seconds=20),
    )
    reapproved = registry.approve(
        HARDWARE_ID,
        next_pairing_id,
        now=NOW + timedelta(seconds=21),
    )

    assert approved.node_id == NODE_ID
    assert superseded.status == "superseded"
    assert superseded.record.node_id == NODE_ID
    assert reapproved.node_id == NODE_ID
    assert reapproved.state == RegistrationState.APPROVED


def test_first_approval_requires_explicit_node_id(registry: RegistrationRegistry) -> None:
    registry.observe_hello(valid_hello(), now=NOW)

    with pytest.raises(RegistrationConflict, match="node_id is required"):
        registry.approve(HARDWARE_ID, PAIRING_ID, now=NOW)


def test_rejects_terminal_pairing_id_but_ignores_legacy_device_epoch(
    registry: RegistrationRegistry,
) -> None:
    registry.observe_hello(valid_hello(), now=NOW)
    registry.reject(HARDWARE_ID, PAIRING_ID)

    replay = registry.observe_hello(valid_hello(), now=NOW + timedelta(seconds=1))
    fresh = registry.observe_hello(
        valid_hello(
            pairing_id="3de01176-a1bb-4f5a-b1f8-cdeaf42e54c0",
            epoch=2,
        ),
        now=NOW + timedelta(seconds=2),
    )

    assert replay.status == "rejected"
    assert replay.reason == "replay_detected"
    assert fresh.status == "superseded"
    assert fresh.record.pairing_epoch == 2


def test_new_epoch_supersedes_pending_session(registry: RegistrationRegistry) -> None:
    registry.observe_hello(valid_hello(), now=NOW)
    next_pairing_id = "ca3e468d-fcdd-413d-b834-a8ac0cbe889e"

    result = registry.observe_hello(
        valid_hello(pairing_id=next_pairing_id, epoch=4),
        now=NOW + timedelta(seconds=1),
    )
    old_replay = registry.observe_hello(valid_hello(), now=NOW + timedelta(seconds=2))

    assert result.status == "superseded"
    assert result.record.pairing_id == next_pairing_id
    assert old_replay.status == "rejected"
    assert old_replay.reason == "replay_detected"


def test_expires_pending_and_refuses_late_approval(registry: RegistrationRegistry) -> None:
    registry.observe_hello(valid_hello(), now=NOW)

    assert registry.expire_pending(now=NOW + timedelta(seconds=120)) == 0
    assert registry.expire_pending(now=NOW + timedelta(seconds=121)) == 1
    assert registry.get(HARDWARE_ID).state == RegistrationState.EXPIRED
    with pytest.raises(RegistrationConflict, match="expired state"):
        registry.approve(HARDWARE_ID, PAIRING_ID, node_id=NODE_ID, now=NOW)


def test_abandons_only_expired_first_registration_and_preserves_replay_tombstone(
    registry: RegistrationRegistry,
    tmp_path: Path,
) -> None:
    registry.observe_hello(valid_hello(), now=NOW)
    registry.expire_pending(now=NOW + timedelta(seconds=121))

    with CredentialLifecycleStore(tmp_path / "credential-lifecycle.sqlite3") as credentials:
        abandoned = registry.abandon_expired_first_registration(
            HARDWARE_ID,
            PAIRING_ID,
            credential_history=credentials,
            now=NOW + timedelta(seconds=122),
        )

    with pytest.raises(KeyError):
        registry.get(HARDWARE_ID)

    old_replay = registry.observe_hello(
        valid_hello(),
        now=NOW + timedelta(seconds=123),
    )
    replacement_pairing_id = "ca3e468d-fcdd-413d-b834-a8ac0cbe889e"
    replacement = registry.observe_hello(
        valid_hello(pairing_id=replacement_pairing_id, epoch=3),
        now=NOW + timedelta(seconds=124),
    )
    events = registry.list_events(hardware_id=HARDWARE_ID)
    tombstone = registry._connection.execute(
        "SELECT state, reason FROM pairing_sessions WHERE pairing_id = ?",
        (PAIRING_ID,),
    ).fetchone()

    assert abandoned.state is RegistrationState.EXPIRED
    assert old_replay.status == "rejected"
    assert old_replay.reason == "replay_detected"
    assert replacement.status == "created"
    assert replacement.record.state is RegistrationState.PENDING
    assert tombstone["state"] == "expired"
    assert tombstone["reason"] == "expired"
    assert [event.event for event in events] == [
        "hello_created",
        "expired_first_registration_abandoned",
        "expired",
        "hello_created",
    ]
    abandonment = next(
        event
        for event in events
        if event.event == "expired_first_registration_abandoned"
    )
    assert abandonment.reason == "expired_first_pairing_recovery"


def test_expired_first_registration_abandonment_rejects_credential_history(
    registry: RegistrationRegistry,
    tmp_path: Path,
) -> None:
    registry.observe_hello(valid_hello(), now=NOW)
    registry.expire_pending(now=NOW + timedelta(seconds=121))

    with CredentialLifecycleStore(tmp_path / "credential-lifecycle.sqlite3") as credentials:
        credentials.activate(
            hardware_id=HARDWARE_ID,
            node_id=NODE_ID,
            generation=1,
            pairing_id=PAIRING_ID,
            now=NOW,
        )
        with pytest.raises(RegistrationConflict, match="credential assignment history"):
            registry.abandon_expired_first_registration(
                HARDWARE_ID,
                PAIRING_ID,
                credential_history=credentials,
                now=NOW + timedelta(seconds=122),
            )

    assert registry.get(HARDWARE_ID).state is RegistrationState.EXPIRED


def test_expired_first_registration_abandonment_rejects_prior_node_assignment(
    registry: RegistrationRegistry,
    tmp_path: Path,
) -> None:
    registry.observe_hello(valid_hello(), now=NOW)
    registry.approve(HARDWARE_ID, PAIRING_ID, node_id=NODE_ID, now=NOW)
    registry.rollback_automatic_approval(HARDWARE_ID, PAIRING_ID, now=NOW)
    registry.expire_pending(now=NOW + timedelta(seconds=121))

    with (
        CredentialLifecycleStore(tmp_path / "credential-lifecycle.sqlite3") as credentials,
        pytest.raises(RegistrationConflict, match="prior node assignment history"),
    ):
        registry.abandon_expired_first_registration(
            HARDWARE_ID,
            PAIRING_ID,
            credential_history=credentials,
            now=NOW + timedelta(seconds=122),
        )


def test_expired_first_registration_abandonment_rejects_pending_state(
    registry: RegistrationRegistry,
    tmp_path: Path,
) -> None:
    registry.observe_hello(valid_hello(), now=NOW)

    with (
        CredentialLifecycleStore(tmp_path / "credential-lifecycle.sqlite3") as credentials,
        pytest.raises(RegistrationConflict, match="only an expired"),
    ):
        registry.abandon_expired_first_registration(
            HARDWARE_ID,
            PAIRING_ID,
            credential_history=credentials,
            now=NOW,
        )


def test_node_id_cannot_be_assigned_to_two_hardware_ids(registry: RegistrationRegistry) -> None:
    registry.observe_hello(valid_hello(), now=NOW)
    registry.approve(HARDWARE_ID, PAIRING_ID, node_id=NODE_ID, now=NOW)

    second = valid_hello(pairing_id="d5bcf708-88a0-4974-8ca9-597482974e94")
    second["hardware_id"] = "ghw-c6-112233445566"
    registry.observe_hello(second, now=NOW)
    with pytest.raises(RegistrationConflict, match="already assigned"):
        registry.approve(
            "ghw-c6-112233445566",
            "d5bcf708-88a0-4974-8ca9-597482974e94",
            node_id=NODE_ID,
            now=NOW,
        )


def test_registry_survives_process_restart(tmp_path: Path) -> None:
    database = tmp_path / "registration.sqlite3"
    with RegistrationRegistry(database) as first:
        first.observe_hello(valid_hello(), now=NOW)
        first.approve(HARDWARE_ID, PAIRING_ID, node_id=NODE_ID, now=NOW)

    with RegistrationRegistry(database) as restored:
        record = restored.get(HARDWARE_ID)

    assert record.state == RegistrationState.APPROVED
    assert record.node_id == NODE_ID
    assert json.loads(json.dumps(record.capabilities)) == [
        "mqtt-runtime-credentials",
        "lcd-pairing-qr",
    ]


def test_logical_location_survives_process_restart(tmp_path: Path) -> None:
    database = tmp_path / "registration.sqlite3"
    with RegistrationRegistry(database) as first:
        first.observe_hello(valid_hello(), now=NOW)
        first.approve(
            HARDWARE_ID,
            PAIRING_ID,
            node_id=NODE_ID,
            logical_location_id=LOGICAL_LOCATION_ID,
            now=NOW,
        )

    with RegistrationRegistry(database) as restored:
        record = restored.get(HARDWARE_ID)
        events = restored.list_events(hardware_id=HARDWARE_ID)

    assert record.logical_location_id == LOGICAL_LOCATION_ID
    assert events[0].logical_location_id == LOGICAL_LOCATION_ID


def test_records_secret_free_audit_events(registry: RegistrationRegistry) -> None:
    registry.observe_hello(valid_hello(), now=NOW)
    registry.approve(HARDWARE_ID, PAIRING_ID, node_id=NODE_ID, now=NOW + timedelta(seconds=1))

    events = registry.list_events(hardware_id=HARDWARE_ID)

    assert [event.event for event in events] == ["operator_approved", "hello_created"]
    assert events[0].occurred_at == NOW + timedelta(seconds=1)
    serialized = json.dumps([event.__dict__ for event in events], default=str)
    assert "node_nonce" not in serialized
    assert "pairing_pop" not in serialized


def test_records_expiry_event(registry: RegistrationRegistry) -> None:
    registry.observe_hello(valid_hello(), now=NOW)

    registry.expire_pending(now=NOW + timedelta(seconds=121))

    assert registry.list_events()[0].event == "expired"


def test_retirement_is_durable_auditable_and_releases_current_node_id(
    registry: RegistrationRegistry,
) -> None:
    registry.observe_hello(valid_hello(), now=NOW)
    registry.approve(
        HARDWARE_ID,
        PAIRING_ID,
        node_id=NODE_ID,
        logical_location_id=LOGICAL_LOCATION_ID,
        now=NOW,
    )

    job = registry.retire(
        HARDWARE_ID,
        system_id="greenhouse",
        reason="hardware_replaced",
        now=NOW + timedelta(seconds=2),
    )
    record = registry.get(HARDWARE_ID)
    events = registry.list_events(hardware_id=HARDWARE_ID)

    assert record.state is RegistrationState.RETIRED
    assert record.node_id is None
    assert record.retired_at == NOW + timedelta(seconds=2)
    assert job.node_id == NODE_ID
    assert job.logical_location_id == LOGICAL_LOCATION_ID
    assert job.runtime_cleanup_complete is False
    assert job.credentials_revoked is False
    assert registry.is_node_id_ingress_allowed(NODE_ID) is False
    assert events[0].event == "operator_retired"
    assert events[0].node_id == NODE_ID
    assert (
        registry.retire(
            HARDWARE_ID,
            system_id="greenhouse",
            now=NOW + timedelta(seconds=3),
        ).retirement_id
        == job.retirement_id
    )


def test_retired_hardware_repair_waits_for_outbox_and_requires_new_node_id(
    registry: RegistrationRegistry,
) -> None:
    registry.observe_hello(valid_hello(), now=NOW)
    registry.approve(HARDWARE_ID, PAIRING_ID, node_id=NODE_ID, now=NOW)
    job = registry.retire(HARDWARE_ID, system_id="greenhouse", now=NOW)

    next_pairing = "ca3e468d-fcdd-413d-b834-a8ac0cbe889e"
    blocked = registry.observe_hello(
        valid_hello(pairing_id=next_pairing, epoch=4),
        now=NOW + timedelta(seconds=1),
    )
    assert blocked.status == "rejected"
    assert blocked.reason == "hardware_retirement_incomplete"

    registry.mark_credentials_revoked(job.retirement_id, evidence="test", now=NOW)
    registry.mark_runtime_cleanup_complete(job.retirement_id, now=NOW)
    repaired = registry.observe_hello(
        valid_hello(pairing_id=next_pairing, epoch=4),
        now=NOW + timedelta(seconds=2),
    )
    assert repaired.status == "repaired_after_retirement"
    assert repaired.record.state is RegistrationState.PENDING
    assert repaired.record.node_id is None

    with pytest.raises(RegistrationConflict, match="permanently reserved"):
        registry.approve(
            HARDWARE_ID,
            next_pairing,
            node_id=NODE_ID,
            now=NOW + timedelta(seconds=3),
        )

    approved = registry.approve(
        HARDWARE_ID,
        next_pairing,
        node_id="gh-n1-new-a9f2f8",
        logical_location_id=LOGICAL_LOCATION_ID,
        now=NOW + timedelta(seconds=4),
    )
    assert approved.node_id == "gh-n1-new-a9f2f8"
    assert approved.state is RegistrationState.APPROVED


def test_retired_node_id_is_permanently_reserved_across_hardware(
    registry: RegistrationRegistry,
) -> None:
    registry.observe_hello(valid_hello(), now=NOW)
    registry.approve(
        HARDWARE_ID,
        PAIRING_ID,
        node_id=NODE_ID,
        logical_location_id=LOGICAL_LOCATION_ID,
        now=NOW,
    )
    job = registry.retire(HARDWARE_ID, system_id="greenhouse", now=NOW)
    registry.mark_credentials_revoked(job.retirement_id, evidence="test", now=NOW)
    registry.mark_runtime_cleanup_complete(job.retirement_id, now=NOW)

    second_hardware = "ghw-c6-112233445566"
    second_pairing = "d5bcf708-88a0-4974-8ca9-597482974e94"
    second = valid_hello(pairing_id=second_pairing, epoch=1)
    second["hardware_id"] = second_hardware
    registry.observe_hello(second, now=NOW)

    with pytest.raises(RegistrationConflict, match="permanently reserved"):
        registry.approve(
            second_hardware,
            second_pairing,
            node_id=NODE_ID,
            logical_location_id=LOGICAL_LOCATION_ID,
            now=NOW,
        )


def test_legacy_registry_schema_adds_location_columns_fail_closed(
    tmp_path: Path,
) -> None:
    database = tmp_path / "registration.sqlite3"
    with RegistrationRegistry(database):
        pass
    with sqlite3.connect(database) as connection:
        for table in (
            "registrations",
            "registration_events",
            "registration_node_history",
            "node_id_leases",
            "retirement_outbox",
        ):
            connection.execute(f"ALTER TABLE {table} DROP COLUMN logical_location_id")

    with RegistrationRegistry(database) as restored:
        for table in (
            "registrations",
            "registration_events",
            "registration_node_history",
            "node_id_leases",
            "retirement_outbox",
        ):
            columns = {
                row["name"] for row in restored._connection.execute(f"PRAGMA table_info({table})").fetchall()
            }
            assert "logical_location_id" in columns


def test_repair_cannot_change_node_id_without_retirement(
    registry: RegistrationRegistry,
) -> None:
    registry.observe_hello(valid_hello(), now=NOW)
    registry.approve(HARDWARE_ID, PAIRING_ID, node_id=NODE_ID, now=NOW)
    next_pairing_id = "ca3e468d-fcdd-413d-b834-a8ac0cbe889e"
    registry.authorize_repair(
        HARDWARE_ID,
        next_pairing_id,
        now=NOW,
    )
    registry.observe_hello(
        valid_hello(pairing_id=next_pairing_id, epoch=4),
        now=NOW + timedelta(seconds=1),
    )

    with pytest.raises(RegistrationConflict, match="requires retiring"):
        registry.approve(
            HARDWARE_ID,
            next_pairing_id,
            node_id="gh-n1-replacement",
            now=NOW + timedelta(seconds=2),
        )


def test_reusable_lease_migrates_fail_closed_to_retired(tmp_path: Path) -> None:
    database = tmp_path / "registration.sqlite3"
    with RegistrationRegistry(database) as registry:
        registry.observe_hello(valid_hello(), now=NOW)
        registry.approve(HARDWARE_ID, PAIRING_ID, node_id=NODE_ID, now=NOW)
        job = registry.retire(HARDWARE_ID, system_id="greenhouse", now=NOW)
        registry.mark_credentials_revoked(job.retirement_id, evidence="test", now=NOW)
        registry.mark_runtime_cleanup_complete(job.retirement_id, now=NOW)

    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            ALTER TABLE node_id_leases RENAME TO node_id_leases_v07;
            CREATE TABLE node_id_leases (
                node_id TEXT PRIMARY KEY,
                hardware_id TEXT NOT NULL,
                logical_location_id TEXT,
                state TEXT NOT NULL CHECK (state IN ('active', 'retiring', 'reusable')),
                retirement_id INTEGER,
                updated_at TEXT NOT NULL
            );
            INSERT INTO node_id_leases
            SELECT node_id, hardware_id, logical_location_id,
                   CASE WHEN state = 'retired' THEN 'reusable' ELSE state END,
                   retirement_id, updated_at
            FROM node_id_leases_v07;
            DROP TABLE node_id_leases_v07;
            """
        )

    with RegistrationRegistry(database) as restored:
        assert restored.node_id_lease_state(NODE_ID).value == "retired"
        assert restored.is_node_id_ingress_allowed(NODE_ID) is False

def test_repair_intent_expires_without_mutating_approved_registration(
    registry: RegistrationRegistry,
) -> None:
    registry.observe_hello(valid_hello(), now=NOW)
    registry.approve(
        HARDWARE_ID,
        PAIRING_ID,
        node_id=NODE_ID,
        now=NOW,
    )

    next_pairing_id = "7e0a9e6d-5b62-4de8-9d90-f1a8dd5774c9"
    registry.authorize_repair(
        HARDWARE_ID,
        next_pairing_id,
        now=NOW,
    )

    blocked = registry.observe_hello(
        valid_hello(pairing_id=next_pairing_id, epoch=4),
        now=NOW + timedelta(seconds=121),
    )

    current = registry.get(HARDWARE_ID)

    assert blocked.status == "rejected"
    assert blocked.reason == "repair_intent_expired"
    assert current.pairing_id == PAIRING_ID
    assert current.state is RegistrationState.APPROVED
    assert current.node_id == NODE_ID


def test_repair_intent_is_lost_on_manager_restart(tmp_path: Path) -> None:
    database = tmp_path / "registration.sqlite3"
    next_pairing_id = "7e0a9e6d-5b62-4de8-9d90-f1a8dd5774c9"

    with RegistrationRegistry(database) as first:
        first.observe_hello(valid_hello(), now=NOW)
        first.approve(
            HARDWARE_ID,
            PAIRING_ID,
            node_id=NODE_ID,
            now=NOW,
        )
        first.authorize_repair(
            HARDWARE_ID,
            next_pairing_id,
            now=NOW,
        )

    with RegistrationRegistry(database) as restored:
        blocked = restored.observe_hello(
            valid_hello(pairing_id=next_pairing_id, epoch=4),
            now=NOW + timedelta(seconds=1),
        )
        current = restored.get(HARDWARE_ID)

    assert blocked.status == "rejected"
    assert blocked.reason == "repair_intent_required"
    assert current.pairing_id == PAIRING_ID
    assert current.state is RegistrationState.APPROVED
    assert current.node_id == NODE_ID

def test_consumed_repair_intent_cannot_be_used_to_supersede_pending_repair(
    registry: RegistrationRegistry,
) -> None:
    pairing_2 = "ca3e468d-fcdd-413d-b834-a8ac0cbe889e"
    pairing_3 = "7e0a9e6d-5b62-4de8-9d90-f1a8dd5774c9"

    registry.observe_hello(valid_hello(), now=NOW)
    registry.approve(
        HARDWARE_ID,
        PAIRING_ID,
        node_id=NODE_ID,
        now=NOW,
    )

    registry.authorize_repair(
        HARDWARE_ID,
        pairing_2,
        now=NOW + timedelta(seconds=1),
    )
    accepted = registry.observe_hello(
        valid_hello(pairing_id=pairing_2, epoch=4),
        now=NOW + timedelta(seconds=2),
    )

    assert accepted.status == "superseded"
    assert accepted.record.state is RegistrationState.PENDING
    assert accepted.record.node_id == NODE_ID

    blocked = registry.observe_hello(
        valid_hello(pairing_id=pairing_3, epoch=5),
        now=NOW + timedelta(seconds=3),
    )
    current = registry.get(HARDWARE_ID)

    assert blocked.status == "rejected"
    assert blocked.reason == "repair_intent_required"
    assert current.pairing_id == pairing_2
    assert current.state is RegistrationState.PENDING
    assert current.node_id == NODE_ID

    with pytest.raises(
        RegistrationConflict,
        match="still pending",
    ):
        registry.authorize_repair(
            HARDWARE_ID,
            pairing_3,
            now=NOW + timedelta(seconds=4),
        )


def test_expired_registered_repair_requires_new_pair_bound_intent(
    registry: RegistrationRegistry,
) -> None:
    pairing_2 = "ca3e468d-fcdd-413d-b834-a8ac0cbe889e"
    pairing_3 = "7e0a9e6d-5b62-4de8-9d90-f1a8dd5774c9"

    registry.observe_hello(valid_hello(), now=NOW)
    registry.approve(
        HARDWARE_ID,
        PAIRING_ID,
        node_id=NODE_ID,
        now=NOW,
    )

    registry.authorize_repair(
        HARDWARE_ID,
        pairing_2,
        now=NOW + timedelta(seconds=1),
    )
    registry.observe_hello(
        valid_hello(pairing_id=pairing_2, epoch=4),
        now=NOW + timedelta(seconds=2),
    )

    assert (
        registry.expire_pending(
            now=NOW + timedelta(seconds=123)
        )
        == 1
    )
    assert registry.get(HARDWARE_ID).state is RegistrationState.EXPIRED

    blocked = registry.observe_hello(
        valid_hello(pairing_id=pairing_3, epoch=5),
        now=NOW + timedelta(seconds=124),
    )

    assert blocked.status == "rejected"
    assert blocked.reason == "repair_intent_required"
    assert registry.get(HARDWARE_ID).pairing_id == pairing_2

    registry.authorize_repair(
        HARDWARE_ID,
        pairing_3,
        now=NOW + timedelta(seconds=125),
    )
    accepted = registry.observe_hello(
        valid_hello(pairing_id=pairing_3, epoch=5),
        now=NOW + timedelta(seconds=126),
    )

    assert accepted.status == "superseded"
    assert accepted.record.pairing_id == pairing_3
    assert accepted.record.state is RegistrationState.PENDING
    assert accepted.record.node_id == NODE_ID

def test_legacy_repair_authorized_flag_is_not_product_correctness_authority(
    registry: RegistrationRegistry,
    tmp_path: Path,
) -> None:
    registry.observe_hello(
        valid_hello(),
        now=NOW,
    )
    registry.expire_pending(
        now=NOW + timedelta(seconds=121)
    )

    # Simulate a legacy database that retained the old durable repair bit.
    # It is compatibility residue only and must no longer affect product
    # recovery decisions.
    with registry._connection:
        registry._connection.execute(
            """
            UPDATE registrations
            SET repair_authorized = 1
            WHERE hardware_id = ?
            """,
            (HARDWARE_ID,),
        )

    with CredentialLifecycleStore(
        tmp_path / "credential-lifecycle.sqlite3"
    ) as credentials:
        abandoned = (
            registry
            .abandon_expired_first_registration(
                HARDWARE_ID,
                PAIRING_ID,
                credential_history=credentials,
                now=NOW + timedelta(seconds=122),
            )
        )

    assert (
        abandoned.state
        is RegistrationState.EXPIRED
    )

    with pytest.raises(KeyError):
        registry.get(HARDWARE_ID)
