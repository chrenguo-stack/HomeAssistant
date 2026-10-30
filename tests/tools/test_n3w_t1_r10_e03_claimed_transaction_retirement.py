from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import n3w_t1_maintenance_transaction as tx  # noqa: E402
import n3w_t1_r10_e03_claimed_transaction_retirement as retirement  # noqa: E402
import n3w_t1_r10_e03_successor_recovery as successor  # noqa: E402


AUTHORITY = {
    "source_head": "a" * 40,
    "executor_blob": "b" * 40,
    "module_set_sha256": "c" * 64,
}


def _plan() -> dict[str, object]:
    return {
        "schema": successor.PLAN_SCHEMA,
        "predecessor_sha256": "b" * 64,
        "current_release_id": "8" * 64,
        "target_release_id": "9" * 64,
        "artifact_sha256": "a" * 64,
        "deployment_before_fingerprint": "1" * 64,
        "deployment_candidate_fingerprint": "2" * 64,
        "service_before_fingerprint": "3" * 64,
        "gate_before_fingerprint": "4" * 64,
        "manager_predecessor_container_id": "manager-old",
        "services_nrestarts": 0,
        "ha_mqtt_sha256": "5" * 64,
        "broker_baseline": {
            "container_id": "broker",
            "image_id": successor.BROKER_IMAGE_ID,
            "started_at": "broker-start",
            "restart_count": 0,
        },
    }


def _binding(plan: dict[str, object]) -> tx.MaintenanceBinding:
    return tx.MaintenanceBinding(
        transaction_id="txn-e03-retirement-target-0001",
        authorization_id_sha256="6" * 64,
        host_binding_sha256="7" * 64,
        current_release_id="8" * 64,
        target_release_id="9" * 64,
        artifact_sha256="a" * 64,
        executor_source_head="d" * 40,
        executor_blob="e" * 40,
        module_set_sha256="f" * 64,
        plan_sha256=tx.sha256_bytes(tx.canonical_bytes(plan)),
        scope=successor.SCOPE,
    )


def _target_document() -> dict[str, object]:
    plan = _plan()
    document = tx.new_transaction(
        _binding(plan),
        predecessor_sha256="b" * 64,
        before={"deployment_inputs": "1" * 64},
        intended_after={"deployment_inputs": "2" * 64},
        plan=plan,
    )
    document = tx.mark_ready(document)
    document = tx.claim_authorization(document)
    document = tx.record_execution_session(
        document,
        "claim-session-retirement-test",
        action="claim",
    )
    return document


@pytest.fixture
def harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    maintenance_root = tmp_path / "maintenance"
    transaction_root = maintenance_root / "transactions"
    retirement_root = maintenance_root / "retirements"
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
    monkeypatch.setattr(retirement, "runtime_authority", lambda: dict(AUTHORITY))

    original_tx_store = tx.TransactionStore
    original_retirement_store = retirement.RetirementStore

    monkeypatch.setattr(
        tx,
        "TransactionStore",
        lambda path: original_tx_store(
            path,
            enforce_root_metadata=False,
        ),
    )
    monkeypatch.setattr(
        retirement,
        "RetirementStore",
        lambda path: original_retirement_store(
            path,
            enforce_root_metadata=False,
        ),
    )

    document = _target_document()
    target_path = transaction_root / (
        str(document["transaction_id"]) + ".json"
    )
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
        lambda: "7" * 64,
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
        lambda: _plan()["service_before_fingerprint"],
    )
    monkeypatch.setattr(
        successor,
        "_gate_fingerprint",
        lambda: _plan()["gate_before_fingerprint"],
    )

    def fake_runtime(service: str):
        if service == "manager":
            return {
                "container_id": "manager-old",
                "image_ref": successor.OLD_MANAGER_IMAGE,
                "image_id": successor.OLD_MANAGER_ID,
                "network_mode": "host",
                "restart_count": 0,
            }
        if service == "homeassistant":
            return {
                "container_id": "ha",
                "image_ref": successor.HA_IMAGE,
                "image_id": successor.HA_IMAGE_ID,
                "network_mode": "host",
                "restart_count": 0,
            }
        raise AssertionError(service)

    monkeypatch.setattr(successor, "runtime", fake_runtime)
    monkeypatch.setattr(
        successor,
        "ha_mqtt_hash",
        lambda: _plan()["ha_mqtt_sha256"],
    )
    monkeypatch.setattr(
        successor,
        "_broker_continuity",
        lambda plan: dict(plan["broker_baseline"]),
    )
    monkeypatch.setattr(
        successor,
        "listener_snapshot",
        lambda: successor.EXPECTED_LISTENERS,
    )
    monkeypatch.setattr(
        successor,
        "systemd_nrestarts",
        lambda _unit: 0,
    )
    monkeypatch.setattr(
        successor,
        "_current_f4_authority",
        lambda: {
            "transaction_sha256": "c" * 64,
            "stage": "PERSISTENCE_ENABLED",
            "status": "PASS",
        },
    )

    def retirement_documents():
        if not retirement_root.exists():
            return []
        values = []
        for path in sorted(retirement_root.glob("*.json")):
            values.append(
                original_retirement_store(
                    path,
                    enforce_root_metadata=False,
                ).load()
            )
        return values

    monkeypatch.setattr(
        retirement,
        "_retirement_documents",
        retirement_documents,
    )

    return {
        "target_store": target_store,
        "target_path": target_path,
        "retirement_root": retirement_root,
        "original_retirement_store": original_retirement_store,
        "document": document,
    }


