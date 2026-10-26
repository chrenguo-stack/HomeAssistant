from __future__ import annotations

import hashlib
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from greenhouse_manager.runtime.n3w_first_registration_ledger import (
    FirstRegistrationAttemptState,
    FirstRegistrationCleanupState,
    FirstRegistrationLedgerConflict,
    FirstRegistrationPhase,
)
from greenhouse_manager.runtime.registration import RegistrationRegistry

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
PAIRING_ID = str(uuid.UUID("12345678-1234-4234-8234-123456789abc"))
HARDWARE_ID = "ghw-c6-001122334455"
HARDWARE_SHA256 = hashlib.sha256(HARDWARE_ID.encode("utf-8")).hexdigest()
DELIVERY_SHA256 = "d" * 64


def _ledger(tmp_path):
    registry = RegistrationRegistry(tmp_path / "manager-state.sqlite3")
    return registry, registry.first_registration_ledger()


def test_ledger_uses_registry_database_and_persists_secret_free_schema(tmp_path) -> None:
    registry, ledger = _ledger(tmp_path)
    try:
        attempt = ledger.create_active(
            pairing_id=PAIRING_ID,
            hardware_id_sha256=HARDWARE_SHA256,
            opened_at=NOW,
            expires_at=NOW + timedelta(seconds=1800),
        )
        assert attempt.state is FirstRegistrationAttemptState.ACTIVE
        assert attempt.phase is FirstRegistrationPhase.BOOTSTRAP_ACCEPTED
        assert attempt.cleanup_state is FirstRegistrationCleanupState.NONE

        columns = {
            row["name"]
            for row in registry._connection.execute(
                "PRAGMA table_info(first_registration_attempts)"
            ).fetchall()
        }
        assert columns == {
            "pairing_id",
            "hardware_id_sha256",
            "opened_at",
            "expires_at",
            "state",
            "phase",
            "cleanup_state",
            "node_id",
            "dynsec_prestate_absent",
            "application_key_prestate_absent",
            "application_key_epoch",
            "delivery_digest_sha256",
            "terminal_at",
            "terminal_reason",
        }
        lowered = {column.lower() for column in columns}
        assert "setup_secret" not in lowered
        assert "hardware_id" not in lowered
        assert "source_ip" not in lowered
        assert "mqtt_password" not in lowered
        assert "system_peer_key" not in lowered

        row = registry._connection.execute(
            """
            SELECT hardware_id_sha256
            FROM first_registration_attempts
            WHERE pairing_id = ?
            """,
            (PAIRING_ID,),
        ).fetchone()
        assert row["hardware_id_sha256"] == HARDWARE_SHA256
    finally:
        registry.close()

    with RegistrationRegistry(tmp_path / "manager-state.sqlite3") as reopened:
        persisted = reopened.first_registration_ledger().get(PAIRING_ID)
        assert persisted.hardware_id_sha256 == HARDWARE_SHA256
        assert persisted.expires_at == NOW + timedelta(seconds=1800)


def test_active_pairing_id_is_non_replayable(tmp_path) -> None:
    registry, ledger = _ledger(tmp_path)
    try:
        ledger.create_active(
            pairing_id=PAIRING_ID,
            hardware_id_sha256=HARDWARE_SHA256,
            opened_at=NOW,
            expires_at=NOW + timedelta(seconds=1800),
        )
        with pytest.raises(
            FirstRegistrationLedgerConflict,
            match="pairing_id already exists",
        ):
            ledger.create_active(
                pairing_id=PAIRING_ID,
                hardware_id_sha256=HARDWARE_SHA256,
                opened_at=NOW,
                expires_at=NOW + timedelta(seconds=1800),
            )
    finally:
        registry.close()


def test_bundle_stage_requires_durable_two_part_ownership_proof(tmp_path) -> None:
    registry, ledger = _ledger(tmp_path)
    try:
        ledger.create_active(
            pairing_id=PAIRING_ID,
            hardware_id_sha256=HARDWARE_SHA256,
            opened_at=NOW,
            expires_at=NOW + timedelta(seconds=1800),
        )
        ledger.mark_hello_observed(PAIRING_ID)
        ledger.record_dynsec_prestate(
            PAIRING_ID,
            node_id="node-0001",
            absent=True,
        )
        with pytest.raises(
            FirstRegistrationLedgerConflict,
            match="ownership proof incomplete",
        ):
            ledger.mark_bundle_staged(
                PAIRING_ID,
                node_id="node-0001",
                application_key_epoch=1,
                delivery_digest_sha256=DELIVERY_SHA256,
            )

        ledger.record_application_key_prestate(
            PAIRING_ID,
            node_id="node-0001",
            absent=True,
        )
        staged = ledger.mark_bundle_staged(
            PAIRING_ID,
            node_id="node-0001",
            application_key_epoch=1,
            delivery_digest_sha256=DELIVERY_SHA256,
        )
        assert staged.phase is FirstRegistrationPhase.BUNDLE_STAGED
        assert staged.node_id == "node-0001"
        assert staged.dynsec_prestate_absent is True
        assert staged.application_key_prestate_absent is True
        assert staged.application_key_epoch == 1
        assert staged.delivery_digest_sha256 == DELIVERY_SHA256
    finally:
        registry.close()


