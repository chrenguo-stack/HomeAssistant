from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_broker_identity_isolated_transaction import (
    FAULT_PHASES,
    BrokerIdentityIsolatedTransactionError,
    run_isolated_fault_matrix,
    run_isolated_snapshot_transaction,
)

TOPIC = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
BASELINE_CONFIG = "persistence true\nallow_anonymous true\n"
CANDIDATE = "gh-m2-isolated-testabcd"


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


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], str | None]] = []
        self.candidate_exists = False
        self.candidate_running = False
        self.admin_deleted = False

    def run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> tuple[int, str]:
        self.calls.append((command, input_text))
        if command[:2] == ("docker", "create"):
            self.candidate_exists = True
            self.candidate_running = False
            name = command[command.index("--name") + 1]
            return 0, name
        if command[:2] == ("docker", "start"):
            if not self.candidate_exists:
                return 1, "missing"
            self.candidate_running = True
            return 0, command[-1]
        if command[:2] == ("docker", "rm"):
            self.candidate_exists = False
            self.candidate_running = False
            return 0, "removed"
        if command[:2] == ("docker", "inspect"):
            if not self.candidate_exists:
                return 1, "missing"
            if "-f" in command:
                return 0, "running" if self.candidate_running else "created"
            return 0, "present"
        if command[:2] == ("docker", "cp"):
            return (0, "copied") if self.candidate_exists else (1, "missing")
        if command[:2] != ("docker", "exec"):
            return 1, "unexpected command"

        command_text = " ".join(command)
        if "mosquitto_sub" in command_text:
            if input_text and "-wrong" in input_text:
                return 1, "client id rejected"
            return 0, "retained-payload"
        if "mosquitto_rr" in command_text:
            if input_text and input_text.lstrip().startswith("{"):
                request = json.loads(input_text)
                responses: list[dict[str, Any]] = []
                for item in request["commands"]:
                    if item.get("command") == "deleteClient" and item.get(
                        "username"
                    ) == "admin":
                        self.admin_deleted = True
                    responses.append({"command": item["command"]})
                config_path = command[command.index("-o") + 1]
                if "admin" in config_path and self.admin_deleted:
                    return 1, "admin rejected"
                return 0, json.dumps({"responses": responses})
            if input_text and "-u admin" in input_text and self.admin_deleted:
                return 1, "admin rejected"
            if input_text and "-u gh-provisioning" in input_text:
                return 0, json.dumps(
                    {"responses": [{"command": "listClients"}]}
                )
            return 1, "anonymous control denied"
        return 1, "unexpected docker exec"