def test_preflight_freezes_exact_ready_before_state(harness) -> None:
    result = retirement.preflight(
        str(harness["document"]["transaction_id"])
    )
    assert result["status"] == "PASS"
    assert result["operation"] == "preflight"
    assert result["target_generation"] == harness["document"]["generation"]
    assert result["target_transaction_sha256"] == retirement.sha_file(
        harness["target_path"]
    )
    assert result["product_mutation"] is False


def _claim(harness, *, retirement_id: str = "retirement-e03-test-0001"):
    preflight = retirement.preflight(
        str(harness["document"]["transaction_id"])
    )
    return retirement.claim(
        target_transaction_id=str(harness["document"]["transaction_id"]),
        expected_preauth_plan_sha256=preflight[
            "retirement_plan_sha256"
        ],
        retirement_id=retirement_id,
        authorization_id="N3W_T1_R10_E03_CLAIMED_TRANSACTION_RETIREMENT_TEST_0001",
        execution_session_id="retirement-session-test-0001",
        confirmation=retirement.CONFIRMATION,
    )


def test_claim_resumes_exact_prepared_record_after_interruption(
    harness,
) -> None:
    target_id = str(harness["document"]["transaction_id"])
    preflight = retirement.preflight(target_id)
    plan = retirement._plan_locked(
        target_id,
        authority=dict(AUTHORITY),
    )
    assert retirement.sha_bytes(retirement.canonical(plan)) == preflight[
        "retirement_plan_sha256"
    ]

    harness["retirement_root"].mkdir(parents=True, exist_ok=True)
    prepared = retirement._record_from_plan(
        plan=plan,
        retirement_id="retirement-e03-test-0001",
        authorization_id_sha256=retirement.sha_text(
            "N3W_T1_R10_E03_CLAIMED_TRANSACTION_RETIREMENT_TEST_0001"
        ),
        execution_session_id_sha256=retirement.sha_text(
            "retirement-session-test-0001"
        ),
    )
    store = harness["original_retirement_store"](
        harness["retirement_root"] / "retirement-e03-test-0001.json",
        enforce_root_metadata=False,
    )
    store.create(prepared)

    result = retirement.claim(
        target_transaction_id=target_id,
        expected_preauth_plan_sha256=preflight[
            "retirement_plan_sha256"
        ],
        retirement_id="retirement-e03-test-0001",
        authorization_id=(
            "N3W_T1_R10_E03_CLAIMED_TRANSACTION_RETIREMENT_TEST_0001"
        ),
        execution_session_id="retirement-session-test-0001",
        confirmation=retirement.CONFIRMATION,
    )
    assert result["retirement_stage"] == "CLAIMED"
    assert result["authorization_consumed"] is True


def test_claim_is_one_shot_and_does_not_change_target(harness) -> None:
    before_sha = retirement.sha_file(harness["target_path"])
    result = _claim(harness)
    assert result["retirement_stage"] == "CLAIMED"
    assert result["authorization_consumed"] is True
    assert result["replay_allowed"] is False
    assert result["product_mutation"] is False
    assert retirement.sha_file(harness["target_path"]) == before_sha

    with pytest.raises(
        retirement.RetirementError,
        match="target_retirement_already_exists",
    ):
        _claim(
            harness,
            retirement_id="retirement-e03-test-0002",
        )


