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
        "compose_before_sha256": "1" * 64,
        "compose_candidate_sha256": "2" * 64,
        "compose_candidate_b64": base64.b64encode(b"candidate-compose").decode("ascii"),
        "compose_before_b64": base64.b64encode(b"before-compose").decode("ascii"),
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
        before={"compose": str(value["compose_before_sha256"])},
        intended_after={"compose": str(value["compose_candidate_sha256"])},
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
            observed_after={"compose": str(value["compose_candidate_sha256"])},
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
            observed_after={"compose": str(value["compose_before_sha256"])},
        )
    if state == "COMMITTED":
        document = tx.transition(
            document,
            "COMMITTED",
            operation="runtime_acceptance_pass",
            observed_after={"compose": str(value["compose_candidate_sha256"])},
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
        action="compose_publish",
        operation_type="compose_publish",
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
        operation_type="compose_publish",
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
        action="compose_publish",
        operation_type="compose_publish",
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
            action="compose_publish",
            operation_type="compose_publish",
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
        operation_type="compose_publish",
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
        action="compose_publish",
        operation_type="compose_publish",
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
        "_compose_reality",
        lambda _plan: pytest.fail("compose must not even be read for publish"),
    )
    with pytest.raises(successor.BlockedError, match="candidate_owner_not_controlled"):
        successor._publish_candidate(plan)


def test_rollback_requires_completed_candidate_write_provenance() -> None:
    document = _document(state="ROLLING_BACK")
    assert successor._completed_compose_publish(document, _plan()) is False


def test_completed_candidate_write_provenance_is_detected() -> None:
    document = _document()
    intent = tx.begin_operation(
        document,
        operation_type="compose_publish",
        before_fingerprint="1" * 64,
        intended_after_fingerprint="2" * 64,
        allowed_states={"APPLYING"},
    )
    document = tx.finish_operation(intent, observed_after_fingerprint="2" * 64)
    assert successor._completed_compose_publish(document, _plan()) is True


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
    monkeypatch.setattr(successor, "systemctl", lambda *_args: "active")
    monkeypatch.setattr(successor, "_verify_candidate_identity", lambda _identity: None)
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
        "compose_publish",
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
