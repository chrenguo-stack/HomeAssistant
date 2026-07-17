from __future__ import annotations

import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path

from .node_mqtt_board_lab_broker import _base_report, _write_esphome_secrets
from .node_mqtt_board_lab_common import (
    ACL_NAME,
    ANONYMOUS_CLIENT_ID,
    CANDIDATE_CLIENT_ID,
    CANDIDATE_USERNAME,
    CONFIG_NAME,
    CONFIRMATION,
    CONTAINER_PREFIX,
    ESPHOME_SECRETS_NAME,
    MANIFEST_NAME,
    MANIFEST_SCHEMA,
    MARKER_NAME,
    OBSERVER_USERNAME,
    PASSWORD_NAME,
    SECRETS_NAME,
    BoardLabIdentity,
    NodeMqttBoardLabError,
    Runner,
    Waiter,
    _fingerprint,
    _identity_from_manifest,
    _load_manifest,
    _load_secrets,
    _private_json,
    _private_write,
    _require,
    _run,
    _validate_bind_host,
    _validate_port,
    _validate_workspace_for_create,
)

NATIVE_BACKEND = "native"
NATIVE_IMAGE = "native-mosquitto-2.0"
NATIVE_VERSION_PATTERN = re.compile(r"mosquitto version (2\.0\.\d+)", re.IGNORECASE)
PID_NAME = "mosquitto.pid"
LOG_NAME = "mosquitto.log"


def _resolve_executable(value: str) -> str:
    candidate = Path(value).expanduser()
    if candidate.parent != Path(".") or candidate.is_absolute():
        resolved = candidate.resolve()
        _require(resolved.is_file(), f"native executable is missing: {candidate.name}")
        _require(os.access(resolved, os.X_OK), f"native executable is not executable: {candidate.name}")
        return str(resolved)
    located = shutil.which(value)
    _require(located is not None, f"native executable is unavailable: {value}")
    resolved = Path(located).resolve()
    _require(os.access(resolved, os.X_OK), f"native executable is not executable: {value}")
    return str(resolved)


def _native_version(mosquitto_bin: str, runner: Runner) -> str:
    result = runner((mosquitto_bin, "-h"), check=False)
    encoded = f"{result.stdout}\n{result.stderr}"
    match = NATIVE_VERSION_PATTERN.search(encoded)
    _require(match is not None, "native Mosquitto must be from the 2.0 release family")
    return match.group(1)


def _native_manifest_fields(manifest: dict[str, object]) -> tuple[str, str, str]:
    _require(manifest.get("backend") == NATIVE_BACKEND, "board-lab manifest is not a native Broker lab")
    mosquitto_bin = manifest.get("native_mosquitto_bin")
    passwd_bin = manifest.get("native_mosquitto_passwd_bin")
    version = manifest.get("native_mosquitto_version")
    _require(isinstance(mosquitto_bin, str), "native Mosquitto path is missing")
    _require(isinstance(passwd_bin, str), "native mosquitto_passwd path is missing")
    _require(isinstance(version, str) and NATIVE_VERSION_PATTERN.fullmatch(f"mosquitto version {version}"), "native Mosquitto version is invalid")
    _require(Path(mosquitto_bin).is_file() and os.access(mosquitto_bin, os.X_OK), "native Mosquitto executable is unavailable")
    _require(Path(passwd_bin).is_file() and os.access(passwd_bin, os.X_OK), "native mosquitto_passwd executable is unavailable")
    return mosquitto_bin, passwd_bin, version


def _native_paths(workspace: Path) -> tuple[Path, Path, Path]:
    return workspace / CONFIG_NAME, workspace / PID_NAME, workspace / LOG_NAME


