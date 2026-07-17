from __future__ import annotations

import json
import stat
import subprocess
from pathlib import Path

import pytest

from greenhouse_manager import node_mqtt_isolated_lab as module


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def __call__(
        self,
        command: module.Sequence[str],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        del check
        values = tuple(command)
        self.commands.append(values)
        if "mosquitto_passwd" in values:
            mount = values[values.index("-v") + 1]
            workspace = Path(mount.split(":", 1)[0])
            (workspace / module.PASSWORD_NAME).write_text(
                "ghn_ci-node:$7$hashed-candidate\n"
                "gho_ci-observer:$7$hashed-observer\n",
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(values, 0, "", "")


def _waiter(host: str, port: int, timeout_s: float) -> None:
    assert host == "127.0.0.1"
    assert port == 18883
    assert timeout_s == 20.0


def _create(tmp_path: Path) -> tuple[Path, FakeRunner, dict[str, object]]:
    workspace = tmp_path / "gh-node-mqtt-lab-unit"
    runner = FakeRunner()
    report = module.create_lab(
        workspace,
        runner=runner,
        waiter=_waiter,
    )
    return workspace, runner, report


def test_plan_is_secret_free_and_pinned(tmp_path: Path) -> None:
    report = module.plan_lab(tmp_path / "gh-node-mqtt-lab-plan")

    assert report["status"] == "node_mqtt_isolated_lab_plan_created"
    assert report["image"] == "eclipse-mosquitto:2.0.22"
    assert report["allow_anonymous"] is True
    assert report["passwords_in_plan"] is False
    assert report["production_execution_invoked"] is False
    assert report["homeassistant_storage_read"] is False
    assert report["node_credentials_delivered"] is False
    assert report["anonymous_closure_enabled"] is False
    assert "password" not in json.dumps(report).lower().replace("passwords_", "")


def test_create_uses_private_files_and_never_puts_secrets_in_argv(
    tmp_path: Path,
) -> None:
    workspace, runner, report = _create(tmp_path)
    secret_document = module._load_secrets(workspace)
    encoded_report = json.dumps(report, sort_keys=True)
    encoded_commands = json.dumps(runner.commands)

    assert report["status"] == "node_mqtt_isolated_lab_created"
    assert report["workspace_private"] is True
    assert report["private_files_mode_0600"] is True
    assert report["password_file_hashed"] is True
    assert stat.S_IMODE(workspace.stat().st_mode) == 0o700
    assert all(
        stat.S_IMODE((workspace / name).stat().st_mode) == 0o600
        for name in (
            module.MARKER_NAME,
            module.MANIFEST_NAME,
            module.SECRETS_NAME,
            module.CONFIG_NAME,
            module.ACL_NAME,
            module.PASSWORD_NAME,
        )
    )
    for value in secret_document.values():
        assert value not in encoded_report
        assert value not in encoded_commands
    assert any("mosquitto_passwd" in command for command in runner.commands)
    assert any("127.0.0.1:18883:1883" in command for command in runner.commands)


def test_candidate_invalidation_and_restore_preserve_private_original(
    tmp_path: Path,
) -> None:
    workspace, runner, _ = _create(tmp_path)
    original = module._load_secrets(workspace)["candidate_password"]

    invalidated = module.invalidate_candidate(
        workspace,
        runner=runner,
        waiter=_waiter,
    )
    assert invalidated["candidate_password_state"] == "invalidated"
    assert invalidated["candidate_secret_output"] is False
    assert module._load_secrets(workspace)["candidate_password"] == original
    assert module._load_json(workspace / module.MANIFEST_NAME)[
        "candidate_password_state"
    ] == "invalidated"

    restored = module.restore_candidate(
        workspace,
        runner=runner,
        waiter=_waiter,
    )
    assert restored["candidate_password_state"] == "valid"
    assert module._load_secrets(workspace)["candidate_password"] == original
    assert module._load_json(workspace / module.MANIFEST_NAME)[
        "candidate_password_state"
    ] == "valid"
    assert original not in json.dumps(runner.commands)


def test_stop_start_and_destroy_are_bound_to_manifest(tmp_path: Path) -> None:
    workspace, runner, _ = _create(tmp_path)

    stopped = module.stop_lab(workspace, runner=runner)
    assert stopped["broker_running"] is False

    started = module.start_lab(workspace, runner=runner, waiter=_waiter)
    assert started["broker_running"] is True

    destroyed = module.destroy_lab(workspace, runner=runner)
    assert destroyed["workspace_removed"] is True
    assert destroyed["private_secrets_removed"] is True
    assert not workspace.exists()


def test_destroy_refuses_unmarked_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "gh-node-mqtt-lab-unmarked"
    workspace.mkdir()
    (workspace / "keep.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(module.NodeMqttIsolatedLabError, match="marker"):
        module.destroy_lab(workspace, runner=FakeRunner())

    assert (workspace / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_create_refuses_nonempty_or_broad_workspace(tmp_path: Path) -> None:
    nonempty = tmp_path / "gh-node-mqtt-lab-nonempty"
    nonempty.mkdir()
    (nonempty / "keep").write_text("keep", encoding="utf-8")

    with pytest.raises(module.NodeMqttIsolatedLabError, match="empty"):
        module.create_lab(nonempty, runner=FakeRunner(), waiter=_waiter)

    with pytest.raises(module.NodeMqttIsolatedLabError, match="cannot be /tmp"):
        module.create_lab(Path("/tmp"), runner=FakeRunner(), waiter=_waiter)


def test_reports_keep_all_production_gates_closed(tmp_path: Path) -> None:
    _, _, report = _create(tmp_path)

    assert report["isolated_lab"] is True
    assert report["production_endpoint_used"] is False
    assert report["production_identity_used"] is False
    assert report["production_execution_invoked"] is False
    assert report["current_services_modified"] is False
    assert report["homeassistant_storage_read"] is False
    assert report["node_credentials_delivered"] is False
    assert report["preserve_anonymous"] is True
    assert report["anonymous_closure_enabled"] is False
    assert report["ready_for_live_apply"] is False
    assert report["ready_for_anonymous_closure"] is False


def test_password_hash_command_uses_file_not_secret_argv(tmp_path: Path) -> None:
    workspace, runner, _ = _create(tmp_path)
    secret_document = module._load_secrets(workspace)
    hash_commands = [
        command for command in runner.commands if "mosquitto_passwd" in command
    ]

    assert len(hash_commands) == 1
    command = hash_commands[0]
    assert "-U" in command
    assert "/lab/passwd" in command
    assert "-b" not in command
    for secret in secret_document.values():
        assert secret not in command
