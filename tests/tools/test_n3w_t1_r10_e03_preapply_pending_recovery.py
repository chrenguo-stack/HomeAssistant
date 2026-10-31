from __future__ import annotations

import contextlib
import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import n3w_t1_maintenance_transaction as tx  # noqa: E402
import n3w_t1_r10_e03_preapply_pending_recovery as recovery  # noqa: E402
import n3w_t1_r10_e03_successor_recovery as successor  # noqa: E402


APPLY_SESSION = "n3w-t1-e03-successor-postreboot-apply-20261030-02"


def _plan() -> dict[str, object]:
    return {
        "gate_before_fingerprint": "1" * 64,
        "gate_after_fingerprint": "2" * 64,
        "service_before_fingerprint": "3" * 64,
        "deployment_before_fingerprint": "4" * 64,
        "manager_predecessor_container_id": "old-manager",
        "preauth_ledger": {
            "mode": "RECONCILED_TERMINAL",
            "ledger_sha256": "5" * 64,
            "attempt_count": 1,
            "registration_count": 0,
            "registration_inventory_sha256": "6" * 64,
            "unresolved_count": 0,
        },
        "broker_baseline": {
            "container_id": "broker",
            "image_id": "sha256:" + "7" * 64,
            "started_at": "start",
            "restart_count": 0,
        },
    }


def _document() -> dict[str, object]:
    plan = _plan()
    binding = tx.MaintenanceBinding(
        transaction_id="txn-e03-pending-recovery-0001",
        authorization_id_sha256="a" * 64,
        host_binding_sha256="b" * 64,
        current_release_id="c" * 64,
        target_release_id="d" * 64,
        artifact_sha256="e" * 64,
        executor_source_head=recovery.AFFECTED_EXECUTOR_SOURCE_HEAD,
        executor_blob=recovery.AFFECTED_EXECUTOR_BLOB,
        module_set_sha256=recovery.AFFECTED_MODULE_SET_SHA256,
        plan_sha256=tx.sha256_bytes(tx.canonical_bytes(plan)),
        scope=successor.SCOPE,
    )
    document = tx.new_transaction(
        binding,
        predecessor_sha256="f" * 64,
        before={"deployment_inputs": "4" * 64},
        intended_after={"deployment_inputs": "8" * 64},
        plan=plan,
    )
    document = tx.mark_ready(document)
    document = tx.claim_authorization(document)
    document = tx.record_execution_session(
        document,
        "claim-session-0001",
        action="claim",
    )
    document = tx.record_execution_session(
        document,
        APPLY_SESSION,
        action="apply",
    )
    document = tx.begin_operation(
        document,
        operation_type="activation_gate_install",
        before_fingerprint="1" * 64,
        intended_after_fingerprint="2" * 64,
        allowed_states={"READY"},
    )
    return document


def _store(tmp_path: Path, document: dict[str, object]) -> tx.TransactionStore:
    path = tmp_path / "transaction.json"
    store = tx.TransactionStore(path, enforce_root_metadata=False)
    store.create(document)
    return store


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    store: tx.TransactionStore,
) -> None:
    monkeypatch.setattr(
        recovery.successor,
        "global_lock",
        lambda: contextlib.nullcontext(),
    )
    monkeypatch.setattr(
        recovery.successor,
        "_transaction_path",
        lambda _txid: store.path,
    )
    monkeypatch.setattr(
        recovery.maintenance,
        "TransactionStore",
        lambda _path: store,
    )
    monkeypatch.setattr(
        recovery,
        "_active_documents",
        lambda: [store.load()],
    )
    monkeypatch.setattr(
        recovery,
        "_runtime_preconditions",
        lambda _document: {
            "broker": {"restart_count": 0},
            "service_fingerprint": "3" * 64,
            "deployment_fingerprint": "4" * 64,
            "gate_fingerprint": "2" * 64,
        },
    )


def test_preflight_accepts_exact_live_stuck_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path, _document())
    _wire(monkeypatch, store)
    before = _sha(store.path)

    result = recovery.preflight(
        "txn-e03-pending-recovery-0001",
        before,
    )

    assert result["status"] == "PASS"
    assert result["transaction_state"] == "READY"
    assert result["operation_seq"] == 1
    assert result["pending_operation"] == "activation_gate_install"
    assert result["gate_reality"] == "AFTER"
    assert result["service_reality"] == "BEFORE"
    assert result["deployment_reality"] == "BEFORE"
    assert _sha(store.path) == before


def test_recover_reconciles_intent_then_aborts_without_cutover(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path, _document())
    _wire(monkeypatch, store)
    monkeypatch.setattr(
        recovery,
        "_assert_gate_nonblocking",
        lambda: None,
    )
    before = _sha(store.path)

    result = recovery.recover(
        "txn-e03-pending-recovery-0001",
        before,
        "session-e03-preapply-recovery-0001",
        recovery.CONFIRMATION,
    )

    persisted = store.load()
    assert result["status"] == "PASS"
    assert result["transaction_state"] == "ABORTED"
    assert result["active_transaction_count"] == 0
    assert result["apply_retried"] is False
    assert result["rollback_invoked"] is False
    assert result["product_cutover"] is False
    assert persisted["state"] == "ABORTED"
    assert persisted["operation_seq"] == 1
    assert persisted["operations"][-1]["status"] == "COMPLETE"
    assert persisted["operations"][-1]["observed_after_fingerprint"] == "2" * 64
    assert tx.pending_operation(persisted) is None
    assert persisted["last_reason"] == recovery.RECOVERY_REASON


def test_recover_rejects_wrong_transaction_sha_before_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path, _document())
    _wire(monkeypatch, store)
    before = _sha(store.path)

    with pytest.raises(recovery.RecoveryError, match="transaction_sha256_drift"):
        recovery.recover(
            "txn-e03-pending-recovery-0001",
            "0" * 64,
            "session-e03-preapply-recovery-0001",
            recovery.CONFIRMATION,
        )

    assert _sha(store.path) == before
    assert store.load()["state"] == "READY"


def test_recover_rejects_runtime_drift_before_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path, _document())
    _wire(monkeypatch, store)
    monkeypatch.setattr(
        recovery,
        "_runtime_preconditions",
        lambda _document: (_ for _ in ()).throw(
            recovery.RecoveryError("service_reality_not_before")
        ),
    )
    before = _sha(store.path)

    with pytest.raises(recovery.RecoveryError, match="service_reality_not_before"):
        recovery.recover(
            "txn-e03-pending-recovery-0001",
            before,
            "session-e03-preapply-recovery-0001",
            recovery.CONFIRMATION,
        )

    assert _sha(store.path) == before
    assert store.load()["state"] == "READY"
