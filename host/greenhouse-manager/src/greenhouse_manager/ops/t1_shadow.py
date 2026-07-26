from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from .t1_backup import BackupError, _extract_verified

PLUGIN_LINE = "plugin /usr/lib/mosquitto_dynamic_security.so"
PLUGIN_CONFIG_LINE = (
    "plugin_opt_config_file /mosquitto/data/dynamic-security.json"
)
PLUGIN_PASSWORD_INIT_LINE = (
    "plugin_opt_password_init_file /mosquitto/config/dynsec-password-init"
)
LEGACY_ROLE = "gh-legacy-anonymous-shadow"
LEGACY_GROUP = "gh-legacy-anonymous-shadow"


class ShadowError(RuntimeError):
    pass


class CommandRunner(Protocol):
    def run(
        self, command: Sequence[str], *, input_text: str | None = None
    ) -> tuple[int, str]: ...


class SubprocessRunner:
    def run(
        self, command: Sequence[str], *, input_text: str | None = None
    ) -> tuple[int, str]:
        completed = subprocess.run(
            tuple(command),
            check=False,
            capture_output=True,
            text=True,
            input=input_text,
        )
        output = completed.stdout if completed.stdout else completed.stderr
        return completed.returncode, output


def prepare_shadow_config(path: Path) -> None:
    config = path.read_text(encoding="utf-8")
    active_lines = [
        line.strip()
        for line in config.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if any(
        line.startswith("plugin ")
        or line.startswith("global_plugin ")
        or line.startswith("auth_plugin ")
        for line in active_lines
    ):
        raise ShadowError("snapshot already contains an authentication plugin")
    anonymous_values = [
        line.split(maxsplit=1)[1].lower()
        for line in active_lines
        if line.startswith("allow_anonymous ") and len(line.split(maxsplit=1)) == 2
    ]
    if not anonymous_values or anonymous_values[-1] not in {
        "true",
        "yes",
        "1",
        "on",
    }:
        raise ShadowError("snapshot does not explicitly allow legacy anonymous access")
    suffix = "" if config.endswith("\n") else "\n"
    path.write_text(
        config
        + suffix
        + "\n# M2 shadow candidate; snapshot copy only\n"
        + PLUGIN_LINE
        + "\n"
        + PLUGIN_CONFIG_LINE
        + "\n"
        + PLUGIN_PASSWORD_INIT_LINE
        + "\n",
        encoding="utf-8",
    )


def legacy_shadow_ctrl_commands() -> tuple[tuple[str, ...], ...]:
    commands: list[tuple[str, ...]] = [
        ("setDefaultACLAccess", "publishClientSend", "deny"),
        ("setDefaultACLAccess", "publishClientReceive", "deny"),
        ("setDefaultACLAccess", "subscribe", "deny"),
        ("setDefaultACLAccess", "unsubscribe", "allow"),
        ("createRole", LEGACY_ROLE),
        (
            "addRoleACL",
            LEGACY_ROLE,
            "publishClientSend",
            "$CONTROL/#",
            "deny",
            "1000",
        ),
        (
            "addRoleACL",
            LEGACY_ROLE,
            "subscribePattern",
            "$CONTROL/#",
            "deny",
            "1000",
        ),
    ]
    for acl_type in (
        "publishClientSend",
        "subscribePattern",
        "publishClientReceive",
        "unsubscribePattern",
    ):
        commands.append(
            ("addRoleACL", LEGACY_ROLE, acl_type, "#", "allow", "100")
        )
    for acl_type in (
        "subscribePattern",
        "publishClientReceive",
        "unsubscribePattern",
    ):
        commands.append(
            (
                "addRoleACL",
                LEGACY_ROLE,
                acl_type,
                "$SYS/#",
                "allow",
                "100",
            )
        )
    commands.extend(
        (
            ("createGroup", LEGACY_GROUP),
            ("addGroupRole", LEGACY_GROUP, LEGACY_ROLE, "100"),
            ("setAnonymousGroup", LEGACY_GROUP),
        )
    )
    return tuple(commands)


def _require_success(
    runner: CommandRunner,
    command: Sequence[str],
    message: str,
    *,
    input_text: str | None = None,
) -> str:
    return_code, output = runner.run(command, input_text=input_text)
    if return_code != 0:
        raise ShadowError(message)
    return output.strip()


def _mount(source: Path, destination: str, *, read_only: bool = False) -> str:
    options = f"type=bind,src={source},dst={destination}"
    if read_only:
        options += ",readonly"
    return options


def _prepare_snapshot_directories(config_dir: Path, data_dir: Path) -> None:
    data_files = sorted(path for path in data_dir.rglob("*") if path.is_file())
    if not data_files:
        raise ShadowError("snapshot Mosquitto data directory is empty")
    preferred_owner = next(
        (path for path in data_files if path.name == "mosquitto.db"),
        data_files[0],
    ).stat()
    os.chown(data_dir, preferred_owner.st_uid, preferred_owner.st_gid)
    data_dir.chmod(0o700)
    config_dir.chmod(0o755)


def _wait_for_file(path: Path, *, timeout_s: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if path.is_file():
            return True
        time.sleep(0.1)
    return path.is_file()


def _candidate_diagnostic(
    runner: CommandRunner, container_id: str, *, secret: str
) -> str:
    probes = {
        "plugin_file": "test -f /usr/lib/mosquitto_dynamic_security.so",
        "config_plugin_line": (
            "grep -Fqx 'plugin /usr/lib/mosquitto_dynamic_security.so' "
            "/mosquitto/config/mosquitto.conf"
        ),
        "password_init_readable": (
            "test -r /mosquitto/config/dynsec-password-init"
        ),
        "data_directory_writable": "test -w /mosquitto/data",
    }
    results: list[str] = []
    for name, script in probes.items():
        return_code, _output = runner.run(
            ("docker", "exec", container_id, "sh", "-c", script)
        )
        results.append(f"{name}={'yes' if return_code == 0 else 'no'}")
    _return_code, output = runner.run(
        ("docker", "logs", "--tail", "80", container_id)
    )
    safe_lines: list[str] = []
    for line in output.replace(secret, "[redacted]").splitlines():
        lowered = line.lower()
        if any(
            token in lowered
            for token in ("dynamic", "plugin", "error", "warning")
        ):
            printable = "".join(character for character in line if character.isprintable())
            safe_lines.append(printable[:240])
    if safe_lines:
        results.append("logs=" + " | ".join(safe_lines[-12:]))
    else:
        results.append("logs=no relevant candidate log lines")
    return "; ".join(results)


def run_shadow_candidate(
    archive: str | Path,
    *,
    expected_retained_topic: str,
    runner: CommandRunner | None = None,
    password_factory: Callable[[], str] | None = None,
    name_factory: Callable[[], str] | None = None,
) -> dict[str, object]:
    if not expected_retained_topic.startswith("gh/"):
        raise ValueError("expected retained topic must be in the gh namespace")
    command_runner = runner or SubprocessRunner()
    archive_path = Path(archive).expanduser().resolve()
    candidate_name = (
        name_factory()
        if name_factory
        else f"gh-m2-shadow-{secrets.token_hex(4)}"
    )
    admin_password = (
        password_factory() if password_factory else secrets.token_urlsafe(32)
    )
    if len(admin_password) < 32:
        raise ValueError("candidate admin password must be at least 32 characters")

    container_id = candidate_name
    created = False
    with tempfile.TemporaryDirectory(prefix="gh-m2-shadow-") as temporary:
        staging = Path(temporary)
        staging.chmod(0o700)
        manifest = _extract_verified(archive_path, staging)
        config_dir = staging / "mosquitto-config"
        data_dir = staging / "mosquitto-data"
        config_path = config_dir / "mosquitto.conf"
        if not config_path.is_file() or not data_dir.is_dir():
            raise ShadowError("snapshot is missing Mosquitto configuration or data")
        prepare_shadow_config(config_path)
        _prepare_snapshot_directories(config_dir, data_dir)
        dynsec_path = data_dir / "dynamic-security.json"
        if dynsec_path.exists():
            raise ShadowError("snapshot already contains Dynamic Security state")

        image_id = manifest["sources"]["mosquitto"]["image_id"]
        data_stat = data_dir.stat()
        password_init_path = config_dir / "dynsec-password-init"
        password_init_path.write_text(admin_password + "\n", encoding="utf-8")
        # Mosquitto drops privileges before the plugin reads this file. The
        # 0700 temporary parent and isolated bind mount remain the security
        # boundary; 0644 avoids guessing the image's runtime uid/gid.
        password_init_path.chmod(0o644)

        create_command = (
            "docker",
            "create",
            "--network",
            "none",
            "--name",
            candidate_name,
            "--mount",
            _mount(config_dir, "/mosquitto/config"),
            "--mount",
            _mount(data_dir, "/mosquitto/data"),
            image_id,
        )
        output = _require_success(
            command_runner,
            create_command,
            "shadow candidate container could not be created",
        )
        created = True
        container_id = output or candidate_name
        try:
            _require_success(
                command_runner,
                ("docker", "start", container_id),
                "shadow candidate broker did not start",
            )
            state = _require_success(
                command_runner,
                (
                    "docker",
                    "inspect",
                    "-f",
                    "{{.State.Status}}",
                    container_id,
                ),
                "shadow candidate state could not be inspected",
            )
            if state != "running":
                raise ShadowError("shadow candidate broker is not running")
            if not _wait_for_file(dynsec_path):
                state = _require_success(
                    command_runner,
                    (
                        "docker",
                        "inspect",
                        "-f",
                        "{{.State.Status}} exit={{.State.ExitCode}}",
                        container_id,
                    ),
                    "shadow candidate final state could not be inspected",
                )
                raise ShadowError(
                    "Dynamic Security candidate state was not created "
                    f"within 10 seconds ({state}); "
                    + _candidate_diagnostic(
                        command_runner,
                        container_id,
                        secret=admin_password,
                    )
                )
            os.chown(dynsec_path, data_stat.st_uid, data_stat.st_gid)
            dynsec_path.chmod(0o600)
            password_init_path.unlink(missing_ok=True)

            client_config = staging / "mosquitto-ctrl.conf"
            client_config.write_text(
                "-h 127.0.0.1\n"
                "-u admin\n"
                f"-P {admin_password}\n"
                "-V 5\n",
                encoding="utf-8",
            )
            client_config.chmod(0o600)
            _require_success(
                command_runner,
                (
                    "docker",
                    "cp",
                    "--archive",
                    str(client_config),
                    f"{container_id}:/tmp/gh-m2-ctrl.conf",
                ),
                "shadow candidate control configuration copy failed",
            )
            for command in legacy_shadow_ctrl_commands():
                _require_success(
                    command_runner,
                    (
                        "docker",
                        "exec",
                        container_id,
                        "mosquitto_ctrl",
                        "-o",
                        "/tmp/gh-m2-ctrl.conf",
                        "dynsec",
                        *command,
                    ),
                    f"shadow candidate policy command failed: {command[0]}",
                )

            probe_topic = "gh/m2/shadow/probe"
            _require_success(
                command_runner,
                (
                    "docker",
                    "exec",
                    container_id,
                    "mosquitto_pub",
                    "-h",
                    "127.0.0.1",
                    "-V",
                    "5",
                    "-q",
                    "1",
                    "-r",
                    "-t",
                    probe_topic,
                    "-m",
                    "ok",
                ),
                "legacy anonymous publish failed in candidate",
            )
            _require_success(
                command_runner,
                (
                    "docker",
                    "exec",
                    container_id,
                    "mosquitto_sub",
                    "-h",
                    "127.0.0.1",
                    "-V",
                    "5",
                    "-C",
                    "1",
                    "-W",
                    "5",
                    "-F",
                    "%t",
                    "-t",
                    probe_topic,
                ),
                "legacy anonymous subscribe failed in candidate",
            )
            retained = _require_success(
                command_runner,
                (
                    "docker",
                    "exec",
                    container_id,
                    "mosquitto_sub",
                    "-h",
                    "127.0.0.1",
                    "-V",
                    "5",
                    "-C",
                    "1",
                    "-W",
                    "5",
                    "-F",
                    "%t",
                    "-t",
                    expected_retained_topic,
                ),
                "snapshot retained state was not recovered",
            )
            if retained != expected_retained_topic:
                raise ShadowError("snapshot retained state topic did not match")

            canary = "gh-shadow-forbidden-canary"
            control_payload = json.dumps(
                {
                    "commands": [
                        {
                            "command": "createClient",
                            "username": canary,
                            "password": "candidate-only",
                            "clientid": canary,
                        }
                    ]
                },
                separators=(",", ":"),
            )
            command_runner.run(
                (
                    "docker",
                    "exec",
                    container_id,
                    "mosquitto_pub",
                    "-h",
                    "127.0.0.1",
                    "-V",
                    "5",
                    "-q",
                    "1",
                    "-t",
                    "$CONTROL/dynamic-security/v1",
                    "-m",
                    control_payload,
                )
            )
            return_code, clients = command_runner.run(
                (
                    "docker",
                    "exec",
                    container_id,
                    "mosquitto_ctrl",
                    "-o",
                    "/tmp/gh-m2-ctrl.conf",
                    "dynsec",
                    "listClients",
                )
            )
            if return_code != 0:
                raise ShadowError("candidate client inventory could not be read")
            if canary in {line.strip() for line in clients.splitlines()}:
                raise ShadowError("anonymous client changed candidate security state")
        finally:
            if created:
                command_runner.run(("docker", "rm", "-f", container_id))

    return {
        "schema": "gh.m2.t1-shadow-candidate/1",
        "archive": archive_path.name,
        "network": "none",
        "legacy_anonymous_application_topics": True,
        "anonymous_control_denied": True,
        "retained_state_recovered": True,
        "current_services_modified": False,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: CommandRunner | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a Dynamic Security shadow candidate from a T1 backup"
    )
    parser.add_argument("archive")
    parser.add_argument("--expected-retained-topic", required=True)
    args = parser.parse_args(argv)
    try:
        result = run_shadow_candidate(
            args.archive,
            expected_retained_topic=args.expected_retained_topic,
            runner=runner,
        )
    except (BackupError, ShadowError, OSError) as error:
        print(f"T1 shadow candidate failed: {error}", file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
