from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_broker_identity_host_replica_adapters import (
    BrokerIdentityHostReplicaError,
    build_host_replica_plan,
    run_host_replica_transaction,
)
from greenhouse_manager.t1_shadow import (
    PLUGIN_CONFIG_LINE,
    PLUGIN_LINE,
    PLUGIN_PASSWORD_INIT_LINE,
)

CONTRACT_SHA = "a" * 64
MOUNT_SHA = "b" * 64
BASELINE = "persistence true\nallow_anonymous true\n"


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write(path: Path, value: str | bytes, mode: int = 0o600) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if isinstance(value, bytes):
        path.write_bytes(value)
    else:
        path.write_text(value, encoding="utf-8")
    path.chmod(mode)
    return path


class FakeDriver:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.requests: list[dict[str, Any]] = []

    def restart_mosquitto(self) -> None:
        self.calls.append("restart_mosquitto")

    def wait_for_dynamic_security_state(self) -> None:
        self.calls.append("wait_for_dynamic_security_state")

    def apply_exact_request(self, request: dict[str, Any]) -> None:
        self.calls.append("apply_exact_request")
        self.requests.append(request)

    def verify_provisioning_identity(self) -> None:
        self.calls.append("verify_provisioning_identity")

    def delete_bootstrap_admin(self) -> None:
        self.calls.append("delete_bootstrap_admin")

    def postactivation_audit(self) -> dict[str, object]:
        self.calls.append("postactivation_audit")
        return {
            "activation_verified": True,
            "rollback_required": False,
            "broker_identity_activated": True,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }

    def restart_after_rollback(self) -> None:
        self.calls.append("restart_after_rollback")

    def verify_anonymous_retained_state(self) -> None:
        self.calls.append("verify_anonymous_retained_state")


def _contract_verifier(contract: dict[str, object]) -> dict[str, object]:
    return {
        "verified": True,
        "contract_sha256": contract["contract_sha256"],
    }