def test_committed_requires_durable_committing_claim(tmp_path) -> None:
    registry, ledger = _ledger(tmp_path)
    try:
        ledger.create_active(
            pairing_id=PAIRING_ID,
            hardware_id_sha256=HARDWARE_SHA256,
            opened_at=NOW,
            expires_at=NOW + timedelta(seconds=1800),
        )
        with pytest.raises(
            FirstRegistrationLedgerConflict,
            match="commit claim missing",
        ):
            ledger.mark_committed(
                PAIRING_ID,
                terminal_at=NOW + timedelta(seconds=10),
            )

        ledger.mark_hello_observed(PAIRING_ID)
        ledger.record_dynsec_prestate(
            PAIRING_ID,
            node_id="node-0001",
            absent=True,
        )
        ledger.record_application_key_prestate(
            PAIRING_ID,
            node_id="node-0001",
            absent=True,
        )
        ledger.mark_bundle_staged(
            PAIRING_ID,
            node_id="node-0001",
            application_key_epoch=1,
            delivery_digest_sha256=DELIVERY_SHA256,
        )
        ledger.claim_committing(PAIRING_ID)
        committed = ledger.mark_committed(
            PAIRING_ID,
            terminal_at=NOW + timedelta(seconds=20),
        )
        assert committed.state is FirstRegistrationAttemptState.COMMITTED
        assert committed.phase is FirstRegistrationPhase.TERMINAL
        assert committed.cleanup_state is FirstRegistrationCleanupState.COMPLETE
        assert ledger.list_reconcilable() == ()
    finally:
        registry.close()


def test_restart_invalidated_attempt_stays_reconcilable_until_cleanup_complete(
    tmp_path,
) -> None:
    registry, ledger = _ledger(tmp_path)
    try:
        ledger.create_active(
            pairing_id=PAIRING_ID,
            hardware_id_sha256=HARDWARE_SHA256,
            opened_at=NOW,
            expires_at=NOW + timedelta(seconds=1800),
        )
        terminal = ledger.terminalize_not_committed(
            PAIRING_ID,
            state=FirstRegistrationAttemptState.RESTART_INVALIDATED,
            cleanup_state=FirstRegistrationCleanupState.REQUIRED,
            terminal_at=NOW + timedelta(seconds=30),
            terminal_reason="replay_detected",
        )
        assert terminal.phase is FirstRegistrationPhase.TERMINAL
        assert ledger.list_reconcilable() == (terminal,)

        failed = ledger.mark_cleanup_failed(PAIRING_ID)
        assert failed.cleanup_state is FirstRegistrationCleanupState.FAILED
        assert ledger.list_reconcilable() == (failed,)

        complete = ledger.mark_cleanup_complete(PAIRING_ID)
        assert complete.cleanup_state is FirstRegistrationCleanupState.COMPLETE
        assert ledger.list_reconcilable() == ()
    finally:
        registry.close()


def test_ledger_write_participates_in_existing_registry_transaction(tmp_path) -> None:
    registry, ledger = _ledger(tmp_path)
    try:
        registry._connection.execute("BEGIN IMMEDIATE")
        ledger.create_active(
            pairing_id=PAIRING_ID,
            hardware_id_sha256=HARDWARE_SHA256,
            opened_at=NOW,
            expires_at=NOW + timedelta(seconds=1800),
        )
        registry._connection.rollback()
        with pytest.raises(KeyError):
            ledger.get(PAIRING_ID)
    finally:
        registry.close()


@pytest.mark.parametrize(
    ("pairing_id", "hardware_sha"),
    (
        ("not-a-uuid", HARDWARE_SHA256),
        (PAIRING_ID.upper(), HARDWARE_SHA256),
        (PAIRING_ID, "A" * 64),
    ),
)
def test_ledger_rejects_noncanonical_identity_binding(
    tmp_path,
    pairing_id,
    hardware_sha,
) -> None:
    registry, ledger = _ledger(tmp_path)
    try:
        with pytest.raises(ValueError):
            ledger.create_active(
                pairing_id=pairing_id,
                hardware_id_sha256=hardware_sha,
                opened_at=NOW,
                expires_at=NOW + timedelta(seconds=1800),
            )
    finally:
        registry.close()
