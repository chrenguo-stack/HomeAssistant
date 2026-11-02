from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import n3w_t1_maintenance_transaction as tx  # noqa: E402
import n3w_t1_r10_e03_claimed_transaction_retirement as retirement  # noqa: E402
import n3w_t1_r10_e03_replacement_baseline_invalidation as invalidation  # noqa: E402
import n3w_t1_r10_e03_successor_recovery as successor  # noqa: E402


AUTHORITY = {
    "source_head": "a" * 40,
    "executor_blob": "b" * 40,
    "module_set_sha256": "c" * 64,
}

OLD_STARTED = "2026-10-25T14:40:59.136962496Z"
NEW_STARTED = "2026-10-30T14:04:04.311501262Z"
BOOT_TIME = 1793369010


def _f4() -> dict[str, object]:
    return {
        "transaction_sha256": "d" * 64,
        "status": "PASS",
    }


def _plan() -> dict[str, object]:
    f4 = _f4()
    return {
        "schema": successor.PLAN_SCHEMA,
        "predecessor_sha256": "1" * 64,
        "current_release_id": "2" * 64,
        "target_release_id": "3" * 64,
        "artifact_sha256": "4" * 64,
        "deployment_before_fingerprint": "5" * 64,
        "deployment_candidate_fingerprint": "6" * 64,
        "service_before_fingerprint": "7" * 64,
        "gate_before_fingerprint": "8" * 64,
        "manager_predecessor_container_id": "manager-old",
        "services_nrestarts": 0,
        "ha_mqtt_sha256": "9" * 64,
        "current_f4_authority": f4,
        "current_f4_authority_sha256": successor.sha_bytes(
            successor.canonical(f4)
        ),
        "supersession": {
            "mode": "TERMINAL_REPLACEMENT",
            "reason": retirement.REASON,
        },
        "broker_baseline": {
            "container_id": "broker-id",
            "image_id": successor.BROKER_IMAGE_ID,
            "image_ref": successor.BROKER_IMAGE,
            "network_mode": "n3wfc4-private",
            "started_at": OLD_STARTED,
            "restart_count": 0,
        },
    }


def _binding(plan: dict[str, object]) -> tx.MaintenanceBinding:
    return tx.MaintenanceBinding(
        transaction_id="txn-e03-invalidation-target-0001",
        authorization_id_sha256="a" * 64,
        host_binding_sha256="b" * 64,
        current_release_id="2" * 64,
        target_release_id="3" * 64,
        artifact_sha256="4" * 64,
        executor_source_head="e" * 40,
        executor_blob="f" * 40,
        module_set_sha256="0" * 64,
        plan_sha256=tx.sha256_bytes(tx.canonical_bytes(plan)),
        scope=successor.SCOPE,
    )


def _target_document() -> dict[str, object]:
    plan = _plan()
    value = tx.new_transaction(
        _binding(plan),
        predecessor_sha256="1" * 64,
        before={"deployment_inputs": "5" * 64},
        intended_after={"deployment_inputs": "6" * 64},
        plan=plan,
    )
    value = tx.mark_ready(value)
    value = tx.claim_authorization(value)
    return tx.record_execution_session(
        value,
        "claim-session-invalidation-test",
        action="claim",
    )


