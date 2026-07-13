from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import greenhouse_manager.t1_manager_identity_migration_preclaim_candidate as module
from greenhouse_manager.t1_manager_identity_migration_preclaim_candidate import (
    ManagerPreclaimCandidateError,
    run_preclaim_candidate_probe,
    validate_preclaim_candidate_report,
)


def _write(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)
    return path


def _runtime() -> dict[str, object]:
    return {
        "container": {
            "image_id": "sha256:manager-image-id",
            "user_spec": "999:999",
        },
        "manager_runtime_uid": 999,
        "manager_runtime_gid": 999,
        "manager_runtime_user_source": "container+image+isolated-candidate",
        "manager_runtime_image_id": "sha256:manager-image-id",
        "manager_runtime_user_spec": "999:999",
    }


class FakeRunner:
    def __init__(
        self,
        *,
        code: int = 0,
        password_file_capability_present: bool = True,
    ) -> None:
        self.code = code
        self.password_file_capability_present = password_file_capability_present
        self.commands: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.commands.append(command)
        return self.code, json.dumps(
            {
                "password_file_capability_present": (
                    self.password_file_capability_present
                ),
                "configuration_valid": self.password_file_capability_present,
                "mqtt_authentication_configured": (
                    self.password_file_capability_present
                ),
                "password_file_used": self.password_file_capability_present,
                "inline_password_used": False,
                "network_attempted": False,
                "secret_values_included": False,
            }
        )


def _materials(tmp_path: Path) -> tuple[Path, Path, Path]:
    environment = _write(
        tmp_path / "material/manager.env",
        "GH_MQTT_USERNAME=manager\n"
        "GH_MQTT_PASSWORD_FILE=/run/secrets/gh_manager_mqtt_password\n"
        "GH_MQTT_CLIENT_ID=manager-client\n",
    )
    password = _write(
        tmp_path / "material/password",
        "candidate-credential-material-value\n",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    return environment, password, workspace


def test_preclaim_probe_is_network_none_read_only_and_removes_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment, password, workspace = _materials(tmp_path)
    monkeypatch.setattr(
        module,
        "verify_bound_runtime_identity",
        lambda *_args, **_kwargs: (os.getuid(), os.getgid()),
    )
    runner = FakeRunner()

    report = run_preclaim_candidate_probe(
        _runtime(),
        environment,
        password,
        workspace,
        runner=runner,
    )

    validate_preclaim_candidate_report(report)
    assert report["preclaim_candidate_probe_passed"] is True
    assert report["password_file_capability_present"] is True
    assert list(workspace.iterdir()) == []
    command = runner.commands[0]
    assert command[:5] == ("docker", "run", "--rm", "--network", "none")
    assert "--read-only" in command
    assert "--cap-drop" in command
    assert "no-new-privileges" in command
    assert command[command.index("--entrypoint") + 1] == "python3"
    assert command[-3:-1] == ("-I", "-c")
    assert command[-1] == module._CHECK_CONFIG_PROGRAM
    assert "password_file_capability_present" in command[-1]
    assert "_mqtt_password_from_env" in command[-1]
    assert "Settings.from_env()" in command[-1]
    assert "manager-client" not in command[-1]
    assert "candidate-credential-material-value" not in command[-1]


def test_preclaim_uses_installed_module_not_new_cli_wrapper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment, password, workspace = _materials(tmp_path)
    monkeypatch.setattr(
        module,
        "verify_bound_runtime_identity",
        lambda *_args, **_kwargs: (os.getuid(), os.getgid()),
    )
    runner = FakeRunner()

    run_preclaim_candidate_probe(
        _runtime(),
        environment,
        password,
        workspace,
        runner=runner,
    )

    command = runner.commands[0]
    assert command[command.index("--entrypoint") + 1] == "python3"
    assert "--check-config" not in command


def test_preclaim_probe_rejects_owner_mismatch_before_docker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment, password, workspace = _materials(tmp_path)
    monkeypatch.setattr(module.os, "geteuid", lambda: 1)
    monkeypatch.setattr(
        module,
        "verify_bound_runtime_identity",
        lambda *_args, **_kwargs: (os.getuid() + 1, os.getgid() + 1),
    )
    runner = FakeRunner()

    with pytest.raises(ManagerPreclaimCandidateError, match="ownership"):
        run_preclaim_candidate_probe(
            _runtime(),
            environment,
            password,
            workspace,
            runner=runner,
        )

    assert runner.commands == []
    assert list(workspace.iterdir()) == []


def test_preclaim_probe_failure_removes_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment, password, workspace = _materials(tmp_path)
    monkeypatch.setattr(
        module,
        "verify_bound_runtime_identity",
        lambda *_args, **_kwargs: (os.getuid(), os.getgid()),
    )

    with pytest.raises(ManagerPreclaimCandidateError, match="configuration probe failed"):
        run_preclaim_candidate_probe(
            _runtime(),
            environment,
            password,
            workspace,
            runner=FakeRunner(code=2),
        )

    assert list(workspace.iterdir()) == []


def test_preclaim_probe_rejects_live_image_without_password_file_capability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment, password, workspace = _materials(tmp_path)
    monkeypatch.setattr(
        module,
        "verify_bound_runtime_identity",
        lambda *_args, **_kwargs: (os.getuid(), os.getgid()),
    )
    runner = FakeRunner(password_file_capability_present=False)

    with pytest.raises(
        ManagerPreclaimCandidateError,
        match="runtime image does not support password-file authentication",
    ):
        run_preclaim_candidate_probe(
            _runtime(),
            environment,
            password,
            workspace,
            runner=runner,
        )

    assert len(runner.commands) == 1
    assert list(workspace.iterdir()) == []
