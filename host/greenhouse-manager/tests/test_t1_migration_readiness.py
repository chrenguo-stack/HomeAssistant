from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from datetime import UTC, datetime
from pathlib import Path

from greenhouse_manager.t1_backup import create_backup
from greenhouse_manager.t1_migration_package import create_migration_package
from greenhouse_manager.t1_migration_readiness import build_readiness_report


class DeterministicBytes:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self, size: int) -> bytes:
        self.value += 1
        return bytes([self.value]) * size


class ReadinessDocker:
    def __init__(self) -> None:
        self.config = "persistence true\nlistener 1883\nallow_anonymous true\n"
        self.manager_env = ["GH_SYSTEM_ID=greenhouse"]
        self.candidate_names: list[str] = []
        self.calls: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.calls.append(command)
        if command[:3] == ("docker", "inspect", "-f"):
            template = command[3]
            name = command[-1]
            if template.startswith('{"image_id"'):
                return (
                    0,
                    json.dumps(
                        {
                            "image_id": f"sha256:{name}",
                            "image_ref": f"test/{name}:latest",
                        }
                    ),
                )
            if template.startswith('{"state"'):
                return (
                    0,
                    json.dumps(
                        {
                            "state": "running",
                            "restarts": "0",
                            "image_id": f"sha256:{name}",
                            "image_ref": f"test/{name}:latest",
                        }
                    ),
                )
            if template == "{{json .Config.Env}}":
                return (0, json.dumps(self.manager_env))
        if command[:4] == (
            "docker",
            "exec",
            "greenhouse-manager",
            "sh",
        ):
            return (0, "absent\n")
        if command[:3] == ("docker", "cp", "--archive"):
            destination = Path(command[4])
            destination.mkdir(parents=True)
            if "mosquitto:/mosquitto/config" in command[3]:
                (destination / "mosquitto.conf").write_text(
                    self.config,
                    encoding="utf-8",
                )
            elif "mosquitto:/mosquitto/data" in command[3]:
                (destination / "mosquitto.db").write_bytes(
                    b"retained-state"
                )
            return (0, "")
        if command[:4] == ("docker", "exec", "mosquitto", "sh"):
            script = command[-1]
            if "cat /mosquitto/config/mosquitto.conf" in script:
                return (0, self.config)
            if "mosquitto_dynamic_security.so" in script:
                return (0, "available\n")
            if "dynamic-security.json" in script:
                return (0, "absent\n")
        if command[:3] == ("docker", "ps", "-a"):
            return (0, "\n".join(self.candidate_names) + "\n")
        if command[:3] == ("docker", "exec", "mosquitto"):
            if "mosquitto_sub" in command:
                return (0, '{"temperature":24.5}\n')
        return (1, "unexpected")


def _inputs(
    tmp_path: Path,
    docker: ReadinessDocker,
) -> tuple[Path, Path, Path]:
    rollback_dir = tmp_path / "rollback"
    package_dir = tmp_path / "packages"
    compose_dir = tmp_path / "compose"
    rollback_dir.mkdir(mode=0o700)
    package_dir.mkdir(mode=0o700)
    compose_dir.mkdir(mode=0o700)
    (compose_dir / "compose.yml").write_text(
        "services:\n  mosquitto:\n    image: eclipse-mosquitto\n",
        encoding="utf-8",
    )
    env_file = compose_dir / ".env"
    env_file.write_text("LOCAL_ONLY=value\n", encoding="utf-8")
    env_file.chmod(0o600)
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
        token_factory=lambda: "readiness",
    )
    return rollback, package, compose_dir


def test_builds_secret_free_ready_report(tmp_path: Path) -> None:
    docker = ReadinessDocker()
    rollback, package, compose_dir = _inputs(tmp_path, docker)

    report = build_readiness_report(
        rollback,
        package,
        compose_directory=compose_dir,
        secret_root=tmp_path / "not-created-secrets",
        expected_retained_topic=(
            "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
        ),
        runner=docker,
        generated_at=datetime(2026, 7, 12, 4, 0, tzinfo=UTC),
    )

    assert report["schema"] == "gh.m2.t1-auth-migration-readiness/1"
    assert report["read_only"] is True
    assert report["apply_enabled"] is False
    assert report["current_services_modified"] is False
    assert report["source_binding"] is True
    assert report["ready"] is True
    assert all(report["gates"].values())
    assert report["transaction_plan"]["apply_enabled"] is False
    assert report["transaction_plan"]["steps"][-1][
        "blocked_until_all_authenticated"
    ] is True
    assert report["candidate_containers"] == ()


def test_detects_live_config_drift_without_modifying_services(
    tmp_path: Path,
) -> None:
    docker = ReadinessDocker()
    rollback, package, compose_dir = _inputs(tmp_path, docker)
    docker.config = (
        "persistence true\nlistener 1883\nallow_anonymous false\n"
        "plugin /usr/lib/mosquitto_dynamic_security.so\n"
    )

    report = build_readiness_report(
        rollback,
        package,
        compose_directory=compose_dir,
        secret_root=tmp_path / "not-created-secrets",
        expected_retained_topic=(
            "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
        ),
        runner=docker,
    )

    assert report["ready"] is False
    assert report["gates"]["live_mosquitto_config_matches_rollback"] is False
    assert report["gates"]["anonymous_access_still_enabled"] is False
    assert report["gates"]["dynamic_security_not_configured"] is False
    assert report["current_services_modified"] is False


def test_manager_secret_values_never_enter_report(tmp_path: Path) -> None:
    docker = ReadinessDocker()
    rollback, package, compose_dir = _inputs(tmp_path, docker)
    docker.manager_env = [
        "GH_MQTT_USERNAME=manager-user",
        "GH_MQTT_PASSWORD=do-not-report-this-secret",
    ]

    report = build_readiness_report(
        rollback,
        package,
        compose_directory=compose_dir,
        secret_root=tmp_path / "not-created-secrets",
        expected_retained_topic=(
            "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
        ),
        runner=docker,
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["ready"] is False
    assert report["gates"]["manager_authentication_not_configured"] is False
    assert report["manager"]["authentication_flags"][
        "gh_mqtt_password"
    ] is True
    assert "do-not-report-this-secret" not in serialized
    assert "manager-user" not in serialized


def test_detects_candidate_container_residue(tmp_path: Path) -> None:
    docker = ReadinessDocker()
    rollback, package, compose_dir = _inputs(tmp_path, docker)
    docker.candidate_names = ["gh-m2-package-rehearsal-leftover"]

    report = build_readiness_report(
        rollback,
        package,
        compose_directory=compose_dir,
        secret_root=tmp_path / "not-created-secrets",
        expected_retained_topic=(
            "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
        ),
        runner=docker,
    )

    assert report["ready"] is False
    assert report["gates"]["no_candidate_containers"] is False
    assert report["candidate_containers"] == (
        "gh-m2-package-rehearsal-leftover",
    )


def test_readiness_imports_without_paho() -> None:
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

        from greenhouse_manager.t1_migration_readiness import REPORT_SCHEMA

        assert REPORT_SCHEMA.endswith("/1")
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


def test_no_install_readiness_launcher_help() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_migration_readiness.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "expected-retained-topic" in completed.stdout
    assert "compose-directory" in completed.stdout
