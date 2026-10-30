from __future__ import annotations

import base64
import contextlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import n3w_t1_maintenance_transaction as tx  # noqa: E402
import n3w_t1_r10_e03_successor_recovery as successor  # noqa: E402


@pytest.fixture(autouse=True)
def _held_lock(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(successor, "_LOCK_DEPTH", 1)


def _plan() -> dict[str, object]:
    return {
        "kind": "successor-test",
        "compose_sha256": "0" * 64,
        "compose_render_sha256": "f" * 64,
        "compose_env_before_sha256": "1" * 64,
        "compose_env_candidate_sha256": "2" * 64,
        "compose_env_candidate_b64": base64.b64encode(
            b"GH_MANAGER_IMAGE=target\n"
        ).decode("ascii"),
        "compose_env_before_b64": base64.b64encode(
            b"GH_MANAGER_IMAGE=before\n"
        ).decode("ascii"),
        "deployment_before_fingerprint": "a" * 64,
        "deployment_candidate_fingerprint": "b" * 64,
        "service_before_fingerprint": "3" * 64,
        "service_stopped_fingerprint": "4" * 64,
        "service_running_fingerprint": "5" * 64,
        "gate_before_fingerprint": "6" * 64,
        "gate_after_fingerprint": "7" * 64,
        "portable_identity": {"test": True},
        "manager_predecessor_container_id": "old-manager",
        "services_nrestarts": 0,
        "ha_mqtt_sha256": "8" * 64,
        "broker_baseline": {
            "container_id": "broker",
            "image_id": "sha256:" + "9" * 64,
            "started_at": "start",
            "restart_count": 0,
        },
    }


def _binding(plan: dict[str, object] | None = None) -> tx.MaintenanceBinding:
    value = plan or _plan()
    return tx.MaintenanceBinding(
        transaction_id="txn-e03-successor-test-0001",
        authorization_id_sha256="a" * 64,
        host_binding_sha256="b" * 64,
        current_release_id="c" * 64,
        target_release_id="d" * 64,
        artifact_sha256="e" * 64,
        executor_source_head="f" * 40,
        executor_blob="1" * 40,
        module_set_sha256="2" * 64,
        plan_sha256=tx.sha256_bytes(tx.canonical_bytes(value)),
        scope=successor.SCOPE,
    )


def _document(
    *,
    state: str = "APPLYING",
    plan: dict[str, object] | None = None,
) -> dict[str, object]:
    value = plan or _plan()
    document = tx.new_transaction(
        _binding(value),
        predecessor_sha256="3" * 64,
        before={
            "deployment_inputs": str(value["deployment_before_fingerprint"])
        },
        intended_after={
            "deployment_inputs": str(value["deployment_candidate_fingerprint"])
        },
        plan=value,
    )
    document = tx.mark_ready(document)
    document = tx.claim_authorization(document)
    if state in {"APPLYING", "VERIFYING", "ROLLING_BACK", "ROLLED_BACK", "COMMITTED"}:
        document = tx.begin_apply(document)
    if state in {"VERIFYING", "ROLLING_BACK", "ROLLED_BACK", "COMMITTED"}:
        document = tx.transition(
            document,
            "VERIFYING",
            operation="candidate_published_owner_controlled",
            observed_after={"deployment_inputs": str(value["deployment_candidate_fingerprint"])},
        )
    if state in {"ROLLING_BACK", "ROLLED_BACK"}:
        document = tx.transition(
            document,
            "ROLLING_BACK",
            operation="rollback_begin",
            reason="test",
        )
    if state == "ROLLED_BACK":
        document = tx.transition(
            document,
            "ROLLED_BACK",
            operation="rollback_compose_restored",
            reason="test",
            observed_after={"deployment_inputs": str(value["deployment_before_fingerprint"])},
        )
    if state == "COMMITTED":
        document = tx.transition(
            document,
            "COMMITTED",
            operation="runtime_acceptance_pass",
            observed_after={"deployment_inputs": str(value["deployment_candidate_fingerprint"])},
        )
    if state == "READY":
        return document
    return document


def _store(tmp_path: Path, document: dict[str, object]) -> tx.TransactionStore:
    path = tmp_path / "transaction.json"
    store = tx.TransactionStore(path, enforce_root_metadata=False)
    store.create(document)
    return store


def test_operation_persists_intent_before_execute_and_completion_after(
    tmp_path: Path,
) -> None:
    document = _document()
    store = _store(tmp_path, document)
    reality = {"value": "1" * 64}
    observations: list[str] = []

    def read_reality() -> str:
        observations.append(reality["value"])
        return reality["value"]

    def execute() -> None:
        persisted = store.load()
        assert persisted["operations"][-1]["status"] == "INTENT"
        reality["value"] = "2" * 64

    result = successor._operation(
        store,
        document,
        binding=_binding(),
        action="deployment_inputs_publish",
        operation_type="deployment_inputs_publish",
        before_fingerprint="1" * 64,
        after_fingerprint="2" * 64,
        reality=read_reality,
        execute=execute,
        allowed_states={"APPLYING"},
    )
    assert observations == ["1" * 64, "2" * 64]
    assert result["operations"][-1]["status"] == "COMPLETE"
    assert result["operations"][-1]["observed_after_fingerprint"] == "2" * 64


def test_operation_reentry_completes_existing_intent_without_second_execute(
    tmp_path: Path,
) -> None:
    document = _document()
    intent = tx.begin_operation(
        document,
        operation_type="deployment_inputs_publish",
        before_fingerprint="1" * 64,
        intended_after_fingerprint="2" * 64,
        allowed_states={"APPLYING"},
    )
    store = _store(tmp_path, intent)
    calls: list[str] = []

    result = successor._operation(
        store,
        intent,
        binding=_binding(),
        action="deployment_inputs_publish",
        operation_type="deployment_inputs_publish",
        before_fingerprint="1" * 64,
        after_fingerprint="2" * 64,
        reality=lambda: "2" * 64,
        execute=lambda: calls.append("execute"),
        allowed_states={"APPLYING"},
    )
    assert calls == []
    assert result["operations"][-1]["status"] == "COMPLETE"


def test_operation_unknown_reality_blocks_without_write(tmp_path: Path) -> None:
    document = _document()
    store = _store(tmp_path, document)
    calls: list[str] = []
    with pytest.raises(successor.BlockedError, match="operation_prestate_unknown"):
        successor._operation(
            store,
            document,
            binding=_binding(),
            action="deployment_inputs_publish",
            operation_type="deployment_inputs_publish",
            before_fingerprint="1" * 64,
            after_fingerprint="2" * 64,
            reality=lambda: "9" * 64,
            execute=lambda: calls.append("write"),
            allowed_states={"APPLYING"},
        )
    assert calls == []
    assert store.load()["operations"] == []


def test_repeated_completed_operation_is_read_only(tmp_path: Path) -> None:
    document = _document()
    intent = tx.begin_operation(
        document,
        operation_type="deployment_inputs_publish",
        before_fingerprint="1" * 64,
        intended_after_fingerprint="2" * 64,
        allowed_states={"APPLYING"},
    )
    complete = tx.finish_operation(
        intent,
        observed_after_fingerprint="2" * 64,
    )
    store = _store(tmp_path, complete)
    generation = complete["generation"]
    result = successor._operation(
        store,
        complete,
        binding=_binding(),
        action="deployment_inputs_publish",
        operation_type="deployment_inputs_publish",
        before_fingerprint="1" * 64,
        after_fingerprint="2" * 64,
        reality=lambda: "2" * 64,
        execute=lambda: pytest.fail("must not execute"),
        allowed_states={"APPLYING"},
    )
    assert result["generation"] == generation
    assert store.load()["generation"] == generation


def test_candidate_publish_refuses_uncontrolled_application_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    monkeypatch.setattr(successor, "_service_fingerprint", lambda: "9" * 64)
    monkeypatch.setattr(
        successor,
        "_deployment_reality",
        lambda _plan: pytest.fail("deployment must not be read for publish"),
    )
    with pytest.raises(successor.BlockedError, match="candidate_owner_not_controlled"):
        successor._publish_candidate_env(plan)


def test_rollback_requires_completed_candidate_write_provenance() -> None:
    document = _document(state="ROLLING_BACK")
    assert successor._completed_deployment_publish(document, _plan()) is False


def test_completed_candidate_write_provenance_is_detected() -> None:
    plan = _plan()
    document = _document(plan=plan)
    intent = tx.begin_operation(
        document,
        operation_type="deployment_inputs_publish",
        before_fingerprint=str(plan["deployment_before_fingerprint"]),
        intended_after_fingerprint=str(plan["deployment_candidate_fingerprint"]),
        allowed_states={"APPLYING"},
    )
    document = tx.finish_operation(
        intent,
        observed_after_fingerprint=str(plan["deployment_candidate_fingerprint"]),
    )
    assert successor._completed_deployment_publish(document, plan) is True


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


def test_readiness_waits_for_delayed_mqtt_then_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    samples = iter(
        [
            {"state": "WAIT", "reason": "manager_mqtt_socket_not_ready"},
            {"state": "WAIT", "reason": "homeassistant_mqtt_socket_not_ready"},
            {"state": "READY", "manager_mqtt_socket_count": 1, "homeassistant_mqtt_socket_count": 1},
        ]
    )
    monkeypatch.setattr(successor, "_load_f4", lambda: object())
    monkeypatch.setattr(
        successor,
        "mqtt_readiness_sample",
        lambda _module, identity: next(samples),
    )
    clock = _Clock()
    result = successor.wait_readiness(
        identity=object(),
        timeout=10,
        poll=1,
        clock=clock.now,
        sleep=clock.sleep,
    )
    assert result["state"] == "READY"
    assert result["f4_authority"] is True


def test_readiness_never_ready_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(successor, "_load_f4", lambda: object())
    monkeypatch.setattr(
        successor,
        "mqtt_readiness_sample",
        lambda _module, identity: {
            "state": "WAIT",
            "reason": "manager_mqtt_socket_not_ready",
        },
    )
    clock = _Clock()
    with pytest.raises(successor.SuccessorError, match="mqtt_readiness_timeout"):
        successor.wait_readiness(
            identity=object(),
            timeout=3,
            poll=1,
            clock=clock.now,
            sleep=clock.sleep,
        )


def test_manager_duplicate_mqtt_socket_is_fatal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = SimpleNamespace(
        _compose_service_inspect=lambda service: {"Name": f"/{service}"},
        _container_established_socket_count=lambda name, port: 2 if port == 8883 else 1,
    )
    monkeypatch.setattr(
        successor,
        "systemctl",
        lambda mode, _unit: "enabled" if mode == "is-enabled" else "active",
    )
    monkeypatch.setattr(
        successor,
        "_verify_candidate_identity",
        lambda _identity: SimpleNamespace(
            runtime_image_id="sha256:" + "1" * 64
        ),
    )
    monkeypatch.setattr(
        successor.portable,
        "verify_docker_image",
        lambda *_args, **_kwargs: SimpleNamespace(status="VERIFIED"),
    )
    monkeypatch.setattr(
        successor,
        "runtime",
        lambda service: {
            "container_id": service,
            "image_id": (
                "sha256:" + "1" * 64
                if service == "manager"
                else successor.HA_IMAGE_ID
            ),
            "image_ref": (
                successor.TARGET_MANAGER_IMAGE
                if service == "manager"
                else successor.HA_IMAGE
            ),
            "started_at": "start",
            "restart_count": 0,
            "network_mode": "host",
        },
    )
    with pytest.raises(
        successor.SuccessorError,
        match="manager_mqtt_socket_count_invalid",
    ):
        successor.mqtt_readiness_sample(module, identity=object())


def test_post_e03_business_ledger_must_be_fully_closed() -> None:
    with pytest.raises(successor.SuccessorError, match="post_ledger_cardinality_invalid"):
        successor.validate_post_ledger(
            {
                "attempt_count": 1,
                "registration_count": 1,
                "registration_inventory_sha256": successor.PRE_INVENTORY_SHA256,
                "unresolved_count": 1,
                "attempts": [],
            }
        )


def test_apply_ready_orders_gate_before_stop_before_publish_before_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _document(state="READY")
    events: list[str] = []

    class Store:
        def load(self):
            return document

    monkeypatch.setattr(successor, "global_lock", lambda: contextlib.nullcontext())
    monkeypatch.setattr(successor.maintenance, "TransactionStore", lambda _path: Store())
    monkeypatch.setattr(successor.portable, "identity_from_dict", lambda _value: object())
    monkeypatch.setattr(successor, "_runtime_rebind", lambda doc, **_kwargs: _binding())
    monkeypatch.setattr(successor, "_runtime_image_exists", lambda *_args: None)
    monkeypatch.setattr(successor, "_assert_gate_blocking", lambda: events.append("gate-blocking"))
    monkeypatch.setattr(
        successor,
        "_operation",
        lambda _store, doc, *, action, **_kwargs: (
            events.append(action) or doc
        ),
    )
    monkeypatch.setattr(successor, "_save", lambda _store, _before, after: after)
    monkeypatch.setattr(successor, "_broker_continuity", lambda _plan: {})
    monkeypatch.setattr(successor, "render_compose_payload", lambda _payload: {"services": {"manager": {"image": successor.TARGET_MANAGER_IMAGE}}})
    monkeypatch.setattr(successor, "_verify_candidate_identity", lambda _identity: None)
    monkeypatch.setattr(successor, "wait_readiness", lambda **_kwargs: events.append("readiness"))
    monkeypatch.setattr(
        successor,
        "strict_acceptance",
        lambda *_args, **_kwargs: {
            "registration_count": 0,
            "unresolved_count": 0,
            "registration_inventory_sha256": successor.EMPTY_INVENTORY_SHA256,
        },
    )

    result = successor.apply(
        "txn-e03-successor-test-0001",
        "session-apply-ready-0001",
    )
    assert result["stage"] == "COMMITTED"
    assert events[:5] == [
        "activation_gate_install",
        "gate-blocking",
        "service_stop",
        "deployment_inputs_publish",
        "service_start",
    ]
    assert events[5] == "readiness"


def test_apply_verify_phase_resumes_without_stopping_or_republishing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _document(state="VERIFYING")
    events: list[str] = []

    class Store:
        def load(self):
            return document

    monkeypatch.setattr(successor, "global_lock", lambda: contextlib.nullcontext())
    monkeypatch.setattr(successor.maintenance, "TransactionStore", lambda _path: Store())
    monkeypatch.setattr(successor.portable, "identity_from_dict", lambda _value: object())
    monkeypatch.setattr(successor, "_runtime_rebind", lambda doc, **_kwargs: _binding())
    monkeypatch.setattr(successor, "_runtime_image_exists", lambda *_args: None)
    monkeypatch.setattr(
        successor,
        "_operation",
        lambda _store, doc, *, action, **_kwargs: (
            events.append(action) or doc
        ),
    )
    monkeypatch.setattr(successor, "_save", lambda _store, _before, after: after)
    monkeypatch.setattr(successor, "wait_readiness", lambda **_kwargs: events.append("readiness"))
    monkeypatch.setattr(
        successor,
        "strict_acceptance",
        lambda *_args, **_kwargs: {
            "registration_count": 0,
            "unresolved_count": 0,
            "registration_inventory_sha256": successor.EMPTY_INVENTORY_SHA256,
        },
    )

    result = successor.apply(
        "txn-e03-successor-test-0001",
        "session-apply-verifying-0001",
    )
    assert result["stage"] == "COMMITTED"
    assert events == ["service_start", "readiness"]


def test_normal_successor_source_has_no_docker_load_tag_or_rmi() -> None:
    source = Path(successor.__file__).read_text(encoding="utf-8")
    forbidden = (
        '"docker", "load"',
        '"docker", "tag"',
        '"docker", "rmi"',
        "'docker', 'load'",
        "'docker', 'tag'",
        "'docker', 'rmi'",
    )
    assert all(value not in source for value in forbidden)


def test_public_result_marks_real_node_telemetry_not_applicable() -> None:
    document = _document(state="COMMITTED")
    result = successor.public_result(
        document,
        operation="apply",
        reason_code="SUCCESSOR_COMMITTED",
        last_proven_state="TARGET_RUNTIME_ACCEPTED",
        mutation_observed=True,
        recovery_class="COMMITTED",
        extra={"real_node_telemetry": "NOT_APPLICABLE"},
    )
    assert result["real_node_telemetry"] == "NOT_APPLICABLE"
    assert result["replay_allowed"] is False


def _portable_identity() -> successor.portable.PortableImageIdentity:
    rootfs = ("sha256:" + "a" * 64,)
    return successor.portable.PortableImageIdentity(
        schema=successor.portable.SCHEMA,
        representation="docker-save",
        archive_sha256=successor.TARGET_MANAGER_TAR_SHA256,
        archive_size_bytes=123456,
        os="linux",
        architecture="arm64",
        variant=None,
        config_digest=successor.TARGET_CONFIG_DIGEST,
        manifest_digest=None,
        index_digest=None,
        config_semantics_sha256="b" * 64,
        rootfs_diff_ids=rootfs,
        rootfs_diff_ids_sha256=successor.sha_bytes(
            successor.canonical(list(rootfs))
        ),
    )


def test_portable_identity_document_digest_is_exact() -> None:
    identity = _portable_identity()
    encoded = successor._portable_identity_b64(identity)
    digest = successor._portable_identity_sha256(identity)
    assert successor._portable_identity_from_b64(encoded, digest) == identity


def test_portable_identity_tamper_rejected_even_with_frozen_tar_and_config() -> None:
    identity = _portable_identity()
    frozen_digest = successor._portable_identity_sha256(identity)
    document = identity.to_dict()
    document["config_semantics_sha256"] = "c" * 64
    tampered = base64.b64encode(successor.canonical(document)).decode("ascii")
    with pytest.raises(
        successor.SuccessorError,
        match="portable_identity_sha256_mismatch",
    ):
        successor._portable_identity_from_b64(tampered, frozen_digest)


def test_preauthorization_api_rejects_identity_digest_mismatch() -> None:
    identity = _portable_identity()
    with pytest.raises(
        successor.SuccessorError,
        match="portable_identity_sha256_mismatch",
    ):
        successor.preauthorization(
            identity=identity,
            expected_identity_sha256="0" * 64,
            predecessor_sha256="1" * 64,
            expected_host_binding_sha256="2" * 64,
        )


def test_claim_rejects_preauth_plan_drift_before_transaction_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _portable_identity()
    identity_sha = successor._portable_identity_sha256(identity)
    seed = {
        "schema": successor.PLAN_SCHEMA,
        "portable_identity": identity.to_dict(),
        "portable_identity_sha256": identity_sha,
    }
    monkeypatch.setattr(
        successor,
        "runtime_authority",
        lambda: {
            "source_head": "1" * 40,
            "executor_blob": "2" * 40,
            "module_set_sha256": "3" * 64,
        },
    )
    monkeypatch.setattr(successor, "preauthorization", lambda **_kwargs: dict(seed))
    monkeypatch.setattr(
        successor,
        "global_lock",
        lambda: contextlib.nullcontext(),
    )
    with pytest.raises(
        successor.SuccessorError,
        match="preauth_plan_sha256_mismatch",
    ):
        successor.claim(
            identity=identity,
            expected_identity_sha256=identity_sha,
            predecessor_sha256="4" * 64,
            expected_host_binding_sha256="5" * 64,
            expected_preauth_plan_sha256="6" * 64,
            transaction_id="txn-e03-successor-plan-drift-0001",
            authorization_id="N3W_T1_R10_E03_SUCCESSOR_RECOVERY_TEST_0001",
            execution_session_id="session-e03-successor-test-0001",
            confirmation=successor.CONFIRMATION,
        )


def test_active_transaction_scan_uses_strict_transaction_store() -> None:
    source = (
        ROOT
        / "tools"
        / "n3w_t1_r10_e03_successor_recovery.py"
    ).read_text(encoding="utf-8")
    section = source.split(
        "def _active_maintenance_documents()", 1
    )[1].split(
        "def _portable_identity_sha256", 1
    )[0]
    assert "transaction_root_metadata_invalid" in section
    assert "maintenance.TransactionStore(path).load()" in section
    assert "path.read_text" not in section


def _predecessor_document() -> dict[str, object]:
    return {
        "schema": successor.PREDECESSOR_SCHEMA,
        "status": "CLAIMED",
        "phase": "AUTHORIZATION_CLAIMED",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "target_source_head": successor.TARGET_SOURCE_HEAD,
        "target_manager_image": successor.TARGET_MANAGER_IMAGE,
        "target_manager_tar_sha256": successor.TARGET_MANAGER_TAR_SHA256,
        "artifact_id": successor.TARGET_ARTIFACT_ID,
        "artifact_digest_sha256": successor.TARGET_ARTIFACT_SHA256,
        "authorization_id_sha256": "1" * 64,
        "executor_source_head": "2" * 40,
        "executor_blob": "3" * 40,
        "compose_sha256": "4" * 64,
        "compose_render_sha256": "5" * 64,
        "ha_mqtt_sha256": "6" * 64,
        "broker_container_id": "7" * 64,
        "broker_image_id": "sha256:" + "8" * 64,
        "broker_started_at": "2026-10-30T00:00:00Z",
        "broker_restart_count": 0,
        "manager_predecessor_container_id": "9" * 64,
        "services_nrestarts": 0,
    }


def test_predecessor_evidence_binds_host_local_continuity_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "predecessor.json"
    path.write_text(
        __import__("json").dumps(_predecessor_document(), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(successor, "PREDECESSOR_TX", path)
    expected = successor.sha_file(path)
    value = successor.predecessor_evidence(expected)
    assert value["broker_container_id"] == "7" * 64
    assert value["manager_predecessor_container_id"] == "9" * 64
    assert value["services_nrestarts"] == 0


def test_predecessor_evidence_rejects_invalid_runtime_continuity_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _predecessor_document()
    document["broker_container_id"] = "not-a-container-id"
    path = tmp_path / "predecessor.json"
    path.write_text(
        __import__("json").dumps(document, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(successor, "PREDECESSOR_TX", path)
    with pytest.raises(
        successor.SuccessorError,
        match="predecessor_field_invalid:broker_container_id",
    ):
        successor.predecessor_evidence(successor.sha_file(path))


def test_preauth_source_rebinds_old_runtime_continuity() -> None:
    source = (
        ROOT / "tools" / "n3w_t1_r10_e03_successor_recovery.py"
    ).read_text(encoding="utf-8")
    section = source.split("def preauthorization(", 1)[1].split(
        "def _execution_session_id", 1
    )[0]
    assert "manager_predecessor_continuity_drift" in section
    assert "broker_predecessor_continuity_drift" in section
    assert "services_owner_restart_continuity_drift" in section
    assert 'predecessor["manager_predecessor_container_id"]' in section
    assert 'predecessor["services_nrestarts"]' in section


def _rolling_back_document() -> dict[str, object]:
    plan = _plan()
    document = _document(state="APPLYING", plan=plan)
    publish = tx.begin_operation(
        document,
        operation_type="deployment_inputs_publish",
        before_fingerprint=str(plan["deployment_before_fingerprint"]),
        intended_after_fingerprint=str(plan["deployment_candidate_fingerprint"]),
        allowed_states={"APPLYING"},
    )
    document = tx.finish_operation(
        publish,
        observed_after_fingerprint=str(plan["deployment_candidate_fingerprint"]),
    )
    document = tx.transition(
        document,
        "VERIFYING",
        operation="candidate_published_owner_controlled",
        observed_after={
            "deployment_inputs": str(plan["deployment_candidate_fingerprint"])
        },
    )
    return tx.transition(
        document,
        "ROLLING_BACK",
        operation="rollback_begin",
        reason="test",
    )


def test_ready_failure_can_be_persisted_as_blocked(tmp_path: Path) -> None:
    document = _document(state="READY")
    store = _store(tmp_path, document)
    blocked = successor._block(store, document, reason="gate_install_failed")
    assert blocked["state"] == "BLOCKED"
    assert store.load()["state"] == "BLOCKED"


def test_rollback_becomes_terminal_only_after_runtime_start_and_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _rolling_back_document()
    store = _store(tmp_path, document)
    plan = _plan()
    reality = {
        "service": "5" * 64,
        "deployment": str(plan["deployment_candidate_fingerprint"]),
    }

    monkeypatch.setattr(
        successor,
        "_runtime_rebind",
        lambda *_args, **_kwargs: _binding(),
    )
    monkeypatch.setattr(
        successor,
        "_service_fingerprint",
        lambda: reality["service"],
    )
    monkeypatch.setattr(
        successor,
        "_stop_services",
        lambda: reality.__setitem__("service", "4" * 64),
    )
    monkeypatch.setattr(successor, "_broker_continuity", lambda _plan: {})
    monkeypatch.setattr(
        successor,
        "_deployment_reality",
        lambda _plan: reality["deployment"],
    )
    monkeypatch.setattr(
        successor,
        "_restore_deployment_env",
        lambda _plan: reality.__setitem__("deployment", str(plan["deployment_before_fingerprint"])),
    )

    def gate_restored() -> None:
        current = store.load()
        assert current["state"] == "ROLLING_BACK"
        assert any(
            item["operation_type"] == "deployment_inputs_rollback"
            and item["status"] == "COMPLETE"
            and item["observed_after_fingerprint"] == str(plan["deployment_before_fingerprint"])
            for item in current["operations"]
        )

    monkeypatch.setattr(
        successor,
        "_assert_gate_rollback_restored",
        gate_restored,
    )
    monkeypatch.setattr(
        successor,
        "_runtime_image_exists",
        lambda *_args, **_kwargs: None,
    )

    def start_services() -> None:
        assert store.load()["state"] == "ROLLING_BACK"
        reality["service"] = "5" * 64

    monkeypatch.setattr(successor, "_start_services", start_services)

    def runtime(service: str):
        if service == "manager":
            return {
                "image_ref": successor.OLD_MANAGER_IMAGE,
                "image_id": successor.OLD_MANAGER_ID,
                "network_mode": "host",
                "restart_count": 0,
            }
        if service == "homeassistant":
            return {
                "image_ref": successor.HA_IMAGE,
                "image_id": successor.HA_IMAGE_ID,
                "network_mode": "host",
                "restart_count": 0,
            }
        raise AssertionError(service)

    monkeypatch.setattr(successor, "runtime", runtime)

    result = successor.rollback(
        "txn-e03-successor-test-0001",
        reason="test",
        execution_session_id=None,
        _store=store,
        _document=document,
    )

    assert result["status"] == "PASS"
    assert result["recovery_class"] == "ROLLED_BACK"
    assert store.load()["state"] == "ROLLED_BACK"


def test_direct_rollback_unknown_reality_persists_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _rolling_back_document()
    store = _store(tmp_path, document)
    monkeypatch.setattr(
        successor,
        "_runtime_rebind",
        lambda *_args, **_kwargs: _binding(),
    )
    monkeypatch.setattr(successor, "_service_fingerprint", lambda: "9" * 64)

    result = successor.rollback(
        "txn-e03-successor-test-0001",
        reason="test",
        execution_session_id=None,
        _store=store,
        _document=document,
    )

    assert result["status"] == "STOP"
    assert result["recovery_class"] == "BLOCKED_ROLLBACK_UNPROVEN"
    assert store.load()["state"] == "BLOCKED"


def test_readiness_rejects_disabled_application_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        successor,
        "systemctl",
        lambda mode, _unit: "disabled" if mode == "is-enabled" else "active",
    )
    with pytest.raises(
        successor.SuccessorError,
        match="services_owner_enablement_drift",
    ):
        successor.mqtt_readiness_sample(object(), identity=object())


def test_readiness_verifies_running_manager_by_portable_content_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = SimpleNamespace(
        _compose_service_inspect=lambda service: {"Name": f"/{service}"},
        _container_established_socket_count=lambda _name, _port: 1,
    )
    monkeypatch.setattr(
        successor,
        "systemctl",
        lambda mode, _unit: "enabled" if mode == "is-enabled" else "active",
    )
    monkeypatch.setattr(
        successor,
        "_verify_candidate_identity",
        lambda _identity: SimpleNamespace(
            runtime_image_id="sha256:" + "a" * 64
        ),
    )
    observed_refs: list[str] = []

    def verify_running(_identity, reference, **_kwargs):
        observed_refs.append(reference)
        return SimpleNamespace(status="MISMATCH")

    monkeypatch.setattr(
        successor.portable,
        "verify_docker_image",
        verify_running,
    )
    monkeypatch.setattr(
        successor,
        "runtime",
        lambda service: {
            "container_id": service,
            "image_id": (
                "sha256:" + "b" * 64
                if service == "manager"
                else successor.HA_IMAGE_ID
            ),
            "image_ref": (
                successor.TARGET_MANAGER_IMAGE
                if service == "manager"
                else successor.HA_IMAGE
            ),
            "started_at": "start",
            "restart_count": 0,
            "network_mode": "host",
        },
    )
    with pytest.raises(
        successor.SuccessorError,
        match="manager_running_portable_identity_mismatch",
    ):
        successor.mqtt_readiness_sample(module, identity=object())
    assert observed_refs == ["sha256:" + "b" * 64]

def test_post_ledger_requires_hardware_session_and_expiry_proof() -> None:
    attempt = {
        "pairing_id_sha256": successor.PAIRING_SHA256,
        "hardware_id_sha256": successor.HARDWARE_SHA256,
        "state": "EXPIRED",
        "phase": "TERMINAL",
        "cleanup_state": "COMPLETE",
        "node_id_present": False,
        "terminal_at_present": True,
        "terminal_reason": "expired",
        "expired_by_clock": True,
        "session_state": "expired",
        "session_reason": "expired",
        "session_hardware_sha256": successor.HARDWARE_SHA256,
        "registration_match_count": 0,
        "current_pairing_matches": False,
        "registration_node_id_present": False,
        "pairing_credential_count": 0,
        "hardware_credential_history_count": 0,
    }
    document = {
        "attempt_count": 1,
        "registration_count": 0,
        "registration_inventory_sha256": successor.EMPTY_INVENTORY_SHA256,
        "unresolved_count": 0,
        "attempts": [attempt],
    }
    successor.validate_post_ledger(document)
    changed = __import__("copy").deepcopy(document)
    changed["attempts"][0]["session_hardware_sha256"] = "0" * 64
    with pytest.raises(successor.SuccessorError, match="post_ledger_state_invalid"):
        successor.validate_post_ledger(changed)
    changed = __import__("copy").deepcopy(document)
    changed["attempts"][0]["expired_by_clock"] = False
    with pytest.raises(successor.SuccessorError, match="post_ledger_state_invalid"):
        successor.validate_post_ledger(changed)


def _strong_snapshot() -> dict[str, object]:
    runtimes = {
        "broker": {
            "container_id": "broker-id",
            "started_at": "broker-start",
            "restart_count": 0,
        },
        "manager": {
            "container_id": "manager-id",
            "started_at": "manager-start",
            "restart_count": 0,
        },
        "homeassistant": {
            "container_id": "ha-id",
            "started_at": "ha-start",
            "restart_count": 0,
        },
    }
    return {
        "schema": successor.RUNTIME_SNAPSHOT_SCHEMA,
        "status": "PASS",
        "boot_id_sha256": "1" * 64,
        "source_head": "2" * 40,
        "control_manifest_sha256": "3" * 64,
        "systemd_state_sha256": "4" * 64,
        "critical_errors_sha256": "5" * 64,
        "homeassistant_http_ready": True,
        "containers": {
            name: {
                "identity_sha256": successor.sha_bytes(
                    successor.canonical([
                        item["container_id"],
                        item["started_at"],
                    ])
                ),
                "restart_count": 0,
                "running": True,
            }
            for name, item in runtimes.items()
        },
        "runtime_service_auth": {
            "manager": {
                "authenticated": True,
                "endpoint_port": 8883,
                "identity_sha256": "6" * 64,
                "owned_socket_count": 1,
                "owned_socket_sha256": "7" * 64,
                "authenticated_connection_sha256": "8" * 64,
            },
            "homeassistant": {
                "authenticated": True,
                "endpoint_port": 1883,
                "identity_sha256": "9" * 64,
                "owned_socket_count": 1,
                "owned_socket_sha256": "a" * 64,
                "authenticated_connection_sha256": "b" * 64,
            },
        },
    }


def test_authenticated_runtime_snapshot_rebinds_container_and_auth_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _strong_snapshot()
    module = SimpleNamespace(runtime_snapshot=lambda: snapshot)
    monkeypatch.setattr(successor, "_load_f4_reboot_verify", lambda: module)

    runtimes = {
        "broker": {
            "container_id": "broker-id",
            "started_at": "broker-start",
            "restart_count": 0,
        },
        "manager": {
            "container_id": "manager-id",
            "started_at": "manager-start",
            "restart_count": 0,
        },
        "homeassistant": {
            "container_id": "ha-id",
            "started_at": "ha-start",
            "restart_count": 0,
        },
    }
    monkeypatch.setattr(successor, "runtime", lambda service: runtimes[service])
    assert successor._authenticated_runtime_snapshot() == snapshot

    snapshot["runtime_service_auth"]["manager"]["authenticated"] = False
    with pytest.raises(
        successor.SuccessorError,
        match="authenticated_runtime_service_invalid:manager",
    ):
        successor._authenticated_runtime_snapshot()


def test_auth_probe_contract_cannot_claim_live_auth_from_partial_probe() -> None:
    with pytest.raises(
        successor.SuccessorError,
        match="broker_auth_probe_contract_invalid",
    ):
        successor._validate_auth_probe(
            {
                "manager_wrong_client_id_rejected": True,
                "provisioning_wrong_client_id_rejected": True,
                "homeassistant_wrong_client_id_rejected": True,
                "anonymous_rejected": True,
                "provisioning_exact_credential_auth": False,
            }
        )


def _closed_post_ledger() -> dict[str, object]:
    return {
        "attempt_count": 1,
        "registration_count": 0,
        "registration_inventory_sha256": successor.EMPTY_INVENTORY_SHA256,
        "unresolved_count": 0,
        "attempts": [{
            "pairing_id_sha256": successor.PAIRING_SHA256,
            "hardware_id_sha256": successor.HARDWARE_SHA256,
            "state": "EXPIRED",
            "phase": "TERMINAL",
            "cleanup_state": "COMPLETE",
            "node_id_present": False,
            "terminal_at_present": True,
            "terminal_reason": "expired",
            "expired_by_clock": True,
            "session_state": "expired",
            "session_reason": "expired",
            "session_hardware_sha256": successor.HARDWARE_SHA256,
            "registration_match_count": 0,
            "current_pairing_matches": False,
            "registration_node_id_present": False,
            "pairing_credential_count": 0,
            "hardware_credential_history_count": 0,
        }],
    }


def _strict_acceptance_fixture(
    monkeypatch: pytest.MonkeyPatch,
    snapshots: list[dict[str, object]],
) -> dict[str, object]:
    plan = _plan()
    auth_probe = {
        "manager_wrong_client_id_rejected": True,
        "provisioning_wrong_client_id_rejected": True,
        "homeassistant_wrong_client_id_rejected": True,
        "anonymous_rejected": True,
        "provisioning_exact_credential_auth": True,
    }
    module = SimpleNamespace(
        _homeassistant_http_readiness=lambda: {"status": "PASS"},
        _broker_auth_negative_and_provisioning_probe=lambda _image: dict(auth_probe),
    )
    monkeypatch.setattr(successor, "_load_f4", lambda: module)
    monkeypatch.setattr(
        successor,
        "mqtt_readiness_sample",
        lambda *_args, **_kwargs: {"state": "READY"},
    )
    monkeypatch.setattr(
        successor,
        "_application_owner_acceptance",
        lambda _plan: {
            "active": "active",
            "enabled": "enabled",
            "manager_count": 1,
            "homeassistant_count": 1,
            "nrestarts": 0,
        },
    )
    runtimes = {
        "manager": {
            "container_id": "manager-new",
            "started_at": "manager-start",
            "restart_count": 0,
        },
        "homeassistant": {
            "container_id": "ha-id",
            "started_at": "ha-start",
            "restart_count": 0,
        },
    }
    monkeypatch.setattr(successor, "runtime", lambda service: runtimes[service])
    monkeypatch.setattr(
        successor,
        "_broker_continuity",
        lambda _plan: {
            "container_id": "broker-id",
            "started_at": "broker-start",
            "restart_count": 0,
        },
    )
    monkeypatch.setattr(
        successor,
        "ha_mqtt_hash",
        lambda: str(plan["ha_mqtt_sha256"]),
    )
    monkeypatch.setattr(
        successor,
        "ledger_in_manager",
        lambda _manager: (_closed_post_ledger(), {}),
    )
    stream = iter(snapshots)
    monkeypatch.setattr(
        successor,
        "_authenticated_runtime_snapshot",
        lambda: next(stream),
    )
    return plan


def test_strict_acceptance_rejects_authenticated_session_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _strong_snapshot()
    final = __import__("copy").deepcopy(first)
    final["runtime_service_auth"]["manager"]["owned_socket_sha256"] = "c" * 64
    plan = _strict_acceptance_fixture(monkeypatch, [first, final])
    with pytest.raises(
        successor.SuccessorError,
        match="authenticated_runtime_evidence_changed",
    ):
        successor.strict_acceptance(
            plan,
            identity=object(),
            stability_seconds=0,
        )


def test_strict_acceptance_reports_authenticated_contract_only_after_strong_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _strong_snapshot()
    plan = _strict_acceptance_fixture(
        monkeypatch,
        [snapshot, __import__("copy").deepcopy(snapshot)],
    )
    result = successor.strict_acceptance(
        plan,
        identity=object(),
        stability_seconds=0,
    )
    assert result["status"] == "PASS"
    assert result["manager_authenticated_mqtt_session"] is True
    assert result["homeassistant_authenticated_mqtt_session"] is True
    assert result["process_socket_ownership"] is True
    assert result["application_owner_stable"] is True
    assert result["real_node_telemetry"] == "NOT_APPLICABLE"


def test_global_maintenance_lock_is_nonblocking_and_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "maintenance"
    root.mkdir(mode=0o700)
    lock_path = root / ".maintenance.lock"
    monkeypatch.setattr(successor, "MAINTENANCE_ROOT", root)
    monkeypatch.setattr(successor, "LOCK_PATH", lock_path)
    monkeypatch.setattr(successor, "_ensure_private_dir", lambda _path: None)
    monkeypatch.setattr(successor.os, "fchown", lambda *_args: None)
    calls: list[int] = []

    def fake_flock(_fd: int, operation: int) -> None:
        calls.append(operation)
        if operation & successor.fcntl.LOCK_EX:
            assert operation & successor.fcntl.LOCK_NB
            raise BlockingIOError()

    monkeypatch.setattr(successor.fcntl, "flock", fake_flock)
    with pytest.raises(
        successor.SuccessorError,
        match="maintenance_lock_busy",
    ):
        with successor.global_lock():
            pytest.fail("busy lock must not enter mutation scope")
    assert successor._LOCK_DEPTH == 0
    assert any(op & successor.fcntl.LOCK_NB for op in calls)


def test_successor_target_release_binding_uses_common_production_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _portable_identity()
    captured = {}

    def common_binding(**kwargs):
        captured.update(kwargs)
        return "e" * 64

    monkeypatch.setattr(
        successor.production_contract,
        "portable_deployment_binding_id_v2",
        common_binding,
    )
    result = successor._target_release_id(
        identity,
        "f" * 64,
        "a" * 64,
        {
            "execstart_sha256": "1" * 64,
            "execstop_sha256": "2" * 64,
        },
    )
    assert result == "e" * 64
    assert captured["identity"] == identity
    assert captured["artifact_sha256"] == successor.TARGET_ARTIFACT_SHA256
    assert captured["deployment_inputs"] == {
        "compose_sha256": "f" * 64,
        "compose_env_sha256": "a" * 64,
    }


def test_successor_module_authority_includes_production_contract_source() -> None:
    source = (
        ROOT / "tools" / "n3w_t1_r10_e03_successor_recovery.py"
    ).read_text(encoding="utf-8")
    runtime_section = source.split("def runtime_authority()", 1)[1].split(
        "def _gate_source_bytes", 1
    )[0]
    assert "n3w_t1_production_v2_contract.py" in runtime_section
    target_section = source.split("def _target_release_id(", 1)[1].split(
        "def ", 1
    )[0]
    assert "production_contract.portable_deployment_binding_id_v2" in target_section
    assert "gh.n3w-r10-e03-target-release-binding/1" not in target_section


def test_build_identity_requires_exact_tar_size_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_identity = _portable_identity()
    captured = {}

    def parse(_path, **kwargs):
        captured.update(kwargs)
        return image_identity

    monkeypatch.setattr(successor.portable, "parse_image_archive", parse)
    result = successor.build_identity(
        Path("/tmp/exact-manager.tar"),
        expected_archive_size_bytes=image_identity.archive_size_bytes,
    )
    assert result["status"] == "PASS"
    assert result["archive_size_bytes"] == image_identity.archive_size_bytes
    assert captured["expected_archive_sha256"] == successor.TARGET_MANAGER_TAR_SHA256
    assert (
        captured["expected_archive_size_bytes"]
        == image_identity.archive_size_bytes
    )


@pytest.mark.parametrize("size", [0, -1, True])
def test_build_identity_rejects_invalid_tar_size_authority(size) -> None:
    with pytest.raises(
        successor.SuccessorError,
        match="artifact_tar_size_authority_invalid",
    ):
        successor.build_identity(
            Path("/tmp/exact-manager.tar"),
            expected_archive_size_bytes=size,
        )


def test_exact_artifact_producer_freezes_and_rechecks_tar_sizes() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "n3w-t1-fresh-install-exact-arm64-ci.yml"
    ).read_text(encoding="utf-8")
    for name in (
        "greenhouse-manager-arm64.tar",
        "homeassistant-arm64.tar",
        "broker-arm64.tar",
    ):
        assert f'(root / "{name}").stat().st_size' in workflow
    assert workflow.count('"tar_size_bytes"') >= 3


def test_gate_fingerprint_requires_systemd_loaded_execcondition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helper = tmp_path / "n3w-t1-maintenance-activation-gate"
    dropin = tmp_path / "90-n3w-maintenance-gate.conf"
    helper_bytes = b"#!/usr/bin/env python3\n"
    helper.write_bytes(helper_bytes)
    dropin.write_bytes(successor.GATE_DROPIN_BYTES)
    monkeypatch.setattr(successor, "GATE_TARGET", helper)
    monkeypatch.setattr(successor, "GATE_DROPIN", dropin)
    monkeypatch.setattr(successor, "_gate_source_bytes", lambda: helper_bytes)

    expected, _state = successor._expected_gate_after()

    monkeypatch.setattr(
        successor,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=b""),
    )
    assert successor._gate_fingerprint() != expected

    monkeypatch.setattr(
        successor,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout=(str(helper) + "\n").encode()
        ),
    )
    assert successor._gate_fingerprint() == expected


def test_claim_rechecks_preauth_inside_global_maintenance_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _portable_identity()
    identity_sha = successor._portable_identity_sha256(identity)
    state = {"locked": False, "preauth_called": False}

    @contextlib.contextmanager
    def lock():
        assert state["locked"] is False
        state["locked"] = True
        try:
            yield
        finally:
            state["locked"] = False

    seed = {
        "schema": successor.PLAN_SCHEMA,
        "portable_identity": identity.to_dict(),
        "portable_identity_sha256": identity_sha,
    }

    def preauth(**_kwargs):
        assert state["locked"] is True
        state["preauth_called"] = True
        return dict(seed)

    monkeypatch.setattr(successor, "global_lock", lock)
    monkeypatch.setattr(successor, "preauthorization", preauth)
    monkeypatch.setattr(
        successor,
        "runtime_authority",
        lambda: {
            "source_head": "1" * 40,
            "executor_blob": "2" * 40,
            "module_set_sha256": "3" * 64,
        },
    )
    with pytest.raises(
        successor.SuccessorError,
        match="preauth_plan_sha256_mismatch",
    ):
        successor.claim(
            identity=identity,
            expected_identity_sha256=identity_sha,
            predecessor_sha256="4" * 64,
            expected_host_binding_sha256="5" * 64,
            expected_preauth_plan_sha256="6" * 64,
            transaction_id="txn-e03-successor-lock-rebind-0001",
            authorization_id="N3W_T1_R10_E03_SUCCESSOR_RECOVERY_TEST_0002",
            execution_session_id="session-e03-successor-lock-test-0001",
            confirmation=successor.CONFIRMATION,
        )
    assert state["preauth_called"] is True
    assert state["locked"] is False


def test_runtime_rebind_recomputes_source_and_target_release_authority() -> None:
    source = (
        ROOT / "tools" / "n3w_t1_r10_e03_successor_recovery.py"
    ).read_text(encoding="utf-8")
    section = source.split("def _runtime_rebind(", 1)[1].split(
        "def _operation(", 1
    )[0]
    assert "unit = verify_service_unit()" in section
    assert "source_release_id = _current_release_id(" in section
    assert "target_release_id = _target_release_id(" in section
    assert "source_release_id != binding.current_release_id" in section
    assert "target_release_id != binding.target_release_id" in section


def _fresh_product_compose() -> bytes:
    return b"""services:
  broker:
    image: local/n3w-mosquitto:2.1.2-3184566d
  manager:
    image: "${GH_MANAGER_IMAGE:?GH_MANAGER_IMAGE required}"
    pull_policy: never
    user: "999:999"
  homeassistant:
    image: local/n3w-homeassistant:2026.10.0-0c73235a
"""


def test_kf137_fresh_product_manager_image_indirection_is_supported() -> None:
    successor.validate_manager_image_indirection(_fresh_product_compose())


def test_kf137_manager_image_env_rewrite_changes_only_exact_authority() -> None:
    before = (
        b"GH_SYSTEM_ID=gh-test\n"
        + f"GH_MANAGER_IMAGE={successor.OLD_MANAGER_IMAGE}\n".encode()
        + b"GH_MQTT_PASSWORD_FILE=/run/secrets/password\n"
    )
    after = successor.rewrite_manager_image_env(before)
    assert after == (
        b"GH_SYSTEM_ID=gh-test\n"
        + f"GH_MANAGER_IMAGE={successor.TARGET_MANAGER_IMAGE}\n".encode()
        + b"GH_MQTT_PASSWORD_FILE=/run/secrets/password\n"
    )


def test_kf137_manager_image_env_rewrite_rejects_duplicate_authority() -> None:
    before = (
        f"GH_MANAGER_IMAGE={successor.OLD_MANAGER_IMAGE}\n"
        f"export GH_MANAGER_IMAGE={successor.OLD_MANAGER_IMAGE}\n"
    ).encode()
    with pytest.raises(
        successor.SuccessorError,
        match="compose_env_manager_image_count_invalid",
    ):
        successor.rewrite_manager_image_env(before)


def test_kf137_literal_manager_image_is_not_silently_reinterpreted() -> None:
    literal = _fresh_product_compose().replace(
        b'image: "${GH_MANAGER_IMAGE:?GH_MANAGER_IMAGE required}"',
        f"image: {successor.OLD_MANAGER_IMAGE}".encode(),
    )
    with pytest.raises(
        successor.SuccessorError,
        match="manager_image_indirection_invalid",
    ):
        successor.validate_manager_image_indirection(literal)


def test_deployment_reality_binds_compose_and_compose_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compose = tmp_path / "docker-compose.yml"
    compose_env = tmp_path / "docker-compose.env"
    compose.write_bytes(_fresh_product_compose())
    compose_env.write_text(
        f"GH_MANAGER_IMAGE={successor.OLD_MANAGER_IMAGE}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(successor, "COMPOSE", compose)
    monkeypatch.setattr(successor, "COMPOSE_ENV", compose_env)
    before = successor._deployment_reality({})
    compose_env.write_text(
        f"GH_MANAGER_IMAGE={successor.TARGET_MANAGER_IMAGE}\n",
        encoding="utf-8",
    )
    after = successor._deployment_reality({})
    assert before != after
    compose.write_bytes(_fresh_product_compose() + b"\n")
    assert successor._deployment_reality({}) != after


def test_source_repair_uses_portable_deployment_binding_v2() -> None:
    source = (
        ROOT / "tools" / "n3w_t1_r10_e03_successor_recovery.py"
    ).read_text(encoding="utf-8")
    assert "portable_deployment_binding_id_v2(" in source
    assert '"compose_env_before_sha256"' in source
    assert '"compose_env_candidate_sha256"' in source
    assert '"deployment_inputs"' in source
    assert "rewrite_manager_image(" not in source