def _skeleton_verifier(skeleton: dict[str, object]) -> dict[str, object]:
    return {
        "verified": True,
        "skeleton_sha256": skeleton["skeleton_sha256"],
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    handoff = tmp_path / "handoff"
    handoff.mkdir(mode=0o700)
    plugin = _write(
        handoff / "material/broker/mosquitto-plugin.conf",
        "\n".join(
            (
                PLUGIN_LINE,
                PLUGIN_CONFIG_LINE,
                PLUGIN_PASSWORD_INIT_LINE,
            )
        )
        + "\n",
    )
    request = _write(
        handoff / "material/broker/dynsec-request.json",
        json.dumps(
            {
                "commands": [
                    {
                        "command": "setDefaultACLAccess",
                        "acls": [],
                    }
                ]
            },
            sort_keys=True,
        ),
    )
    password = _write(
        handoff / "material/bootstrap/dynsec-password-init",
        b"bootstrap-password\n",
    )

    contract: dict[str, object] = {
        "schema": "gh.m2.t1-broker-identity-production-executor-contract/1",
        "contract_sha256": CONTRACT_SHA,
        "source_binding": {
            "baseline_broker_config_sha256": _sha_bytes(BASELINE.encode("utf-8")),
        },
        "material_bindings": [
            {
                "path": "material/broker/dynsec-request.json",
                "sha256": _sha_bytes(request.read_bytes()),
                "contains_secret": True,
            },
            {
                "path": "material/broker/mosquitto-plugin.conf",
                "sha256": _sha_bytes(plugin.read_bytes()),
                "contains_secret": False,
            },
            {
                "path": "material/bootstrap/dynsec-password-init",
                "sha256": _sha_bytes(password.read_bytes()),
                "contains_secret": True,
            },
        ],
    }
    contract_file = _write(
        tmp_path / "production-executor-contract.json",
        json.dumps(contract, sort_keys=True),
    )

    skeleton: dict[str, object] = {
        "schema": "gh.m2.t1-broker-identity-production-adapter-skeleton/1",
        "skeleton_sha256": "c" * 64,
        "contract_sha256": CONTRACT_SHA,
        "mount_binding_sha256": MOUNT_SHA,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    skeleton_file = _write(
        tmp_path / "production-adapter-skeleton.json",
        json.dumps(skeleton, sort_keys=True),
    )

    replica = tmp_path / "replica"
    replica.mkdir(mode=0o700)
    _write(
        replica / ".gh-m2-host-replica.json",
        json.dumps(
            {
                "schema": "gh.m2.t1-broker-identity-host-replica/1",
                "replica_only": True,
                "contract_sha256": CONTRACT_SHA,
                "mount_binding_sha256": MOUNT_SHA,
            },
            sort_keys=True,
        ),
    )
    config_dir = replica / "mosquitto/config"
    data_dir = replica / "mosquitto/data"
    config_dir.mkdir(parents=True, mode=0o700)
    data_dir.mkdir(parents=True, mode=0o700)
    _write(config_dir / "mosquitto.conf", BASELINE)
    return contract_file, skeleton_file, handoff, replica


def _plan(
    contract_file: Path,
    skeleton_file: Path,
    handoff: Path,
    replica: Path,
) -> dict[str, object]:
    return build_host_replica_plan(
        contract_file,
        skeleton_file,
        handoff,
        replica,
        contract_verifier=_contract_verifier,
        skeleton_verifier=_skeleton_verifier,
    )


def _run(
    contract_file: Path,
    skeleton_file: Path,
    handoff: Path,
    replica: Path,
    driver: FakeDriver,
    *,
    fault_phase: str | None = None,
) -> dict[str, object]:
    return run_host_replica_transaction(
        contract_file,
        skeleton_file,
        handoff,
        replica,
        driver=driver,
        fault_phase=fault_phase,
        contract_verifier=_contract_verifier,
        skeleton_verifier=_skeleton_verifier,
    )


def test_builds_replica_only_atomic_transaction_plan(tmp_path: Path) -> None:
    contract_file, skeleton_file, handoff, replica = _fixture(tmp_path)
    plan = _plan(contract_file, skeleton_file, handoff, replica)

    assert plan["schema"] == "gh.m2.t1-broker-identity-host-replica-plan/1"
    assert plan["replica_transaction_ready"] is True
    assert plan["replica_only"] is True
    assert plan["real_t1_target_allowed"] is False
    assert plan["docker_commands_available"] is False
    assert plan["production_executor_available"] is False
    assert plan["execution_enabled"] is False
    assert plan["apply_enabled"] is False
    assert plan["current_services_modified"] is False
    assert str(replica) not in json.dumps(plan)


def test_successful_replica_transaction_uses_injected_driver(tmp_path: Path) -> None:
    contract_file, skeleton_file, handoff, replica = _fixture(tmp_path)
    driver = FakeDriver()
    report = _run(contract_file, skeleton_file, handoff, replica, driver)

    config = (replica / "mosquitto/config/mosquitto.conf").read_text(
        encoding="utf-8"
    )
    assert PLUGIN_LINE in config
    assert PLUGIN_CONFIG_LINE in config
    assert PLUGIN_PASSWORD_INIT_LINE in config
    assert (replica / "mosquitto/config/dynsec-password-init").read_bytes() == (
        b"bootstrap-password\n"
    )
    assert report["mutation_completed"] is True
    assert report["postactivation_verified"] is True
    assert report["rollback_completed"] is False
    assert report["replica_only"] is True
    assert report["current_services_modified"] is False
    assert driver.calls == [
        "restart_mosquitto",
        "wait_for_dynamic_security_state",
        "apply_exact_request",
        "verify_provisioning_identity",
        "delete_bootstrap_admin",
        "postactivation_audit",
    ]
    assert driver.requests[0]["commands"][0]["command"] == "setDefaultACLAccess"


def test_fault_after_request_forces_complete_replica_rollback(tmp_path: Path) -> None:
    contract_file, skeleton_file, handoff, replica = _fixture(tmp_path)
    driver = FakeDriver()
    report = _run(
        contract_file,
        skeleton_file,
        handoff,
        replica,
        driver,
        fault_phase="after_request",
    )

    assert report["fault_injected"] is True
    assert report["rollback_completed"] is True
    assert (replica / "mosquitto/config/mosquitto.conf").read_text(
        encoding="utf-8"
    ) == BASELINE
    assert not (replica / "mosquitto/config/dynsec-password-init").exists()
    assert driver.calls[-2:] == [
        "restart_after_rollback",
        "verify_anonymous_retained_state",
    ]


def test_rollback_failure_is_reported_as_terminal(tmp_path: Path) -> None:
    contract_file, skeleton_file, handoff, replica = _fixture(tmp_path)
    driver = FakeDriver()

    with pytest.raises(
        BrokerIdentityHostReplicaError,
        match="transaction failed and rollback failed",
    ):
        _run(
            contract_file,
            skeleton_file,
            handoff,
            replica,
            driver,
            fault_phase="rollback_incomplete",
        )


def test_rejects_unmarked_real_host_target(tmp_path: Path) -> None:
    contract_file, skeleton_file, handoff, _replica = _fixture(tmp_path)

    with pytest.raises(
        BrokerIdentityHostReplicaError,
        match="system temporary directory",
    ):
        _plan(contract_file, skeleton_file, handoff, Path("/"))


def test_no_install_launcher_has_no_execute_option() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_broker_identity_host_replica_plan.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "replica_root" in completed.stdout
    assert "--execute" not in completed.stdout
    assert "--enable" not in completed.stdout
