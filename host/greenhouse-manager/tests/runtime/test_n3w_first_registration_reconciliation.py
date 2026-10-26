from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.runtime.credential_lifecycle import CredentialLifecycleStore
from greenhouse_manager.runtime.dynsec_api import DynsecError, DynsecProvisioner
from greenhouse_manager.runtime.dynsec_plan import NodeCredentials, build_node_provisioning_plan
from greenhouse_manager.runtime.n3w_first_registration_ledger import (
    FirstRegistrationAttemptState,
    FirstRegistrationCleanupState,
)
from greenhouse_manager.runtime.n3w_first_registration_reconciliation import (
    FirstRegistrationCommitClassification,
    FirstRegistrationReconciler,
    FirstRegistrationReconciliationError,
)
from greenhouse_manager.runtime.n3w_node_application_keys import SqliteNodeApplicationKeyAdmin
from greenhouse_manager.runtime.registration import RegistrationRegistry, RegistrationState


NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
HARDWARE_ID = "ghw-c6-98a316a9f2f8"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
NODE_ID = "gh-n1-a9f2f8"
SYSTEM_ID = "greenhouse"


def _hello() -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": PAIRING_ID,
        "pairing_epoch": 1,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "F1.0-RC2-N2.0",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials", "lcd-pairing-qr"],
        "sent_at_ms": 120345,
    }


class FakeDynsecTransport:
    def __init__(self) -> None:
        self.client: dict[str, Any] | None = None
        self.role: dict[str, Any] | None = None
        self.calls: list[str] = []

    def execute(
        self,
        commands: tuple[dict[str, Any], ...],
    ) -> tuple[dict[str, Any], ...]:
        responses: list[dict[str, Any]] = []
        for command in commands:
            name = str(command["command"])
            self.calls.append(name)

            if name == "createRole":
                if self.role is not None:
                    raise DynsecError("role exists")
                self.role = {
                    "rolename": command["rolename"],
                    "acls": list(command["acls"]),
                }
                responses.append({"command": name})
                continue

            if name == "createClient":
                if self.client is not None:
                    raise DynsecError("client exists")
                self.client = {
                    "username": command["username"],
                    "clientid": command["clientid"],
                    "roles": list(command["roles"]),
                }
                responses.append({"command": name})
                continue

            if name == "deleteClient":
                self.client = None
                responses.append({"command": name})
                continue

            if name == "deleteRole":
                self.role = None
                responses.append({"command": name})
                continue

            if name == "listClients":
                values: list[object] = []
                if self.client is not None:
                    values.append(self.client["username"])
                responses.append(
                    {
                        "command": name,
                        "data": {"clients": values},
                    }
                )
                continue

            if name == "listRoles":
                values = []
                if self.role is not None:
                    values.append(self.role["rolename"])
                responses.append(
                    {
                        "command": name,
                        "data": {"roles": values},
                    }
                )
                continue

            if name == "getClient":
                if self.client is None:
                    raise DynsecError("client missing")
                responses.append(
                    {
                        "command": name,
                        "data": dict(self.client),
                    }
                )
                continue

            if name == "getRole":
                if self.role is None:
                    raise DynsecError("role missing")
                responses.append(
                    {
                        "command": name,
                        "data": dict(self.role),
                    }
                )
                continue

            raise AssertionError(name)

        return tuple(responses)


class Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.registration = RegistrationRegistry(
            tmp_path / "registration.sqlite3",
            pending_ttl_s=120,
        )
        self.credentials = CredentialLifecycleStore(
            tmp_path / "credentials.sqlite3"
        )
        key_dir = tmp_path / "keys"
        key_dir.mkdir(mode=0o700)
        self.keys = SqliteNodeApplicationKeyAdmin(
            tmp_path / "application-keys.sqlite3",
            key_dir,
            node_state=self.registration.node_id_lease_state,
        )
        self.transport = FakeDynsecTransport()
        self.dynsec = DynsecProvisioner(self.transport)
        self.reconciler = FirstRegistrationReconciler(
            registry=self.registration,
            credential_store=self.credentials,
            application_keys=self.keys,
            dynsec=self.dynsec,
            system_id=SYSTEM_ID,
        )

    def close(self) -> None:
        self.keys.close()
        self.credentials.close()
        self.registration.close()

    def open_attempt(self) -> None:
        self.registration.first_registration_ledger().create_active(
            pairing_id=PAIRING_ID,
            hardware_id_sha256=hashlib.sha256(
                HARDWARE_ID.encode("utf-8")
            ).hexdigest(),
            opened_at=NOW,
            expires_at=NOW + timedelta(seconds=1800),
        )

    def observe_and_approve(self) -> None:
        self.registration.observe_hello(
            _hello(),
            now=NOW + timedelta(seconds=1),
        )
        ledger = self.registration.first_registration_ledger()
        ledger.mark_hello_observed(PAIRING_ID)
        self.registration.approve(
            HARDWARE_ID,
            PAIRING_ID,
            node_id=NODE_ID,
            now=NOW + timedelta(seconds=2),
        )

    def stage_bundle(self) -> int:
        ledger = self.registration.first_registration_ledger()
        ledger.record_dynsec_prestate(
            PAIRING_ID,
            node_id=NODE_ID,
            absent=True,
        )
        plan = build_node_provisioning_plan(
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            generation=1,
        )
        self.dynsec.provision(
            plan,
            NodeCredentials(
                username=plan.username,
                client_id=plan.client_id,
                generation=1,
                password="secret",
            ),
        )
        ledger.record_application_key_prestate(
            PAIRING_ID,
            node_id=NODE_ID,
            absent=True,
        )
        result = self.keys.stage_key(
            node_id=NODE_ID,
            key_material=bytes(range(32)),
        )
        epoch = int(result["key_epoch"])
        ledger.mark_bundle_staged(
            PAIRING_ID,
            node_id=NODE_ID,
            application_key_epoch=epoch,
            delivery_digest_sha256="a" * 64,
        )
        return epoch


@pytest.fixture
def harness(tmp_path: Path):
    instance = Harness(tmp_path)
    yield instance
    instance.close()


def test_restart_before_hello_terminalizes_ledger_only(
    harness: Harness,
) -> None:
    harness.open_attempt()
    attempt = harness.registration.first_registration_ledger().get(
        PAIRING_ID
    )

    result = harness.reconciler.reconcile_attempt(
        attempt,
        now=NOW + timedelta(seconds=10),
    )

    assert (
        result.classification
        is FirstRegistrationCommitClassification.DEFINITELY_NOT_COMMITTED
    )
    assert (
        result.state
        is FirstRegistrationAttemptState.RESTART_INVALIDATED
    )
    assert (
        result.cleanup_state
        is FirstRegistrationCleanupState.COMPLETE
    )
    assert harness.registration.get_by_pairing_id(PAIRING_ID) is None


def test_committing_exact_cross_store_state_recovers_committed(
    harness: Harness,
) -> None:
    harness.open_attempt()
    harness.observe_and_approve()
    epoch = harness.stage_bundle()
    ledger = harness.registration.first_registration_ledger()
    ledger.claim_committing(PAIRING_ID)
    harness.keys.activate_key(
        node_id=NODE_ID,
        key_epoch=epoch,
    )
    harness.credentials.activate(
        hardware_id=HARDWARE_ID,
        pairing_id=PAIRING_ID,
        node_id=NODE_ID,
        generation=1,
        now=NOW + timedelta(seconds=5),
    )

    result = harness.reconciler.reconcile_attempt(
        ledger.get(PAIRING_ID),
        now=NOW + timedelta(seconds=6),
    )

    assert (
        result.classification
        is FirstRegistrationCommitClassification.COMMITTED
    )
    assert result.state is FirstRegistrationAttemptState.COMMITTED
    assert result.cleanup_state is FirstRegistrationCleanupState.COMPLETE
    assert harness.transport.client is not None
    assert harness.transport.role is not None


