from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Protocol

SAFE_DIRECTIVES = frozenset(
    {
        "acl_file",
        "allow_anonymous",
        "include_dir",
        "listener",
        "password_file",
        "per_listener_settings",
        "persistence",
        "persistence_location",
        "plugin",
        "plugin_opt_config_file",
    }
)


class CommandRunner(Protocol):
    def run(self, command: Sequence[str]) -> tuple[int, str]: ...


class SubprocessRunner:
    def run(self, command: Sequence[str]) -> tuple[int, str]:
        completed = subprocess.run(
            tuple(command),
            check=False,
            capture_output=True,
            text=True,
        )
        output = completed.stdout if completed.stdout else completed.stderr
        return completed.returncode, output


@dataclass(frozen=True, slots=True)
class ContainerStatus:
    name: str
    state: str
    health: str | None
    restart_count: int
    image: str


def parse_safe_directives(config: str) -> tuple[dict[str, str], ...]:
    directives: list[dict[str, str]] = []
    for raw_line in config.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition(" ")
        key = key.lower()
        if not separator:
            key, separator, value = line.partition("\t")
        if key not in SAFE_DIRECTIVES:
            continue
        directives.append({"directive": key, "value": value.strip()})
    return tuple(directives)


def _inspect_container(runner: CommandRunner, name: str) -> ContainerStatus:
    template = json.dumps(
        {
            "state": "{{.State.Status}}",
            "health": '{{if .State.Health}}{{.State.Health.Status}}{{end}}',
            "restarts": "{{.RestartCount}}",
            "image": "{{.Config.Image}}",
        },
        separators=(",", ":"),
    )
    return_code, output = runner.run(("docker", "inspect", "-f", template, name))
    if return_code != 0:
        return ContainerStatus(name, "missing", None, 0, "unknown")
    document = json.loads(output)
    health = document["health"] or None
    return ContainerStatus(
        name=name,
        state=document["state"],
        health=health,
        restart_count=int(document["restarts"]),
        image=document["image"],
    )


def _command_output(runner: CommandRunner, command: Sequence[str]) -> str | None:
    return_code, output = runner.run(command)
    if return_code != 0:
        return None
    return output.strip()


def build_report(
    runner: CommandRunner,
    *,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    observed_at = generated_at or datetime.now(UTC)
    broker = _inspect_container(runner, "mosquitto")
    manager = _inspect_container(runner, "greenhouse-manager")

    broker_version_output = _command_output(
        runner, ("docker", "exec", "mosquitto", "mosquitto", "-h")
    )
    broker_version = "unknown"
    if broker_version_output:
        for line in broker_version_output.splitlines():
            if line.lower().startswith("mosquitto version"):
                broker_version = line.strip()
                break

    config = _command_output(
        runner,
        (
            "docker",
            "exec",
            "mosquitto",
            "sh",
            "-c",
            "test -r /mosquitto/config/mosquitto.conf && "
            "cat /mosquitto/config/mosquitto.conf",
        ),
    )
    directives = parse_safe_directives(config or "")
    directive_map = {
        entry["directive"]: entry["value"] for entry in directives
    }

    plugin_available = (
        _command_output(
            runner,
            (
                "docker",
                "exec",
                "mosquitto",
                "sh",
                "-c",
                "test -f /usr/lib/mosquitto_dynamic_security.so && echo available",
            ),
        )
        == "available"
    )
    manager_version = _command_output(
        runner,
        (
            "docker",
            "exec",
            "greenhouse-manager",
            "python",
            "-c",
            "import importlib.metadata as m; print(m.version('greenhouse-manager'))",
        ),
    ) or "unknown"

    anonymous_value = directive_map.get("allow_anonymous")
    anonymous_mode: bool | None
    if anonymous_value is None:
        anonymous_mode = None
    else:
        anonymous_mode = anonymous_value.lower() in {"true", "yes", "1", "on"}

    dynamic_security_configured = any(
        entry["directive"] == "plugin"
        and "dynamic_security" in entry["value"]
        for entry in directives
    )
    gates = {
        "broker_running": broker.state == "running",
        "manager_running": manager.state == "running",
        "dynamic_security_plugin_available": plugin_available,
        "anonymous_access_not_changed": anonymous_mode is not False,
        "shadow_migration_not_active": not dynamic_security_configured,
    }
    return {
        "schema": "gh.m2.t1-preflight/1",
        "generated_at": observed_at.astimezone(UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "read_only": True,
        "containers": {
            "mosquitto": asdict(broker),
            "greenhouse_manager": asdict(manager),
        },
        "broker": {
            "version": broker_version,
            "safe_directives": directives,
            "anonymous_mode": anonymous_mode,
            "dynamic_security_plugin_available": plugin_available,
            "dynamic_security_configured": dynamic_security_configured,
        },
        "manager": {"version": manager_version},
        "gates": gates,
        "ready": all(gates.values()),
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: CommandRunner | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Read-only M2 T1 migration preflight")
    parser.add_argument(
        "--pretty", action="store_true", help="pretty-print the secret-free report"
    )
    args = parser.parse_args(argv)
    report = build_report(runner or SubprocessRunner())
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
