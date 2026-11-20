from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from n3w_t1_core_updater_ha_u13b_postcondition import (
    verify_u13b_usb_ahead_postcondition_readonly,
)
from n3w_t1_core_updater_ha_usb import (
    record_rollback_target_cleanup,
    record_rollback_predecessor_image_restored,
    record_rollback_ha_data_restored,
    record_rollback_predecessor_runtime_started,
    record_rollback_complete,
    start_rollback,
)
from n3w_t1_core_updater_ha_usb_state import U9, U13B
from n3w_t1_core_updater_v2_common import UpdaterV2Error

from test_n3w_t1_u13b_controller import (
    origin_transaction, media, usb_snapshot,
    TARGET_RECORD, PREDECESSOR_RECORD, BACKUP_RECORD,
)


def successors():
    initial = origin_transaction(U9)
    b0 = start_rollback(
        initial, failure_code="target_health_acceptance_failed",
        target=TARGET_RECORD, predecessor=PREDECESSOR_RECORD,
        backup=BACKUP_RECORD,
    )
    b1 = record_rollback_target_cleanup(
        b0, services_quiesced=True,
        target_runtime_absent=True, target_image_absent=True,
    )
    b2 = record_rollback_predecessor_image_restored(
        b1, predecessor=PREDECESSOR_RECORD,
        predecessor_image_exact_present=True,
    )
    b3 = record_rollback_ha_data_restored(
        b2, backup=BACKUP_RECORD, ha_data_backup_restored=True,
    )
    b4 = record_rollback_predecessor_runtime_started(
        b3, predecessor_runtime_started=True,
        production_config_mounted=True, manager_running=True,
        broker_running=True, homeassistant_running=True,
    )
    terminal = record_rollback_complete(
        b4, predecessor_health_verified=True,
        manager_mqtt_authenticated=True,
        homeassistant_mqtt_authenticated=True,
        homeassistant_http_ready=True,
    )
    return [
        (initial, b0, "observe_rollback_entry"),
        (b0, b1, "observe_target_cleanup"),
        (b1, b2, "observe_predecessor_image"),
        (b2, b3, "observe_ha_data_restored"),
        (b3, b4, "observe_predecessor_runtime"),
        (b4, terminal, "observe_predecessor_health"),
    ]


class Observer:
    def __init__(self, outcome=True):
        self.outcome = outcome
        self.calls = []

    def __getattr__(self, name):
        if not name.startswith("observe_"):
            raise AttributeError(name)
        def observe(*, transaction, media):
            self.calls.append((name, transaction["phase"]))
            return self.outcome
        return observe


@pytest.mark.parametrize("index", range(6))
def test_readonly_postcondition_dispatches_only_exact_successor(index, tmp_path):
    old, new, method = successors()[index]
    obs = Observer()
    result = verify_u13b_usb_ahead_postcondition_readonly(
        host_transaction=old,
        media=media(tmp_path),
        snapshot=usb_snapshot(
            old, phase=new["phase"], mirrored_transaction=new
        ),
        observer=obs,
    )
    assert result.eligible_for_later_host_only_reconciliation is True
    assert result.host_phase == old["phase"]
    assert result.usb_phase == new["phase"]
    assert obs.calls == [(method, new["phase"])]
    assert old["phase"] != new["phase"]


@pytest.mark.parametrize("outcome", [False, None, 1, "true", {}])
def test_readonly_postcondition_fail_closed_on_non_true_observation(outcome, tmp_path):
    old, new, _ = successors()[0]
    with pytest.raises(
        UpdaterV2Error, match="u13b_postcondition_observation_failed"
    ):
        verify_u13b_usb_ahead_postcondition_readonly(
            host_transaction=old,
            media=media(tmp_path),
            snapshot=usb_snapshot(
                old, phase=new["phase"], mirrored_transaction=new
            ),
            observer=Observer(outcome),
        )


def test_readonly_postcondition_never_observes_exact_host_usb(tmp_path):
    host = origin_transaction(U9)
    observer = Observer()
    with pytest.raises(
        UpdaterV2Error, match="u13b_postcondition_usb_ahead_required"
    ):
        verify_u13b_usb_ahead_postcondition_readonly(
            host_transaction=host,
            media=media(tmp_path),
            snapshot=usb_snapshot(host),
            observer=observer,
        )
    assert observer.calls == []


def test_readonly_postcondition_rejects_unbound_mirror_before_observation(tmp_path):
    host, successor, _ = successors()[0]
    mirror = dict(successor)
    mirror["target_image_ref"] = "local/n3w-homeassistant:other"
    observer = Observer()
    with pytest.raises(
        UpdaterV2Error, match="u13b_postcondition_usb_ahead_required"
    ):
        verify_u13b_usb_ahead_postcondition_readonly(
            host_transaction=host,
            media=media(tmp_path),
            snapshot=usb_snapshot(
                host, phase=successor["phase"], mirrored_transaction=mirror
            ),
            observer=observer,
        )
    assert observer.calls == []


def test_readonly_postcondition_missing_observer_fails_closed(tmp_path):
    host, successor, _ = successors()[0]
    with pytest.raises(
        UpdaterV2Error, match="u13b_postcondition_observer_missing"
    ):
        verify_u13b_usb_ahead_postcondition_readonly(
            host_transaction=host,
            media=media(tmp_path),
            snapshot=usb_snapshot(
                host, phase=successor["phase"], mirrored_transaction=successor
            ),
            observer=object(),
        )