@pytest.fixture
def harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    maintenance_root = tmp_path / "maintenance"
    transaction_root = maintenance_root / "transactions"
    invalidation_root = maintenance_root / "invalidations"
    transaction_root.mkdir(parents=True)

    monkeypatch.setattr(successor, "MAINTENANCE_ROOT", maintenance_root)
    monkeypatch.setattr(successor, "TRANSACTION_ROOT", transaction_root)
    monkeypatch.setattr(
        successor,
        "LOCK_PATH",
        maintenance_root / ".maintenance.lock",
    )
    monkeypatch.setattr(
        successor,
        "global_lock",
        lambda: contextlib.nullcontext(),
    )
    monkeypatch.setattr(
        retirement,
        "readonly_global_lock",
        lambda: contextlib.nullcontext(),
    )
    monkeypatch.setattr(
        successor,
        "_ensure_private_dir",
        lambda path: path.mkdir(parents=True, exist_ok=True),
    )
    monkeypatch.setattr(
        invalidation,
        "runtime_authority",
        lambda: dict(AUTHORITY),
    )

    original_tx_store = tx.TransactionStore
    original_invalidation_store = invalidation.InvalidationStore

    monkeypatch.setattr(
        tx,
        "TransactionStore",
        lambda path: original_tx_store(
            path,
            enforce_root_metadata=False,
        ),
    )
    monkeypatch.setattr(
        invalidation,
        "InvalidationStore",
        lambda path: original_invalidation_store(
            path,
            enforce_root_metadata=False,
        ),
    )

    document = _target_document()
    target_path = transaction_root / f"{document['transaction_id']}.json"
    target_store = original_tx_store(
        target_path,
        enforce_root_metadata=False,
    )
    target_store.create(document)

    monkeypatch.setattr(
        successor,
        "_active_maintenance_documents",
        lambda: [target_store.load()],
    )
    monkeypatch.setattr(
        successor,
        "host_binding_sha256",
        lambda: "b" * 64,
    )
    monkeypatch.setattr(
        tx,
        "assert_predecessor_immutable",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        successor,
        "predecessor_evidence",
        lambda _sha: {"status": "PASS"},
    )
    monkeypatch.setattr(
        successor,
        "_deployment_reality",
        lambda plan: plan["deployment_before_fingerprint"],
    )
    monkeypatch.setattr(
        successor,
        "_service_fingerprint",
        lambda: "7" * 64,
    )
    monkeypatch.setattr(
        successor,
        "_gate_fingerprint",
        lambda: "8" * 64,
    )
    monkeypatch.setattr(
        successor,
        "ha_mqtt_hash",
        lambda: "9" * 64,
    )
    monkeypatch.setattr(
        successor,
        "systemd_nrestarts",
        lambda _unit: 0,
    )
    monkeypatch.setattr(
        successor,
        "systemctl",
        lambda operation, _unit: (
            "active" if operation == "is-active" else "enabled"
        ),
    )
    monkeypatch.setattr(
        successor,
        "listener_count",
        lambda protocol, port: 1
        if protocol == "tcp" and port == 8883
        else 0,
    )
    monkeypatch.setattr(
        successor,
        "listener_snapshot",
        lambda: dict(successor.EXPECTED_LISTENERS),
    )
    monkeypatch.setattr(
        successor,
        "_current_f4_authority",
        _f4,
    )
    monkeypatch.setattr(
        retirement,
        "assert_supersession",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(
        invalidation,
        "_boot_evidence",
        lambda: {
            "boot_id_sha256": "1" * 64,
            "boot_time_unix": BOOT_TIME,
        },
    )

    runtimes = {
        "manager": {
            "container_id": "manager-old",
            "image_id": successor.OLD_MANAGER_ID,
            "image_ref": successor.OLD_MANAGER_IMAGE,
            "network_mode": "host",
            "started_at": NEW_STARTED,
            "restart_count": 0,
        },
        "homeassistant": {
            "container_id": "ha-id",
            "image_id": successor.HA_IMAGE_ID,
            "image_ref": successor.HA_IMAGE,
            "network_mode": "host",
            "started_at": NEW_STARTED,
            "restart_count": 0,
        },
        "broker": {
            "container_id": "broker-id",
            "image_id": successor.BROKER_IMAGE_ID,
            "image_ref": successor.BROKER_IMAGE,
            "network_mode": "n3wfc4-private",
            "started_at": NEW_STARTED,
            "restart_count": 0,
        },
    }
    monkeypatch.setattr(
        successor,
        "runtime",
        lambda service: dict(runtimes[service]),
    )

    return {
        "document": document,
        "target_path": target_path,
        "target_store": target_store,
        "invalidation_root": invalidation_root,
        "runtimes": runtimes,
    }


def test_preflight_accepts_only_started_at_reboot_drift(harness) -> None:
    result = invalidation.preflight(
        str(harness["document"]["transaction_id"])
    )
    assert result["status"] == "PASS"
    assert result["target_generation"] == harness["document"]["generation"]
    assert result["broker_invalidation"]["expected_broker_started_at"] == OLD_STARTED
    assert result["broker_invalidation"]["observed_broker_started_at"] == NEW_STARTED
    assert result["product_mutation"] is False
    assert result["service_stop_start"] is False
    assert result["docker_mutation"] is False


@pytest.mark.parametrize(
    "key,value,error",
    [
        ("container_id", "other-broker", "broker_non_started_at_drift:container_id"),
        (
            "image_id",
            "sha256:" + "a" * 64,
            "broker_non_started_at_drift:image_id",
        ),
        ("image_ref", "other/image:tag", "broker_non_started_at_drift:image_ref"),
        ("network_mode", "host", "broker_non_started_at_drift:network_mode"),
        ("restart_count", 1, "broker_non_started_at_drift:restart_count"),
    ],
)
def test_preflight_rejects_broader_broker_drift(
    harness,
    key: str,
    value,
    error: str,
) -> None:
    harness["runtimes"]["broker"][key] = value
    with pytest.raises(invalidation.InvalidationError, match=error):
        invalidation.preflight(
            str(harness["document"]["transaction_id"])
        )


def test_preflight_requires_started_at_to_change(harness) -> None:
    harness["runtimes"]["broker"]["started_at"] = OLD_STARTED
    with pytest.raises(
        invalidation.InvalidationError,
        match="broker_started_at_not_invalidated",
    ):
        invalidation.preflight(
            str(harness["document"]["transaction_id"])
        )


def test_preflight_requires_current_boot_temporal_proof(
    harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        invalidation,
        "_boot_evidence",
        lambda: {
            "boot_id_sha256": "1" * 64,
            "boot_time_unix": 1,
        },
    )
    with pytest.raises(
        invalidation.InvalidationError,
        match="broker_started_at_not_current_boot",
    ):
        invalidation.preflight(
            str(harness["document"]["transaction_id"])
        )


def _claim(harness):
    preflight = invalidation.preflight(
        str(harness["document"]["transaction_id"])
    )
    return invalidation.claim(
        target_transaction_id=str(
            harness["document"]["transaction_id"]
        ),
        expected_preauth_plan_sha256=preflight[
            "invalidation_plan_sha256"
        ],
        invalidation_id="invalidation-e03-test-0001",
        authorization_id=(
            "N3W_T1_R10_E03_REPLACEMENT_BASELINE_INVALIDATION_TEST_0001"
        ),
        execution_session_id="invalidation-session-test-0001",
        confirmation=invalidation.CONFIRMATION,
    )


def test_claim_is_one_shot_and_does_not_mutate_target(harness) -> None:
    before = invalidation.sha_file(harness["target_path"])
    result = _claim(harness)
    assert result["invalidation_stage"] == "CLAIMED"
    assert result["authorization_consumed"] is True
    assert result["replay_allowed"] is False
    assert invalidation.sha_file(harness["target_path"]) == before

    with pytest.raises(
        invalidation.InvalidationError,
        match="target_invalidation_already_exists",
    ):
        _claim(harness)


def test_invalidate_transitions_only_target_to_blocked(harness) -> None:
    _claim(harness)
    result = invalidation.invalidate(
        invalidation_id="invalidation-e03-test-0001",
        target_transaction_id=str(
            harness["document"]["transaction_id"]
        ),
        execution_session_id="invalidation-session-test-0001",
    )
    assert result["invalidation_stage"] == "COMMITTED"
    assert result["target_state"] == "BLOCKED"
    assert result["product_mutation"] is False

    target = harness["target_store"].load()
    assert target["state"] == "BLOCKED"
    assert target["generation"] == harness["document"]["generation"] + 1
    assert target["last_operation"] == "baseline_invalidated_before_apply"
    assert target["last_reason"] == invalidation.REASON
    assert target["operation_seq"] == 0
    assert target["operations"] == []
    assert target["observed_after"] == {}
    assert target["authorization_consumed"] is True
    assert target["replay_allowed"] is False
    assert target["state"] in tx.TERMINAL_STATES
    assert target["state"] not in tx.ACTIVE_STATES


def test_invalidate_resumes_after_target_save_before_record_commit(
    harness,
) -> None:
    _claim(harness)
    target = harness["target_store"].load()
    blocked = invalidation._block_target(target)
    harness["target_store"].save(
        blocked,
        expected_generation=target["generation"],
    )

    result = invalidation.invalidate(
        invalidation_id="invalidation-e03-test-0001",
        target_transaction_id=str(
            harness["document"]["transaction_id"]
        ),
        execution_session_id="invalidation-session-test-0001",
    )
    assert result["invalidation_stage"] == "COMMITTED"
    assert result["target_state"] == "BLOCKED"


def test_block_target_rejects_apply_session() -> None:
    value = tx.record_execution_session(
        _target_document(),
        "apply-session-test-0001",
        action="apply",
    )
    with pytest.raises(
        invalidation.InvalidationError,
        match="target_execution_session_forbidden",
    ):
        invalidation._block_target(value)


def test_source_contains_no_product_mutation_operations() -> None:
    source = (
        ROOT
        / "tools"
        / "n3w_t1_r10_e03_replacement_baseline_invalidation.py"
    ).read_text(encoding="utf-8")
    assert 'sub.add_parser("apply")' not in source
    assert '"systemctl", "stop"' not in source
    assert '"systemctl", "start"' not in source
    assert '("docker", "load"' not in source
    assert '("docker", "tag"' not in source
    assert '("docker", "rmi"' not in source
    assert '"BLOCKED"' in source
