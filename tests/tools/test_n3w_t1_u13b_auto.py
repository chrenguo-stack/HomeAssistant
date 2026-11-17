from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from n3w_t1_core_updater_ha_u13b import U13BRollbackResult
from n3w_t1_core_updater_ha_u13b_auto import (
    U13BAutomaticRollbackCoordinator,
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