def test_retire_transitions_only_ready_to_aborted(harness) -> None:
    _claim(harness)
    result = retirement.retire(
        retirement_id="retirement-e03-test-0001",
        target_transaction_id=str(
            harness["document"]["transaction_id"]
        ),
    )
    target = harness["target_store"].load()
    assert result["status"] == "PASS"
    assert result["retirement_stage"] == "COMMITTED"
    assert target["state"] == "ABORTED"
    assert target["authorization_consumed"] is True
    assert target["replay_allowed"] is False
    assert target["operation_seq"] == 0
    assert target["operations"] == []
    assert target["observed_after"] == {}
    assert retirement.target_retirement_invariant_sha256(
        target
    ) == retirement.target_retirement_invariant_sha256(
        harness["document"]
    )


def test_claimed_before_abort_is_resumable_by_same_authority(harness) -> None:
    _claim(harness)
    target = harness["target_store"].load()
    assert target["state"] == "READY"
    result = retirement.retire(
        retirement_id="retirement-e03-test-0001",
        target_transaction_id=str(target["transaction_id"]),
    )
    assert result["retirement_stage"] == "COMMITTED"
    assert harness["target_store"].load()["state"] == "ABORTED"


def test_aborted_before_evidence_commit_only_finalizes_evidence(harness) -> None:
    _claim(harness)
    target = harness["target_store"].load()
    aborted = tx.abort_claimed_ready_before_apply(
        target,
        reason=retirement.REASON,
    )
    harness["target_store"].save(
        aborted,
        expected_generation=target["generation"],
    )
    after_sha = retirement.sha_file(harness["target_path"])

    result = retirement.retire(
        retirement_id="retirement-e03-test-0001",
        target_transaction_id=str(target["transaction_id"]),
    )
    assert result["retirement_stage"] == "COMMITTED"
    assert retirement.sha_file(harness["target_path"]) == after_sha


@pytest.mark.parametrize(
    "mutator,error",
    [
        (
            lambda d: tx.begin_apply(d),
            "abort_before_apply_state_invalid",
        ),
        (
            lambda d: {
                **d,
                "operation_seq": 1,
                "operations": [
                    {
                        "operation_seq": 1,
                        "operation_type": "service_stop",
                        "before_fingerprint": "1" * 64,
                        "intended_after_fingerprint": "2" * 64,
                        "observed_after_fingerprint": "2" * 64,
                        "status": "COMPLETE",
                        "last_error_code": None,
                    }
                ],
            },
            "abort_before_apply_operation_history_present",
        ),
    ],
)
def test_preflight_rejects_ineligible_target(
    harness,
    mutator,
    error: str,
) -> None:
    current = harness["target_store"].load()
    changed = mutator(current)
    if changed["generation"] == current["generation"]:
        changed["generation"] += 1
        changed["last_operation"] = "test-drift"
    harness["target_store"].save(
        changed,
        expected_generation=current["generation"],
    )
    with pytest.raises(Exception, match=error):
        retirement.preflight(str(current["transaction_id"]))


def test_preflight_rejects_non_before_runtime(
    harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        successor,
        "_deployment_reality",
        lambda _plan: "f" * 64,
    )
    with pytest.raises(
        retirement.RetirementError,
        match="deployment_reality_not_exact_before",
    ):
        retirement.preflight(
            str(harness["document"]["transaction_id"])
        )


@pytest.mark.parametrize(
    "probe,error",
    [
        ("service", "service_reality_not_exact_before"),
        ("gate", "gate_reality_not_exact_before"),
    ],
)
def test_preflight_rejects_non_before_service_or_gate(
    harness,
    monkeypatch: pytest.MonkeyPatch,
    probe: str,
    error: str,
) -> None:
    if probe == "service":
        monkeypatch.setattr(
            successor,
            "_service_fingerprint",
            lambda: "f" * 64,
        )
    else:
        monkeypatch.setattr(
            successor,
            "_gate_fingerprint",
            lambda: "f" * 64,
        )
    with pytest.raises(retirement.RetirementError, match=error):
        retirement.preflight(
            str(harness["document"]["transaction_id"])
        )