def test_bundle_staged_without_mqtt_commit_is_cleaned_exactly(
    harness: Harness,
) -> None:
    harness.open_attempt()
    harness.observe_and_approve()
    epoch = harness.stage_bundle()
    ledger = harness.registration.first_registration_ledger()

    result = harness.reconciler.reconcile_attempt(
        ledger.get(PAIRING_ID),
        now=NOW + timedelta(seconds=20),
    )

    assert (
        result.classification
        is FirstRegistrationCommitClassification.DEFINITELY_NOT_COMMITTED
    )
    assert result.cleanup_state is FirstRegistrationCleanupState.COMPLETE
    assert harness.transport.client is None
    assert harness.transport.role is None
    snapshot = harness.keys.snapshot_node(
        node_id=NODE_ID,
        key_epoch=epoch,
    )
    assert snapshot.requested_state == "REVOKED"

    registration = harness.registration.get_by_pairing_id(PAIRING_ID)
    assert registration is not None
    assert registration.current_pairing_id is None
    assert registration.state is RegistrationState.REJECTED
    assert registration.reason == "replay_detected"
    assert harness.registration.node_id_lease_state(NODE_ID).value == "retired"


def test_pre_stage_target_presence_is_unknown_and_not_deleted(
    harness: Harness,
) -> None:
    harness.open_attempt()
    harness.observe_and_approve()
    ledger = harness.registration.first_registration_ledger()
    ledger.record_dynsec_prestate(
        PAIRING_ID,
        node_id=NODE_ID,
        absent=True,
    )
    plan = build_node_provisioning_plan(
        system_id=SYSTEM_ID,
        node_id=NODE_ID,
        generation=1,
    )
    harness.dynsec.provision(
        plan,
        NodeCredentials(
            username=plan.username,
            client_id=plan.client_id,
            generation=1,
            password="secret",
        ),
    )

    result = harness.reconciler.reconcile_attempt(
        ledger.get(PAIRING_ID),
        now=NOW + timedelta(seconds=20),
    )

    assert (
        result.classification
        is FirstRegistrationCommitClassification.UNKNOWN
    )
    assert result.cleanup_state is FirstRegistrationCleanupState.FAILED
    assert harness.transport.client is not None
    assert harness.transport.role is not None


def test_required_reentry_resumes_cleanup_without_reclassification(
    harness: Harness,
) -> None:
    harness.open_attempt()
    harness.observe_and_approve()
    epoch = harness.stage_bundle()
    ledger = harness.registration.first_registration_ledger()
    terminal = ledger.terminalize_not_committed(
        PAIRING_ID,
        state=FirstRegistrationAttemptState.RESTART_INVALIDATED,
        cleanup_state=FirstRegistrationCleanupState.REQUIRED,
        terminal_at=NOW + timedelta(seconds=20),
        terminal_reason="replay_detected",
    )

    harness.dynsec.deprovision(
        build_node_provisioning_plan(
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            generation=1,
        )
    )
    harness.keys.revoke_key(
        node_id=NODE_ID,
        key_epoch=epoch,
    )
    before = list(harness.transport.calls)

    result = harness.reconciler.reconcile_attempt(
        terminal,
        now=NOW + timedelta(seconds=30),
    )

    assert (
        result.classification
        is FirstRegistrationCommitClassification.DEFINITELY_NOT_COMMITTED
    )
    assert result.cleanup_state is FirstRegistrationCleanupState.COMPLETE
    assert "getClient" not in harness.transport.calls[len(before):]
    assert "getRole" not in harness.transport.calls[len(before):]


