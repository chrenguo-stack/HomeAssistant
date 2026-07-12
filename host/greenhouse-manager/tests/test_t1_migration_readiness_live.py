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


def _labels(
    project: str,
    working_dir: Path,
    config_files: str,
) -> dict[str, str]:
    return {
        "com.docker.compose.project": project,
        "com.docker.compose.project.working_dir": str(working_dir),
        "com.docker.compose.project.config_files": config_files,
    }


def _run(
    tmp_path: Path,
    runner: LabelRunner,
    requested: Path | None = None,
    report: dict[str, object] | None = None,
) -> dict[str, object]:
    requested_directory = requested or tmp_path / "unused"
    return build_live_readiness_report(
        tmp_path / "rollback.tar.gz",
        tmp_path / "migration.tar.gz",
        compose_directory=requested_directory,
        expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
        runner=runner,
        base_builder=_builder_for(
            report or _base_report(requested_directory)
        ),
    )


def test_discovers_nonstandard_compose_filename_from_live_labels(
    tmp_path: Path,
) -> None:
    working = tmp_path / "live-stack"
    working.mkdir()
    config = working / "greenhouse.t1.stack.yaml"
    config.write_text("services: {}\n", encoding="utf-8")
    env = working / ".env"
    env.write_text("LOCAL_ONLY=value\n", encoding="utf-8")
    env.chmod(0o600)
    labels = _labels("greenhouse", working, str(config))
    runner = LabelRunner(
        {
            "mosquitto": labels,
            "greenhouse-manager": labels,
        }
    )

    result = _run(tmp_path, runner)

    assert result["ready"] is True
    assert result["gates"]["compose_metadata_consistent"] is True
    assert result["gates"]["compose_configuration_present"] is True
    assert result["gates"]["compose_env_private"] is True
    assert result["compose"]["source"] == "docker_compose_labels"
    assert result["compose"]["project"] == "greenhouse"
    assert result["compose"]["projects"] == ["greenhouse"]
    assert result["compose"]["directory"] == str(working.resolve())
    assert result["compose"]["files"][0]["path"] == str(config.resolve())
    assert result["compose"]["env"]["mode"] == "600"
    assert len(result["compose"]["deployments"]) == 1


def test_same_source_allows_project_and_path_form_differences(
    tmp_path: Path,
) -> None:
    working = tmp_path / "stack"
    working.mkdir()
    config = working / "greenhouse-stack.yml"
    config.write_text("services: {}\n", encoding="utf-8")
    runner = LabelRunner(
        {
            "mosquitto": _labels(
                "greenhouse-broker",
                working,
                str(config),
            ),
            "greenhouse-manager": _labels(
                "greenhouse-manager",
                working / ".",
                config.name,
            ),
        }
    )

    result = _run(tmp_path, runner)

    assert result["ready"] is True
    assert result["compose"]["project"] is None
    assert result["compose"]["projects"] == [
        "greenhouse-broker",
        "greenhouse-manager",
    ]
    assert len(result["compose"]["deployments"]) == 1
    assert result["compose"]["deployments"][0]["containers"] == [
        "greenhouse-manager",
        "mosquitto",
    ]
    assert result["compose"]["deployments"][0]["env"]["exists"] is False


