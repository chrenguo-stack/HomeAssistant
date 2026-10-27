from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import pytest

from greenhouse_manager.runtime.n3w_first_registration_ledger import (
    FirstRegistrationAttemptState,
    FirstRegistrationCleanupState,
)
from greenhouse_manager.runtime.n3w_first_registration_reconciliation import (
    FirstRegistrationCommitClassification,
)
from greenhouse_manager.runtime.n3w_first_registration_intent import (
    FirstRegistrationIntentStore,
)
from greenhouse_manager.runtime.n3w_first_registration_transaction import (
    FIRST_REGISTRATION_TTL_SECONDS,
    FirstRegistrationTransactionRejected,
    FirstRegistrationTransactionService,
)
from greenhouse_manager.runtime.registration import RegistrationRegistry

NOW = datetime(2026, 10, 27, 1, 0, tzinfo=UTC)
HARDWARE_ID = "ghw-c6-00000000000a"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
SECRET = bytes(range(32))


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def request() -> dict[str, str]:
    return {
        "manager_id": "manager_lab_01",
        "system_id": "greenhouse",
        "hardware_id": HARDWARE_ID,
        "pairing_id": PAIRING_ID,
        "setup_secret": _b64(SECRET),
    }


class Window:
    def __init__(self, registry: RegistrationRegistry) -> None:
        self.registry = registry
        self.calls = 0
        self.fail = False
        self.deadlines = []

    def open_first_registration(self, intent):
        self.calls += 1
        durable = self.registry.first_registration_ledger().get(
            intent.pairing_id
        )
        assert durable.expires_at == intent.expires_at
        self.deadlines.append(intent.expires_at)
        if self.fail:
            raise RuntimeError("synthetic open failure")
        return {"pairing_host": "192.0.2.1"}


def service(registry, intents, window):
    return FirstRegistrationTransactionService(
        registry=registry,
        intents=intents,
        window=window,
        manager_id="manager_lab_01",
        system_id="greenhouse",
        clock=lambda: NOW,
    )


def test_durable_active_exists_before_window_and_deadline_is_1800(tmp_path) -> None:
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        intents = FirstRegistrationIntentStore()
        window = Window(registry)
        result = service(registry, intents, window).start(
            request(),
            source_ip="192.0.2.44",
        )
        attempt = registry.first_registration_ledger().get(PAIRING_ID)

        assert attempt.opened_at == NOW
        assert (
            attempt.expires_at
            == NOW + timedelta(seconds=FIRST_REGISTRATION_TTL_SECONDS)
        )
        assert result.expires_at == attempt.expires_at
        assert window.calls == 1
        assert intents.current() is not None
        assert intents.current().expires_at == attempt.expires_at


def test_exact_duplicate_reuses_deadline_and_conflicting_secret_is_busy(tmp_path) -> None:
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        intents = FirstRegistrationIntentStore()
        window = Window(registry)
        tx = service(registry, intents, window)

        first = tx.start(request(), source_ip="192.0.2.44")
        second = tx.start(request(), source_ip="192.0.2.44")

        assert first.expires_at == second.expires_at
        assert window.deadlines == [first.expires_at, first.expires_at]

        conflicting = request()
        conflicting["setup_secret"] = _b64(bytes(reversed(range(32))))
        with pytest.raises(
            FirstRegistrationTransactionRejected,
            match="registration_busy",
        ):
            tx.start(
                conflicting,
                source_ip="192.0.2.44",
            )


def test_window_failure_preserves_active_attempt_for_exact_retry(tmp_path) -> None:
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        intents = FirstRegistrationIntentStore()
        window = Window(registry)
        tx = service(registry, intents, window)
        window.fail = True

        with pytest.raises(
            FirstRegistrationTransactionRejected,
            match="bootstrap_unavailable",
        ):
            tx.start(
                request(),
                source_ip="192.0.2.44",
            )

        first = registry.first_registration_ledger().get(PAIRING_ID)
        assert first.state.value == "ACTIVE"
        assert intents.current() is not None

        window.fail = False
        retry = tx.start(
            request(),
            source_ip="192.0.2.44",
        )
        assert retry.expires_at == first.expires_at
        assert window.calls == 2