def _write_native_broker_files(
    workspace: Path,
    identity: BoardLabIdentity,
    *,
    candidate_password: str,
    observer_password: str,
    mosquitto_passwd_bin: str,
    runner: Runner,
) -> None:
    _require(not any(character.isspace() for character in str(workspace)), "native workspace path cannot contain whitespace")
    config_path, pid_path, log_path = _native_paths(workspace)
    config = "\n".join(
        (
            "per_listener_settings true",
            f"listener {identity.port} {identity.bind_host}",
            "allow_anonymous true",
            "persistence false",
            "connection_messages true",
            f"log_dest file {log_path}",
            "log_type all",
            f"pid_file {pid_path}",
            f"password_file {workspace / PASSWORD_NAME}",
            f"acl_file {workspace / ACL_NAME}",
            "",
        )
    )
    acl = "\n".join(
        (
            "pattern write lab/state/%c/#",
            "pattern read lab/control/%c/#",
            "",
            f"user {identity.observer_username}",
            "topic read lab/state/#",
            "topic write lab/control/#",
            "",
        )
    )
    password_plain = "\n".join(
        (
            f"{identity.candidate_username}:{candidate_password}",
            f"{identity.observer_username}:{observer_password}",
            "",
        )
    )
    _private_write(config_path, config)
    _private_write(workspace / ACL_NAME, acl)
    _private_write(workspace / PASSWORD_NAME, password_plain)
    runner((mosquitto_passwd_bin, "-U", str(workspace / PASSWORD_NAME)))
    password_data = (workspace / PASSWORD_NAME).read_text(encoding="utf-8")
    _require(candidate_password not in password_data, "candidate password remained plaintext")
    _require(observer_password not in password_data, "observer password remained plaintext")
    (workspace / PASSWORD_NAME).chmod(0o600)


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def _read_pid(pid_path: Path) -> int:
    try:
        encoded = pid_path.read_text(encoding="ascii").strip()
        pid = int(encoded)
    except (OSError, UnicodeError, ValueError) as error:
        raise NodeMqttBoardLabError("native Broker PID file is invalid") from error
    _require(pid > 1, "native Broker PID is invalid")
    return pid


def _process_command(pid: int, runner: Runner) -> str:
    result = runner(("ps", "-p", str(pid), "-o", "command="), check=False)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _validate_native_process(pid: int, mosquitto_bin: str, config_path: Path, runner: Runner) -> None:
    command = _process_command(pid, runner)
    _require(command, "native Broker process is not running")
    _require(Path(mosquitto_bin).name in command, "native Broker PID does not belong to Mosquitto")
    _require(str(config_path) in command, "native Broker PID is not bound to this workspace")


def _wait_for_pid(pid_path: Path, timeout_s: float) -> int:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if pid_path.is_file():
            return _read_pid(pid_path)
        time.sleep(0.1)
    raise NodeMqttBoardLabError("native Broker PID file was not created")


def _start_native_broker(
    workspace: Path,
    identity: BoardLabIdentity,
    *,
    mosquitto_bin: str,
    runner: Runner,
    waiter: Waiter,
) -> None:
    config_path, pid_path, _ = _native_paths(workspace)
    if pid_path.exists():
        stale_pid = _read_pid(pid_path)
        if _process_command(stale_pid, runner):
            raise NodeMqttBoardLabError("native Broker is already running")
        pid_path.unlink()
    _require(not _port_open(identity.bind_host, identity.port), "native Broker port is already in use")
    runner((mosquitto_bin, "-c", str(config_path), "-d"))
    waiter(identity.bind_host, identity.port, 20.0)
    pid = _wait_for_pid(pid_path, 5.0)
    _validate_native_process(pid, mosquitto_bin, config_path, runner)


def _stop_native_broker(
    workspace: Path,
    identity: BoardLabIdentity,
    *,
    mosquitto_bin: str,
    runner: Runner,
) -> bool:
    config_path, pid_path, _ = _native_paths(workspace)
    if not pid_path.exists():
        _require(not _port_open(identity.bind_host, identity.port), "native Broker port is open without a bound PID file")
        return False
    pid = _read_pid(pid_path)
    _validate_native_process(pid, mosquitto_bin, config_path, runner)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if not _process_command(pid, runner) and not _port_open(identity.bind_host, identity.port):
            pid_path.unlink(missing_ok=True)
            return True
        time.sleep(0.1)
    raise NodeMqttBoardLabError("native Broker did not stop cleanly")


def _native_report(
    identity: BoardLabIdentity,
    *,
    version: str,
    status: str,
    broker_running: bool | None,
) -> dict[str, object]:
    report = _base_report(identity, status=status, broker_running=broker_running)
    report.update(
        {
            "backend": NATIVE_BACKEND,
            "docker_required": False,
            "native_broker": True,
            "native_mosquitto_version": version,
            "native_version_family": "2.0",
            "native_process_workspace_bound": True,
        }
    )
    return report


