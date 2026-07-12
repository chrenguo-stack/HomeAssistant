from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from greenhouse_manager.t1_migration_readiness_live import (
    build_live_readiness_report,
)


class LabelRunner:
    def __init__(self, labels: dict[str, dict[str, str]]) -> None:
        self.labels = labels
        self.calls: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.calls.append(command)
        if command[:4] == (
            "docker",
            "inspect",
            "-f",
            "{{json .Config.Labels}}",
        ):
            return (0, json.dumps(self.labels.get(command[-1], {})))
        return (1, "unexpected")


def _base_report(
    requested_directory: Path,
    *,
    fallback_files: list[dict[str, Any]] | None = None,
    fallback_env: dict[str, Any] | None = None,
) -> dict[str, object]:
    files = fallback_files or []
    env = fallback_env or {
        "path": str(requested_directory / ".env"),
        "exists": False,
        "mode": None,
        "sha256": None,
    }
    return {
        "compose": {
            "directory": str(requested_directory),
            "files": files,
            "env": env,
        },
        "gates": {
            "unrelated_gate": True,
            "compose_directory_present": bool(files),
            "compose_configuration_present": bool(files),
            "compose_env_private": env.get("mode") == "600",
        },
        "ready": False,
    }


def _builder_for(report: dict[str, object]):
    def build(*_args: object, **_kwargs: object) -> dict[str, object]:
        return report

    return build


def test_discovers_nonstandard_compose_filename_from_live_labels(
    tmp_path: Path,
) -> None:
    requested = tmp_path / "requested"
    working = tmp_path / "live-stack"
    requested.mkdir()
    working.mkdir()
    config = working / "greenhouse.t1.stack.yaml"
    config.write_text("services: {}\n", encoding="utf-8")
    env = working / ".env"
    env.write_text("LOCAL_ONLY=value\n", encoding="utf-8")
    env.chmod(0o600)
    labels = {
        "com.docker.compose.project": "greenhouse",
        "com.docker.compose.project.working_dir": str(working),
        "com.docker.compose.project.config_files": str(config),
    }
    runner = LabelRunner(
        {
            "mosquitto": labels,
            "greenhouse-manager": labels,
        }
    )
    report = _base_report(requested)

    result = build_live_readiness_report(
        tmp_path / "rollback.tar.gz",
        tmp_path / "migration.tar.gz",
        compose_directory=requested,
        expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
        runner=runner,
        base_builder=_builder_for(report),
    )

    assert result["ready"] is True
    assert result["gates"]["compose_metadata_consistent"] is True
    assert result["gates"]["compose_configuration_present"] is True
    assert result["gates"]["compose_env_private"] is True
    assert result["compose"]["source"] == "docker_compose_labels"
    assert result["compose"]["project"] == "greenhouse"
    assert result["compose"]["directory"] == str(working.resolve())
    assert result["compose"]["files"][0]["path"] == str(config.resolve())
    assert result["compose"]["env"]["mode"] == "600"


def test_resolves_relative_compose_config_against_working_directory(
    tmp_path: Path,
) -> None:
    working = tmp_path / "stack"
    working.mkdir()
    config = working / "deployment.t1.yml"
    config.write_text("services: {}\n", encoding="utf-8")
    env = working / ".env"
    env.write_text("LOCAL_ONLY=value\n", encoding="utf-8")
    env.chmod(0o600)
    labels = {
        "com.docker.compose.project": "greenhouse",
        "com.docker.compose.project.working_dir": str(working),
        "com.docker.compose.project.config_files": config.name,
    }
    runner = LabelRunner(
        {
            "mosquitto": labels,
            "greenhouse-manager": labels,
        }
    )

    result = build_live_readiness_report(
        tmp_path / "rollback.tar.gz",
        tmp_path / "migration.tar.gz",
        compose_directory=tmp_path / "unused",
        expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
        runner=runner,
        base_builder=_builder_for(_base_report(tmp_path / "unused")),
    )

    assert result["ready"] is True
    assert result["compose"]["files"][0]["path"] == str(config.resolve())


def test_disagreeing_live_compose_labels_block_readiness(
    tmp_path: Path,
) -> None:
    first = {
        "com.docker.compose.project": "greenhouse",
        "com.docker.compose.project.working_dir": "/opt/stack-a",
        "com.docker.compose.project.config_files": "stack.yml",
    }
    second = {
        **first,
        "com.docker.compose.project.working_dir": "/opt/stack-b",
    }
    runner = LabelRunner(
        {
            "mosquitto": first,
            "greenhouse-manager": second,
        }
    )

    result = build_live_readiness_report(
        tmp_path / "rollback.tar.gz",
        tmp_path / "migration.tar.gz",
        compose_directory=tmp_path / "requested",
        expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
        runner=runner,
        base_builder=_builder_for(_base_report(tmp_path / "requested")),
    )

    assert result["ready"] is False
    assert result["gates"]["compose_metadata_consistent"] is False
    assert result["compose"]["metadata_reason"] == "compose_labels_disagree"


def test_falls_back_to_requested_directory_when_labels_are_absent(
    tmp_path: Path,
) -> None:
    requested = tmp_path / "requested"
    requested.mkdir()
    config = requested / "compose.yml"
    config.write_text("services: {}\n", encoding="utf-8")
    env = requested / ".env"
    env.write_text("LOCAL_ONLY=value\n", encoding="utf-8")
    env.chmod(0o600)
    fallback_files = [
        {
            "path": str(config),
            "exists": True,
            "mode": "644",
            "sha256": "config-sha",
        }
    ]
    fallback_env = {
        "path": str(env),
        "exists": True,
        "mode": "600",
        "sha256": "env-sha",
    }
    runner = LabelRunner(
        {
            "mosquitto": {},
            "greenhouse-manager": {},
        }
    )
    report = _base_report(
        requested,
        fallback_files=fallback_files,
        fallback_env=fallback_env,
    )

    result = build_live_readiness_report(
        tmp_path / "rollback.tar.gz",
        tmp_path / "migration.tar.gz",
        compose_directory=requested,
        expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
        runner=runner,
        base_builder=_builder_for(report),
    )

    assert result["ready"] is True
    assert result["gates"]["compose_metadata_consistent"] is True
    assert result["compose"]["source"] == "requested_directory_fallback"
