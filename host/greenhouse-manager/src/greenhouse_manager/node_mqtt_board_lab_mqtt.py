from __future__ import annotations

import contextlib
import json
import secrets
import time
from pathlib import Path

import paho.mqtt.client as mqtt

from .node_mqtt_board_lab_broker import _base_report
from .node_mqtt_board_lab_common import (
    ANONYMOUS_CLIENT_ID,
    CANDIDATE_CLIENT_ID,
    CONFIRMATION,
    ESPHOME_SECRETS_NAME,
    BoardLabIdentity,
    _canonical_json,
    _fingerprint,
    _identity_from_manifest,
    _load_manifest,
    _load_secrets,
    _private_write,
    _require,
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
    with contextlib.suppress(OSError, mqtt.MQTTException):
        client.disconnect()
    with contextlib.suppress(OSError, mqtt.MQTTException):
        client.loop_stop()


def _observe_publish(
    *,
    identity: BoardLabIdentity,
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
    subscription_failed = False
    observer = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"lab-observer-{secrets.token_hex(3)}",
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
        nonlocal subscription_failed
        if reason_code.is_failure:
            subscription_failed = True
            return
        result, _ = client.subscribe("lab/state/#", qos=0)
        if result != mqtt.MQTT_ERR_SUCCESS:
            subscription_failed = True

    def observer_subscribe(
        client: mqtt.Client,
        userdata: object,
        mid: int,
        reason_code_list: list[mqtt.ReasonCode],
        properties: mqtt.Properties | None,
    ) -> None:
        nonlocal subscribed, subscription_failed
        if reason_code_list and any(reason_code.is_failure for reason_code in reason_code_list):
            subscription_failed = True
            return
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
    observer.on_subscribe = observer_subscribe
    observer.on_message = observer_message
    publisher: mqtt.Client | None = None
    try:
        observer.connect(identity.bind_host, identity.port, keepalive=10)
        observer.loop_start()
        subscribe_deadline = time.monotonic() + timeout_s
        while not subscribed and not subscription_failed and time.monotonic() < subscribe_deadline:
            time.sleep(0.05)
        _require(not subscription_failed and subscribed, "observer could not subscribe in board lab")
        publisher, connected = _connect_client(
            host=identity.bind_host,
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
        observation_deadline = time.monotonic() + timeout_s
        while not observed and time.monotonic() < observation_deadline:
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
    _require(anonymous_ok, "anonymous board-lab publish was not observed")
    _require(candidate_ok, "candidate board-lab publish was not observed")
    report = _base_report(identity, status="node_mqtt_board_lab_valid_smoke_succeeded", broker_running=True)
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
    _require(manifest.get("candidate_password_state") == "invalidated", "candidate is not invalidated")
    candidate, candidate_connected = _connect_client(
        host=identity.bind_host,
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
    _require(anonymous_ok, "anonymous board-lab path stopped working")
    report = _base_report(identity, status="node_mqtt_board_lab_invalid_smoke_succeeded", broker_running=True)
    report.update(
        {
            "candidate_connection_rejected": True,
            "candidate_rejection_classification": "broker_rejected_in_nonproduction_probe",
            "anonymous_connect_and_publish": True,
            "observer_received_anonymous": True,
            "candidate_password_state": "invalidated",
        }
    )
    return report


def observe_heartbeats(
    workspace: str | Path,
    *,
    duration_s: float,
    output: str | Path,
) -> dict[str, object]:
    _require(1 <= duration_s <= 3600, "observation duration must be between 1 and 3600 seconds")
    resolved, manifest = _load_manifest(Path(workspace))
    identity = _identity_from_manifest(manifest)
    secret_document = _load_secrets(resolved)
    output_path = Path(output).expanduser().resolve()
    _require(output_path.parent.exists(), "observation output parent does not exist")
    _require(output_path != Path("/"), "observation output path is invalid")
    observations: list[dict[str, object]] = []
    connected = False
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"lab-observer-{secrets.token_hex(3)}",
        protocol=mqtt.MQTTv311,
    )
    client.username_pw_set(identity.observer_username, str(secret_document["observer_password"]))

    def on_connect(
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        nonlocal connected
        if not reason_code.is_failure:
            client.subscribe("lab/state/#", qos=0)
            connected = True

    def on_message(
        client: mqtt.Client,
        userdata: object,
        message: mqtt.MQTTMessage,
    ) -> None:
        payload_text = message.payload.decode("utf-8", "replace")
        try:
            payload: object = json.loads(payload_text)
        except json.JSONDecodeError:
            payload = {"payload_fingerprint": _fingerprint(payload_text), "payload_valid_json": False}
        observations.append(
            {
                "observed_monotonic_ms": int(time.monotonic() * 1000),
                "topic": message.topic,
                "payload": payload,
            }
        )

    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(identity.bind_host, identity.port, keepalive=10)
        client.loop_start()
        deadline = time.monotonic() + duration_s
        connect_deadline = min(deadline, time.monotonic() + 8.0)
        while not connected and time.monotonic() < connect_deadline:
            time.sleep(0.05)
        _require(connected, "board-lab observer could not connect")
        while time.monotonic() < deadline:
            time.sleep(0.1)
    finally:
        _close_client(client)
    encoded = "".join(_canonical_json(item) + "\n" for item in observations)
    secret_values = tuple(str(value) for value in secret_document.values())
    _require(not any(value in encoded for value in secret_values), "raw secret appeared in heartbeat capture")
    _private_write(output_path, encoded)
    report = _base_report(
        identity,
        status="node_mqtt_board_lab_heartbeat_observation_completed",
        broker_running=True,
    )
    report.update(
        {
            "heartbeat_count": len(observations),
            "heartbeat_profiles": sorted(
                {
                    str(item.get("payload", {}).get("profile"))
                    for item in observations
                    if isinstance(item.get("payload"), dict) and item["payload"].get("profile") is not None
                }
            ),
            "observation_output_fingerprint": _fingerprint(encoded),
            "observation_output_private": output_path.stat().st_mode & 0o777 == 0o600,
        }
    )
    return report


def _control_topic(command: str) -> tuple[str, str]:
    mapping = {
        "activate": (f"lab/control/{ANONYMOUS_CLIENT_ID}/activate", "activate"),
        "observe-success": (f"lab/control/{CANDIDATE_CLIENT_ID}/observe-success", "observe-success"),
        "observe-failure": (f"lab/control/{CANDIDATE_CLIENT_ID}/observe-failure", "observe-failure"),
        "commit": (f"lab/control/{CANDIDATE_CLIENT_ID}/commit", "commit"),
        "rollback": (f"lab/control/{CANDIDATE_CLIENT_ID}/rollback", "rollback"),
        "hold-reboot-anonymous": (
            f"lab/control/{ANONYMOUS_CLIENT_ID}/reboot-hold",
            "hold",
        ),
        "release-reboot-anonymous": (
            f"lab/control/{ANONYMOUS_CLIENT_ID}/reboot-hold",
            "release",
        ),
        "hold-reboot-candidate": (
            f"lab/control/{CANDIDATE_CLIENT_ID}/reboot-hold",
            "hold",
        ),
        "release-reboot-candidate": (
            f"lab/control/{CANDIDATE_CLIENT_ID}/reboot-hold",
            "release",
        ),
    }
    _require(command in mapping, "unsupported board-lab control command")
    return mapping[command]


def send_control(
    workspace: str | Path,
    *,
    command: str,
    confirmation: str,
) -> dict[str, object]:
    _require(confirmation == CONFIRMATION, "non-production board-lab confirmation mismatch")
    resolved, manifest = _load_manifest(Path(workspace))
    identity = _identity_from_manifest(manifest)
    secret_document = _load_secrets(resolved)
    topic, payload = _control_topic(command)
    client, connected = _connect_client(
        host=identity.bind_host,
        port=identity.port,
        client_id=f"lab-control-{secrets.token_hex(3)}",
        username=identity.observer_username,
        password=str(secret_document["observer_password"]),
    )
    try:
        _require(connected, "board-lab control client could not connect")
        info = client.publish(topic, payload, qos=1, retain=False)
        info.wait_for_publish(timeout=8.0)
        _require(info.is_published(), "board-lab control message was not published")
    finally:
        _close_client(client)
    report = _base_report(identity, status="node_mqtt_board_lab_control_published", broker_running=True)
    report.update(
        {
            "control_command": command,
            "control_topic_fingerprint": _fingerprint(topic),
            "control_retained": False,
            "production_authorization_consumed": False,
        }
    )
    return report


def _private_yaml_secret_values(path: Path) -> list[str]:
    values: list[str] = []
    protected_keys = {
        "board_lab_wifi_password",
        "board_lab_candidate_password",
    }
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() not in protected_keys:
            continue
        value = value.strip().strip('"').strip("'")
        if value and not value.startswith("REPLACE_"):
            values.append(value)
    return values


def check_serial_log(
    workspace: str | Path,
    *,
    log_path: str | Path,
) -> dict[str, object]:
    resolved, manifest = _load_manifest(Path(workspace))
    identity = _identity_from_manifest(manifest)
    secret_document = _load_secrets(resolved)
    log = Path(log_path).expanduser().resolve().read_text(encoding="utf-8", errors="replace")
    protected_values = [str(value) for value in secret_document.values()]
    protected_values.extend(_private_yaml_secret_values(resolved / ESPHOME_SECRETS_NAME))
    protected_values = [value for value in protected_values if len(value) >= 8]
    matches = [value for value in protected_values if value in log]
    _require(not matches, "raw secret appeared in serial log")
    report = _base_report(
        identity,
        status="node_mqtt_board_lab_serial_log_check_succeeded",
        broker_running=None,
    )
    report.update(
        {
            "serial_log_line_count": len(log.splitlines()),
            "serial_log_fingerprint": _fingerprint(log),
            "protected_value_count": len(set(protected_values)),
            "secret_match_count": 0,
        }
    )
    return report
