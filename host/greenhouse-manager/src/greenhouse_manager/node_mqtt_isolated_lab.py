from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import stat
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import paho.mqtt.client as mqtt

SCHEMA = "gh.m2.node-mqtt-isolated-lab/1"
MANIFEST_SCHEMA = "gh.m2.node-mqtt-isolated-lab-manifest/1"
DEFAULT_IMAGE = "eclipse-mosquitto:2.0.22"
CONTAINER_PREFIX = "gh-m2-node-auth-lab-"
MARKER_NAME = ".gh-node-mqtt-isolated-lab"
MANIFEST_NAME = "manifest.json"
SECRETS_NAME = "lab-secrets.json"
CONFIG_NAME = "mosquitto.conf"
ACL_NAME = "acl"
PASSWORD_NAME = "passwd"


class NodeMqttIsolatedLabError(RuntimeError):
    """Raised when an isolated MQTT lab operation fails closed."""


class Runner(Protocol):
    def __call__(
        self,
        command: Sequence[str],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]: ...


class Waiter(Protocol):
    def __call__(self, host: str, port: int, timeout_s: float) -> None: ...


@dataclass(frozen=True, slots=True)
class LabIdentity:
    lab_id: str
    container_name: str
    image: str
    host: str
    port: int
    candidate_username: str
    candidate_client_id: str
    anonymous_client_id: str
    observer_username: str


