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
    def __init__(self, events, *, result=None, error=None):
        self.events = events
        self.result = result
        self.error = error
        self.calls = 0

    def reconcile(self):
        self.calls += 1
        self.events.append("reconcile")
        if self.error is not None:
            raise self.error
        return self.result


class Controller:
    def __init__(self, events, *, result=None, error=None):
        self.events = events
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


@pytest.mark.parametrize("status", [ALREADY_EXACT, RECONCILED])
def test_d4_reconciles_before_normal_rollback(status):
    events = []
    writer = Writer(events, result=reconciliation(status))
    controller = Controller(events)
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
    writer = Writer(
        events,
        error=UpdaterV2Error("u13b_reconciliation_divergent_stop"),
    )
    controller = Controller(events)

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
    writer = Writer(events, result=reconciliation(RECONCILED))
    controller = Controller(
        events,
        error=UpdaterV2Error("u13b_host_usb_reconciliation_stop"),
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
    writer = Writer(events, result=reconciliation("UNKNOWN"))
    controller = Controller(events)

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
