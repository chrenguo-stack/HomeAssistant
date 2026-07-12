from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from greenhouse_manager.t1_backup import create_backup
from greenhouse_manager.t1_shadow import (
    PLUGIN_CONFIG_LINE,
    PLUGIN_LINE,
    PLUGIN_PASSWORD_INIT_LINE,
    ShadowError,
    legacy_shadow_ctrl_commands,
    prepare_shadow_config,
    run_shadow_candidate,
)


class ShadowDocker:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], str | None]] = []
        self.control_config = ""

    def run(
        self, command: tuple[str, ...], *, input_text: str | None = None
    ) -> tuple[int, str]:
        self.calls.append((command, input_text))
        if command[:3] == ("docker", "inspect", "-f"):
            if command[3].startswith('{"image_id"'):
                name = command[-1]
                return (
                    0,
                    json.dumps(
                        {
                            "image_id": f"sha256:{name}",
                            "image_ref": f"test/{name}:latest",
                        }
                    ),
                )
            return (0, "running\n")
        if command[:4] == ("docker", "exec", "greenhouse-manager", "sh"):
            return (0, "absent\n")
        if command[:3] == ("docker", "cp", "--archive") and ":" in command[3]:
            destination = Path(command[4])
            destination.mkdir(parents=True)
            if "mosquitto:/mosquitto/config" in command[3]:
                (destination / "mosquitto.conf").write_text(
                    "persistence true\nlistener 1883\nallow_anonymous true\n",
                    encoding="utf-8",
                )
            elif "mosquitto:/mosquitto/data" in command[3]:
                (destination / "mosquitto.db").write_bytes(b"retained-state")
            return (0, "")
        if command[:2] == ("docker", "create"):
            self.mounts = [
                item for item in command if item.startswith("type=bind,src=")
            ]
            return (0, "shadow-container-id\n")
        if command[:2] == ("docker", "start"):
            config_mount = next(
                item for item in self.mounts if item.endswith("dst=/mosquitto/config")
            )
            data_mount = next(
                item for item in self.mounts if item.endswith("dst=/mosquitto/data")
            )
            config_directory = Path(
                config_mount.removeprefix("type=bind,src=").removesuffix(
                    ",dst=/mosquitto/config"
                )
            )
            data_directory = Path(
                data_mount.removeprefix("type=bind,src=").removesuffix(
                    ",dst=/mosquitto/data"
                )
            )
            self.password_init = (
                config_directory / "dynsec-password-init"
            ).read_text(encoding="utf-8")
            self.password_init_mode = (
                config_directory / "dynsec-password-init"
            ).stat().st_mode & 0o777
            (data_directory / "dynamic-security.json").write_text(
                "{}\n", encoding="utf-8"
            )
            return (0, "")
        if command[:2] == ("docker", "rm"):
            return (0, "")
        if command[:3] == ("docker", "cp", "--archive"):
            self.control_config = Path(command[3]).read_text(encoding="utf-8")
            return (0, "")
        if command[:3] == ("docker", "exec", "shadow-container-id"):
            if command[-2:] == ("getClient", "gh-shadow-forbidden-canary"):
                return (1, "client not found")
            if command[3] == "mosquitto_sub":
                return (0, command[-1] + "\n")
            return (0, "")
        return (1, "unexpected")


def test_prepares_snapshot_copy_without_disabling_anonymous(tmp_path: Path) -> None:
    config = tmp_path / "mosquitto.conf"
    config.write_text(
        "persistence true\nlistener 1883\nallow_anonymous true\n",
        encoding="utf-8",
    )

    prepare_shadow_config(config)

    updated = config.read_text(encoding="utf-8")
    assert "allow_anonymous true" in updated
    assert PLUGIN_LINE in updated
    assert PLUGIN_CONFIG_LINE in updated
    assert PLUGIN_PASSWORD_INIT_LINE in updated


@pytest.mark.parametrize(
    "config",
    [
        "listener 1883\nallow_anonymous false\n",
        "listener 1883\n",
        (
            "listener 1883\nallow_anonymous true\n"
            "plugin /usr/lib/mosquitto_dynamic_security.so\n"
        ),
    ],
)
def test_rejects_unsafe_or_already_migrated_snapshot(
    tmp_path: Path, config: str
) -> None:
    path = tmp_path / "mosquitto.conf"
    path.write_text(config, encoding="utf-8")

    with pytest.raises(ShadowError):
        prepare_shadow_config(path)


def test_legacy_policy_dependency_order_and_control_deny() -> None:
    commands = legacy_shadow_ctrl_commands()
    names = [command[0] for command in commands]

    assert names[:4] == ["setDefaultACLAccess"] * 4
    assert names[4] == "createRole"
    assert names[-3:] == ["createGroup", "addGroupRole", "setAnonymousGroup"]
    assert (
        "addRoleACL",
        "gh-legacy-anonymous-shadow",
        "publishClientSend",
        "$CONTROL/#",
        "deny",
    ) in commands
    assert (
        "addRoleACL",
        "gh-legacy-anonymous-shadow",
        "subscribePattern",
        "#",
        "allow",
    ) in commands
    assert not any(
        command[0] == "addRoleACL"
        and command[2] == "publishClientSend"
        and command[3] == "$SYS/#"
        for command in commands
    )


def test_snapshot_candidate_is_isolated_and_keeps_secret_out_of_argv(
    tmp_path: Path,
) -> None:
    docker = ShadowDocker()
    output = tmp_path / "private"
    output.mkdir(mode=0o700)
    archive = create_backup(
        output,
        runner=docker,
        now=datetime(2026, 7, 11, 20, 0, tzinfo=UTC),
    )
    password = "test-shadow-password-32-characters-long"

    result = run_shadow_candidate(
        archive,
        expected_retained_topic=(
            "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
        ),
        runner=docker,
        password_factory=lambda: password,
        name_factory=lambda: "gh-m2-shadow-test",
    )

    assert result["network"] == "none"
    assert result["retained_state_recovered"] is True
    assert result["anonymous_control_denied"] is True
    assert result["current_services_modified"] is False
    command_text = "\n".join(
        " ".join(command) for command, _input_text in docker.calls
    )
    assert password not in command_text
    assert f"-P {password}" in docker.control_config
    assert docker.password_init == password + "\n"
    assert docker.password_init_mode == 0o644
    assert not any(command[:2] == ("docker", "run") for command, _ in docker.calls)
    assert any(
        command[:3] == ("docker", "create", "--network")
        and command[3] == "none"
        for command, _input_text in docker.calls
    )
    assert any(
        command[:3] == ("docker", "rm", "-f")
        for command, _input_text in docker.calls
    )
