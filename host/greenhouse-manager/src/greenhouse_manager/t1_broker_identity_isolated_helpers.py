from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from .t1_broker_identity_activation_checks import Runner, read_json

_CANDIDATE_NAME = re.compile(r"^gh-m2-isolated-[a-z0-9-]{8,80}$")
_CONTROL = "$CONTROL/dynamic-security/v1"
_RESPONSE = "$CONTROL/dynamic-security/v1/response"
_LIST_CLIENTS = '{"commands":[{"command":"listClients"}]}'


class BrokerIdentityIsolatedTransactionError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(value: object, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise BrokerIdentityIsolatedTransactionError(f"{label} path is missing")
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise BrokerIdentityIsolatedTransactionError(f"{label} path is unsafe")
    return relative


def _private_file(path: Path, label: str) -> None:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise BrokerIdentityIsolatedTransactionError(
            f"{label} is missing or not private"
        )


def _tree_inventory(root: Path) -> tuple[tuple[str, int, str], ...]:
    records: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise BrokerIdentityIsolatedTransactionError(
                "isolated transaction source contains a symlink"
            )
        if path.is_file():
            records.append(
                (
                    path.relative_to(root).as_posix(),
                    path.stat().st_mode & 0o777,
                    _sha(path),
                )
            )
    return tuple(records)


def _active_config_lines(path: Path) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def _anonymous_enabled(lines: Sequence[str]) -> bool:
    accepted = {
        "allow_anonymous true",
        "allow_anonymous yes",
        "allow_anonymous 1",
        "allow_anonymous on",
    }
    return any(line.lower() in accepted for line in lines)


def _request_commands(path: Path) -> tuple[dict[str, Any], ...]:
    request = read_json(path, "isolated Dynamic Security request")
    raw = request.get("commands")
    if not isinstance(raw, list) or not raw:
        raise BrokerIdentityIsolatedTransactionError(
            "isolated Dynamic Security request is empty"
        )
    commands: list[dict[str, Any]] = []
    for command in raw:
        if not isinstance(command, dict) or not isinstance(
            command.get("command"), str
        ):
            raise BrokerIdentityIsolatedTransactionError(
                "isolated Dynamic Security request is invalid"
            )
        commands.append(command)
    return tuple(commands)


def _temporary_client(
    runner: Runner,
    container_id: str,
    config: str,
    program: str,
    arguments: Sequence[str],
) -> tuple[int, str]:
    script = (
        "umask 077; f=/tmp/gh-m2-isolated-check-$$.conf; "
        'trap \'rm -f "$f"\' EXIT; cat > "$f"; '
        f'{program} -o "$f" "$@"'
    )
    return runner.run(
        (
            "docker",
            "exec",
            "-i",
            container_id,
            "sh",
            "-c",
            script,
            "sh",
            *arguments,
        ),
        input_text=config,
    )


def _ha_config(update: dict[str, Any], client_id: str | None = None) -> str:
    username = update.get("username")
    password = update.get("password")
    required_id = update.get("required_client_id")
    if not all(
        isinstance(value, str) and value
        for value in (username, password, required_id)
    ):
        raise BrokerIdentityIsolatedTransactionError(
            "isolated Home Assistant identity is incomplete"
        )
    selected = client_id or str(required_id)
    return (
        f"-h 127.0.0.1\n-u {username}\n-P {password}\n"
        f"-i {selected}\n-V 5\n"
    )


def _identity_retained(
    runner: Runner,
    container_id: str,
    config: str,
    topic: str,
) -> bool:
    code, output = _temporary_client(
        runner,
        container_id,
        config,
        "mosquitto_sub",
        ("-C", "1", "-W", "5", "-F", "%p", "-t", topic),
    )
    return code == 0 and bool(output.strip())


def _list_clients(
    runner: Runner,
    container_id: str,
    config: str,
) -> bool:
    code, output = _temporary_client(
        runner,
        container_id,
        config,
        "mosquitto_rr",
        (
            "-q",
            "1",
            "-W",
            "5",
            "-t",
            _CONTROL,
            "-e",
            _RESPONSE,
            "-m",
            _LIST_CLIENTS,
        ),
    )
    if code != 0:
        return False
    try:
        value = json.loads(output)
    except json.JSONDecodeError:
        return False
    responses = value.get("responses") if isinstance(value, dict) else None
    return bool(
        isinstance(responses, list)
        and responses
        and isinstance(responses[0], dict)
        and responses[0].get("command") == "listClients"
        and not responses[0].get("error")
    )


def _anonymous_retained(
    runner: Runner,
    container_id: str,
    topic: str,
) -> bool:
    code, output = runner.run(
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
            "%p",
            "-t",
            topic,
        )
    )
    return code == 0 and bool(output.strip())


def _anonymous_control_denied(runner: Runner, container_id: str) -> bool:
    code, output = runner.run(
        (
            "docker",
            "exec",
            container_id,
            "mosquitto_rr",
            "-h",
            "127.0.0.1",
            "-V",
            "5",
            "-q",
            "1",
            "-W",
            "2",
            "-t",
            _CONTROL,
            "-e",
            _RESPONSE,
            "-m",
            _LIST_CLIENTS,
        )
    )
    if code != 0:
        return True
    try:
        value = json.loads(output)
    except json.JSONDecodeError:
        return False
    responses = value.get("responses") if isinstance(value, dict) else None
    return bool(
        isinstance(responses, list)
        and responses
        and isinstance(responses[0], dict)
        and responses[0].get("error")
    )