def test_claim_rejects_target_generation_or_sha_drift_after_preflight(
    harness,
) -> None:
    target_id = str(harness["document"]["transaction_id"])
    preflight = retirement.preflight(target_id)
    current = harness["target_store"].load()
    changed = dict(current)
    changed["generation"] += 1
    changed["last_operation"] = "external-safe-drift"
    harness["target_store"].save(
        changed,
        expected_generation=current["generation"],
    )
    with pytest.raises(
        retirement.RetirementError,
        match="preauth_plan_sha256_mismatch",
    ):
        retirement.claim(
            target_transaction_id=target_id,
            expected_preauth_plan_sha256=preflight[
                "retirement_plan_sha256"
            ],
            retirement_id="retirement-e03-test-drift-0001",
            authorization_id=(
                "N3W_T1_R10_E03_CLAIMED_TRANSACTION_RETIREMENT_TEST_DRIFT_0001"
            ),
            execution_session_id="retirement-session-test-drift-0001",
            confirmation=retirement.CONFIRMATION,
        )


def test_record_validation_rejects_plan_record_cross_binding_drift(
    harness,
) -> None:
    target_id = str(harness["document"]["transaction_id"])
    plan = retirement._plan_locked(
        target_id,
        authority=dict(AUTHORITY),
    )
    record = retirement._record_from_plan(
        plan=plan,
        retirement_id="retirement-e03-test-crossbind-0001",
        authorization_id_sha256="1" * 64,
        execution_session_id_sha256="2" * 64,
    )
    record["target_transaction_sha256_before"] = "3" * 64
    with pytest.raises(
        retirement.RetirementError,
        match="retirement_plan_record_cross_binding_invalid",
    ):
        retirement.validate_record(record)


def test_committed_supersession_binds_aborted_transaction_and_evidence(
    harness,
) -> None:
    _claim(harness)
    retirement.retire(
        retirement_id="retirement-e03-test-0001",
        target_transaction_id=str(
            harness["document"]["transaction_id"]
        ),
    )
    old = harness["target_store"].load()
    supersession = retirement.committed_supersession(
        predecessor_sha256=str(old["predecessor_sha256"]),
        current_release_id=str(old["current_release_id"]),
        target_release_id=str(old["target_release_id"]),
        artifact_sha256=str(old["artifact_sha256"]),
    )
    assert supersession is not None
    assert supersession["mode"] == "TERMINAL_REPLACEMENT"
    assert supersession["retired_state"] == "ABORTED"
    assert supersession["retired_operation_seq"] == 0


def test_supersession_rejects_retired_transaction_byte_drift(
    harness,
) -> None:
    _claim(harness)
    retirement.retire(
        retirement_id="retirement-e03-test-0001",
        target_transaction_id=str(
            harness["document"]["transaction_id"]
        ),
    )
    old = harness["target_store"].load()
    expected = retirement.committed_supersession(
        predecessor_sha256=str(old["predecessor_sha256"]),
        current_release_id=str(old["current_release_id"]),
        target_release_id=str(old["target_release_id"]),
        artifact_sha256=str(old["artifact_sha256"]),
    )
    assert expected is not None

    payload = harness["target_path"].read_bytes()
    harness["target_path"].write_bytes(payload + b" ")
    with pytest.raises(
        retirement.RetirementError,
        match="retirement_supersession_ambiguous",
    ):
        retirement.assert_supersession(
            expected,
            predecessor_sha256=str(old["predecessor_sha256"]),
            current_release_id=str(old["current_release_id"]),
            target_release_id=str(old["target_release_id"]),
            artifact_sha256=str(old["artifact_sha256"]),
        )


def test_source_has_no_product_mutation_operations() -> None:
    source = (
        ROOT
        / "tools"
        / "n3w_t1_r10_e03_claimed_transaction_retirement.py"
    ).read_text(encoding="utf-8")
    assert 'sub.add_parser("apply")' not in source
    assert '"systemctl", "stop"' not in source
    assert '"systemctl", "start"' not in source
    assert '("docker", "load"' not in source
    assert '("docker", "tag"' not in source
    assert '("docker", "rmi"' not in source
    assert "abort_claimed_ready_before_apply" in source