def plan_native_board_lab(
    workspace: str | Path,
    *,
    bind_host: str = "127.0.0.1",
    port: int = 18883,
    mosquitto_bin: str = "mosquitto",
    mosquitto_passwd_bin: str = "mosquitto_passwd",
    runner: Runner = _run,
) -> dict[str, object]:
    bind_host = _validate_bind_host(bind_host)
    port = _validate_port(port)
    resolved = Path(workspace).expanduser().resolve()
    _require(not any(character.isspace() for character in str(resolved)), "native workspace path cannot contain whitespace")
    resolved_mosquitto = _resolve_executable(mosquitto_bin)
    resolved_passwd = _resolve_executable(mosquitto_passwd_bin)
    version = _native_version(resolved_mosquitto, runner)
    return {
        "schema": "gh.m2.node-mqtt-board-lab-native-plan/1",
        "status": "node_mqtt_board_lab_native_plan_created",
        "workspace_fingerprint": _fingerprint(str(resolved)),
        "bind_host_class": "loopback" if bind_host.startswith("127.") else "non_global",
        "port": port,
        "backend": NATIVE_BACKEND,
        "docker_required": False,
        "native_mosquitto_version": version,
        "native_version_family": "2.0",
        "allow_anonymous": True,
        "passwords_generated_at_create": True,
        "passwords_in_plan": False,
        "workspace_mode": "0700",
        "secret_file_mode": "0600",
        "explicit_nonproduction_confirmation_required": True,
        "board_lab": True,
        "production_endpoint_used": False,
        "production_identity_used": False,
        "production_execution_invoked": False,
        "current_services_modified": False,
        "homeassistant_storage_read": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "source_paths_included": False,
        "ready_for_live_apply": False,
        "ready_for_anonymous_closure": False,
        "ready_for_node_credential_generation": False,
    }


def create_native_board_lab(
    workspace: str | Path,
    *,
    confirmation: str,
    bind_host: str = "127.0.0.1",
    port: int = 18883,
    mosquitto_bin: str = "mosquitto",
    mosquitto_passwd_bin: str = "mosquitto_passwd",
    runner: Runner = _run,
    waiter: Waiter,
) -> dict[str, object]:
    _require(confirmation == CONFIRMATION, "non-production board-lab confirmation mismatch")
    bind_host = _validate_bind_host(bind_host)
    port = _validate_port(port)
    resolved_mosquitto = _resolve_executable(mosquitto_bin)
    resolved_passwd = _resolve_executable(mosquitto_passwd_bin)
    version = _native_version(resolved_mosquitto, runner)
    resolved = _validate_workspace_for_create(Path(workspace))
    _require(not any(character.isspace() for character in str(resolved)), "native workspace path cannot contain whitespace")
    lab_id = secrets.token_hex(8)
    identity = BoardLabIdentity(
        lab_id=lab_id,
        container_name=f"{CONTAINER_PREFIX}native-{lab_id[:8]}",
        image=NATIVE_IMAGE,
        bind_host=bind_host,
        port=port,
        candidate_username=CANDIDATE_USERNAME,
        candidate_client_id=CANDIDATE_CLIENT_ID,
        anonymous_client_id=ANONYMOUS_CLIENT_ID,
        observer_username=OBSERVER_USERNAME,
    )
    candidate_password = secrets.token_urlsafe(32)
    observer_password = secrets.token_urlsafe(32)
    secret_document = {
        "candidate_password": candidate_password,
        "observer_password": observer_password,
    }
    manifest: dict[str, object] = {
        "schema": MANIFEST_SCHEMA,
        "lab_id": identity.lab_id,
        "container_name": identity.container_name,
        "image": identity.image,
        "backend": NATIVE_BACKEND,
        "bind_host": identity.bind_host,
        "port": identity.port,
        "candidate_username": identity.candidate_username,
        "candidate_client_id": identity.candidate_client_id,
        "anonymous_client_id": identity.anonymous_client_id,
        "observer_username": identity.observer_username,
        "candidate_password_fingerprint": _fingerprint(candidate_password),
        "observer_password_fingerprint": _fingerprint(observer_password),
        "candidate_password_state": "valid",
        "workspace_fingerprint": _fingerprint(str(resolved)),
        "production_identity_used": False,
        "native_mosquitto_bin": resolved_mosquitto,
        "native_mosquitto_passwd_bin": resolved_passwd,
        "native_mosquitto_version": version,
    }
    _private_write(resolved / MARKER_NAME, identity.lab_id + "\n")
    _private_json(resolved / SECRETS_NAME, secret_document)
    _private_json(resolved / MANIFEST_NAME, manifest)
    _write_esphome_secrets(resolved, identity, candidate_password=candidate_password)
    try:
        _write_native_broker_files(
            resolved,
            identity,
            candidate_password=candidate_password,
            observer_password=observer_password,
            mosquitto_passwd_bin=resolved_passwd,
            runner=runner,
        )
        _start_native_broker(
            resolved,
            identity,
            mosquitto_bin=resolved_mosquitto,
            runner=runner,
            waiter=waiter,
        )
    except Exception:
        try:
            _stop_native_broker(
                resolved,
                identity,
                mosquitto_bin=resolved_mosquitto,
                runner=runner,
            )
        except Exception:
            pass
        raise
    report = _native_report(
        identity,
        version=version,
        status="node_mqtt_board_lab_native_created",
        broker_running=True,
    )
    report.update(
        {
            "allow_anonymous": True,
            "candidate_password_fingerprint": _fingerprint(candidate_password),
            "observer_password_fingerprint": _fingerprint(observer_password),
            "password_file_hashed": True,
            "esphome_private_secrets_created": True,
            "workspace_private": resolved.stat().st_mode & 0o777 == 0o700,
            "private_files_mode_0600": all(
                (resolved / name).stat().st_mode & 0o777 == 0o600
                for name in (
                    MARKER_NAME,
                    MANIFEST_NAME,
                    SECRETS_NAME,
                    ESPHOME_SECRETS_NAME,
                    CONFIG_NAME,
                    ACL_NAME,
                    PASSWORD_NAME,
                )
            ),
        }
    )
    return report