def test_required_cleanup_rejects_drifted_dynsec_target_without_deleting(
    harness: Harness,
) -> None:
    harness.open_attempt()
    harness.observe_and_approve()
    harness.stage_bundle()
    ledger = harness.registration.first_registration_ledger()
    terminal = ledger.terminalize_not_committed(
        PAIRING_ID,
        state=FirstRegistrationAttemptState.RESTART_INVALIDATED,
        cleanup_state=FirstRegistrationCleanupState.REQUIRED,
        terminal_at=NOW + timedelta(seconds=20),
        terminal_reason="replay_detected",
    )

    assert harness.transport.client is not None
    harness.transport.client["clientid"] = "externally-drifted"

    with pytest.raises(
        FirstRegistrationReconciliationError,
        match="first-registration cleanup failed",
    ):
        harness.reconciler.reconcile_attempt(
            terminal,
            now=NOW + timedelta(seconds=30),
        )

    assert harness.transport.client is not None
    assert harness.transport.role is not None
    failed = ledger.get(PAIRING_ID)
    assert failed.cleanup_state is FirstRegistrationCleanupState.FAILED


def test_required_reentry_finishes_revoked_key_file_cleanup(
    harness: Harness,
) -> None:
    harness.open_attempt()
    harness.observe_and_approve()
    epoch = harness.stage_bundle()
    ledger = harness.registration.first_registration_ledger()
    terminal = ledger.terminalize_not_committed(
        PAIRING_ID,
        state=FirstRegistrationAttemptState.RESTART_INVALIDATED,
        cleanup_state=FirstRegistrationCleanupState.REQUIRED,
        terminal_at=NOW + timedelta(seconds=20),
        terminal_reason="replay_detected",
    )

    with sqlite3.connect(harness.keys.database) as connection:
        connection.execute(
            """
            UPDATE n3w_relay_key_epochs
            SET state='REVOKED',enabled=0
            WHERE node_id=? AND key_epoch=?
            """,
            (NODE_ID, epoch),
        )

    assert list(harness.keys.key_dir.glob("*.key"))

    result = harness.reconciler.reconcile_attempt(
        terminal,
        now=NOW + timedelta(seconds=30),
    )

    assert result.cleanup_state is FirstRegistrationCleanupState.COMPLETE
    assert list(harness.keys.key_dir.glob("*.key")) == []


def test_registration_cleanup_missing_history_fails_atomically(
    harness: Harness,
) -> None:
    harness.open_attempt()
    harness.observe_and_approve()
    ledger = harness.registration.first_registration_ledger()

    harness.registration._connection.execute(
        """
        DELETE FROM registration_node_history
        WHERE hardware_id=? AND node_id=?
        """,
        (HARDWARE_ID, NODE_ID),
    )
    harness.registration._connection.commit()

    with pytest.raises(
        FirstRegistrationReconciliationError,
        match="first-registration cleanup failed",
    ):
        harness.reconciler.reconcile_attempt(
            ledger.get(PAIRING_ID),
            now=NOW + timedelta(seconds=20),
        )

    current = harness.registration.get(HARDWARE_ID)
    assert current.pairing_id == PAIRING_ID
    assert current.state is RegistrationState.APPROVED
    assert current.node_id == NODE_ID
    assert harness.registration.node_id_lease_state(NODE_ID).value == "active"
    failed = ledger.get(PAIRING_ID)
    assert failed.cleanup_state is FirstRegistrationCleanupState.FAILED


def test_dynsec_plan_inspector_rejects_client_binding_drift(
    harness: Harness,
) -> None:
    plan = build_node_provisioning_plan(
        system_id=SYSTEM_ID,
        node_id=NODE_ID,
        generation=1,
    )
    harness.dynsec.provision(
        plan,
        NodeCredentials(
            username=plan.username,
            client_id=plan.client_id,
            generation=1,
            password="secret",
        ),
    )
    assert harness.dynsec.inspect_plan(plan).exact_match is True

    assert harness.transport.client is not None
    harness.transport.client["clientid"] = "wrong-client"

    inspection = harness.dynsec.inspect_plan(plan)
    assert inspection.client_present is True
    assert inspection.client_matches is False
    assert inspection.exact_match is False
