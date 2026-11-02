#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import n3w_t1_maintenance_transaction as maintenance
import n3w_t1_r10_e03_successor_recovery as successor

SCHEMA = "gh.n3w-r10-e03-preapply-pending-recovery/1"
CONFIRMATION = "N3W_T1_R10_E03_PREAPPLY_PENDING_RECOVERY"

AFFECTED_EXECUTOR_SOURCE_HEAD = "4bec6c071af547615955602ac8d6232f0a54bc63"
AFFECTED_EXECUTOR_BLOB = "0517454a1c8c973eb7456ef793c0e5493dc1841b"
AFFECTED_MODULE_SET_SHA256 = (
    "1e1f9ae691993b6aeafbc4edb7565f3f3fc1dee87b64cf48e5fa21781ecb95b8"
)
AFFECTED_APPLY_SESSION_SHA256 = (
    "67a44319e6c3aa8ef9192a42c0f7a7ed771c836bea8991ae0ef9435942364b54"
)
EXPECTED_PENDING_OPERATION = "activation_gate_install"
RECOVERY_REASON = "PENDING_ACTIVATION_GATE_RECONCILED_NO_PRODUCT_CUTOVER"


class RecoveryError(RuntimeError):
    pass


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _save(
    store: maintenance.TransactionStore,
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    store.save(after, expected_generation=before["generation"])
    return store.load()


def _active_documents() -> list[dict[str, Any]]:
    return successor._active_maintenance_documents()


def _ensure_no_other_active(document: dict[str, Any]) -> None:
    maintenance.ensure_no_other_active(
        _active_documents(),
        transaction_id=document["transaction_id"],
    )


def _require_affected_authority(document: dict[str, Any]) -> None:
    if document["executor_source_head"] != AFFECTED_EXECUTOR_SOURCE_HEAD:
        raise RecoveryError("affected_executor_source_head_drift")
    if document["executor_blob"] != AFFECTED_EXECUTOR_BLOB:
        raise RecoveryError("affected_executor_blob_drift")
    if document["module_set_sha256"] != AFFECTED_MODULE_SET_SHA256:
        raise RecoveryError("affected_module_set_drift")
    apply_sessions = [
        item
        for item in document["execution_sessions"]
        if item.get("action") == "apply"
    ]
    if (
        len(apply_sessions) != 1
        or apply_sessions[0].get("session_id_sha256")
        != AFFECTED_APPLY_SESSION_SHA256
    ):
        raise RecoveryError("affected_apply_session_drift")


def _assert_gate_nonblocking() -> None:
    result = successor.run(
        (str(successor.GATE_TARGET),),
        allowed=frozenset({0, 1}),
    )
    if result.returncode != 0:
        raise RecoveryError("activation_gate_not_nonblocking")


def _runtime_preconditions(document: dict[str, Any]) -> dict[str, Any]:
    plan = document["plan"]
    manager = successor.runtime("manager")
    if (
        manager["container_id"] != plan["manager_predecessor_container_id"]
        or manager["image_ref"] != successor.OLD_MANAGER_IMAGE
        or manager["image_id"] != successor.OLD_MANAGER_ID
        or manager["network_mode"] != "host"
        or manager["restart_count"] != 0
    ):
        raise RecoveryError("manager_predecessor_continuity_drift")
    homeassistant = successor.runtime("homeassistant")
    if (
        homeassistant["image_ref"] != successor.HA_IMAGE
        or homeassistant["image_id"] != successor.HA_IMAGE_ID
        or homeassistant["network_mode"] != "host"
        or homeassistant["restart_count"] != 0
    ):
        raise RecoveryError("homeassistant_predecessor_continuity_drift")
    successor._assert_preauth_ledger_rebind(
        plan,
        manager["container_id"],
    )
    broker = successor._broker_continuity(plan)
    service = successor._service_fingerprint()
    deployment = successor._deployment_reality(plan)
    gate = successor._gate_fingerprint()
    if service != plan["service_before_fingerprint"]:
        raise RecoveryError("service_reality_not_before")
    if deployment != plan["deployment_before_fingerprint"]:
        raise RecoveryError("deployment_reality_not_before")
    if gate != plan["gate_after_fingerprint"]:
        raise RecoveryError("gate_reality_not_after")
    return {
        "broker": broker,
        "service_fingerprint": service,
        "deployment_fingerprint": deployment,
        "gate_fingerprint": gate,
    }


def preflight(
    transaction_id: str,
    expected_transaction_sha256: str,
) -> dict[str, Any]:
    with successor.global_lock():
        path = successor._transaction_path(transaction_id)
        if sha_file(path) != expected_transaction_sha256:
            raise RecoveryError("transaction_sha256_drift")
        store = maintenance.TransactionStore(path)
        document = store.load()
        _require_affected_authority(document)
        _ensure_no_other_active(document)
        if document["state"] != "READY":
            raise RecoveryError("transaction_state_not_ready")
        if document["authorization_consumed"] is not True:
            raise RecoveryError("authorization_not_consumed")
        if document["replay_allowed"] is not False:
            raise RecoveryError("replay_contract_drift")
        if document["operation_seq"] != 1:
            raise RecoveryError("operation_seq_drift")
        pending = maintenance.pending_operation(document)
        if pending is None:
            raise RecoveryError("pending_operation_missing")
        plan = document["plan"]
        if (
            pending["operation_type"] != EXPECTED_PENDING_OPERATION
            or pending["before_fingerprint"] != plan["gate_before_fingerprint"]
            or pending["intended_after_fingerprint"] != plan["gate_after_fingerprint"]
        ):
            raise RecoveryError("pending_operation_binding_drift")
        reality = _runtime_preconditions(document)
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "operation": "preflight",
            "transaction_sha256": sha_file(path),
            "transaction_state": document["state"],
            "transaction_generation": document["generation"],
            "operation_seq": document["operation_seq"],
            "pending_operation": pending["operation_type"],
            "gate_reality": "AFTER",
            "service_reality": "BEFORE",
            "deployment_reality": "BEFORE",
            "broker_restart_count": reality["broker"]["restart_count"],
            "board_access": False,
            "product_cutover": False,
        }


