from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_broker_identity_runtime_binding_manifest import (
    BrokerIdentityRuntimeBindingManifestError,
    capture_runtime_binding_manifest,
    verify_runtime_binding_manifest,
)

CONTRACT_SHA = "a" * 64
SKELETON_SHA = "b" * 64
DRIVER_SHA = "c" * 64
BASELINE = "persistence true\nallow_anonymous true\n"


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def _fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, FakeRunner, dict[str, Any]]:
    deployment = tmp_path / "deployment"
    config_source = deployment / "mosquitto/config"
    data_source = deployment / "mosquitto/data"
    config_source.mkdir(parents=True, mode=0o700)
    data_source.mkdir(parents=True, mode=0o700)
    config_file = config_source / "mosquitto.conf"
    config_file.write_text(BASELINE, encoding="utf-8")
    compose_file = deployment / "compose.yaml"
    compose_file.write_text("services: {}\n", encoding="utf-8")

    document: dict[str, Any] = {
        "Id": "f" * 64,
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
    mount_binding = {
        "image_id": document["Image"],
        "image_ref": document["Config"]["Image"],
        "compose_working_directory": str(deployment.resolve()),
        "compose_config_files": [str(compose_file.resolve())],
        "config_source": str(config_source.resolve()),
        "data_source": str(data_source.resolve()),
    }
    mount_sha = _sha_text(_canonical(mount_binding))
    driver = {
        "schema": "gh.m2.t1-broker-identity-production-driver-contract/1",
        "driver_contract_sha256": DRIVER_SHA,
        "contract_sha256": CONTRACT_SHA,
        "skeleton_sha256": SKELETON_SHA,
        "mount_binding_sha256": mount_sha,
    }
    executor = {
        "schema": "gh.m2.t1-broker-identity-production-executor-contract/1",
        "contract_sha256": CONTRACT_SHA,
        "source_binding": {
            "baseline_broker_config_sha256": _sha_text(BASELINE),
        },
    }
    gate = {
        "schema": "gh.m2.t1-broker-identity-live-mount-gate/1",
        "contract_sha256": CONTRACT_SHA,
        "mount_binding_sha256": mount_sha,
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
    output = tmp_path / "greenhouse-m2-runtime-bindings-test"
    return (
        _write_private(tmp_path / "driver.json", driver),
        _write_private(tmp_path / "executor.json", executor),
        _write_private(tmp_path / "gate.json", gate),
        output,
        FakeRunner(document),
        document,
    )


def _capture(
    tmp_path: Path,
    *,
    output: Path | None = None,
    mutate_document=None,
) -> tuple[dict[str, object], Path, FakeRunner]:
    driver, executor, gate, default_output, runner, document = _fixture(tmp_path)
    if mutate_document is not None:
        mutate_document(document)
    destination = output or default_output
    report = capture_runtime_binding_manifest(
        driver,
        executor,
        gate,
        destination,
        runner=runner,
        now=datetime(2026, 7, 12, 9, 30, tzinfo=UTC),
        driver_verifier=lambda _document: {
            "verified": True,
            "driver_contract_sha256": DRIVER_SHA,
        },
        executor_verifier=lambda _document: {
            "verified": True,
            "contract_sha256": CONTRACT_SHA,
        },
    )
    return report, destination / str(report["runtime_binding_file"]), runner


def test_captures_private_runtime_binding_without_service_mutation(tmp_path: Path) -> None:
    report, manifest_file, runner = _capture(tmp_path)
    verified = verify_runtime_binding_manifest(manifest_file)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

    assert report["schema"] == "gh.m2.t1-broker-identity-runtime-binding-capture/1"
    assert report["runtime_binding_captured"] is True
    assert report["read_only_capture"] is True
    assert report["path_values_redacted_from_stdout"] is True
    assert report["production_driver_installed"] is False
    assert report["production_executor_available"] is False
    assert report["execution_enabled"] is False
    assert report["apply_enabled"] is False
    assert report["operator_action_authorized"] is False
    assert report["ready_for_live_activation"] is False
    assert report["current_services_modified"] is False
    assert report["preserve_anonymous"] is True
    assert report["anonymous_closure_enabled"] is False
    assert verified["verified"] is True
    assert manifest_file.stat().st_mode & 0o777 == 0o600
    assert manifest["private_manifest"] is True
    assert manifest["runtime"]["container_id"] == "f" * 64
    assert manifest["path_identity"]["config_file"]["sha256"] == _sha_text(BASELINE)
    assert runner.calls == [("docker", "inspect", "mosquitto")]
    assert str(tmp_path / "deployment") not in json.dumps(report)


def test_rejects_runtime_mount_drift_after_gate(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        document["Config"]["Image"] = "eclipse-mosquitto:3"

    with pytest.raises(
        BrokerIdentityRuntimeBindingManifestError,
        match="no longer matches the gate",
    ):
        _capture(tmp_path, mutate_document=mutate)


def test_rejects_live_config_drift(tmp_path: Path) -> None:
    driver, executor, gate, output, runner, document = _fixture(tmp_path)
    del document
    config_path = Path(runner.document["Mounts"][0]["Source"]) / "mosquitto.conf"
    config_path.write_text("allow_anonymous false\n", encoding="utf-8")

    with pytest.raises(
        BrokerIdentityRuntimeBindingManifestError,
        match="has drifted from the contract",
    ):
        capture_runtime_binding_manifest(
            driver,
            executor,
            gate,
            output,
            runner=runner,
            driver_verifier=lambda _document: {
                "verified": True,
                "driver_contract_sha256": DRIVER_SHA,
            },
            executor_verifier=lambda _document: {
                "verified": True,
                "contract_sha256": CONTRACT_SHA,
            },
        )


def test_rejects_existing_dynamic_security_state(tmp_path: Path) -> None:
    driver, executor, gate, output, runner, document = _fixture(tmp_path)
    del document
    state = Path(runner.document["Mounts"][1]["Source"]) / "dynamic-security.json"
    state.write_text("{}\n", encoding="utf-8")

    with pytest.raises(
        BrokerIdentityRuntimeBindingManifestError,
        match="already exists",
    ):
        capture_runtime_binding_manifest(
            driver,
            executor,
            gate,
            output,
            runner=runner,
            driver_verifier=lambda _document: {
                "verified": True,
                "driver_contract_sha256": DRIVER_SHA,
            },
            executor_verifier=lambda _document: {
                "verified": True,
                "contract_sha256": CONTRACT_SHA,
            },
        )


def test_rejects_output_directory_inside_live_deployment(tmp_path: Path) -> None:
    driver, executor, gate, _output, runner, document = _fixture(tmp_path)
    output = Path(document["Config"]["Labels"]["com.docker.compose.project.working_dir"])
    output = output / "greenhouse-m2-runtime-bindings-overlap"

    with pytest.raises(
        BrokerIdentityRuntimeBindingManifestError,
        match="overlaps the live deployment",
    ):
        capture_runtime_binding_manifest(
            driver,
            executor,
            gate,
            output,
            runner=runner,
            driver_verifier=lambda _document: {
                "verified": True,
                "driver_contract_sha256": DRIVER_SHA,
            },
            executor_verifier=lambda _document: {
                "verified": True,
                "contract_sha256": CONTRACT_SHA,
            },
        )


def test_no_install_launcher_help() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_broker_identity_runtime_binding_manifest.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "driver_contract_file" in completed.stdout
    assert "executor_contract_file" in completed.stdout
    assert "live_mount_gate_file" in completed.stdout
    assert "output_directory" in completed.stdout
    assert "--execute" not in completed.stdout
    assert "--apply" not in completed.stdout
    assert "--live" not in completed.stdout