def test_status_requires_exact_delivery_binding_and_never_opens_window(tmp_path) -> None:
    import hashlib

    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        intents = FirstRegistrationIntentStore()
        window = Window(registry)
        tx = service(registry, intents, window)

        tx.start(request(), source_ip="192.0.2.44")
        ledger = registry.first_registration_ledger()
        ledger.mark_hello_observed(PAIRING_ID)
        ledger.record_dynsec_prestate(
            PAIRING_ID,
            node_id="node_status_01",
            absent=True,
        )
        ledger.record_application_key_prestate(
            PAIRING_ID,
            node_id="node_status_01",
            absent=True,
        )
        digest = bytes([0x44]) * 32
        ledger.mark_bundle_staged(
            PAIRING_ID,
            node_id="node_status_01",
            application_key_epoch=1,
            delivery_digest_sha256=hashlib.sha256(
                digest
            ).hexdigest(),
        )
        before_calls = window.calls

        status = tx.status(
            {
                "manager_id": "manager_lab_01",
                "system_id": "greenhouse",
                "hardware_id": HARDWARE_ID,
                "pairing_id": PAIRING_ID,
                "delivery_digest": _b64(digest),
            },
            source_ip="192.0.2.99",
        )
        wrong = tx.status(
            {
                "manager_id": "manager_lab_01",
                "system_id": "greenhouse",
                "hardware_id": HARDWARE_ID,
                "pairing_id": PAIRING_ID,
                "delivery_digest": _b64(bytes([0x45]) * 32),
            },
            source_ip="192.0.2.99",
        )

        assert status.status == "pending"
        assert status.transaction_disposition == "wait"
        assert wrong.status == "unknown"
        assert wrong.transaction_disposition == "wait"
        assert window.calls == before_calls


class DeadlineReconciler:
    def __init__(self, registry: RegistrationRegistry) -> None:
        self.ledger = registry.first_registration_ledger()
        self.calls = 0

    def reconcile_deadline(self, pairing_id: str, *, now: datetime):
        from types import SimpleNamespace

        self.calls += 1
        self.ledger.terminalize_not_committed(
            pairing_id,
            state=FirstRegistrationAttemptState.EXPIRED,
            cleanup_state=FirstRegistrationCleanupState.REQUIRED,
            terminal_at=now,
            terminal_reason="expired",
        )
        self.ledger.mark_cleanup_complete(pairing_id)
        return SimpleNamespace(
            classification=(
                FirstRegistrationCommitClassification
                .DEFINITELY_NOT_COMMITTED
            )
        )


def test_expired_active_retry_reconciles_before_returning_terminal(tmp_path) -> None:
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        intents = FirstRegistrationIntentStore()
        window = Window(registry)
        start = FirstRegistrationTransactionService(
            registry=registry,
            intents=intents,
            window=window,
            manager_id="manager_lab_01",
            system_id="greenhouse",
            clock=lambda: NOW,
        )
        window.fail = True

        with pytest.raises(
            FirstRegistrationTransactionRejected,
            match="bootstrap_unavailable",
        ):
            start.start(
                request(),
                source_ip="192.0.2.44",
            )

        reconciler = DeadlineReconciler(registry)
        expired = FirstRegistrationTransactionService(
            registry=registry,
            intents=intents,
            window=window,
            manager_id="manager_lab_01",
            system_id="greenhouse",
            clock=lambda: NOW + timedelta(seconds=1800),
            reconciler=reconciler,
        )

        with pytest.raises(
            FirstRegistrationTransactionRejected,
            match="expired",
        ):
            expired.start(
                request(),
                source_ip="192.0.2.44",
            )

        attempt = registry.first_registration_ledger().get(PAIRING_ID)
        assert reconciler.calls == 1
        assert attempt.state is FirstRegistrationAttemptState.EXPIRED
        assert (
            attempt.cleanup_state
            is FirstRegistrationCleanupState.COMPLETE
        )
        assert intents.current() is None