def _fixture(
    tmp_path: Path,
) -> tuple[Path, Path, dict[str, Any], dict[str, Any]]:
    handoff = tmp_path / "greenhouse-broker-identity-handoff-test"
    stage = tmp_path / "greenhouse-t1-auth-stage-test"
    handoff.mkdir(mode=0o700)
    stage.mkdir(mode=0o700)

    stage_manifest = {
        "schema": "gh.m2.t1-auth-migration-stage/1",
        "activation_enabled": False,
        "current_services_modified": False,
        "active_paths_modified": False,
    }
    stage_manifest_path = _write(
        stage / "stage-manifest.json",
        json.dumps(stage_manifest, sort_keys=True),
    )
    rollback = _write(handoff / "rollback/fresh.tar.gz", b"fresh-rollback")
    manifest = {
        "schema": "gh.m2.t1-broker-identity-activation-handoff/1",
        "stage": {
            "name": stage.name,
            "manifest_sha256": hashlib.sha256(
                stage_manifest_path.read_bytes()
            ).hexdigest(),
            "broker_config_sha256": _sha_bytes(BASELINE_CONFIG.encode()),
        },
        "fresh_rollback": {
            "path": "rollback/fresh.tar.gz",
            "sha256": hashlib.sha256(rollback.read_bytes()).hexdigest(),
        },
    }
    _write(handoff / "manifest.json", json.dumps(manifest, sort_keys=True))
    _write(
        handoff / "activation-plan.json",
        json.dumps(
            {"schema": "gh.m2.t1-broker-identity-activation-plan/1"}
        ),
    )
    _write(
        handoff / "material/broker/dynsec-request.json",
        json.dumps(
            {
                "commands": [
                    {"command": "setDefaultACLAccess"},
                    {
                        "command": "createClient",
                        "username": "gh-provisioning",
                    },
                ]
            }
        ),
    )
    _write(
        handoff / "material/broker/mosquitto-plugin.conf",
        "# isolated candidate\n"
        "plugin /usr/lib/mosquitto_dynamic_security.so\n"
        "plugin_opt_config_file /mosquitto/data/dynamic-security.json\n"
        "plugin_opt_password_init_file "
        "/mosquitto/config/dynsec-password-init\n",
    )
    _write(
        handoff / "material/bootstrap/dynsec-password-init",
        "bootstrap-secret\n",
    )
    _write(
        handoff / "material/bootstrap/admin-client.conf",
        "-h 127.0.0.1\n-u admin\n-P bootstrap-secret\n"
        "-i gh-m2-bootstrap-admin\n-V 5\n",
    )
    _write(
        handoff / "material/provisioning/mosquitto-client.conf",
        "-h 127.0.0.1\n-u gh-provisioning\n-P provisioning-secret\n"
        "-i gh-provisioning-client\n-V 5\n",
    )
    _write(
        handoff / "material/homeassistant/mqtt-update.json",
        json.dumps(
            {
                "username": "gh-homeassistant",
                "password": "homeassistant-secret",
                "required_client_id": "gh-homeassistant-client",
            }
        ),
    )
    return handoff, stage, manifest, stage_manifest


def _handoff_verifier(_path: Path) -> dict[str, object]:
    return {
        "fresh_rollback_verified": True,
        "candidate_rehearsal_verified": True,
        "preserve_anonymous": True,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
    }


def _backup_extractor(_archive: Path, destination: Path) -> dict[str, Any]:
    _write(
        destination / "mosquitto-config/mosquitto.conf",
        BASELINE_CONFIG,
        0o644,
    )
    _write(
        destination / "mosquitto-data/mosquitto.db",
        b"retained-state",
        0o600,
    )
    return {
        "schema": "gh.m2.t1-backup/1",
        "sources": {"mosquitto": {"image_id": "sha256:test-image"}},
    }


def _wait_for_file(path: Path, **_kwargs: object) -> bool:
    _write(path, "{}\n", 0o600)
    return True


def _run(
    tmp_path: Path,
    *,
    fault_phase: str | None = None,
) -> tuple[dict[str, object], FakeRunner]:
    handoff, stage, _manifest, stage_manifest = _fixture(tmp_path)
    runner = FakeRunner()
    report = run_isolated_snapshot_transaction(
        handoff,
        stage,
        expected_retained_topic=TOPIC,
        fault_phase=fault_phase,
        runner=runner,
        name_factory=lambda: CANDIDATE,
        handoff_verifier=_handoff_verifier,
        stage_verifier=lambda _path: stage_manifest,
        backup_extractor=_backup_extractor,
        wait_for_file=_wait_for_file,
    )
    return report, runner


def test_success_path_uses_only_network_none_and_cleans_candidate(
    tmp_path: Path,
) -> None:
    report, runner = _run(tmp_path)

    assert report["schema"] == (
        "gh.m2.t1-broker-identity-isolated-transaction/1"
    )
    assert report["postactivation_verified"] is True
    assert report["rollback_completed"] is False
    assert report["candidate_cleanup_verified"] is True
    assert report["handoff_immutable"] is True
    assert report["stage_immutable"] is True
    assert report["network"] == "none"
    assert report["production_executor_available"] is False
    assert report["live_activation_enabled"] is False
    assert report["apply_enabled"] is False
    assert report["current_services_modified"] is False
    assert runner.candidate_exists is False
    create_commands = [
        command
        for command, _input in runner.calls
        if command[:2] == ("docker", "create")
    ]
    assert create_commands
    assert all("--network" in command for command in create_commands)
    assert all(
        command[command.index("--network") + 1] == "none"
        for command in create_commands
    )
    assert all(
        command[command.index("--name") + 1] != "mosquitto"
        for command in create_commands
    )


