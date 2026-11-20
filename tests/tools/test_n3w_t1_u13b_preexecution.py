from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from n3w_t1_core_updater_ha_u13b_preexecution import (
    ALREADY_ROLLED_BACK,
    HOST_RECONCILIATION_REQUIRED,
    ROLLBACK_ELIGIBLE,
    U13B_READONLY_PREEXECUTION_PASS,
    U13BReadOnlyPreexecutionInspector,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error
from test_n3w_t1_u13b_controller import (
    Store,
    media,
    origin_transaction,
    usb_snapshot,
)
from test_n3w_t1_u13b_postcondition import successors
from n3w_t1_core_updater_ha_usb_state import U9


class ReadOnlyBackend:
    def __init__(self, prepared_media, snapshots):
        self.media = prepared_media
        self.snapshots = list(snapshots)
        self.reads = 0
        self.releases = 0
        self.resolutions = 0

    def resolve_transaction_media_for_reconciliation(self, transaction):
        self.resolutions += 1
        return self.media

    def release_transaction_media_for_reconciliation(self, prepared_media):
        assert prepared_media == self.media
        self.releases += 1

    def read_transaction_metadata(self, transaction, prepared_media):
        assert prepared_media == self.media
        index = min(self.reads, len(self.snapshots) - 1)
        self.reads += 1
        return self.snapshots[index]


class Observer:
    def __init__(self, outcomes=None):
        self.outcomes = dict(outcomes or {})
        self.calls = []

    def __getattr__(self, name):
        if not name.startswith("observe_"):
            raise AttributeError(name)

        def observe(*, transaction, media):
            self.calls.append((name, transaction["phase"]))
            return self.outcomes.get(name, True)

        return observe


def inspect(tmp_path, host, snapshots, observer=None):
    store = Store(host)
    backend = ReadOnlyBackend(media(tmp_path), snapshots)
    observer = observer or Observer()
    result = U13BReadOnlyPreexecutionInspector(
        transaction_store=store,
        backend=backend,
        observer=observer,
    ).inspect()
    return result, store, backend, observer


def test_exact_entry_is_readonly_rollback_eligible(tmp_path):
    host = origin_transaction(U9)
    snapshot = usb_snapshot(host)
    result, store, backend, observer = inspect(
        tmp_path, host, [snapshot, snapshot]
    )

    assert result.status == U13B_READONLY_PREEXECUTION_PASS
    assert result.action == ROLLBACK_ELIGIBLE
    assert result.reconciliation_required is False
    assert result.rollback_execution_required is True
    assert result.transaction_mutation is False
    assert result.usb_mutation is False
    assert result.service_mutation is False
    assert result.image_mutation is False
    assert result.rollback_operation_replay is False
    assert observer.calls == [("observe_rollback_entry", U9)]
    assert store.writes == []
    assert backend.resolutions == 1
    assert backend.releases == 1


def test_exact_progress_rechecks_recovery_assets_and_current_postcondition(tmp_path):
    _old, host, _method = successors()[2]
    snapshot = usb_snapshot(host)
    result, store, backend, observer = inspect(
        tmp_path, host, [snapshot, snapshot]
    )

    assert result.action == ROLLBACK_ELIGIBLE
    assert result.observed_recovery_assets is True
    assert result.observed_postcondition == "observe_predecessor_image"
    assert observer.calls == [
        ("observe_rollback_entry", host["phase"]),
        ("observe_predecessor_image", host["phase"]),
    ]
    assert store.writes == []
    assert backend.releases == 1


def test_usb_one_phase_ahead_is_observed_but_not_reconciled(tmp_path):
    host, successor, method = successors()[2]
    snapshot = usb_snapshot(
        host,
        phase=successor["phase"],
        mirrored_transaction=successor,
    )
    result, store, backend, observer = inspect(
        tmp_path, host, [snapshot, snapshot]
    )

    assert result.action == HOST_RECONCILIATION_REQUIRED
    assert result.reconciliation_required is True
    assert result.host_phase == host["phase"]
    assert result.usb_phase == successor["phase"]
    assert result.effective_phase == successor["phase"]
    assert result.observed_postcondition == method
    assert observer.calls == [
        ("observe_rollback_entry", successor["phase"]),
        (method, successor["phase"]),
    ]
    assert store.writes == []
    assert backend.releases == 1


def test_exact_terminal_is_pass_without_future_rollback_mutation(tmp_path):
    _old, terminal, _method = successors()[-1]
    snapshot = usb_snapshot(terminal)
    result, store, backend, observer = inspect(
        tmp_path, terminal, [snapshot, snapshot]
    )

    assert result.action == ALREADY_ROLLED_BACK
    assert result.terminal_rolled_back is True
    assert result.rollback_execution_required is False
    assert result.observed_postcondition == "observe_predecessor_health"
    assert observer.calls == [
        ("observe_rollback_entry", terminal["phase"]),
        ("observe_predecessor_health", terminal["phase"]),
    ]
    assert store.writes == []
    assert backend.releases == 1


def test_non_true_recovery_observation_fails_closed_and_releases_media(tmp_path):
    host = origin_transaction(U9)
    snapshot = usb_snapshot(host)
    store = Store(host)
    backend = ReadOnlyBackend(media(tmp_path), [snapshot])
    observer = Observer({"observe_rollback_entry": 1})

    with pytest.raises(
        UpdaterV2Error,
        match="u13b_preexecution_observation_failed",
    ):
        U13BReadOnlyPreexecutionInspector(
            transaction_store=store,
            backend=backend,
            observer=observer,
        ).inspect()

    assert store.writes == []
    assert backend.releases == 1


def test_usb_snapshot_drift_after_observation_fails_closed(tmp_path):
    host = origin_transaction(U9)
    first = usb_snapshot(host)
    drifted = usb_snapshot(host)
    drifted.manifest["usb_device_identity_public_fingerprint"] = "f" * 64
    store = Store(host)
    backend = ReadOnlyBackend(media(tmp_path), [first, drifted])

    with pytest.raises(
        UpdaterV2Error,
        match="u13b_preexecution_usb_snapshot_drift",
    ):
        U13BReadOnlyPreexecutionInspector(
            transaction_store=store,
            backend=backend,
            observer=Observer(),
        ).inspect()

    assert store.writes == []
    assert backend.releases == 1


def test_host_ahead_or_divergent_state_never_becomes_pass(tmp_path):
    predecessor, host, _method = successors()[2]
    snapshot = usb_snapshot(
        host,
        phase=predecessor["phase"],
        mirrored_transaction=predecessor,
    )
    store = Store(host)
    backend = ReadOnlyBackend(media(tmp_path), [snapshot])

    with pytest.raises(UpdaterV2Error, match="u13b_preexecution_"):
        U13BReadOnlyPreexecutionInspector(
            transaction_store=store,
            backend=backend,
            observer=Observer(),
        ).inspect()

    assert store.writes == []
    assert backend.releases == 1


def test_preexecution_source_has_no_mutating_rollback_entrypoints():
    source_path = ROOT / "tools" / "n3w_t1_core_updater_ha_u13b_preexecution.py"
    source = source_path.read_text(encoding="utf-8")
    start = source.index("class U13BReadOnlyPreexecutionInspector:")
    body = source[start:]
    forbidden = (
        ".write(",
        "sync_transaction_metadata(",
        ".rollback(",
        "resolve_transaction_media(",
        "record_rollback_",
        "start_rollback(",
    )
    for token in forbidden:
        assert token not in body
