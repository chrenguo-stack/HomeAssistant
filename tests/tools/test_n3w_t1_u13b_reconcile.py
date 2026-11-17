from __future__ import annotations

from contextlib import contextmanager
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from n3w_t1_core_updater_ha_u13b_reconcile import (
    ALREADY_EXACT,
    RECONCILED,
    U13BHostOnlyReconciliationWriter,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error
from test_n3w_t1_u13b_controller import media, usb_snapshot
from test_n3w_t1_u13b_postcondition import successors


class Store:
    def __init__(
        self,
        document,
        *,
        on_lock=None,
        persist_then_raise=False,
        busy=False,
    ):
        self.document = document
        self.on_lock = on_lock
        self.persist_then_raise = persist_then_raise
        self.busy = busy
        self.writes = []
        self.lock_entries = 0

    @contextmanager
    def lock(self):
        if self.busy:
            raise UpdaterV2Error("upgrade_transaction_busy")
        self.lock_entries += 1
        if self.on_lock is not None:
            self.on_lock(self)
        yield

    def read(self):
        return self.document

    def write(self, document):
        self.document = document
        self.writes.append(document)
        if self.persist_then_raise:
            self.persist_then_raise = False
            raise RuntimeError("synthetic_response_loss_after_host_write")


class Backend:
    def __init__(self, observed_media, snapshots):
        self.media = observed_media
        self.snapshots = list(snapshots)
        self.reads = 0
        self.resolves = 0

    def resolve_transaction_media_for_reconciliation(self, transaction):
        self.resolves += 1
        return self.media

    def read_transaction_metadata(self, transaction, media_value):
        assert media_value is self.media
        index = min(self.reads, len(self.snapshots) - 1)
        self.reads += 1
        return self.snapshots[index]

    def sync_transaction_metadata(self, *args, **kwargs):
        raise AssertionError("D3 must never write USB metadata")


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
def test_d3_reconciles_all_six_legal_edges_host_only(tmp_path, index):
    old, new, method = successors()[index]
    snapshot = usb_snapshot(
        old, phase=new["phase"], mirrored_transaction=new
    )
    store = Store(old)
    backend = Backend(media(tmp_path), [snapshot, snapshot])
    observer = Observer()

    result = U13BHostOnlyReconciliationWriter(
        transaction_store=store,
        backend=backend,
        observer=observer,
    ).reconcile()

    assert result.status == RECONCILED
    assert result.host_write_performed is True
    assert result.previous_phase == old["phase"]
    assert result.current_phase == new["phase"]
    assert store.document == new
    assert store.writes == [new]
    assert store.lock_entries == 1
    assert backend.reads == 2
    assert observer.calls == [(method, new["phase"])]


def test_d3_exact_is_idempotent_noop_without_observer_or_write(tmp_path):
    host, _new, _method = successors()[0]
    snapshot = usb_snapshot(host)
    store = Store(host)
    observer = Observer()
    result = U13BHostOnlyReconciliationWriter(
        transaction_store=store,
        backend=Backend(media(tmp_path), [snapshot]),
        observer=observer,
    ).reconcile()
    assert result.status == ALREADY_EXACT
    assert result.host_write_performed is False
    assert store.writes == []
    assert observer.calls == []


def test_d3_postcondition_failure_never_writes_host(tmp_path):
    old, new, _method = successors()[1]
    snapshot = usb_snapshot(
        old, phase=new["phase"], mirrored_transaction=new
    )
    store = Store(old)
    with pytest.raises(
        UpdaterV2Error,
        match="u13b_reconciliation_postcondition_failed",
    ):
        U13BHostOnlyReconciliationWriter(
            transaction_store=store,
            backend=Backend(media(tmp_path), [snapshot]),
            observer=Observer(False),
        ).reconcile()
    assert store.writes == []


def test_d3_rejects_usb_snapshot_drift_after_observation(tmp_path):
    old, new, _method = successors()[1]
    first = usb_snapshot(
        old, phase=new["phase"], mirrored_transaction=new
    )
    drifted = usb_snapshot(old)
    store = Store(old)
    with pytest.raises(
        UpdaterV2Error,
        match="u13b_reconciliation_usb_snapshot_drift",
    ):
        U13BHostOnlyReconciliationWriter(
            transaction_store=store,
            backend=Backend(media(tmp_path), [first, drifted]),
            observer=Observer(),
        ).reconcile()
    assert store.writes == []


def test_d3_busy_global_lock_never_reads_or_writes(tmp_path):
    old, new, _method = successors()[0]
    snapshot = usb_snapshot(
        old, phase=new["phase"], mirrored_transaction=new
    )
    store = Store(old, busy=True)
    backend = Backend(media(tmp_path), [snapshot])
    with pytest.raises(UpdaterV2Error, match="upgrade_transaction_busy"):
        U13BHostOnlyReconciliationWriter(
            transaction_store=store,
            backend=backend,
            observer=Observer(),
        ).reconcile()
    assert store.writes == []
    assert backend.resolves == 0


def test_d3_fresh_locked_host_state_wins_over_stale_candidate(tmp_path):
    old, new, _method = successors()[0]
    snapshot = usb_snapshot(
        old, phase=new["phase"], mirrored_transaction=new
    )
    store = Store(old, on_lock=lambda value: setattr(value, "document", new))
    observer = Observer()
    result = U13BHostOnlyReconciliationWriter(
        transaction_store=store,
        backend=Backend(media(tmp_path), [snapshot]),
        observer=observer,
    ).reconcile()
    assert result.status == ALREADY_EXACT
    assert store.writes == []
    assert observer.calls == []


def test_d3_crash_after_atomic_host_write_is_idempotent_on_retry(tmp_path):
    old, new, method = successors()[2]
    snapshot = usb_snapshot(
        old, phase=new["phase"], mirrored_transaction=new
    )
    store = Store(old, persist_then_raise=True)
    backend = Backend(media(tmp_path), [snapshot, snapshot])
    observer = Observer()

    writer = U13BHostOnlyReconciliationWriter(
        transaction_store=store,
        backend=backend,
        observer=observer,
    )
    with pytest.raises(
        RuntimeError,
        match="synthetic_response_loss_after_host_write",
    ):
        writer.reconcile()
    assert store.document == new
    assert store.writes == [new]
    assert observer.calls == [(method, new["phase"])]

    retry = U13BHostOnlyReconciliationWriter(
        transaction_store=store,
        backend=Backend(media(tmp_path), [snapshot]),
        observer=Observer(),
    ).reconcile()
    assert retry.status == ALREADY_EXACT
    assert store.writes == [new]
