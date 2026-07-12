from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_broker_identity_live_mount_gate import (
    BrokerIdentityLiveMountGateError,
    build_live_mount_gate,
)

TOPIC = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
BASELINE = "persistence true\nallow_anonymous true\n"
IMAGE_ID = "sha256:test-mosquitto-image"


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write(path: Path, value: str | bytes, mode: int = 0o600) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if isinstance(value, bytes):
        path.write_bytes(value)
    else:
        path.write_text(value, encoding="utf-8")
    path.chmod(mode)
    return path


class FakeRunner:
    def __init__(
        self,
        document: dict[str, Any],
        *,
        config: str = BASELINE,
        dynamic_state_absent: bool = True,
        residue: str = "",
    ) -> None:
        self.document = document
        self.config = config
        self.dynamic_state_absent = dynamic_state_absent
        self.residue = residue
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
        if command[:3] == ("docker", "inspect", "-f"):
            name = command[-1]
            return 0, json.dumps(
                {
                    "state": "running",
                    "restarts": "0",
                    "image_id": f"sha256:{name}",
                }
            )
        if command[:3] == ("docker", "exec", "mosquitto"):
            text = " ".join(command)
            if "cat /mosquitto/config/mosquitto.conf" in text:
                return 0, self.config
            if "test ! -e /mosquitto/data/dynamic-security.json" in text:
                return (0, "") if self.dynamic_state_absent else (1, "present")
            if "mosquitto_sub" in text:
                return 0, "retained-payload\n"
        if command[:4] == ("docker", "ps", "-a", "--format"):
            return 0, self.residue
        return 1, "unexpected command"


def _fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path, dict[str, object], dict[str, Any]]:
    handoff = tmp_path / "greenhouse-broker-identity-handoff-test"
    stage = tmp_path / "greenhouse-t1-auth-stage-test"
    deployment = tmp_path / "deployment"
    config_source = deployment / "mosquitto/config"
    data_source = deployment / "mosquitto/data"
    config_source.mkdir(parents=True, mode=0o700)
    data_source.mkdir(parents=True, mode=0o700)
    compose_file = _write(deployment / "compose.yaml", "services: {}\n", 0o600)
    handoff.mkdir(mode=0o700)
    stage.mkdir(mode=0o700)
    rollback = _write(handoff / "rollback/fresh.tar.gz", b"rollback")
    _write(
        handoff / "manifest.json",
        json.dumps(
            {
                "schema": "gh.m2.t1-broker-identity-activation-handoff/1",
                "fresh_rollback": {
                    "path": "rollback/fresh.tar.gz",
                    "sha256": hashlib.sha256(rollback.read_bytes()).hexdigest(),
                },
            }
        ),
    )
    contract: dict[str, object] = {
        "schema": "gh.m2.t1-broker-identity-production-executor-contract/1",
        "contract_sha256": "a" * 64,
        "source_binding": {
            "baseline_broker_config_sha256": _sha_text(BASELINE),
        },
    }
    contract_file = _write(
        tmp_path / "production-executor-contract.json",
        json.dumps(contract, sort_keys=True),
    )
    document: dict[str, Any] = {
        "State": {"Status": "running"},
        "RestartCount": 0,
        "Image": IMAGE_ID,
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
    return contract_file, handoff, stage, contract, document


def _contract_verifier(contract: dict[str, object]) -> dict[str, object]:
    return {
        "verified": True,
        "contract_sha256": contract["contract_sha256"],
    }


def _build(
    tmp_path: Path,
    *,
    document_mutator=None,
    config: str = BASELINE,
    dynamic_state_absent: bool = True,
    residue: str = "",
    rebuilt_digest: str | None = None,
    backup_image: str = IMAGE_ID,
) -> tuple[dict[str, object], FakeRunner, dict[str, Any]]:
    contract_file, handoff, stage, contract, document = _fixture(tmp_path)
    if document_mutator is not None:
        document_mutator(document)
    runner = FakeRunner(
        document,
        config=config,
        dynamic_state_absent=dynamic_state_absent,
        residue=residue,
    )
    rebuilt = dict(contract)
    if rebuilt_digest is not None:
        rebuilt["contract_sha256"] = rebuilt_digest
    report = build_live_mount_gate(
        contract_file,
        handoff,
        stage,
        expected_retained_topic=TOPIC,
        runner=runner,
        contract_builder=lambda _handoff, _stage: rebuilt,
        contract_verifier=_contract_verifier,
        backup_verifier=lambda _path: {
            "schema": "gh.m2.t1-backup/1",
            "sources": {"mosquitto": {"image_id": backup_image}},
        },
    )
    return report, runner, document


def test_builds_read_only_live_mount_binding_gate(tmp_path: Path) -> None:
    report, runner, _document = _build(tmp_path)

    assert report["schema"] == "gh.m2.t1-broker-identity-live-mount-gate/1"
    assert report["read_only"] is True
    assert report["mount_binding_ready"] is True
    assert report["production_executor_available"] is False
    assert report["execution_enabled"] is False
    assert report["apply_enabled"] is False
    assert report["operator_action_authorized"] is False
    assert report["ready_for_live_activation"] is False
    assert report["current_services_modified"] is False
    assert report["preserve_anonymous"] is True
    assert report["anonymous_closure_enabled"] is False
    assert all(report["checks"].values())
    assert not any(
        command[:2]
        in {
            ("docker", "create"),
            ("docker", "start"),
            ("docker", "restart"),
            ("docker", "rm"),
            ("docker", "cp"),
        }
        for command in runner.calls
    )


def test_rejects_contract_rebuild_drift(tmp_path: Path) -> None:
    with pytest.raises(
        BrokerIdentityLiveMountGateError,
        match="does not match current handoff",
    ):
        _build(tmp_path, rebuilt_digest="b" * 64)


def test_rejects_non_bind_config_mount(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        document["Mounts"][0]["Type"] = "volume"

    with pytest.raises(
        BrokerIdentityLiveMountGateError,
        match="writable bind mount",
    ):
        _build(tmp_path, document_mutator=mutate)


def test_rejects_mount_outside_compose_deployment(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)

    def mutate(document: dict[str, Any]) -> None:
        document["Mounts"][1]["Source"] = str(outside)

    with pytest.raises(
        BrokerIdentityLiveMountGateError,
        match="outside the Compose deployment",
    ):
        _build(tmp_path, document_mutator=mutate)


def test_rejects_live_config_drift(tmp_path: Path) -> None:
    with pytest.raises(
        BrokerIdentityLiveMountGateError,
        match="live_config_bound",
    ):
        _build(tmp_path, config="persistence true\nallow_anonymous false\n")


def test_rejects_existing_dynamic_security_state(tmp_path: Path) -> None:
    with pytest.raises(
        BrokerIdentityLiveMountGateError,
        match="dynamic_security_state_absent",
    ):
        _build(tmp_path, dynamic_state_absent=False)


def test_rejects_candidate_residue(tmp_path: Path) -> None:
    with pytest.raises(
        BrokerIdentityLiveMountGateError,
        match="candidate container residue",
    ):
        _build(tmp_path, residue="gh-m2-isolated-leftover\n")


def test_rejects_live_image_mismatch(tmp_path: Path) -> None:
    with pytest.raises(
        BrokerIdentityLiveMountGateError,
        match="image does not match",
    ):
        _build(tmp_path, backup_image="sha256:other")


def test_no_install_launcher_help() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_broker_identity_live_mount_gate.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "expected-retained-topic" in completed.stdout
    assert "contract_file" in completed.stdout
