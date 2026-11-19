from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from n3w_t1_core_updater_ha_u13b import U13BRollbackResult
import n3w_t1_core_updater_ha_u13b_auto as auto
from n3w_t1_core_updater_ha_u13b_auto import (
    U13BAutomaticRollbackCoordinator,
    U9PlusBoundedRecoveryCoordinator,
    U9PlusRecoveryCompletionEvidence,
)
from n3w_t1_core_updater_ha_u13b_reconcile import (
    ALREADY_EXACT,
    RECONCILED,
    U13BHostOnlyReconciliationResult,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error


def reconciliation(status):
    return U13BHostOnlyReconciliationResult(
        status=status,
        transaction={"phase": "successor"},
        previous_phase="old",
        current_phase="successor",
        host_write_performed=status == RECONCILED,
    )


class Writer:
    def __init__(
        self,
        events,
        *,
        result=None,
        error=None,
        transaction_store=None,
        backend=None,
    ):
        self.events = events
        self.result = result
        self.error = error
        self.calls = 0
        self.transaction_store = transaction_store
        self.backend = backend

    def reconcile(self):
        self.calls += 1
        self.events.append("reconcile")
        if self.error is not None:
            raise self.error
        return self.result


class Controller:
    def __init__(
        self,
        events,
        *,
        result=None,
        error=None,
        transaction_store=None,
        backend=None,
    ):
        self.events = events
        self.transaction_store = transaction_store
        self.backend = backend
        self.result = result or U13BRollbackResult(
            transaction={"phase": "U13B_ROLLED_BACK"},
            initial_phase="successor",
            completed=True,
        )
        self.error = error
        self.calls = []

    def rollback(self, *, failure_code):
        self.events.append("rollback")
        self.calls.append(failure_code)
        if self.error is not None:
            raise self.error
        return self.result


def bound_pair(events, *, writer_result=None, writer_error=None, controller_error=None):
    store = object()
    backend = object()
    return (
        Writer(
            events,
            result=writer_result,
            error=writer_error,
            transaction_store=store,
            backend=backend,
        ),
        Controller(
            events,
            error=controller_error,
            transaction_store=store,
            backend=backend,
        ),
    )


@pytest.mark.parametrize("status", [ALREADY_EXACT, RECONCILED])
def test_d4_reconciles_before_normal_rollback(status):
    events = []
    writer, controller = bound_pair(
        events, writer_result=reconciliation(status)
    )
    result = U13BAutomaticRollbackCoordinator(
        reconciliation_writer=writer,
        rollback_controller=controller,
    ).rollback(failure_code="target_health_acceptance_failed")

    assert events == ["reconcile", "rollback"]
    assert writer.calls == 1
    assert controller.calls == ["target_health_acceptance_failed"]
    assert result.reconciliation.status == status
    assert result.rollback.completed is True


def test_d4_reconciliation_failure_blocks_all_rollback_operations():
    events = []
    writer, controller = bound_pair(
        events,
        writer_error=UpdaterV2Error(
            "u13b_reconciliation_divergent_stop"
        ),
    )

    with pytest.raises(
        UpdaterV2Error,
        match="u13b_reconciliation_divergent_stop",
    ):
        U13BAutomaticRollbackCoordinator(
            reconciliation_writer=writer,
            rollback_controller=controller,
        ).rollback(failure_code="resume")

    assert events == ["reconcile"]
    assert controller.calls == []


def test_d4_does_not_hide_normal_controller_revalidation_failure():
    events = []
    writer, controller = bound_pair(
        events,
        writer_result=reconciliation(RECONCILED),
        controller_error=UpdaterV2Error(
            "u13b_host_usb_reconciliation_stop"
        ),
    )

    with pytest.raises(
        UpdaterV2Error,
        match="u13b_host_usb_reconciliation_stop",
    ):
        U13BAutomaticRollbackCoordinator(
            reconciliation_writer=writer,
            rollback_controller=controller,
        ).rollback(failure_code="resume")

    assert events == ["reconcile", "rollback"]


def test_d4_rejects_unknown_reconciliation_result_before_controller():
    events = []
    writer, controller = bound_pair(
        events, writer_result=reconciliation("UNKNOWN")
    )

    with pytest.raises(
        UpdaterV2Error,
        match="u13b_automatic_reconciliation_result_invalid",
    ):
        U13BAutomaticRollbackCoordinator(
            reconciliation_writer=writer,
            rollback_controller=controller,
        ).rollback(failure_code="resume")

    assert events == ["reconcile"]
    assert controller.calls == []



def test_d4_rejects_mismatched_transaction_store_binding():
    events = []
    backend = object()
    writer = Writer(
        events,
        result=reconciliation(ALREADY_EXACT),
        transaction_store=object(),
        backend=backend,
    )
    controller = Controller(
        events,
        transaction_store=object(),
        backend=backend,
    )
    with pytest.raises(
        UpdaterV2Error,
        match="u13b_automatic_transaction_store_binding_invalid",
    ):
        U13BAutomaticRollbackCoordinator(
            reconciliation_writer=writer,
            rollback_controller=controller,
        )


def test_d4_rejects_mismatched_backend_binding():
    events = []
    store = object()
    writer = Writer(
        events,
        result=reconciliation(ALREADY_EXACT),
        transaction_store=store,
        backend=object(),
    )
    controller = Controller(
        events,
        transaction_store=store,
        backend=object(),
    )
    with pytest.raises(
        UpdaterV2Error,
        match="u13b_automatic_backend_binding_invalid",
    ):
        U13BAutomaticRollbackCoordinator(
            reconciliation_writer=writer,
            rollback_controller=controller,
        )



class RecoveryStore:
    def __init__(self, phase):
        self.document = {
            "phase": phase,
            "authorization_id_sha256": "a" * 64,
            "authorization_claimed": True,
            "authorization_consumed": True,
        }

    def read(self):
        return dict(self.document)


class RecoveryRollback:
    def __init__(self, store):
        self.transaction_store = store
        self.backend = object()
        self.calls = []
        self.rollback_controller = self

    def rollback(self, *, failure_code):
        self.calls.append(failure_code)
        self.transaction_store.document["phase"] = "U13B_ROLLED_BACK"
        return object()


class RecoveryOracle:
    def __init__(self, *, fresh=True):
        self.calls = []
        self.fresh = fresh

    def verify(self, transaction, *, recovery_started_unix):
        self.calls.append((dict(transaction), recovery_started_unix))
        return U9PlusRecoveryCompletionEvidence(
            predecessor_runtime_healthy=True,
            homeassistant_http_ready=True,
            manager_ready=True,
            broker_ready=True,
            fresh_greenhouse_telemetry_visible=self.fresh,
            preupgrade_history_readable=True,
            host_usb_terminal_exact=True,
            authorization_replay_absent=True,
        )


def _recovery_coordinator(monkeypatch, phase, *, rollback=None, oracle=None):
    store = RecoveryStore(phase)
    monkeypatch.setattr(
        auto,
        "validate_transaction_document",
        lambda document: dict(document),
    )
    rollback = rollback or RecoveryRollback(store)
    oracle = oracle or RecoveryOracle()
    coordinator = U9PlusBoundedRecoveryCoordinator(
        transaction_store=store,
        rollback_coordinator=rollback,
        completion_oracle=oracle,
        clock=lambda: 1234.0,
    )
    return coordinator, store, rollback, oracle


def test_u9_plus_restart_conservatively_rolls_back_without_reclaiming_authorization(
    monkeypatch,
):
    coordinator, store, rollback, oracle = _recovery_coordinator(
        monkeypatch,
        "U9_LIVE_AUTHORIZATION_CLAIMED",
    )

    result = coordinator.recover_once()

    assert result == {"phase": "ROLLED_BACK", "error_code": None}
    assert store.document["phase"] == "U13B_ROLLED_BACK"
    assert store.document["authorization_claimed"] is True
    assert store.document["authorization_consumed"] is True
    assert rollback.calls == ["u9_plus_restart_bounded_recovery"]
    assert oracle.calls[0][1] == 1234


def test_u9_plus_missing_bound_media_is_recoverable_and_never_substituted(
    monkeypatch,
):
    coordinator, _store, rollback, oracle = _recovery_coordinator(
        monkeypatch,
        "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED",
    )

    def missing(*, failure_code):
        rollback.calls.append(failure_code)
        raise UpdaterV2Error("usb_transaction_media_unavailable")

    rollback.rollback = missing

    result = coordinator.recover_once()

    assert result == {
        "phase": "RECOVERY_MEDIA_REQUIRED",
        "error_code": None,
    }
    assert rollback.calls == ["u9_plus_restart_bounded_recovery"]
    assert oracle.calls == []


def test_u9_plus_existing_terminal_requires_customer_oracle(monkeypatch):
    oracle = RecoveryOracle(fresh=False)
    coordinator, _store, rollback, _ = _recovery_coordinator(
        monkeypatch,
        "U13B_ROLLED_BACK",
        oracle=oracle,
    )

    with pytest.raises(
        UpdaterV2Error,
        match="u9_plus_recovery_customer_oracle_incomplete",
    ):
        coordinator.recover_once()

    assert rollback.calls == []
    assert coordinator.public_status()["phase"] == "ERROR"


def test_u9_plus_rejects_unconsumed_authorization(monkeypatch):
    coordinator, store, rollback, oracle = _recovery_coordinator(
        monkeypatch,
        "U9_LIVE_AUTHORIZATION_CLAIMED",
    )
    store.document["authorization_consumed"] = False

    with pytest.raises(
        UpdaterV2Error,
        match="u9_plus_recovery_authorization_not_consumed",
    ):
        coordinator.recover_once()

    assert rollback.calls == []
    assert oracle.calls == []



def test_u9_plus_detects_authorization_identity_drift(monkeypatch):
    coordinator, store, rollback, oracle = _recovery_coordinator(
        monkeypatch,
        "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED",
    )
    original = rollback.rollback

    def mutate(*, failure_code):
        result = original(failure_code=failure_code)
        store.document["authorization_id_sha256"] = "b" * 64
        return result

    rollback.rollback = mutate
    with pytest.raises(
        UpdaterV2Error,
        match="u9_plus_recovery_authorization_drift",
    ):
        coordinator.recover_once()

    assert oracle.calls == []
    assert coordinator.public_status()["phase"] == "ERROR"
