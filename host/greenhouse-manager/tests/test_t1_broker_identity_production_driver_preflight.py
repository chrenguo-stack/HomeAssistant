from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_broker_identity_production_driver_preflight import (
    BrokerIdentityProductionDriverPreflightError,
    build_production_driver_preflight,
    verify_production_driver_preflight,
)

DRIVER_SHA = "a" * 64
CONTRACT_SHA = "b" * 64
MOUNT_SHA = "c" * 64
MANIFEST_SHA = "d" * 64
BASELINE = "persistence true\nallow_anonymous true\n"
TOPIC = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"


def _sha_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _identity(path: Path, *, include_sha256: bool = False) -> dict[str, object]:
    stat = path.stat()
    result: dict[str, object] = {
        "device": stat.st_dev,
        "inode": stat.st_ino,
        "mode": stat.st_mode & 0o777,
        "uid": stat.st_uid,
        "gid": stat.st_gid,
    }
    if include_sha256:
        result["sha256"] = _sha_path(path)
    return result


def _write_private(path: Path, document: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    path.chmod(0o600)
    return path


class FakeRunner:
    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document
        self.calls: list[tuple[str, ...]] = []

    def run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> tuple[int, str]:
        del input_text
        self.calls.append(command)
        if command == ("docker", "inspect", "mosquitto"):
            return 0, json.dumps([self.document])
        return 1, "unexpected command"


def _fixture(tmp_path: Path) -> dict[str, object]:
    deployment = tmp_path / "deployment"
    config_source = deployment / "mosquitto/config"
    data_source = deployment / "mosquitto/data"
    config_source.mkdir(parents=True, mode=0o700)
    data_source.mkdir(parents=True, mode=0o700)
    compose_file = deployment / "compose.yaml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    config_file = config_source / "mosquitto.conf"
    config_file.write_text(BASELINE, encoding="utf-8")
    state_file = data_source / "dynamic-security.json"

    inspect_document: dict[str, Any] = {
        "Id": "e" * 64,
        "State": {
            "Status": "running",
            "StartedAt": "2026-07-12T09:00:00.000000000Z",
        },
        "RestartCount": 0,
        "Image": "sha256:" + "1" * 64,
        "Config": {
            "Image": "eclipse-mosquitto:2",
            "Labels": {
                "com.docker.compose.project.working_dir": str(deployment),
                "com.docker.compose.project.config_files": str(compose_file),
            },
        },
        "Mounts": [
            {
                "Type": "bind",
                "Source": str(config_source),
                "Destination": "/mosquitto/config",
                "RW": True,
            },
            {
                "Type": "bind",
                "Source": str(data_source),
                "Destination": "/mosquitto/data",
                "RW": True,
            },
        ],
    }
    driver = {
        "schema": "gh.m2.t1-broker-identity-production-driver-contract/1",
        "driver_contract_sha256": DRIVER_SHA,
        "contract_sha256": CONTRACT_SHA,
        "mount_binding_sha256": MOUNT_SHA,
    }
    executor = {
        "schema": "gh.m2.t1-broker-identity-production-executor-contract/1",
        "contract_sha256": CONTRACT_SHA,
    }
    manifest = {
        "schema": "gh.m2.t1-broker-identity-runtime-binding-manifest/1",
        "manifest_sha256": MANIFEST_SHA,
        "created_at": "2026-07-12T09:30:00Z",
        "driver_contract_sha256": DRIVER_SHA,
        "contract_sha256": CONTRACT_SHA,
        "mount_binding_sha256": MOUNT_SHA,
        "runtime": {
            "container_name": "mosquitto",
            "container_id": inspect_document["Id"],
            "image_id": inspect_document["Image"],
            "image_ref": inspect_document["Config"]["Image"],
            "started_at": inspect_document["State"]["StartedAt"],
            "restart_count": 0,
        },
        "paths": {
            "compose_working_directory": str(deployment.resolve()),
            "compose_config_files": [str(compose_file.resolve())],
            "config_source": str(config_source.resolve()),
            "data_source": str(data_source.resolve()),
            "config_file": str(config_file.resolve()),
            "dynamic_security_state_file": str(state_file.resolve()),
        },
        "path_identity": {
            "compose_working_directory": _identity(deployment),
            "compose_config_files": [_identity(compose_file, include_sha256=True)],
            "config_source": _identity(config_source),
            "data_source": _identity(data_source),
            "config_file": _identity(config_file, include_sha256=True),
        },
        "baseline_config_sha256": _sha_path(config_file),
    }
    handoff = tmp_path / "handoff"
    stage = tmp_path / "stage"
    handoff.mkdir()
    stage.mkdir()
    return {
        "driver_path": _write_private(tmp_path / "driver.json", driver),
        "executor_path": _write_private(tmp_path / "executor.json", executor),
        "manifest_path": _write_private(tmp_path / "manifest.json", manifest),
        "driver": driver,
        "executor": executor,
        "manifest": manifest,
        "handoff": handoff,
        "stage": stage,
        "runner": FakeRunner(inspect_document),
        "inspect_document": inspect_document,
        "compose_file": compose_file,
    }


def _live_gate() -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-broker-identity-live-mount-gate/1",
        "contract_sha256": CONTRACT_SHA,
        "mount_binding_sha256": MOUNT_SHA,
        "checks": {"all": True},
        "read_only": True,
        "mount_binding_ready": True,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def _preactivation() -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-broker-identity-preactivation-gate/1",
        "checks": {"all": True},
        "read_only": True,
        "preconditions_ready": True,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def _build(
    tmp_path: Path,
    *,
    now: datetime | None = None,
    executor_builder=None,
) -> tuple[dict[str, object], dict[str, object]]:
    fixture = _fixture(tmp_path)
    executor_document = fixture["executor"]
    builder = executor_builder or (lambda _handoff, _stage: executor_document)
    report = build_production_driver_preflight(
        fixture["driver_path"],
        fixture["executor_path"],
        fixture["manifest_path"],
        fixture["handoff"],
        fixture["stage"],
        expected_retained_topic=TOPIC,
        expected_target_fingerprint="target-fingerprint",
        expected_entry_fingerprint="entry-fingerprint",
        expected_storage_sha256="f" * 64,
        runner=fixture["runner"],
        now=now or datetime(2026, 7, 12, 9, 35, tzinfo=UTC),
        driver_verifier=lambda _document: {
            "verified": True,
            "driver_contract_sha256": DRIVER_SHA,
        },
        executor_verifier=lambda _document: {
            "verified": True,
            "contract_sha256": CONTRACT_SHA,
        },
        manifest_verifier=lambda _path: {
            "verified": True,
            "manifest_sha256": MANIFEST_SHA,
        },
        executor_builder=builder,
        live_gate_builder=lambda *_args, **_kwargs: _live_gate(),
        preactivation_builder=lambda *_args, **_kwargs: _preactivation(),
    )
    return report, fixture


def test_revalidates_runtime_binding_without_enabling_execution(tmp_path: Path) -> None:
    report, fixture = _build(tmp_path)
    verified = verify_production_driver_preflight(report)

    assert verified["verified"] is True
    assert report["preflight_ready"] is True
    assert report["read_only"] is True
    assert report["path_values_redacted"] is True
    assert all(report["checks"].values())
    assert report["production_driver_installed"] is False
    assert report["production_executor_available"] is False
    assert report["execution_enabled"] is False
    assert report["apply_enabled"] is False
    assert report["operator_action_authorized"] is False
    assert report["ready_for_live_activation"] is False
    assert report["current_services_modified"] is False
    assert report["preserve_anonymous"] is True
    assert report["anonymous_closure_enabled"] is False
    assert fixture["runner"].calls == [("docker", "inspect", "mosquitto")]
    assert str(tmp_path / "deployment") not in json.dumps(report)


def test_rejects_stale_runtime_binding(tmp_path: Path) -> None:
    with pytest.raises(
        BrokerIdentityProductionDriverPreflightError,
        match="manifest is stale",
    ):
        _build(tmp_path, now=datetime(2026, 7, 12, 10, 0, tzinfo=UTC))


def test_rejects_container_identity_drift(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    fixture["runner"].document["Id"] = "9" * 64

    with pytest.raises(
        BrokerIdentityProductionDriverPreflightError,
        match="runtime identity has drifted",
    ):
        build_production_driver_preflight(
            fixture["driver_path"],
            fixture["executor_path"],
            fixture["manifest_path"],
            fixture["handoff"],
            fixture["stage"],
            expected_retained_topic=TOPIC,
            expected_target_fingerprint="target",
            expected_entry_fingerprint="entry",
            expected_storage_sha256="f" * 64,
            runner=fixture["runner"],
            now=datetime(2026, 7, 12, 9, 35, tzinfo=UTC),
            driver_verifier=lambda _document: {
                "verified": True,
                "driver_contract_sha256": DRIVER_SHA,
            },
            executor_verifier=lambda _document: {
                "verified": True,
                "contract_sha256": CONTRACT_SHA,
            },
            manifest_verifier=lambda _path: {
                "verified": True,
                "manifest_sha256": MANIFEST_SHA,
            },
            executor_builder=lambda _handoff, _stage: fixture["executor"],
            live_gate_builder=lambda *_args, **_kwargs: _live_gate(),
            preactivation_builder=lambda *_args, **_kwargs: _preactivation(),
        )


def test_rejects_host_path_identity_drift(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    fixture["compose_file"].write_text("services: {changed: true}\n", encoding="utf-8")

    with pytest.raises(
        BrokerIdentityProductionDriverPreflightError,
        match="path identity has drifted",
    ):
        build_production_driver_preflight(
            fixture["driver_path"],
            fixture["executor_path"],
            fixture["manifest_path"],
            fixture["handoff"],
            fixture["stage"],
            expected_retained_topic=TOPIC,
            expected_target_fingerprint="target",
            expected_entry_fingerprint="entry",
            expected_storage_sha256="f" * 64,
            runner=fixture["runner"],
            now=datetime(2026, 7, 12, 9, 35, tzinfo=UTC),
            driver_verifier=lambda _document: {
                "verified": True,
                "driver_contract_sha256": DRIVER_SHA,
            },
            executor_verifier=lambda _document: {
                "verified": True,
                "contract_sha256": CONTRACT_SHA,
            },
            manifest_verifier=lambda _path: {
                "verified": True,
                "manifest_sha256": MANIFEST_SHA,
            },
            executor_builder=lambda _handoff, _stage: fixture["executor"],
            live_gate_builder=lambda *_args, **_kwargs: _live_gate(),
            preactivation_builder=lambda *_args, **_kwargs: _preactivation(),
        )


def test_rejects_rebuilt_executor_drift(tmp_path: Path) -> None:
    with pytest.raises(
        BrokerIdentityProductionDriverPreflightError,
        match="no longer matches handoff and stage",
    ):
        _build(tmp_path, executor_builder=lambda _handoff, _stage: {"drift": True})


def test_rejects_tampered_preflight_report(tmp_path: Path) -> None:
    report, _fixture_data = _build(tmp_path)
    report["execution_enabled"] = True
    with pytest.raises(
        BrokerIdentityProductionDriverPreflightError,
        match="fingerprint does not match",
    ):
        verify_production_driver_preflight(report)


def test_no_install_launcher_help() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_broker_identity_production_driver_preflight.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "runtime_binding_manifest_file" in completed.stdout
    assert "expected-retained-topic" in completed.stdout
    assert "expected-target-fingerprint" in completed.stdout
    assert "expected-entry-fingerprint" in completed.stdout
    assert "expected-storage-sha256" in completed.stdout
    assert "--execute" not in completed.stdout
    assert "--apply" not in completed.stdout
    assert "--live" not in completed.stdout
