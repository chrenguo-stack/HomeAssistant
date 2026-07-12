from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
import textwrap
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_backup import create_backup
from greenhouse_manager.t1_migration_package import create_migration_package
from greenhouse_manager.t1_migration_rehearsal import (
    MigrationPackageError,
    PackageMaterial,
    run_migration_package_rehearsal,
)


class DeterministicBytes:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self, size: int) -> bytes:
        self.value += 1
        return bytes([self.value]) * size


class PackageRehearsalDocker:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], str | None]] = []
        self.mounts: list[str] = []
        self.password_init = ""
        self.applied_commands: list[dict[str, Any]] = []
        self.copied_configs: dict[str, str] = {}

    def run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
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
        if command[:4] == (
            "docker",
            "exec",
            "greenhouse-manager",
            "sh",
        ):
            return (0, "absent\n")
        if (
            command[:3] == ("docker", "cp", "--archive")
            and ":" in command[3]
        ):
            destination = Path(command[4])
            destination.mkdir(parents=True)
            if "mosquitto:/mosquitto/config" in command[3]:
                (destination / "mosquitto.conf").write_text(
                    "persistence true\nlistener 1883\nallow_anonymous true\n",
                    encoding="utf-8",
                )
            elif "mosquitto:/mosquitto/data" in command[3]:
                (destination / "mosquitto.db").write_bytes(
                    b"retained-state"
                )
            return (0, "")
        if command[:2] == ("docker", "create"):
            self.mounts = [
                item
                for item in command
                if item.startswith("type=bind,src=")
            ]
            return (0, "package-rehearsal-container\n")
        if command[:2] == ("docker", "start"):
            config_mount = next(
                item
                for item in self.mounts
                if item.endswith("dst=/mosquitto/config")
            )
            data_mount = next(
                item
                for item in self.mounts
                if item.endswith("dst=/mosquitto/data")
            )
            config_directory = Path(
                config_mount.removeprefix(
                    "type=bind,src="
                ).removesuffix(",dst=/mosquitto/config")
            )
            data_directory = Path(
                data_mount.removeprefix(
                    "type=bind,src="
                ).removesuffix(",dst=/mosquitto/data")
            )
            self.password_init = (
                config_directory / "dynsec-password-init"
            ).read_text(encoding="utf-8")
            (data_directory / "dynamic-security.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            return (0, "")
        if (
            command[:3] == ("docker", "cp", "--archive")
            and ":" not in command[3]
        ):
            source = Path(command[3])
            self.copied_configs[command[4]] = source.read_text(
                encoding="utf-8"
            )
            return (0, "")
        if command[:4] == (
            "docker",
            "exec",
            "-i",
            "package-rehearsal-container",
        ):
            request = json.loads(input_text or "{}")
            commands = request["commands"]
            self.applied_commands.extend(commands)
            return (
                0,
                json.dumps(
                    {
                        "responses": [
                            {"command": item["command"]}
                            for item in commands
                        ]
                    }
                ),
            )
        if command[:2] == ("docker", "rm"):
            return (0, "")
        return (1, "unexpected")


def _build_inputs(
    tmp_path: Path,
    docker: PackageRehearsalDocker,
) -> tuple[Path, Path]:
    rollback_dir = tmp_path / "rollback"
    package_dir = tmp_path / "packages"
    rollback_dir.mkdir(mode=0o700)
    package_dir.mkdir(mode=0o700)
    rollback = create_backup(
        rollback_dir,
        runner=docker,
        now=datetime(2026, 7, 12, 3, 20, tzinfo=UTC),
    )
    package = create_migration_package(
        rollback,
        package_dir,
        now=datetime(2026, 7, 12, 3, 25, tzinfo=UTC),
        random_bytes=DeterministicBytes(),
        token_factory=lambda: "feedface",
    )
    return rollback, package


def test_rehearsal_applies_exact_package_only_to_network_none_candidate(
    tmp_path: Path,
) -> None:
    docker = PackageRehearsalDocker()
    rollback, package = _build_inputs(tmp_path, docker)
    verification_calls: list[PackageMaterial] = []

    def verification_executor(
        _runner: Any,
        container_id: str,
        _staging: Path,
        _bootstrap_transport: Any,
        material: PackageMaterial,
        expected_retained_topic: str,
    ) -> dict[str, bool]:
        assert container_id == "package-rehearsal-container"
        assert expected_retained_topic.endswith(
            "/gh-n1-a9f2f8/telemetry"
        )
        assert material.system_id == "greenhouse"
        assert material.node_id == "gh-n1-a9f2f8"
        assert material.node_credentials.client_id == "gh-n1-a9f2f8"
        assert set(material.service_credentials) == {
            "provisioning",
            "manager",
            "homeassistant",
        }
        verification_calls.append(material)
        return {
            "exact_package_identity_matrix": True,
            "client_id_binding": True,
            "provisioning_control_only": True,
            "bootstrap_admin_removed": True,
            "provisioning_after_admin_removal": True,
            "legacy_anonymous_after_admin_removal": True,
            "anonymous_control_denied": True,
            "retained_state_recovered": True,
        }

    result = run_migration_package_rehearsal(
        rollback,
        package,
        expected_retained_topic=(
            "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
        ),
        runner=docker,
        name_factory=lambda: "gh-m2-package-rehearsal-test",
        verification_executor=verification_executor,
    )

    assert result["schema"] == "gh.m2.t1-auth-migration-rehearsal/1"
    assert result["network"] == "none"
    assert result["source_binding"] is True
    assert result["exact_package_request_applied"] is True
    assert result["bootstrap_admin_removed"] is True
    assert result["current_services_modified"] is False
    assert len(verification_calls) == 1

    create_clients = [
        command
        for command in docker.applied_commands
        if command["command"] == "createClient"
    ]
    assert len(create_clients) == 4
    assert any(
        command["command"] == "setAnonymousGroup"
        for command in docker.applied_commands
    )
    assert docker.password_init
    assert any(
        command[:4] == ("docker", "create", "--network", "none")
        for command, _input in docker.calls
    )
    assert any(
        command[:3] == ("docker", "rm", "-f")
        for command, _input in docker.calls
    )

    command_text = "\n".join(
        " ".join(command) for command, _input in docker.calls
    )
    with tarfile.open(package, "r:gz") as archive:
        member = archive.getmember("bootstrap/dynsec-password-init")
        stream = archive.extractfile(member)
        assert stream is not None
        bootstrap_password = stream.read().decode("utf-8").strip()
    assert bootstrap_password not in command_text
    assert (
        "package-rehearsal-container:/tmp/gh-m2-package-admin.conf"
        in docker.copied_configs
    )


def test_rehearsal_rejects_package_bound_to_another_rollback(
    tmp_path: Path,
) -> None:
    docker = PackageRehearsalDocker()
    first_rollback, package = _build_inputs(tmp_path, docker)
    second_dir = tmp_path / "second-rollback"
    second_dir.mkdir(mode=0o700)
    second_rollback = create_backup(
        second_dir,
        runner=docker,
        now=datetime(2026, 7, 12, 3, 21, tzinfo=UTC),
    )
    assert first_rollback.name != second_rollback.name

    with pytest.raises(
        MigrationPackageError,
        match="does not match",
    ):
        run_migration_package_rehearsal(
            second_rollback,
            package,
            expected_retained_topic=(
                "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
            ),
            runner=docker,
            verification_executor=lambda *_args: {},
        )

    assert not any(
        command[:2] == ("docker", "create")
        for command, _input in docker.calls
    )


def test_rehearsal_imports_without_paho() -> None:
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

        from greenhouse_manager.t1_migration_rehearsal import (
            PACKAGE_REHEARSAL_SCHEMA,
        )

        assert PACKAGE_REHEARSAL_SCHEMA.endswith("/1")
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


def test_no_install_rehearsal_launcher_help() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_migration_rehearsal.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "expected-retained-topic" in completed.stdout