@pytest.mark.parametrize(
    "fault_phase",
    [phase for phase in FAULT_PHASES if phase != "rollback_incomplete"],
)
def test_faults_force_verified_rollback(
    tmp_path: Path,
    fault_phase: str,
) -> None:
    report, runner = _run(tmp_path, fault_phase=fault_phase)

    assert report["fault_phase"] == fault_phase
    assert report["fault_injected"] is True
    assert report["rollback_completed"] is True
    assert report["candidate_cleanup_verified"] is True
    assert report["handoff_immutable"] is True
    assert report["stage_immutable"] is True
    assert report["current_services_modified"] is False
    assert runner.candidate_exists is False


def test_incomplete_rollback_is_reported_explicitly(tmp_path: Path) -> None:
    handoff, stage, _manifest, stage_manifest = _fixture(tmp_path)

    with pytest.raises(
        BrokerIdentityIsolatedTransactionError,
        match="rollback failed",
    ):
        run_isolated_snapshot_transaction(
            handoff,
            stage,
            expected_retained_topic=TOPIC,
            fault_phase="rollback_incomplete",
            runner=FakeRunner(),
            name_factory=lambda: CANDIDATE,
            handoff_verifier=_handoff_verifier,
            stage_verifier=lambda _path: stage_manifest,
            backup_extractor=_backup_extractor,
            wait_for_file=_wait_for_file,
        )


def test_fault_matrix_covers_every_phase(tmp_path: Path) -> None:
    handoff, stage, _manifest, stage_manifest = _fixture(tmp_path)
    report = run_isolated_fault_matrix(
        handoff,
        stage,
        expected_retained_topic=TOPIC,
        runner=FakeRunner(),
        name_factory=lambda: CANDIDATE,
        handoff_verifier=_handoff_verifier,
        stage_verifier=lambda _path: stage_manifest,
        backup_extractor=_backup_extractor,
        wait_for_file=_wait_for_file,
    )

    assert report["schema"] == (
        "gh.m2.t1-broker-identity-isolated-fault-matrix/1"
    )
    assert report["all_faults_exercised"] is True
    assert report["forced_rollback_verified"] is True
    assert report["rollback_failure_explicit"] is True
    assert set(report["scenarios"]) == set(FAULT_PHASES)
    assert report["current_services_modified"] is False


def test_rejects_candidate_name_outside_isolated_namespace(
    tmp_path: Path,
) -> None:
    handoff, stage, _manifest, stage_manifest = _fixture(tmp_path)

    with pytest.raises(
        BrokerIdentityIsolatedTransactionError,
        match="candidate name is invalid",
    ):
        run_isolated_snapshot_transaction(
            handoff,
            stage,
            expected_retained_topic=TOPIC,
            runner=FakeRunner(),
            name_factory=lambda: "mosquitto",
            handoff_verifier=_handoff_verifier,
            stage_verifier=lambda _path: stage_manifest,
            backup_extractor=_backup_extractor,
            wait_for_file=_wait_for_file,
        )


def test_module_imports_without_paho() -> None:
    project = Path(__file__).resolve().parents[1]
    script = textwrap.dedent(
        """
        import importlib.abc
        import sys

        class BlockPaho(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "paho" or fullname.startswith("paho."):
                    raise ModuleNotFoundError(
                        "blocked for no-install host test",
                        name=fullname,
                    )
                return None

        sys.meta_path.insert(0, BlockPaho())

        from greenhouse_manager.t1_broker_identity_isolated_transaction import (
            FAULT_MATRIX_SCHEMA,
        )

        assert FAULT_MATRIX_SCHEMA.endswith("/1")
        """
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project / "src")
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_no_install_launcher_help() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_broker_identity_isolated_transaction.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "fault-matrix" in completed.stdout
    assert "expected-retained-topic" in completed.stdout
