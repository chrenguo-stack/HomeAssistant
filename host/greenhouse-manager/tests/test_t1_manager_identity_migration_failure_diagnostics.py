from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_manager_identity_migration_failure_diagnostics import (
    FAILURE_FILE,
    ROLLBACK_FAILURE_FILE,
    StageAwareManagerDriver,
    StageAwareTransactionAdapters,
    TransactionStageRecorder,
    build_failure_diagnostic,
)


def _private_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "transaction-test"
    workspace.mkdir(mode=0o700)
    return workspace


def _write_private_json(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o600)


class FakeDriver:
    def __init__(self, *, fail_stage: str | None = None) -> None:
        self.fail_stage = fail_stage

    def _step(self, stage: str) -> None:
        if self.fail_stage == stage:
            raise RuntimeError("secret=password token=do-not-persist")

    def recreate_manager(
        self,
        *,
        environment_file: Path,
        password_file: Path,
        overlay_file: Path,
    ) -> None:
        del environment_file, password_file, overlay_file
        self._step("manager_recreate")

    def verify_authenticated_identity(self, username: str, client_id: str) -> None:
        del username, client_id
        self._step("authenticated_identity")

    def verify_ingress_subscription(self) -> None:
        self._step("ingress_subscription")

    def verify_canonical_publication(self) -> None:
        self._step("canonical_publication")

    def verify_availability_publication(self) -> None:
        self._step("availability_publication")

    def verify_discovery_publication(self) -> None:
        self._step("discovery_publication")

    def verify_reconnect(self) -> None:
        self._step("reconnect")

    def verify_existing_entities(self) -> None:
        self._step("existing_entities")

    def postactivation_audit(self) -> dict[str, object]:
        self._step("postactivation_audit")
        return {"ok": True}

    def recreate_after_rollback(self) -> None:
        self._step("rollback_manager_recreate")

    def verify_legacy_anonymous_path(self) -> None:
        self._step("rollback_anonymous_path")


class FakeAdapters:
    def __init__(self, *, fail_stage: str | None = None) -> None:
        self.fail_stage = fail_stage
        self.mutation_started = False

    def _step(self, stage: str) -> dict[str, object]:
        if self.fail_stage == stage:
            raise RuntimeError("secret=adapter-password")
        return {"stage": stage}

    def prepare(self) -> dict[str, object]:
        return self._step("adapter_prepare")

    def mutation_executor(self) -> dict[str, object]:
        self.mutation_started = True
        return self._step("mutation_pipeline")

    def postactivation_auditor(self) -> dict[str, object]:
        return self._step("postactivation_pipeline")

    def rollback_executor(self) -> dict[str, object]:
        return self._step("rollback_pipeline")


def test_driver_failure_records_stage_without_message_or_secret(tmp_path: Path) -> None:
    workspace = _private_workspace(tmp_path)
    recorder = TransactionStageRecorder(workspace)
    driver = StageAwareManagerDriver(
        FakeDriver(fail_stage="canonical_publication"),
        recorder,
    )

    with pytest.raises(RuntimeError, match="do-not-persist"):
        driver.verify_canonical_publication()

    diagnostic = json.loads((workspace / FAILURE_FILE).read_text(encoding="utf-8"))
    serialized = json.dumps(diagnostic, sort_keys=True)

    assert diagnostic["failed_stage"] == "canonical_publication"
    assert diagnostic["failure_code"] == "M2_MANAGER_CANONICAL_PUBLICATION_FAILED"
    assert diagnostic["exception_class"] == "RuntimeError"
    assert diagnostic["exception_message_included"] is False
    assert diagnostic["secret_values_included"] is False
    assert diagnostic["path_values_redacted"] is True
    assert "password" not in serialized
    assert "do-not-persist" not in serialized
    assert (workspace / FAILURE_FILE).stat().st_mode & 0o777 == 0o600

    driver.recreate_after_rollback()
    driver.verify_legacy_anonymous_path()

    unchanged = json.loads((workspace / FAILURE_FILE).read_text(encoding="utf-8"))
    assert unchanged == diagnostic
    assert not (workspace / ROLLBACK_FAILURE_FILE).exists()


def test_driver_diagnostic_retains_allowlisted_probe_subfailure(
    tmp_path: Path,
) -> None:
    workspace = _private_workspace(tmp_path)
    recorder = TransactionStageRecorder(workspace)

    class ProbeFailureDriver(FakeDriver):
        def verify_authenticated_identity(
            self,
            username: str,
            client_id: str,
        ) -> None:
            del username, client_id
            raise ManagerProductionRuntimeProbeError(
                "secret=must-not-persist",
                failure_code=(
                    ManagerRuntimeProbeFailureCode.MQTT_SOCKET_APPEARANCE_TIMED_OUT
                ),
            )

    driver = StageAwareManagerDriver(ProbeFailureDriver(), recorder)

    with pytest.raises(ManagerProductionRuntimeProbeError):
        driver.verify_authenticated_identity("manager", "client")

    diagnostic = json.loads((workspace / FAILURE_FILE).read_text(encoding="utf-8"))
    serialized = json.dumps(diagnostic, sort_keys=True)

    assert diagnostic["failure_code"] == "M2_MANAGER_IDENTITY_BINDING_FAILED"
    assert (
        diagnostic["probe_failure_code"]
        == "mqtt_socket_appearance_timed_out"
    )
    assert diagnostic["exception_message_included"] is False
    assert "must-not-persist" not in serialized


