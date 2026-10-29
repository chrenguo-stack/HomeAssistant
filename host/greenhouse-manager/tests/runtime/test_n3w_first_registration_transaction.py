from __future__ import annotations

import base64
import threading
from datetime import UTC, datetime, timedelta

import pytest

from greenhouse_manager.runtime.n3w_first_registration_intent import (
    FirstRegistrationIntentStore,
)
from greenhouse_manager.runtime.n3w_first_registration_ledger import (
    FirstRegistrationAttemptState,
    FirstRegistrationCleanupState,
)
from greenhouse_manager.runtime.n3w_first_registration_reconciliation import (
    FirstRegistrationCommitClassification,
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


class ManualDeadlineTimer:
    def __init__(self, delay_seconds, callback) -> None:
        self.delay_seconds = delay_seconds
        self.callback = callback
        self.started = False
        self.cancelled = False

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True

    def fire(self) -> None:
        if self.started and not self.cancelled:
            self.callback()


class ManualDeadlineTimerFactory:
    def __init__(self) -> None:
        self.timers = []

    def __call__(self, delay_seconds, callback):
        timer = ManualDeadlineTimer(delay_seconds, callback)
        self.timers.append(timer)
        return timer


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class RejectingIntentStore(FirstRegistrationIntentStore):
    def activate(self, intent):
        raise RuntimeError("synthetic intent activation failure")


def service(registry, intents, window, **kwargs):
    kwargs.setdefault(
        "deadline_timer_factory",
        ManualDeadlineTimerFactory(),
    )
    return FirstRegistrationTransactionService(
        registry=registry,
        intents=intents,
        window=window,
        manager_id="manager_lab_01",
        system_id="greenhouse",
        clock=lambda: NOW,
        **kwargs,
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
        ) as secret_busy:
            tx.start(
                conflicting,
                source_ip="192.0.2.44",
            )
        assert (
            secret_busy.value.detail
            == "active_intent_setup_secret_mismatch"
        )

        with pytest.raises(
            FirstRegistrationTransactionRejected,
            match="registration_busy",
        ) as source_busy:
            tx.start(
                request(),
                source_ip="192.0.2.45",
            )
        assert (
            source_busy.value.detail
            == "active_intent_source_ip_mismatch"
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


class FlakyDeadlineReconciler(DeadlineReconciler):
    def __init__(self, registry: RegistrationRegistry) -> None:
        super().__init__(registry)
        self.failures_remaining = 1

    def reconcile_deadline(self, pairing_id: str, *, now: datetime):
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            self.calls += 1
            raise RuntimeError("synthetic deadline reconcile failure")
        return super().reconcile_deadline(pairing_id, now=now)


class FailingWindowCloseReconciler(DeadlineReconciler):
    def __init__(self, registry: RegistrationRegistry) -> None:
        super().__init__(registry)
        self.attempt_calls = 0

    def reconcile_attempt(self, attempt, *, now: datetime):
        self.attempt_calls += 1
        raise RuntimeError("synthetic window-close reconcile failure")


class BlockingWindow(Window):
    def __init__(self, registry: RegistrationRegistry) -> None:
        super().__init__(registry)
        self.entered = threading.Event()
        self.release = threading.Event()
        self._lock = threading.Lock()
        self.inflight = 0
        self.max_inflight = 0

    def open_first_registration(self, intent):
        with self._lock:
            self.inflight += 1
            self.max_inflight = max(
                self.max_inflight,
                self.inflight,
            )
        self.entered.set()
        assert self.release.wait(2.0)
        try:
            return super().open_first_registration(intent)
        finally:
            with self._lock:
                self.inflight -= 1


def test_concurrent_exact_confirms_are_serialized(tmp_path) -> None:
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        intents = FirstRegistrationIntentStore()
        window = BlockingWindow(registry)
        tx = service(registry, intents, window)
        results = []
        errors = []

        def run_confirm() -> None:
            try:
                results.append(
                    tx.start(
                        request(),
                        source_ip="192.0.2.44",
                    )
                )
            except Exception as error:
                errors.append(error)

        first = threading.Thread(target=run_confirm)
        second = threading.Thread(target=run_confirm)
        first.start()
        assert window.entered.wait(1.0)
        second.start()
        window.release.set()
        first.join(2.0)
        second.join(2.0)

        assert not first.is_alive()
        assert not second.is_alive()
        assert errors == []
        assert len(results) == 2
        assert results[0].expires_at == results[1].expires_at
        assert window.max_inflight == 1
        assert window.calls == 2


def test_successful_window_handoff_cancels_prewindow_deadline(tmp_path) -> None:
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        intents = FirstRegistrationIntentStore()
        window = Window(registry)
        timers = ManualDeadlineTimerFactory()
        tx = FirstRegistrationTransactionService(
            registry=registry,
            intents=intents,
            window=window,
            manager_id="manager_lab_01",
            system_id="greenhouse",
            clock=lambda: NOW,
            deadline_timer_factory=timers,
        )

        tx.start(
            request(),
            source_ip="192.0.2.44",
        )

        assert len(timers.timers) == 1
        assert timers.timers[0].started is True
        assert timers.timers[0].cancelled is True
        assert (
            timers.timers[0].delay_seconds
            == FIRST_REGISTRATION_TTL_SECONDS
        )


def test_intent_activation_failure_still_has_deadline_owner(tmp_path) -> None:
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        intents = RejectingIntentStore()
        window = Window(registry)
        timers = ManualDeadlineTimerFactory()
        clock = MutableClock(NOW)
        reconciler = DeadlineReconciler(registry)
        tx = FirstRegistrationTransactionService(
            registry=registry,
            intents=intents,
            window=window,
            manager_id="manager_lab_01",
            system_id="greenhouse",
            clock=clock,
            reconciler=reconciler,
            deadline_timer_factory=timers,
        )

        with pytest.raises(
            FirstRegistrationTransactionRejected,
            match="bootstrap_unavailable",
        ) as rejected:
            tx.start(
                request(),
                source_ip="192.0.2.44",
            )

        assert rejected.value.detail == "intent_activation_unavailable"
        active = registry.first_registration_ledger().get(PAIRING_ID)
        assert active.state is FirstRegistrationAttemptState.ACTIVE
        assert len(timers.timers) == 1
        assert timers.timers[0].started is True
        assert timers.timers[0].cancelled is False

        clock.now = NOW + timedelta(
            seconds=FIRST_REGISTRATION_TTL_SECONDS
        )
        timers.timers[0].fire()

        expired = registry.first_registration_ledger().get(PAIRING_ID)
        assert expired.state is FirstRegistrationAttemptState.EXPIRED
        assert (
            expired.cleanup_state
            is FirstRegistrationCleanupState.COMPLETE
        )


def test_deadline_reconcile_failure_rearms_bounded_retry(tmp_path) -> None:
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        intents = FirstRegistrationIntentStore()
        window = Window(registry)
        window.fail = True
        timers = ManualDeadlineTimerFactory()
        clock = MutableClock(NOW)
        reconciler = FlakyDeadlineReconciler(registry)
        tx = FirstRegistrationTransactionService(
            registry=registry,
            intents=intents,
            window=window,
            manager_id="manager_lab_01",
            system_id="greenhouse",
            clock=clock,
            reconciler=reconciler,
            deadline_timer_factory=timers,
        )

        with pytest.raises(
            FirstRegistrationTransactionRejected,
            match="bootstrap_unavailable",
        ):
            tx.start(
                request(),
                source_ip="192.0.2.44",
            )

        clock.now = NOW + timedelta(
            seconds=FIRST_REGISTRATION_TTL_SECONDS
        )
        timers.timers[0].fire()

        still_active = registry.first_registration_ledger().get(PAIRING_ID)
        assert still_active.state is FirstRegistrationAttemptState.ACTIVE
        assert reconciler.calls == 1
        assert len(timers.timers) == 2
        assert timers.timers[1].started is True
        assert timers.timers[1].cancelled is False
        assert timers.timers[1].delay_seconds == 5.0

        timers.timers[1].fire()

        expired = registry.first_registration_ledger().get(PAIRING_ID)
        assert reconciler.calls == 2
        assert expired.state is FirstRegistrationAttemptState.EXPIRED
        assert (
            expired.cleanup_state
            is FirstRegistrationCleanupState.COMPLETE
        )
        assert len(timers.timers) == 2


def test_window_close_reconcile_failure_restores_deadline_owner(tmp_path) -> None:
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        intents = FirstRegistrationIntentStore()
        window = Window(registry)
        timers = ManualDeadlineTimerFactory()
        reconciler = FailingWindowCloseReconciler(registry)
        tx = FirstRegistrationTransactionService(
            registry=registry,
            intents=intents,
            window=window,
            manager_id="manager_lab_01",
            system_id="greenhouse",
            clock=lambda: NOW,
            reconciler=reconciler,
            deadline_timer_factory=timers,
        )

        tx.start(
            request(),
            source_ip="192.0.2.44",
        )
        assert len(timers.timers) == 1
        assert timers.timers[0].cancelled is True

        tx.window_closed(
            PAIRING_ID,
            "worker_failure",
        )

        active = registry.first_registration_ledger().get(PAIRING_ID)
        assert active.state is FirstRegistrationAttemptState.ACTIVE
        assert reconciler.attempt_calls == 1
        assert len(timers.timers) == 2
        assert timers.timers[1].started is True
        assert timers.timers[1].cancelled is False
        assert (
            timers.timers[1].delay_seconds
            == FIRST_REGISTRATION_TTL_SECONDS
        )


def test_window_failure_deadline_expires_without_followup_request(tmp_path) -> None:
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        intents = FirstRegistrationIntentStore()
        window = Window(registry)
        window.fail = True
        timers = ManualDeadlineTimerFactory()
        clock = MutableClock(NOW)
        reconciler = DeadlineReconciler(registry)
        tx = FirstRegistrationTransactionService(
            registry=registry,
            intents=intents,
            window=window,
            manager_id="manager_lab_01",
            system_id="greenhouse",
            clock=clock,
            reconciler=reconciler,
            deadline_timer_factory=timers,
        )

        with pytest.raises(
            FirstRegistrationTransactionRejected,
            match="bootstrap_unavailable",
        ):
            tx.start(
                request(),
                source_ip="192.0.2.44",
            )

        active = registry.first_registration_ledger().get(PAIRING_ID)
        assert active.state is FirstRegistrationAttemptState.ACTIVE
        assert len(timers.timers) == 1
        assert timers.timers[0].cancelled is False

        clock.now = NOW + timedelta(
            seconds=FIRST_REGISTRATION_TTL_SECONDS
        )
        timers.timers[0].fire()

        expired = registry.first_registration_ledger().get(PAIRING_ID)
        assert reconciler.calls == 1
        assert expired.state is FirstRegistrationAttemptState.EXPIRED
        assert (
            expired.cleanup_state
            is FirstRegistrationCleanupState.COMPLETE
        )
        assert intents.current() is None


def test_exact_retry_after_window_failure_keeps_original_deadline_owner(
    tmp_path,
) -> None:
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        intents = FirstRegistrationIntentStore()
        window = Window(registry)
        window.fail = True
        timers = ManualDeadlineTimerFactory()
        tx = FirstRegistrationTransactionService(
            registry=registry,
            intents=intents,
            window=window,
            manager_id="manager_lab_01",
            system_id="greenhouse",
            clock=lambda: NOW,
            deadline_timer_factory=timers,
        )

        with pytest.raises(
            FirstRegistrationTransactionRejected,
            match="bootstrap_unavailable",
        ):
            tx.start(
                request(),
                source_ip="192.0.2.44",
            )
        assert len(timers.timers) == 1

        window.fail = False
        retry = tx.start(
            request(),
            source_ip="192.0.2.44",
        )

        assert retry.expires_at == (
            NOW + timedelta(
                seconds=FIRST_REGISTRATION_TTL_SECONDS
            )
        )
        assert len(timers.timers) == 1
        assert timers.timers[0].cancelled is True


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