def test_independent_compose_projects_are_valid_inventory(
    tmp_path: Path,
) -> None:
    broker = tmp_path / "ha_docker"
    manager = tmp_path / "t1"
    broker.mkdir()
    manager.mkdir()
    broker_config = broker / "docker-compose.yml"
    manager_config = manager / "docker-compose.manager.yml"
    broker_config.write_text("services: {}\n", encoding="utf-8")
    manager_config.write_text("services: {}\n", encoding="utf-8")
    manager_env = manager / ".env"
    manager_env.write_text("LOCAL_ONLY=value\n", encoding="utf-8")
    manager_env.chmod(0o600)
    runner = LabelRunner(
        {
            "mosquitto": _labels(
                "ha_docker",
                broker,
                str(broker_config),
            ),
            "greenhouse-manager": _labels(
                "t1",
                manager,
                manager_config.name,
            ),
        }
    )

    result = _run(tmp_path, runner)

    assert result["ready"] is True
    assert result["gates"]["compose_metadata_consistent"] is True
    assert result["gates"]["compose_directory_present"] is True
    assert result["gates"]["compose_configuration_present"] is True
    assert result["gates"]["compose_env_private"] is True
    assert result["compose"]["projects"] == ["ha_docker", "t1"]
    assert result["compose"]["directory"] is None
    assert result["compose"]["files"] == []
    assert result["compose"]["env"] is None
    assert len(result["compose"]["deployments"]) == 2
    deployments = {
        item["directory"]: item
        for item in result["compose"]["deployments"]
    }
    assert deployments[str(broker.resolve())]["containers"] == ["mosquitto"]
    assert deployments[str(broker.resolve())]["env"]["exists"] is False
    assert deployments[str(manager.resolve())]["containers"] == [
        "greenhouse-manager"
    ]
    assert deployments[str(manager.resolve())]["env"]["mode"] == "600"


def test_existing_non_private_env_is_the_only_compose_failure(
    tmp_path: Path,
) -> None:
    broker = tmp_path / "ha_docker"
    manager = tmp_path / "t1"
    broker.mkdir()
    manager.mkdir()
    broker_config = broker / "docker-compose.yml"
    manager_config = manager / "docker-compose.manager.yml"
    broker_config.write_text("services: {}\n", encoding="utf-8")
    manager_config.write_text("services: {}\n", encoding="utf-8")
    manager_env = manager / ".env"
    manager_env.write_text("LOCAL_ONLY=value\n", encoding="utf-8")
    manager_env.chmod(0o644)
    runner = LabelRunner(
        {
            "mosquitto": _labels(
                "ha_docker",
                broker,
                str(broker_config),
            ),
            "greenhouse-manager": _labels(
                "t1",
                manager,
                manager_config.name,
            ),
        }
    )

    result = _run(tmp_path, runner)

    false_gates = sorted(
        key
        for key, value in result["gates"].items()
        if value is not True
    )
    assert result["ready"] is False
    assert false_gates == ["compose_env_private"]
    assert result["compose"]["metadata_consistent"] is True
    non_private = [
        item["env"]
        for item in result["compose"]["deployments"]
        if item["env"]["exists"] and item["env"]["mode"] != "600"
    ]
    assert len(non_private) == 1
    assert non_private[0]["path"] == str(manager_env.resolve())
    assert non_private[0]["mode"] == "644"


def test_missing_config_file_blocks_configuration_gate(
    tmp_path: Path,
) -> None:
    working = tmp_path / "stack"
    working.mkdir()
    missing = working / "missing.yml"
    labels = _labels("greenhouse", working, missing.name)
    runner = LabelRunner(
        {
            "mosquitto": labels,
            "greenhouse-manager": labels,
        }
    )

    result = _run(tmp_path, runner)

    assert result["ready"] is False
    assert result["gates"]["compose_metadata_consistent"] is True
    assert result["gates"]["compose_directory_present"] is True
    assert result["gates"]["compose_configuration_present"] is False


def test_incomplete_labels_block_metadata_gate(tmp_path: Path) -> None:
    working = tmp_path / "stack"
    working.mkdir()
    runner = LabelRunner(
        {
            "mosquitto": _labels("greenhouse", working, "stack.yml"),
            "greenhouse-manager": {
                "com.docker.compose.project": "greenhouse-manager",
                "com.docker.compose.project.working_dir": str(working),
            },
        }
    )

    result = _run(tmp_path, runner)

    assert result["ready"] is False
    assert result["gates"]["compose_metadata_consistent"] is False
    assert result["compose"]["metadata_reason"] == "compose_labels_incomplete"


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

    result = _run(
        tmp_path,
        runner,
        requested=requested,
        report=report,
    )

    assert result["ready"] is True
    assert result["gates"]["compose_metadata_consistent"] is True
    assert result["compose"]["source"] == "requested_directory_fallback"
