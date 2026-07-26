from __future__ import annotations

import ipaddress
import os
import secrets
import shutil
import socket
import time
from pathlib import Path

from .node_mqtt_board_lab_common import (
    ACL_NAME,
    ANONYMOUS_CLIENT_ID,
    CANDIDATE_CLIENT_ID,
    CANDIDATE_USERNAME,
    CONFIG_NAME,
    CONFIRMATION,
    CONTAINER_PREFIX,
    DEFAULT_IMAGE,
    ESPHOME_SECRETS_NAME,
    MANIFEST_NAME,
    MANIFEST_SCHEMA,
    MARKER_NAME,
    OBSERVER_USERNAME,
    PASSWORD_NAME,
    SCHEMA,
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


def _write_broker_files(
    workspace: Path,
    identity: BoardLabIdentity,
    *,
    candidate_password: str,
    observer_password: str,
    runner: Runner,
) -> None:
    config = "\n".join(
        (
            "listener 1883 0.0.0.0",
            "allow_anonymous true",
            "persistence false",
            "connection_messages true",
            "log_dest stdout",
            "log_type all",
            "password_file /lab/passwd",
            "acl_file /lab/acl",
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
    _private_write(workspace / CONFIG_NAME, config)
    _private_write(workspace / ACL_NAME, acl)
    _private_write(workspace / PASSWORD_NAME, password_plain)

    uid_gid = f"{os.getuid()}:{os.getgid()}"
    runner(
        (
            "docker",
            "run",
            "--rm",
            "--user",
            uid_gid,
            "-v",
            f"{workspace}:/lab",
            identity.image,
            "mosquitto_passwd",
            "-U",
            "/lab/passwd",
        )
    )
    password_data = (workspace / PASSWORD_NAME).read_text(encoding="utf-8")
    _require(candidate_password not in password_data, "candidate password remained plaintext")
    _require(observer_password not in password_data, "observer password remained plaintext")
    (workspace / PASSWORD_NAME).chmod(0o600)


def _write_esphome_secrets(
    workspace: Path,
    identity: BoardLabIdentity,
    *,
    candidate_password: str,
) -> None:
    content = "\n".join(
        (
            '# Private, non-production board-lab values. Never commit this file.',
            'board_lab_wifi_ssid: "REPLACE_IN_PRIVATE_WORKSPACE"',
            'board_lab_wifi_password: "REPLACE_IN_PRIVATE_WORKSPACE"',
            f'board_lab_broker_host: "{identity.bind_host}"',
            f"board_lab_broker_port: {identity.port}",
            f'board_lab_candidate_password: "{candidate_password}"',
            f'board_lab_candidate_secret_fingerprint: "{_fingerprint(candidate_password)}"',
            "",
        )
    )
    _private_write(workspace / ESPHOME_SECRETS_NAME, content)


def _docker_remove(container_name: str, runner: Runner) -> None:
    runner(("docker", "rm", "-f", container_name), check=False)


def _wait_for_port(host: str, port: int, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError as error:
            last_error = error
            time.sleep(0.2)
    raise NodeMqttBoardLabError("board-lab Broker did not become reachable") from last_error


def _start_broker(
    workspace: Path,
    identity: BoardLabIdentity,
    *,
    runner: Runner,
    waiter: Waiter,
) -> None:
    _docker_remove(identity.container_name, runner)
    uid_gid = f"{os.getuid()}:{os.getgid()}"
    runner(
        (
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            identity.container_name,
            "--user",
            uid_gid,
            "-p",
            f"{identity.bind_host}:{identity.port}:1883",
            "-v",
            f"{workspace}:/lab:ro",
            identity.image,
            "mosquitto",
            "-c",
            "/lab/mosquitto.conf",
        )
    )
    waiter(identity.bind_host, identity.port, 20.0)


def _base_report(
    identity: BoardLabIdentity,
    *,
    status: str,
    broker_running: bool | None,
) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": status,
        "lab_id": identity.lab_id,
        "image": identity.image,
        "bind_host_class": (
            "loopback" if ipaddress.ip_address(identity.bind_host).is_loopback else "non_global"
        ),
        "port": identity.port,
        "container_name_fingerprint": _fingerprint(identity.container_name),
        "candidate_username_fingerprint": _fingerprint(identity.candidate_username),
        "candidate_client_id": identity.candidate_client_id,
        "anonymous_client_id": identity.anonymous_client_id,
        "observer_username_fingerprint": _fingerprint(identity.observer_username),
        "broker_running": broker_running,
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


def plan_board_lab(
    workspace: str | Path,
    *,
    bind_host: str = "127.0.0.1",
    port: int = 18883,
    image: str = DEFAULT_IMAGE,
) -> dict[str, object]:
    bind_host = _validate_bind_host(bind_host)
    port = _validate_port(port)
    _require(image == DEFAULT_IMAGE, "board-lab image must be pinned")
    resolved = Path(workspace).expanduser().resolve()
    return {
        "schema": SCHEMA,
        "status": "node_mqtt_board_lab_plan_created",
        "workspace_fingerprint": _fingerprint(str(resolved)),
        "image": image,
        "bind_host_class": "loopback" if ipaddress.ip_address(bind_host).is_loopback else "non_global",
        "port": port,
        "allow_anonymous": True,
        "candidate_identity_nonproduction": True,
        "observer_identity_nonproduction": True,
        "passwords_generated_at_create": True,
        "passwords_in_plan": False,
        "docker_required": True,
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


def create_board_lab(
    workspace: str | Path,
    *,
    confirmation: str,
    bind_host: str = "127.0.0.1",
    port: int = 18883,
    image: str = DEFAULT_IMAGE,
    runner: Runner = _run,
    waiter: Waiter = _wait_for_port,
) -> dict[str, object]:
    _require(confirmation == CONFIRMATION, "non-production board-lab confirmation mismatch")
    bind_host = _validate_bind_host(bind_host)
    port = _validate_port(port)
    _require(image == DEFAULT_IMAGE, "board-lab image must be pinned")
    resolved = _validate_workspace_for_create(Path(workspace))
    lab_id = secrets.token_hex(8)
    identity = BoardLabIdentity(
        lab_id=lab_id,
        container_name=f"{CONTAINER_PREFIX}{lab_id[:8]}",
        image=image,
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
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "lab_id": identity.lab_id,
        "container_name": identity.container_name,
        "image": identity.image,
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
    }
    _private_write(resolved / MARKER_NAME, identity.lab_id + "\n")
    _private_json(resolved / SECRETS_NAME, secret_document)
    _private_json(resolved / MANIFEST_NAME, manifest)
    _write_esphome_secrets(resolved, identity, candidate_password=candidate_password)
    try:
        _write_broker_files(
            resolved,
            identity,
            candidate_password=candidate_password,
            observer_password=observer_password,
            runner=runner,
        )
        _start_broker(resolved, identity, runner=runner, waiter=waiter)
    except Exception:
        _docker_remove(identity.container_name, runner)
        raise
    report = _base_report(identity, status="node_mqtt_board_lab_created", broker_running=True)
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


def start_board_lab(
    workspace: str | Path,
    *,
    runner: Runner = _run,
    waiter: Waiter = _wait_for_port,
) -> dict[str, object]:
    resolved, manifest = _load_manifest(Path(workspace))
    identity = _identity_from_manifest(manifest)
    _start_broker(resolved, identity, runner=runner, waiter=waiter)
    return _base_report(identity, status="node_mqtt_board_lab_started", broker_running=True)


def stop_board_lab(
    workspace: str | Path,
    *,
    runner: Runner = _run,
) -> dict[str, object]:
    _, manifest = _load_manifest(Path(workspace))
    identity = _identity_from_manifest(manifest)
    _docker_remove(identity.container_name, runner)
    return _base_report(identity, status="node_mqtt_board_lab_stopped", broker_running=False)


def _rewrite_candidate_state(
    workspace: Path,
    *,
    valid: bool,
    runner: Runner,
    waiter: Waiter,
) -> dict[str, object]:
    resolved, manifest = _load_manifest(workspace)
    identity = _identity_from_manifest(manifest)
    secret_document = _load_secrets(resolved)
    original_candidate = str(secret_document["candidate_password"])
    observer_password = str(secret_document["observer_password"])
    broker_candidate = original_candidate if valid else secrets.token_urlsafe(32)
    _docker_remove(identity.container_name, runner)
    _write_broker_files(
        resolved,
        identity,
        candidate_password=broker_candidate,
        observer_password=observer_password,
        runner=runner,
    )
    manifest["candidate_password_state"] = "valid" if valid else "invalidated"
    _private_json(resolved / MANIFEST_NAME, manifest)
    _start_broker(resolved, identity, runner=runner, waiter=waiter)
    report = _base_report(
        identity,
        status=(
            "node_mqtt_board_lab_candidate_restored"
            if valid
            else "node_mqtt_board_lab_candidate_invalidated"
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


def invalidate_candidate(
    workspace: str | Path,
    *,
    runner: Runner = _run,
    waiter: Waiter = _wait_for_port,
) -> dict[str, object]:
    return _rewrite_candidate_state(Path(workspace), valid=False, runner=runner, waiter=waiter)


def restore_candidate(
    workspace: str | Path,
    *,
    runner: Runner = _run,
    waiter: Waiter = _wait_for_port,
) -> dict[str, object]:
    return _rewrite_candidate_state(Path(workspace), valid=True, runner=runner, waiter=waiter)


def destroy_board_lab(
    workspace: str | Path,
    *,
    runner: Runner = _run,
) -> dict[str, object]:
    resolved, manifest = _load_manifest(Path(workspace))
    identity = _identity_from_manifest(manifest)
    _docker_remove(identity.container_name, runner)
    marker_value = (resolved / MARKER_NAME).read_text(encoding="utf-8").strip()
    _require(marker_value == identity.lab_id, "refusing to destroy an unbound workspace")
    shutil.rmtree(resolved)
    report = _base_report(identity, status="node_mqtt_board_lab_destroyed", broker_running=False)
    report.update({"workspace_removed": not resolved.exists(), "private_secrets_removed": True})
    return report