def _load_native(workspace: Path) -> tuple[Path, dict[str, object], BoardLabIdentity, str, str, str]:
    resolved, loaded = _load_manifest(workspace)
    manifest: dict[str, object] = dict(loaded)
    identity = _identity_from_manifest(manifest)
    mosquitto_bin, passwd_bin, version = _native_manifest_fields(manifest)
    return resolved, manifest, identity, mosquitto_bin, passwd_bin, version


def start_native_board_lab(
    workspace: str | Path,
    *,
    runner: Runner = _run,
    waiter: Waiter,
) -> dict[str, object]:
    resolved, _, identity, mosquitto_bin, _, version = _load_native(Path(workspace))
    _start_native_broker(resolved, identity, mosquitto_bin=mosquitto_bin, runner=runner, waiter=waiter)
    return _native_report(identity, version=version, status="node_mqtt_board_lab_native_started", broker_running=True)


def stop_native_board_lab(
    workspace: str | Path,
    *,
    runner: Runner = _run,
) -> dict[str, object]:
    resolved, _, identity, mosquitto_bin, _, version = _load_native(Path(workspace))
    _stop_native_broker(resolved, identity, mosquitto_bin=mosquitto_bin, runner=runner)
    return _native_report(identity, version=version, status="node_mqtt_board_lab_native_stopped", broker_running=False)


def _rewrite_native_candidate_state(
    workspace: Path,
    *,
    valid: bool,
    runner: Runner,
    waiter: Waiter,
) -> dict[str, object]:
    resolved, manifest, identity, mosquitto_bin, passwd_bin, version = _load_native(workspace)
    secret_document = _load_secrets(resolved)
    original_candidate = str(secret_document["candidate_password"])
    observer_password = str(secret_document["observer_password"])
    broker_candidate = original_candidate if valid else secrets.token_urlsafe(32)
    _stop_native_broker(resolved, identity, mosquitto_bin=mosquitto_bin, runner=runner)
    _write_native_broker_files(
        resolved,
        identity,
        candidate_password=broker_candidate,
        observer_password=observer_password,
        mosquitto_passwd_bin=passwd_bin,
        runner=runner,
    )
    manifest["candidate_password_state"] = "valid" if valid else "invalidated"
    _private_json(resolved / MANIFEST_NAME, manifest)
    _start_native_broker(resolved, identity, mosquitto_bin=mosquitto_bin, runner=runner, waiter=waiter)
    report = _native_report(
        identity,
        version=version,
        status=(
            "node_mqtt_board_lab_native_candidate_restored"
            if valid
            else "node_mqtt_board_lab_native_candidate_invalidated"
        ),
        broker_running=True,
    )
    report.update(
        {
            "candidate_password_state": manifest["candidate_password_state"],
            "candidate_original_secret_preserved_private": True,
            "candidate_secret_output": False,
        }
    )
    return report


def invalidate_native_candidate(
    workspace: str | Path,
    *,
    runner: Runner = _run,
    waiter: Waiter,
) -> dict[str, object]:
    return _rewrite_native_candidate_state(Path(workspace), valid=False, runner=runner, waiter=waiter)


def restore_native_candidate(
    workspace: str | Path,
    *,
    runner: Runner = _run,
    waiter: Waiter,
) -> dict[str, object]:
    return _rewrite_native_candidate_state(Path(workspace), valid=True, runner=runner, waiter=waiter)


def destroy_native_board_lab(
    workspace: str | Path,
    *,
    runner: Runner = _run,
) -> dict[str, object]:
    resolved, _, identity, mosquitto_bin, _, version = _load_native(Path(workspace))
    _stop_native_broker(resolved, identity, mosquitto_bin=mosquitto_bin, runner=runner)
    marker_value = (resolved / MARKER_NAME).read_text(encoding="utf-8").strip()
    _require(marker_value == identity.lab_id, "refusing to destroy an unbound workspace")
    shutil.rmtree(resolved)
    report = _native_report(
        identity,
        version=version,
        status="node_mqtt_board_lab_native_destroyed",
        broker_running=False,
    )
    report.update({"workspace_removed": not resolved.exists(), "private_secrets_removed": True})
    return report
