from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .t1_migration_readiness import (
    CommandRunner,
    ReadinessError,
    SubprocessRunner,
    _private_file_observation,
)
from .t1_migration_readiness import (
    build_readiness_report as _build_base_report,
)

_PROJECT_LABEL = "com.docker.compose.project"
_WORKING_DIR_LABEL = "com.docker.compose.project.working_dir"
_CONFIG_FILES_LABEL = "com.docker.compose.project.config_files"
_COMPOSE_CONTAINERS = ("mosquitto", "greenhouse-manager")

BaseBuilder = Callable[..., dict[str, object]]


@dataclass(frozen=True, slots=True)
class ComposeSourceObservation:
    container: str
    project: str | None
    working_dir: Path | None
    config_files: tuple[Path, ...]
    complete: bool


@dataclass(frozen=True, slots=True)
class ComposeDiscovery:
    labels_present: bool
    consistent: bool
    projects: tuple[str, ...]
    working_dir: Path | None
    config_files: tuple[Path, ...]
    observations: tuple[ComposeSourceObservation, ...]
    reason: str | None


def _inspect_labels(
    runner: CommandRunner,
    container: str,
) -> dict[str, str]:
    return_code, output = runner.run(
        (
            "docker",
            "inspect",
            "-f",
            "{{json .Config.Labels}}",
            container,
        )
    )
    if return_code != 0:
        raise ReadinessError(
            f"Compose labels cannot be inspected: {container}"
        )
    try:
        document = json.loads(output)
    except json.JSONDecodeError as error:
        raise ReadinessError(
            f"Compose labels returned invalid JSON: {container}"
        ) from error
    if document is None:
        return {}
    if not isinstance(document, dict):
        raise ReadinessError(
            f"Compose labels are not a JSON object: {container}"
        )
    return {
        str(key): str(value)
        for key, value in document.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _resolve_config_files(
    working_dir: Path,
    raw_config_files: str,
) -> tuple[Path, ...]:
    resolved: list[Path] = []
    for raw_path in raw_config_files.split(","):
        value = raw_path.strip()
        if not value:
            continue
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = working_dir / path
        resolved.append(path.resolve())
    return tuple(resolved)


def _observe_compose_source(
    runner: CommandRunner,
    container: str,
) -> tuple[ComposeSourceObservation, bool]:
    labels = _inspect_labels(runner, container)
    raw_project = labels.get(_PROJECT_LABEL, "").strip()
    raw_working_dir = labels.get(_WORKING_DIR_LABEL, "").strip()
    raw_config_files = labels.get(_CONFIG_FILES_LABEL, "").strip()
    labels_present = bool(
        raw_project or raw_working_dir or raw_config_files
    )

    working_dir = (
        Path(raw_working_dir).expanduser().resolve()
        if raw_working_dir
        else None
    )
    config_files = (
        _resolve_config_files(working_dir, raw_config_files)
        if working_dir is not None and raw_config_files
        else ()
    )
    observation = ComposeSourceObservation(
        container=container,
        project=raw_project or None,
        working_dir=working_dir,
        config_files=config_files,
        complete=bool(raw_project and working_dir is not None and config_files),
    )
    return observation, labels_present


def discover_live_compose(runner: CommandRunner) -> ComposeDiscovery:
    observations: list[ComposeSourceObservation] = []
    labels_present = False
    for container in _COMPOSE_CONTAINERS:
        observation, container_labels_present = _observe_compose_source(
            runner,
            container,
        )
        observations.append(observation)
        labels_present = labels_present or container_labels_present

    frozen_observations = tuple(observations)
    if not labels_present:
        return ComposeDiscovery(
            labels_present=False,
            consistent=False,
            projects=(),
            working_dir=None,
            config_files=(),
            observations=frozen_observations,
            reason="compose_labels_absent",
        )

    projects = tuple(
        sorted(
            {
                observation.project
                for observation in observations
                if observation.project is not None
            }
        )
    )
    if any(not observation.complete for observation in observations):
        return ComposeDiscovery(
            labels_present=True,
            consistent=False,
            projects=projects,
            working_dir=None,
            config_files=(),
            observations=frozen_observations,
            reason="compose_labels_incomplete",
        )

    first = observations[0]
    same_source = all(
        observation.working_dir == first.working_dir
        and observation.config_files == first.config_files
        for observation in observations[1:]
    )
    if not same_source:
        return ComposeDiscovery(
            labels_present=True,
            consistent=False,
            projects=projects,
            working_dir=None,
            config_files=(),
            observations=frozen_observations,
            reason="compose_sources_disagree",
        )

    return ComposeDiscovery(
        labels_present=True,
        consistent=True,
        projects=projects,
        working_dir=first.working_dir,
        config_files=first.config_files,
        observations=frozen_observations,
        reason=None,
    )


def _observation_report(
    observation: ComposeSourceObservation,
) -> dict[str, object]:
    return {
        "project": observation.project,
        "directory": (
            str(observation.working_dir)
            if observation.working_dir is not None
            else None
        ),
        "files": [str(path) for path in observation.config_files],
        "complete": observation.complete,
    }


def _compose_source_report(
    discovery: ComposeDiscovery,
) -> dict[str, dict[str, object]]:
    return {
        observation.container: _observation_report(observation)
        for observation in discovery.observations
    }


def _apply_compose_discovery(
    report: dict[str, object],
    discovery: ComposeDiscovery,
) -> None:
    gates = report.get("gates")
    compose = report.get("compose")
    if not isinstance(gates, dict) or not isinstance(compose, dict):
        raise ReadinessError("base readiness report is missing Compose gates")

    requested_directory = str(compose.get("directory", ""))
    if not discovery.labels_present:
        files = compose.get("files")
        fallback_present = isinstance(files, list) and bool(files)
        compose["source"] = "requested_directory_fallback"
        compose["requested_directory"] = requested_directory
        compose["metadata_consistent"] = fallback_present
        compose["metadata_reason"] = discovery.reason
        compose["container_sources"] = _compose_source_report(discovery)
        gates["compose_metadata_consistent"] = fallback_present
        report["ready"] = all(bool(value) for value in gates.values())
        return

    if not discovery.consistent or discovery.working_dir is None:
        compose.clear()
        compose.update(
            {
                "source": "docker_compose_labels",
                "requested_directory": requested_directory,
                "projects": list(discovery.projects),
                "directory": None,
                "files": [],
                "env": None,
                "container_sources": _compose_source_report(discovery),
                "metadata_consistent": False,
                "metadata_reason": discovery.reason,
            }
        )
        gates["compose_directory_present"] = False
        gates["compose_configuration_present"] = False
        gates["compose_env_private"] = False
        gates["compose_metadata_consistent"] = False
        report["ready"] = False
        return

    file_observations = tuple(
        _private_file_observation(path)
        for path in discovery.config_files
    )
    env_observation = _private_file_observation(
        discovery.working_dir / ".env"
    )
    compose.clear()
    compose.update(
        {
            "source": "docker_compose_labels",
            "requested_directory": requested_directory,
            "project": (
                discovery.projects[0]
                if len(discovery.projects) == 1
                else None
            ),
            "projects": list(discovery.projects),
            "directory": str(discovery.working_dir),
            "files": [asdict(item) for item in file_observations],
            "env": asdict(env_observation),
            "container_sources": _compose_source_report(discovery),
            "metadata_consistent": True,
            "metadata_reason": None,
        }
    )
    gates["compose_directory_present"] = discovery.working_dir.is_dir()
    gates["compose_configuration_present"] = bool(file_observations) and all(
        item.exists for item in file_observations
    )
    gates["compose_env_private"] = (
        env_observation.exists and env_observation.mode == "600"
    )
    gates["compose_metadata_consistent"] = True
    report["ready"] = all(bool(value) for value in gates.values())


def build_live_readiness_report(
    rollback_archive: str | Path,
    migration_package: str | Path,
    *,
    compose_directory: str | Path = "/opt/HomeAssistant/infra/compose/t1",
    secret_root: str | Path = "/opt/greenhouse-secrets/mqtt",
    expected_retained_topic: str,
    runner: CommandRunner | None = None,
    generated_at: datetime | None = None,
    base_builder: BaseBuilder | None = None,
) -> dict[str, object]:
    command_runner = runner or SubprocessRunner()
    builder = base_builder or _build_base_report
    report = builder(
        rollback_archive,
        migration_package,
        compose_directory=compose_directory,
        secret_root=secret_root,
        expected_retained_topic=expected_retained_topic,
        runner=command_runner,
        generated_at=generated_at,
    )
    discovery = discover_live_compose(command_runner)
    _apply_compose_discovery(report, discovery)
    return report


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: CommandRunner | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only real T1 authenticated MQTT migration readiness audit "
            "with normalized live Compose source discovery."
        )
    )
    parser.add_argument("rollback_archive")
    parser.add_argument("migration_package")
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument(
        "--compose-directory",
        default="/opt/HomeAssistant/infra/compose/t1",
        help="fallback directory used only when Compose labels are absent",
    )
    parser.add_argument(
        "--secret-root",
        default="/opt/greenhouse-secrets/mqtt",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build_live_readiness_report(
            args.rollback_archive,
            args.migration_package,
            compose_directory=args.compose_directory,
            secret_root=args.secret_root,
            expected_retained_topic=args.expected_retained_topic,
            runner=runner,
        )
    except (ReadinessError, OSError, ValueError) as error:
        print(
            f"T1 migration readiness audit failed: {error}",
            file=sys.stderr,
        )
        return 2
    json.dump(
        report,
        sys.stdout,
        ensure_ascii=False,
        indent=2 if args.pretty else None,
        separators=None if args.pretty else (",", ":"),
    )
    sys.stdout.write("\n")
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
