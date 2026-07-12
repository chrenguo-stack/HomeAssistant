from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_broker_identity_host_replica_adapters import (
    FAULT_PHASES,
    BrokerIdentityHostReplicaError,
)
from greenhouse_manager.t1_broker_identity_host_replica_fault_matrix import (
    InMemoryReplicaBrokerDriver,
    run_host_replica_fault_matrix,
)


def _template(tmp_path: Path) -> Path:
    root = tmp_path / "replica-template"
    root.mkdir(mode=0o700)
    marker = root / ".gh-m2-host-replica.json"
    marker.write_text('{"replica_only":true}\n', encoding="utf-8")
    marker.chmod(0o600)
    config = root / "mosquitto/config"
    data = root / "mosquitto/data"
    config.mkdir(parents=True, mode=0o700)
    data.mkdir(parents=True, mode=0o700)
    broker = config / "mosquitto.conf"
    broker.write_text("allow_anonymous true\n", encoding="utf-8")
    broker.chmod(0o600)
    return root


def _plan_builder(*_args: object, **_kwargs: object) -> dict[str, object]:
    return {
        "replica_transaction_ready": True,
        "replica_only": True,
        "real_t1_target_allowed": False,
        "docker_commands_available": False,
        "current_services_modified": False,
    }


def test_fault_matrix_uses_independent_scenarios_and_preserves_template(
    tmp_path: Path,
) -> None:
    template = _template(tmp_path)
    before = (template / "mosquitto/config/mosquitto.conf").read_bytes()
    scenarios: list[Path] = []
    phases: list[str] = []

    def transaction_runner(
        _contract: Path,
        _skeleton: Path,
        _handoff: Path,
        scenario: Path,
        *,
        driver: object,
        fault_phase: str,
        **_kwargs: object,
    ) -> dict[str, object]:
        assert isinstance(driver, InMemoryReplicaBrokerDriver)
        assert scenario != template
        assert scenario.is_dir()
        scenarios.append(scenario)
        phases.append(fault_phase)
        if fault_phase == "rollback_incomplete":
            raise BrokerIdentityHostReplicaError(
                "host replica transaction failed and rollback failed"
            )
        return {
            "fault_injected": True,
            "rollback_completed": True,
            "replica_only": True,
            "current_services_modified": False,
        }

    report = run_host_replica_fault_matrix(
        tmp_path / "contract.json",
        tmp_path / "skeleton.json",
        tmp_path / "handoff",
        template,
        plan_builder=_plan_builder,
        transaction_runner=transaction_runner,
    )

    assert report["schema"] == (
        "gh.m2.t1-broker-identity-host-replica-fault-matrix/1"
    )
    assert report["all_faults_exercised"] is True
    assert report["forced_rollback_verified"] is True
    assert report["rollback_failure_explicit"] is True
    assert report["template_immutable"] is True
    assert report["scenario_isolation_verified"] is True
    assert report["replica_only"] is True
    assert report["real_t1_target_allowed"] is False
    assert report["docker_commands_available"] is False
    assert report["current_services_modified"] is False
    assert tuple(phases) == FAULT_PHASES
    assert len({str(path) for path in scenarios}) == len(FAULT_PHASES)
    assert (template / "mosquitto/config/mosquitto.conf").read_bytes() == before


def test_fault_matrix_rejects_missing_forced_rollback(tmp_path: Path) -> None:
    template = _template(tmp_path)

    def transaction_runner(
        _contract: Path,
        _skeleton: Path,
        _handoff: Path,
        _scenario: Path,
        *,
        fault_phase: str,
        **_kwargs: object,
    ) -> dict[str, object]:
        if fault_phase == "rollback_incomplete":
            raise BrokerIdentityHostReplicaError(
                "host replica transaction failed and rollback failed"
            )
        return {
            "fault_injected": True,
            "rollback_completed": False,
            "replica_only": True,
            "current_services_modified": False,
        }

    with pytest.raises(
        BrokerIdentityHostReplicaError,
        match="did not force rollback",
    ):
        run_host_replica_fault_matrix(
            tmp_path / "contract.json",
            tmp_path / "skeleton.json",
            tmp_path / "handoff",
            template,
            plan_builder=_plan_builder,
            transaction_runner=transaction_runner,
        )


def test_in_memory_driver_records_only_secret_free_digest() -> None:
    driver = InMemoryReplicaBrokerDriver()
    request: dict[str, Any] = {
        "commands": [
            {
                "command": "createClient",
                "username": "service",
                "password": "not-returned",
            }
        ]
    }
    driver.apply_exact_request(request)

    assert driver.events == ["apply_exact_request"]
    assert isinstance(driver.request_sha256, str)
    assert len(driver.request_sha256) == 64
    assert "not-returned" not in json.dumps(driver.__dict__)


def test_no_install_launcher_exposes_only_replica_matrix_arguments() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_broker_identity_host_replica_fault_matrix.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "replica_template_root" in completed.stdout
    assert "--live" not in completed.stdout
    assert "--enable" not in completed.stdout