def _run(
    command: Sequence[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise NodeMqttIsolatedLabError(message)


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _private_write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _private_json(path: Path, value: Mapping[str, Any]) -> None:
    _private_write(path, _canonical_json(value) + "\n")


def _validate_port(port: int) -> int:
    _require(1024 <= port <= 65535, "lab port must be between 1024 and 65535")
    return port


def _validate_workspace_for_create(workspace: Path) -> Path:
    resolved = workspace.expanduser().resolve()
    _require(resolved != Path("/"), "workspace cannot be filesystem root")
    _require(resolved != Path("/tmp"), "workspace cannot be /tmp itself")
    _require(len(resolved.parts) >= 3, "workspace path is too broad")
    if resolved.exists():
        _require(resolved.is_dir(), "workspace exists and is not a directory")
        _require(not any(resolved.iterdir()), "workspace must be empty")
    else:
        resolved.mkdir(parents=True, mode=0o700)
    resolved.chmod(0o700)
    return resolved


def _manifest_path(workspace: Path) -> Path:
    return workspace / MANIFEST_NAME


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise NodeMqttIsolatedLabError(f"invalid private lab file: {path.name}") from error
    _require(isinstance(value, dict), f"{path.name} root must be an object")
    return value


def _load_manifest(workspace: Path) -> tuple[Path, dict[str, Any]]:
    resolved = workspace.expanduser().resolve()
    marker = resolved / MARKER_NAME
    manifest_path = _manifest_path(resolved)
    _require(resolved.is_dir(), "lab workspace does not exist")
    _require(marker.is_file(), "lab marker is missing")
    manifest = _load_json(manifest_path)
    _require(manifest.get("schema") == MANIFEST_SCHEMA, "lab manifest schema mismatch")
    lab_id = manifest.get("lab_id")
    _require(isinstance(lab_id, str) and len(lab_id) == 16, "lab ID is invalid")
    _require(marker.read_text(encoding="utf-8").strip() == lab_id, "lab marker mismatch")
    _require(
        manifest.get("workspace_fingerprint") == _fingerprint(str(resolved)),
        "workspace binding mismatch",
    )
    container_name = manifest.get("container_name")
    _require(
        isinstance(container_name, str) and container_name.startswith(CONTAINER_PREFIX),
        "container name is invalid",
    )
    port = manifest.get("port")
    _require(isinstance(port, int), "lab port is invalid")
    _validate_port(port)
    return resolved, manifest


def _load_secrets(workspace: Path) -> dict[str, Any]:
    secrets_path = workspace / SECRETS_NAME
    _require(secrets_path.is_file(), "private lab secrets are missing")
    secrets_document = _load_json(secrets_path)
    for key in ("candidate_password", "observer_password"):
        value = secrets_document.get(key)
        _require(isinstance(value, str) and len(value) >= 24, f"{key} is invalid")
    return secrets_document


def _identity_from_manifest(manifest: Mapping[str, Any]) -> LabIdentity:
    return LabIdentity(
        lab_id=str(manifest["lab_id"]),
        container_name=str(manifest["container_name"]),
        image=str(manifest["image"]),
        host=str(manifest["host"]),
        port=int(manifest["port"]),
        candidate_username=str(manifest["candidate_username"]),
        candidate_client_id=str(manifest["candidate_client_id"]),
        anonymous_client_id=str(manifest["anonymous_client_id"]),
        observer_username=str(manifest["observer_username"]),
    )


def _write_broker_files(
    workspace: Path,
    identity: LabIdentity,
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
    raise NodeMqttIsolatedLabError("isolated broker did not become reachable") from last_error


def _start_broker(
    workspace: Path,
    identity: LabIdentity,
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
            f"127.0.0.1:{identity.port}:1883",
            "-v",
            f"{workspace}:/lab:ro",
            identity.image,
            "mosquitto",
            "-c",
            "/lab/mosquitto.conf",
        )
    )
    waiter(identity.host, identity.port, 20.0)


def _base_report(
    identity: LabIdentity,
    *,
    status: str,
    broker_running: bool,
) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": status,
        "lab_id": identity.lab_id,
        "image": identity.image,
        "host": identity.host,
        "port": identity.port,
        "container_name_fingerprint": _fingerprint(identity.container_name),
        "candidate_username_fingerprint": _fingerprint(identity.candidate_username),
        "candidate_client_id": identity.candidate_client_id,
        "anonymous_client_id": identity.anonymous_client_id,
        "observer_username_fingerprint": _fingerprint(identity.observer_username),
        "broker_running": broker_running,
        "isolated_lab": True,
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
    }


def plan_lab(
    workspace: str | Path,
    *,
    port: int = 18883,
    image: str = DEFAULT_IMAGE,
) -> dict[str, object]:
    port = _validate_port(port)
    resolved = Path(workspace).expanduser().resolve()
    _require(image == DEFAULT_IMAGE, "isolated lab image must be pinned")
    return {
        "schema": SCHEMA,
        "status": "node_mqtt_isolated_lab_plan_created",
        "workspace_fingerprint": _fingerprint(str(resolved)),
        "image": image,
        "host": "127.0.0.1",
        "port": port,
        "allow_anonymous": True,
        "candidate_identity_nonproduction": True,
        "observer_identity_nonproduction": True,
        "passwords_generated_at_create": True,
        "passwords_in_plan": False,
        "docker_required": True,
        "workspace_mode": "0700",
        "secret_file_mode": "0600",
        "isolated_lab": True,
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
    }


def create_lab(
    workspace: str | Path,
    *,
    port: int = 18883,
    image: str = DEFAULT_IMAGE,
    runner: Runner = _run,
    waiter: Waiter = _wait_for_port,
) -> dict[str, object]:
    port = _validate_port(port)
    _require(image == DEFAULT_IMAGE, "isolated lab image must be pinned")
    resolved = _validate_workspace_for_create(Path(workspace))
    lab_id = secrets.token_hex(8)
    identity = LabIdentity(
        lab_id=lab_id,
        container_name=f"{CONTAINER_PREFIX}{lab_id[:8]}",
        image=image,
        host="127.0.0.1",
        port=port,
        candidate_username="ghn_ci-node",
        candidate_client_id="ci-node",
        anonymous_client_id="ci-node-anon",
        observer_username="gho_ci-observer",
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
        "host": identity.host,
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
    report = _base_report(
        identity,
        status="node_mqtt_isolated_lab_created",
        broker_running=True,
    )
    report.update(
        {
            "allow_anonymous": True,
            "candidate_password_fingerprint": _fingerprint(candidate_password),
            "observer_password_fingerprint": _fingerprint(observer_password),
            "password_file_hashed": True,
            "workspace_private": resolved.stat().st_mode & 0o777 == 0o700,
            "private_files_mode_0600": all(
                (resolved / name).stat().st_mode & 0o777 == 0o600
                for name in (
                    MARKER_NAME,
                    MANIFEST_NAME,
                    SECRETS_NAME,
                    CONFIG_NAME,
                    ACL_NAME,
                    PASSWORD_NAME,
                )
            ),
        }
    )
    return report


def start_lab(
    workspace: str | Path,
    *,
    runner: Runner = _run,
    waiter: Waiter = _wait_for_port,
) -> dict[str, object]:
    resolved, manifest = _load_manifest(Path(workspace))
    identity = _identity_from_manifest(manifest)
    _start_broker(resolved, identity, runner=runner, waiter=waiter)
    return _base_report(
        identity,
        status="node_mqtt_isolated_lab_started",
        broker_running=True,
    )


def stop_lab(
    workspace: str | Path,
    *,
    runner: Runner = _run,
) -> dict[str, object]:
    _, manifest = _load_manifest(Path(workspace))
    identity = _identity_from_manifest(manifest)
    _docker_remove(identity.container_name, runner)
    return _base_report(
        identity,
        status="node_mqtt_isolated_lab_stopped",
        broker_running=False,
    )


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
            "node_mqtt_isolated_lab_candidate_restored"
            if valid
            else "node_mqtt_isolated_lab_candidate_invalidated"
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
    return _rewrite_candidate_state(
        Path(workspace),
        valid=False,
        runner=runner,
        waiter=waiter,
    )


def restore_candidate(
    workspace: str | Path,
    *,
    runner: Runner = _run,
    waiter: Waiter = _wait_for_port,
) -> dict[str, object]:
    return _rewrite_candidate_state(
        Path(workspace),
        valid=True,
        runner=runner,
        waiter=waiter,
    )


def _connect_client(
    *,
    host: str,
    port: int,
    client_id: str,
    username: str | None,
    password: str | None,
    timeout_s: float = 8.0,
) -> tuple[mqtt.Client, bool]:
    connected = False
    finished = False

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt.MQTTv311,
    )
    if username is not None:
        client.username_pw_set(username, password)

    def on_connect(
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        nonlocal connected, finished
        connected = not reason_code.is_failure
        finished = True

    def on_disconnect(
        client: mqtt.Client,
        userdata: object,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        nonlocal finished
        if not connected:
            finished = True

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    try:
        client.connect(host, port, keepalive=10)
        client.loop_start()
        deadline = time.monotonic() + timeout_s
        while not finished and time.monotonic() < deadline:
            time.sleep(0.05)
        return client, connected
    except (OSError, mqtt.MQTTException):
        return client, False


def _close_client(client: mqtt.Client) -> None:
    try:
        client.disconnect()
    except (OSError, mqtt.MQTTException):
        pass
    try:
        client.loop_stop()
    except (OSError, mqtt.MQTTException):
        pass


def _observe_publish(
    *,
    identity: LabIdentity,
    observer_password: str,
    publisher_client_id: str,
    publisher_username: str | None,
    publisher_password: str | None,
    timeout_s: float = 8.0,
) -> bool:
    token = secrets.token_hex(12)
    target_topic = f"lab/state/{publisher_client_id}/heartbeat"
    observed = False
    subscribed = False

    observer = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"ci-observer-{secrets.token_hex(3)}",
        protocol=mqtt.MQTTv311,
    )
    observer.username_pw_set(identity.observer_username, observer_password)

    def observer_connect(
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        nonlocal subscribed
        if not reason_code.is_failure:
            client.subscribe("lab/state/#", qos=0)
            subscribed = True

    def observer_message(
        client: mqtt.Client,
        userdata: object,
        message: mqtt.MQTTMessage,
    ) -> None:
        nonlocal observed
        payload = message.payload.decode("utf-8", "replace")
        if message.topic == target_topic and payload == token:
            observed = True

    observer.on_connect = observer_connect
    observer.on_message = observer_message
    publisher: mqtt.Client | None = None
    try:
        observer.connect(identity.host, identity.port, keepalive=10)
        observer.loop_start()
        deadline = time.monotonic() + timeout_s
        while not subscribed and time.monotonic() < deadline:
            time.sleep(0.05)
        _require(subscribed, "observer could not subscribe in isolated lab")

        publisher, connected = _connect_client(
            host=identity.host,
            port=identity.port,
            client_id=publisher_client_id,
            username=publisher_username,
            password=publisher_password,
            timeout_s=timeout_s,
        )
        if not connected:
            return False
        info = publisher.publish(target_topic, token, qos=0, retain=False)
        info.wait_for_publish(timeout=timeout_s)
        while not observed and time.monotonic() < deadline:
            time.sleep(0.05)
        return observed
    finally:
        if publisher is not None:
            _close_client(publisher)
        _close_client(observer)


def smoke_valid(workspace: str | Path) -> dict[str, object]:
    resolved, manifest = _load_manifest(Path(workspace))
    identity = _identity_from_manifest(manifest)
    secret_document = _load_secrets(resolved)
    _require(manifest.get("candidate_password_state") == "valid", "candidate is not restored")
    anonymous_ok = _observe_publish(
        identity=identity,
        observer_password=str(secret_document["observer_password"]),
        publisher_client_id=identity.anonymous_client_id,
        publisher_username=None,
        publisher_password=None,
    )
    candidate_ok = _observe_publish(
        identity=identity,
        observer_password=str(secret_document["observer_password"]),
        publisher_client_id=identity.candidate_client_id,
        publisher_username=identity.candidate_username,
        publisher_password=str(secret_document["candidate_password"]),
    )
    _require(anonymous_ok, "anonymous isolated publish was not observed")
    _require(candidate_ok, "candidate isolated publish was not observed")
    report = _base_report(
        identity,
        status="node_mqtt_isolated_lab_valid_smoke_succeeded",
        broker_running=True,
    )
    report.update(
        {
            "anonymous_connect_and_publish": True,
            "candidate_connect_and_publish": True,
            "observer_received_both": True,
            "candidate_password_state": "valid",
        }
    )
    return report


def smoke_invalid(workspace: str | Path) -> dict[str, object]:
    resolved, manifest = _load_manifest(Path(workspace))
    identity = _identity_from_manifest(manifest)
    secret_document = _load_secrets(resolved)
    _require(
        manifest.get("candidate_password_state") == "invalidated",
        "candidate has not been invalidated",
    )
    candidate, candidate_connected = _connect_client(
        host=identity.host,
        port=identity.port,
        client_id=identity.candidate_client_id,
        username=identity.candidate_username,
        password=str(secret_document["candidate_password"]),
    )
    _close_client(candidate)
    anonymous_ok = _observe_publish(
        identity=identity,
        observer_password=str(secret_document["observer_password"]),
        publisher_client_id=identity.anonymous_client_id,
        publisher_username=None,
        publisher_password=None,
    )
    _require(not candidate_connected, "invalid candidate unexpectedly connected")
    _require(anonymous_ok, "anonymous fallback path stopped working")
    report = _base_report(
        identity,
        status="node_mqtt_isolated_lab_invalid_smoke_succeeded",
        broker_running=True,
    )
    report.update(
        {
            "candidate_connection_rejected": True,
            "candidate_rejection_classification": "broker_rejected_in_isolated_probe",
            "anonymous_connect_and_publish": True,
            "observer_received_anonymous": True,
            "candidate_password_state": "invalidated",
        }
    )
    return report


def destroy_lab(
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
    report = _base_report(
        identity,
        status="node_mqtt_isolated_lab_destroyed",
        broker_running=False,
    )
    report.update(
        {
            "workspace_removed": not resolved.exists(),
            "private_secrets_removed": True,
        }
    )
    return report


def _add_common_workspace(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("--workspace", type=Path, required=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create and exercise a non-production isolated MQTT node-auth lab"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan")
    _add_common_workspace(plan_parser)
    plan_parser.add_argument("--port", type=int, default=18883)
    plan_parser.add_argument("--image", default=DEFAULT_IMAGE)

    create_parser = subparsers.add_parser("create")
    _add_common_workspace(create_parser)
    create_parser.add_argument("--port", type=int, default=18883)
    create_parser.add_argument("--image", default=DEFAULT_IMAGE)

    for command in (
        "start",
        "stop",
        "smoke-valid",
        "invalidate-candidate",
        "smoke-invalid",
        "restore-candidate",
        "destroy",
    ):
        _add_common_workspace(subparsers.add_parser(command))

    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            report = plan_lab(args.workspace, port=args.port, image=args.image)
        elif args.command == "create":
            report = create_lab(args.workspace, port=args.port, image=args.image)
        elif args.command == "start":
            report = start_lab(args.workspace)
        elif args.command == "stop":
            report = stop_lab(args.workspace)
        elif args.command == "smoke-valid":
            report = smoke_valid(args.workspace)
        elif args.command == "invalidate-candidate":
            report = invalidate_candidate(args.workspace)
        elif args.command == "smoke-invalid":
            report = smoke_invalid(args.workspace)
        elif args.command == "restore-candidate":
            report = restore_candidate(args.workspace)
        elif args.command == "destroy":
            report = destroy_lab(args.workspace)
        else:
            raise NodeMqttIsolatedLabError("unsupported command")
    except (
        NodeMqttIsolatedLabError,
        OSError,
        UnicodeError,
        subprocess.SubprocessError,
        mqtt.MQTTException,
    ) as error:
        print(f"Node MQTT isolated lab failed: {error}", file=sys.stderr)
        return 2
    print(_canonical_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