def recover(
    transaction_id: str,
    expected_transaction_sha256: str,
    execution_session_id: str,
    confirmation: str,
) -> dict[str, Any]:
    if confirmation != CONFIRMATION:
        raise RecoveryError("confirmation_invalid")
    with successor.global_lock():
        path = successor._transaction_path(transaction_id)
        if sha_file(path) != expected_transaction_sha256:
            raise RecoveryError("transaction_sha256_drift")
        store = maintenance.TransactionStore(path)
        document = store.load()
        _require_affected_authority(document)
        _ensure_no_other_active(document)
        if document["state"] != "READY":
            raise RecoveryError("transaction_state_not_ready")
        if document["operation_seq"] != 1:
            raise RecoveryError("operation_seq_drift")
        pending = maintenance.pending_operation(document)
        if pending is None:
            raise RecoveryError("pending_operation_missing")
        plan = document["plan"]
        if (
            pending["operation_type"] != EXPECTED_PENDING_OPERATION
            or pending["before_fingerprint"] != plan["gate_before_fingerprint"]
            or pending["intended_after_fingerprint"] != plan["gate_after_fingerprint"]
        ):
            raise RecoveryError("pending_operation_binding_drift")
        _runtime_preconditions(document)

        session_document = maintenance.record_execution_session(
            document,
            execution_session_id,
            action="preapply_pending_recovery",
        )
        document = _save(store, document, session_document)

        pending = maintenance.pending_operation(document)
        if pending is None:
            raise RecoveryError("pending_operation_lost")
        completed = maintenance.finish_operation(
            document,
            observed_after_fingerprint=plan["gate_after_fingerprint"],
        )
        document = _save(store, document, completed)

        aborted = maintenance.transition(
            document,
            "ABORTED",
            operation="preapply_pending_recovery_abort",
            reason=RECOVERY_REASON,
        )
        document = _save(store, document, aborted)

        reality = _runtime_preconditions(document)
        _assert_gate_nonblocking()
        active = [
            item
            for item in _active_documents()
            if item["state"] in maintenance.ACTIVE_STATES
        ]
        if active:
            raise RecoveryError("active_transaction_remains_after_abort")

        return {
            "schema": SCHEMA,
            "status": "PASS",
            "operation": "recover",
            "transaction_sha256": sha_file(path),
            "transaction_state": document["state"],
            "transaction_generation": document["generation"],
            "operation_seq": document["operation_seq"],
            "last_operation": document["last_operation"],
            "last_reason": document["last_reason"],
            "gate_reality": "AFTER_NONBLOCKING",
            "service_reality": "BEFORE",
            "deployment_reality": "BEFORE",
            "broker_restart_count": reality["broker"]["restart_count"],
            "active_transaction_count": 0,
            "apply_retried": False,
            "rollback_invoked": False,
            "product_cutover": False,
            "board_access": False,
        }


def _emit(value: dict[str, Any], *, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    stream.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="operation", required=True)

    pre = sub.add_parser("preflight")
    pre.add_argument("--transaction-id", required=True)
    pre.add_argument("--expected-transaction-sha256", required=True)

    rec = sub.add_parser("recover")
    rec.add_argument("--transaction-id", required=True)
    rec.add_argument("--expected-transaction-sha256", required=True)
    rec.add_argument("--execution-session-id", required=True)
    rec.add_argument("--confirmation", required=True)

    args = parser.parse_args()
    try:
        if args.operation == "preflight":
            result = preflight(
                args.transaction_id,
                args.expected_transaction_sha256,
            )
        else:
            result = recover(
                args.transaction_id,
                args.expected_transaction_sha256,
                args.execution_session_id,
                args.confirmation,
            )
        _emit(result)
        return 0
    except Exception as error:
        _emit(
            {
                "schema": SCHEMA,
                "status": "STOP",
                "operation": args.operation,
                "reason_code": successor.safe_reason(error),
                "apply_retried": False,
                "rollback_invoked": False,
                "board_access": False,
            },
            error=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