def test_rollback_failure_is_separate_from_primary_failure(tmp_path: Path) -> None:
    workspace = _private_workspace(tmp_path)
    recorder = TransactionStageRecorder(workspace)
    primary = StageAwareManagerDriver(
        FakeDriver(fail_stage="authenticated_identity"),
        recorder,
    )

    with pytest.raises(RuntimeError):
        primary.verify_authenticated_identity("manager", "client")

    rollback = StageAwareManagerDriver(
        FakeDriver(fail_stage="rollback_manager_recreate"),
        recorder,
    )

    with pytest.raises(RuntimeError):
        rollback.recreate_after_rollback()

    primary_document = json.loads(
        (workspace / FAILURE_FILE).read_text(encoding="utf-8")
    )
    rollback_document = json.loads(
        (workspace / ROLLBACK_FAILURE_FILE).read_text(encoding="utf-8")
    )

    assert primary_document["failed_stage"] == "authenticated_identity"
    assert rollback_document["failed_stage"] == "rollback_manager_recreate"
    assert rollback_document["rollback_failure"] is True
    assert rollback_document["failure_code"] == "M2_MANAGER_ROLLBACK_RECREATE_FAILED"


def test_adapter_wrapper_records_broad_fallback_stage(tmp_path: Path) -> None:
    workspace = _private_workspace(tmp_path)
    recorder = TransactionStageRecorder(workspace)
    adapters = StageAwareTransactionAdapters(
        FakeAdapters(fail_stage="mutation_pipeline"),
        recorder,
    )

    with pytest.raises(RuntimeError):
        adapters.mutation_executor()

    diagnostic = json.loads((workspace / FAILURE_FILE).read_text(encoding="utf-8"))

    assert adapters.mutation_started is True
    assert diagnostic["failed_stage"] == "mutation_pipeline"
    assert diagnostic["failure_code"] == "M2_MANAGER_MUTATION_PIPELINE_FAILED"


def test_specific_driver_failure_is_not_overwritten_by_pipeline_wrapper(
    tmp_path: Path,
) -> None:
    workspace = _private_workspace(tmp_path)
    recorder = TransactionStageRecorder(workspace)
    driver = StageAwareManagerDriver(
        FakeDriver(fail_stage="discovery_publication"),
        recorder,
    )

    class DriverBackedAdapters(FakeAdapters):
        def mutation_executor(self) -> dict[str, object]:
            self.mutation_started = True
            driver.verify_discovery_publication()
            return {"ok": True}

    adapters = StageAwareTransactionAdapters(DriverBackedAdapters(), recorder)

    with pytest.raises(RuntimeError):
        adapters.mutation_executor()

    diagnostic = json.loads((workspace / FAILURE_FILE).read_text(encoding="utf-8"))

    assert diagnostic["failed_stage"] == "discovery_publication"
    assert diagnostic["failure_code"] == "M2_MANAGER_DISCOVERY_PUBLICATION_FAILED"


def test_read_only_diagnostic_reports_rollback_terminal_state(tmp_path: Path) -> None:
    workspace = _private_workspace(tmp_path)
    recorder = TransactionStageRecorder(workspace)
    driver = StageAwareManagerDriver(
        FakeDriver(fail_stage="reconnect"),
        recorder,
    )

    with pytest.raises(RuntimeError):
        driver.verify_reconnect()

    _write_private_json(
        workspace / "journal.json",
        {
            "schema": "gh.m2.t1-manager-identity-production-journal/1",
            "phase": "rollback_completed",
        },
    )

    report = build_failure_diagnostic(workspace)

    assert report == {
        "schema": "gh.m2.t1-manager-identity-failure-diagnostic/1",
        "transaction_phase": "rollback_completed",
        "failure_stage_available": True,
        "rollback_failure_stage_available": False,
        "rollback_completed": True,
        "rollback_terminal": False,
        "secret_values_included": False,
        "path_values_redacted": True,
        "failed_stage": "reconnect",
        "failure_code": "M2_MANAGER_RECONNECT_FAILED",
        "failure_exception_class": "RuntimeError",
    }


def test_read_only_diagnostic_supports_legacy_transaction_without_stage(
    tmp_path: Path,
) -> None:
    workspace = _private_workspace(tmp_path)
    _write_private_json(
        workspace / "journal.json",
        {
            "schema": "gh.m2.t1-manager-identity-production-journal/1",
            "phase": "rollback_completed",
        },
    )

    report = build_failure_diagnostic(workspace)

    assert report["failure_stage_available"] is False
    assert report["rollback_completed"] is True
    assert report["rollback_terminal"] is False
    assert "failed_stage" not in report


def test_read_only_diagnostic_rejects_non_private_journal(tmp_path: Path) -> None:
    workspace = _private_workspace(tmp_path)
    _write_private_json(workspace / "journal.json", {"phase": "rollback_completed"})
    (workspace / "journal.json").chmod(0o644)

    with pytest.raises(Exception, match="mode 0600"):
        build_failure_diagnostic(workspace)
