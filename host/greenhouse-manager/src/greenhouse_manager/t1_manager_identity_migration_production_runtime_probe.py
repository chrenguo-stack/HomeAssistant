from __future__ import annotations

import json
import re
import secrets
import threading
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .t1_manager_identity_migration_production_host_adapters import (
    ManagerHostBinding,
)
from .t1_manager_runtime_secret_ownership import (
    ManagerRuntimeSecretOwnershipError,
    verify_bound_runtime_identity,
)
from .t1_migration_readiness import CommandRunner, SubprocessRunner
from .topics import (
    availability_topic,
    canonical_telemetry_subscription,
    canonical_telemetry_topic,
    ingress_subscription,
)

SCHEMA = "gh.m2.t1-manager-identity-production-runtime-probe/1"
_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_CONTAINER_ID = re.compile(r"^[0-9a-f]{64}$")


class ManagerProductionRuntimeProbeError(RuntimeError):
    pass


class RetainedReader(Protocol):
    def read(self, topic: str) -> bytes: ...


ReaderFactory = Callable[[], RetainedReader]
Sleeper = Callable[[float], None]


def _load_paho_mqtt() -> Any:
    try:
        import paho.mqtt.client as mqtt
    except ModuleNotFoundError as error:
        if error.name is None or not error.name.startswith("paho"):
            raise
        raise ManagerProductionRuntimeProbeError(
            "paho-mqtt is required for manager runtime probes"
        ) from error
    return mqtt


class PahoAnonymousRetainedReader:
    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 1883,
        timeout_s: float = 8.0,
    ) -> None:
        if not host or not 1 <= port <= 65535 or timeout_s <= 0:
            raise ValueError("retained reader configuration is invalid")
        self.host = host
        self.port = port
        self.timeout_s = timeout_s

    @staticmethod
    def _allowed_topic(topic: str) -> bool:
        return (
            topic.startswith("gh/") or topic.startswith("homeassistant/")
        ) and "+" not in topic and "#" not in topic

    def read(self, topic: str) -> bytes:
        if not self._allowed_topic(topic):
            raise ValueError("retained probe topic is outside the allowed namespaces")
        mqtt = _load_paho_mqtt()
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"gh-m2-manager-read-{secrets.token_hex(6)}",
            protocol=mqtt.MQTTv5,
        )
        connected = threading.Event()
        received = threading.Event()
        failures: list[str] = []
        payloads: list[bytes] = []

        def on_connect(
            _client: Any,
            _userdata: Any,
            _flags: Any,
            reason_code: Any,
            _properties: Any,
        ) -> None:
            if reason_code == 0:
                connected.set()
            else:
                failures.append(str(reason_code))
                connected.set()

        def on_message(_client: Any, _userdata: Any, message: Any) -> None:
            if message.topic == topic:
                payloads.append(bytes(message.payload))
                received.set()

        client.on_connect = on_connect
        client.on_message = on_message
        try:
            client.connect(self.host, self.port, keepalive=30)
        except OSError as error:
            raise ManagerProductionRuntimeProbeError(
                "anonymous retained probe could not connect"
            ) from error
        client.loop_start()
        try:
            if not connected.wait(self.timeout_s):
                raise ManagerProductionRuntimeProbeError(
                    "anonymous retained probe connection timed out"
                )
            if failures:
                raise ManagerProductionRuntimeProbeError(
                    "anonymous retained probe was rejected"
                )
            result, _mid = client.subscribe(topic, qos=0)
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise ManagerProductionRuntimeProbeError(
                    "anonymous retained probe subscribe failed"
                )
            if not received.wait(self.timeout_s):
                raise ManagerProductionRuntimeProbeError(
                    "anonymous retained probe timed out"
                )
            if not payloads or not payloads[-1]:
                raise ManagerProductionRuntimeProbeError(
                    "anonymous retained probe returned an empty payload"
                )
            return payloads[-1]
        finally:
            client.disconnect()
            client.loop_stop()


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ManagerProductionRuntimeProbeError("runtime timestamp is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ManagerProductionRuntimeProbeError(
            "runtime timestamp is invalid"
        ) from error
    if parsed.tzinfo is None:
        raise ManagerProductionRuntimeProbeError("runtime timestamp has no timezone")
    return parsed.astimezone(UTC)


def _read_json_payload(payload: bytes, label: str) -> dict[str, Any]:
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ManagerProductionRuntimeProbeError(f"{label} payload is invalid") from error
    if not isinstance(document, dict):
        raise ManagerProductionRuntimeProbeError(f"{label} payload must be an object")
    return document


def _environment(config: Mapping[str, Any]) -> dict[str, str]:
    raw = config.get("Env")
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise ManagerProductionRuntimeProbeError(
            "greenhouse-manager environment metadata is invalid"
        )
    values: dict[str, str] = {}
    for item in raw:
        key, separator, value = item.partition("=")
        if separator:
            values[key] = value
    return values


def _discovery_signature(document: Mapping[str, Any]) -> tuple[object, ...]:
    device = document.get("device")
    if not isinstance(device, dict):
        raise ManagerProductionRuntimeProbeError(
            "Home Assistant Discovery device metadata is missing"
        )
    identifiers = device.get("identifiers")
    if not isinstance(identifiers, list) or not identifiers or any(
        not isinstance(item, str) or not item for item in identifiers
    ):
        raise ManagerProductionRuntimeProbeError(
            "Home Assistant Discovery identifiers are invalid"
        )
    unique_ids: list[str] = []
    top_level = document.get("unique_id")
    if isinstance(top_level, str) and top_level:
        unique_ids.append(top_level)
    components = document.get("components")
    if components is not None:
        if not isinstance(components, dict):
            raise ManagerProductionRuntimeProbeError(
                "Home Assistant Discovery components are invalid"
            )
        for component in components.values():
            if not isinstance(component, dict):
                raise ManagerProductionRuntimeProbeError(
                    "Home Assistant Discovery component is invalid"
                )
            unique_id = component.get("unique_id")
            if not isinstance(unique_id, str) or not unique_id:
                raise ManagerProductionRuntimeProbeError(
                    "Home Assistant Discovery component unique_id is invalid"
                )
            unique_ids.append(unique_id)
    if not unique_ids:
        raise ManagerProductionRuntimeProbeError(
            "Home Assistant Discovery unique_id inventory is empty"
        )
    return (
        tuple(sorted(identifiers)),
        tuple(sorted(unique_ids)),
        document.get("state_topic"),
        json.dumps(document.get("availability"), sort_keys=True, ensure_ascii=False),
    )


class ManagerProductionRuntimeProbe:
    def __init__(
        self,
        binding: ManagerHostBinding,
        *,
        system_id: str,
        node_id: str,
        discovery_topic: str,
        runner: CommandRunner | None = None,
        reader_factory: ReaderFactory | None = None,
        proc_root: str | Path = "/proc",
        mqtt_port: int = 1883,
        timeout_s: float = 35.0,
        poll_interval_s: float = 1.0,
        sleeper: Sleeper = time.sleep,
    ) -> None:
        if _ID.fullmatch(system_id) is None or _ID.fullmatch(node_id) is None:
            raise ValueError("runtime probe system_id or node_id is invalid")
        if (
            not discovery_topic.startswith("homeassistant/")
            or "+" in discovery_topic
            or "#" in discovery_topic
        ):
            raise ValueError("runtime probe Discovery topic is invalid")
        if not 1 <= mqtt_port <= 65535 or timeout_s <= 0 or poll_interval_s <= 0:
            raise ValueError("runtime probe timing or port is invalid")
        self.binding = binding
        self.system_id = system_id
        self.node_id = node_id
        self.discovery_topic = discovery_topic
        self.runner = runner or SubprocessRunner()
        self.reader_factory = reader_factory or (
            lambda: PahoAnonymousRetainedReader(port=mqtt_port)
        )
        self.proc_root = Path(proc_root)
        self.mqtt_port = mqtt_port
        self.timeout_s = timeout_s
        self.poll_interval_s = poll_interval_s
        self.sleeper = sleeper
        self.canonical_topic = canonical_telemetry_topic(system_id, node_id)
        self.availability_topic = availability_topic(system_id, node_id)
        self._baseline_discovery_signature: tuple[object, ...] | None = None
        self._baseline_canonical_node: str | None = None
        self._checks: dict[str, bool] = {}

    def capture_baseline(self) -> dict[str, object]:
        reader = self.reader_factory()
        canonical = _read_json_payload(
            reader.read(self.canonical_topic),
            "canonical telemetry baseline",
        )
        availability = _read_json_payload(
            reader.read(self.availability_topic),
            "availability baseline",
        )
        discovery = _read_json_payload(
            reader.read(self.discovery_topic),
            "Discovery baseline",
        )
        if canonical.get("node_id") != self.node_id:
            raise ManagerProductionRuntimeProbeError(
                "canonical telemetry baseline node_id does not match"
            )
        if availability.get("node_id") != self.node_id or availability.get("state") not in {
            "online",
            "unavailable",
        }:
            raise ManagerProductionRuntimeProbeError(
                "availability baseline does not match the expected node"
            )
        self._baseline_canonical_node = self.node_id
        self._baseline_discovery_signature = _discovery_signature(discovery)
        self._checks["baseline_captured"] = True
        return {
            "schema": SCHEMA,
            "baseline_captured": True,
            "canonical_topic_verified": True,
            "availability_topic_verified": True,
            "discovery_topic_verified": True,
            "secret_values_included": False,
            "path_values_redacted": True,
        }

    def _inspect(self) -> dict[str, Any]:
        code, output = self.runner.run(("docker", "inspect", "greenhouse-manager"))
        if code != 0:
            raise ManagerProductionRuntimeProbeError(
                "greenhouse-manager cannot be inspected"
            )
        try:
            documents = json.loads(output)
        except json.JSONDecodeError as error:
            raise ManagerProductionRuntimeProbeError(
                "greenhouse-manager inspection returned invalid JSON"
            ) from error
        if (
            not isinstance(documents, list)
            or len(documents) != 1
            or not isinstance(documents[0], dict)
        ):
            raise ManagerProductionRuntimeProbeError(
                "exactly one greenhouse-manager container is required"
            )
        document = documents[0]
        state = document.get("State")
        config = document.get("Config")
        if not isinstance(state, dict) or not isinstance(config, dict):
            raise ManagerProductionRuntimeProbeError(
                "greenhouse-manager runtime metadata is incomplete"
            )
        if state.get("Status") != "running" or int(document.get("RestartCount", -1)) != 0:
            raise ManagerProductionRuntimeProbeError(
                "greenhouse-manager must be running with restart count zero"
            )
        return document

    def _expected_password_target(self) -> str:
        values: dict[str, str] = {}
        for raw in self.binding.material_environment.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            if not separator or key in values:
                raise ManagerProductionRuntimeProbeError(
                    "manager material environment is invalid"
                )
            values[key] = value
        target = values.get("GH_MQTT_PASSWORD_FILE")
        if not target or not Path(target).is_absolute():
            raise ManagerProductionRuntimeProbeError(
                "manager password mount target is invalid"
            )
        return target

    def _validate_identity_binding(self, document: Mapping[str, Any]) -> tuple[int, datetime, Path]:
        state = document["State"]
        config = document["Config"]
        assert isinstance(state, dict)
        assert isinstance(config, dict)
        values = _environment(config)
        try:
            verify_bound_runtime_identity(
                {
                    "manager_runtime_uid": self.binding.manager_runtime_uid,
                    "manager_runtime_gid": self.binding.manager_runtime_gid,
                    "manager_runtime_user_source": self.binding.manager_runtime_user_source,
                    "manager_runtime_image_id": self.binding.manager_runtime_image_id,
                    "manager_runtime_user_spec": self.binding.manager_runtime_user_spec,
                },
                image_id=document.get("Image"),
                user_spec=config.get("User", ""),
            )
        except ManagerRuntimeSecretOwnershipError as error:
            raise ManagerProductionRuntimeProbeError(
                "greenhouse-manager runtime ownership binding failed"
            ) from error
        expected_password_target = self._expected_password_target()
        if (
            values.get("GH_MQTT_USERNAME") != self.binding.username
            or values.get("GH_MQTT_CLIENT_ID") != self.binding.client_id
            or values.get("GH_MQTT_PASSWORD_FILE") != expected_password_target
            or bool(values.get("GH_MQTT_PASSWORD", ""))
        ):
            raise ManagerProductionRuntimeProbeError(
                "greenhouse-manager authenticated environment binding failed"
            )
        mounts = document.get("Mounts")
        if not isinstance(mounts, list):
            raise ManagerProductionRuntimeProbeError(
                "greenhouse-manager mount inventory is missing"
            )
        matching = [
            item
            for item in mounts
            if isinstance(item, dict)
            and item.get("Source") == str(self.binding.password_target)
            and item.get("Destination") == expected_password_target
            and item.get("RW") is False
        ]
        if len(matching) != 1:
            raise ManagerProductionRuntimeProbeError(
                "greenhouse-manager password mount binding failed"
            )
        if (
            not self.binding.password_target.is_file()
            or self.binding.password_target.is_symlink()
        ):
            raise ManagerProductionRuntimeProbeError(
                "greenhouse-manager password source is missing or unsafe"
            )
        password_stat = self.binding.password_target.stat()
        if (
            password_stat.st_mode & 0o777 != 0o600
            or password_stat.st_uid != self.binding.manager_runtime_uid
            or password_stat.st_gid != self.binding.manager_runtime_gid
        ):
            raise ManagerProductionRuntimeProbeError(
                "greenhouse-manager password source is missing or unsafe"
            )
        pid = state.get("Pid")
        if not isinstance(pid, int) or pid <= 0:
            raise ManagerProductionRuntimeProbeError(
                "greenhouse-manager process ID is invalid"
            )
        started_at = _parse_time(state.get("StartedAt"))
        log_path_raw = document.get("LogPath")
        container_id = document.get("Id")
        if (
            not isinstance(log_path_raw, str)
            or not isinstance(container_id, str)
            or _CONTAINER_ID.fullmatch(container_id) is None
        ):
            raise ManagerProductionRuntimeProbeError(
                "greenhouse-manager log binding is incomplete"
            )
        log_path = Path(log_path_raw)
        if (
            not log_path.is_absolute()
            or log_path.is_symlink()
            or not log_path.is_file()
            or log_path.name != f"{container_id}-json.log"
            or log_path.parent.name != container_id
        ):
            raise ManagerProductionRuntimeProbeError(
                "greenhouse-manager Docker JSON log path is unsafe"
            )
        return pid, started_at, log_path

    def _mqtt_socket_inodes(self, pid: int) -> set[str]:
        observed: set[str] = set()
        for name in ("tcp", "tcp6"):
            path = self.proc_root / str(pid) / "net" / name
            if not path.is_file() or path.is_symlink():
                continue
            lines = path.read_text(encoding="ascii").splitlines()
            for line in lines[1:]:
                fields = line.split()
                if len(fields) < 10:
                    continue
                remote = fields[2]
                state = fields[3]
                if ":" not in remote or state != "01":
                    continue
                _address, raw_port = remote.rsplit(":", 1)
                try:
                    port = int(raw_port, 16)
                except ValueError:
                    continue
                if port == self.mqtt_port:
                    observed.add(fields[9])
        return observed

    def _stable_mqtt_socket(self, pid: int) -> bool:
        first = self._mqtt_socket_inodes(pid)
        if not first:
            return False
        self.sleeper(min(self.poll_interval_s, 2.0))
        second = self._mqtt_socket_inodes(pid)
        return bool(first & second)

    @staticmethod
    def _log_messages(log_path: Path, started_at: datetime) -> tuple[str, ...]:
        size = log_path.stat().st_size
        with log_path.open("rb") as stream:
            if size > 4 * 1024 * 1024:
                stream.seek(size - 4 * 1024 * 1024)
                stream.readline()
            payload = stream.read()
        messages: list[str] = []
        for raw in payload.splitlines():
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            try:
                timestamp = _parse_time(item.get("time"))
            except ManagerProductionRuntimeProbeError:
                continue
            message = item.get("log")
            if timestamp >= started_at and isinstance(message, str):
                messages.append(message.strip())
        return tuple(messages)

    def _wait_for_log(self, expected: str) -> None:
        deadline = time.monotonic() + self.timeout_s
        while True:
            document = self._inspect()
            _pid, started_at, log_path = self._validate_identity_binding(document)
            if any(expected in message for message in self._log_messages(log_path, started_at)):
                return
            if time.monotonic() >= deadline:
                raise ManagerProductionRuntimeProbeError(
                    "greenhouse-manager expected runtime log evidence timed out"
                )
            self.sleeper(self.poll_interval_s)

    def verify_authenticated_identity(self, username: str, client_id: str) -> None:
        if username != self.binding.username or client_id != self.binding.client_id:
            raise ManagerProductionRuntimeProbeError(
                "greenhouse-manager identity probe inputs do not match the binding"
            )
        document = self._inspect()
        pid, _started_at, _log_path = self._validate_identity_binding(document)
        if not self._stable_mqtt_socket(pid):
            raise ManagerProductionRuntimeProbeError(
                "greenhouse-manager has no stable MQTT TCP session"
            )
        self._checks["manager_authenticated"] = True

    def verify_ingress_subscription(self) -> None:
        self._wait_for_log(f"Subscribed to {ingress_subscription(self.system_id)}")
        self._checks["ingress_subscription_verified"] = True

    def verify_canonical_publication(self) -> None:
        self._wait_for_log(f"Accepted telemetry node={self.node_id} ")
        document = _read_json_payload(
            self.reader_factory().read(self.canonical_topic),
            "canonical telemetry",
        )
        if document.get("node_id") != self.node_id:
            raise ManagerProductionRuntimeProbeError(
                "canonical telemetry node_id does not match"
            )
        self._checks["canonical_publication_verified"] = True

    def verify_availability_publication(self) -> None:
        document = _read_json_payload(
            self.reader_factory().read(self.availability_topic),
            "availability",
        )
        if document.get("node_id") != self.node_id or document.get("state") != "online":
            raise ManagerProductionRuntimeProbeError(
                "manager availability publication is not online"
            )
        self._checks["availability_publication_verified"] = True

    def verify_discovery_publication(self) -> None:
        self._wait_for_log(
            f"Published Home Assistant discovery node={self.node_id} "
            f"topic={self.discovery_topic}"
        )
        document = _read_json_payload(
            self.reader_factory().read(self.discovery_topic),
            "Home Assistant Discovery",
        )
        signature = _discovery_signature(document)
        if self._baseline_discovery_signature is None:
            raise ManagerProductionRuntimeProbeError(
                "Home Assistant Discovery baseline was not captured"
            )
        if signature != self._baseline_discovery_signature:
            raise ManagerProductionRuntimeProbeError(
                "Home Assistant Discovery identity changed during manager migration"
            )
        self._checks["discovery_publication_verified"] = True

    def verify_reconnect(self) -> None:
        self._wait_for_log(f"Subscribed to {ingress_subscription(self.system_id)}")
        self._wait_for_log(
            f"Subscribed to {canonical_telemetry_subscription(self.system_id)}"
        )
        document = self._inspect()
        pid, _started_at, _log_path = self._validate_identity_binding(document)
        if not self._stable_mqtt_socket(pid):
            raise ManagerProductionRuntimeProbeError(
                "greenhouse-manager MQTT session did not remain stable after reconnect"
            )
        self._checks["reconnect_verified"] = True

    def verify_existing_entities(self) -> None:
        if self._baseline_discovery_signature is None or self._baseline_canonical_node is None:
            raise ManagerProductionRuntimeProbeError(
                "entity continuity baseline was not captured"
            )
        canonical = _read_json_payload(
            self.reader_factory().read(self.canonical_topic),
            "canonical telemetry continuity",
        )
        discovery = _read_json_payload(
            self.reader_factory().read(self.discovery_topic),
            "Discovery continuity",
        )
        if canonical.get("node_id") != self._baseline_canonical_node:
            raise ManagerProductionRuntimeProbeError(
                "canonical node identity changed during manager migration"
            )
        if _discovery_signature(discovery) != self._baseline_discovery_signature:
            raise ManagerProductionRuntimeProbeError(
                "Home Assistant entity identity changed during manager migration"
            )
        self._checks["existing_entities_verified"] = True

    def verify_legacy_anonymous_path(self) -> None:
        canonical = _read_json_payload(
            self.reader_factory().read(self.canonical_topic),
            "anonymous compatibility",
        )
        if canonical.get("node_id") != self.node_id:
            raise ManagerProductionRuntimeProbeError(
                "anonymous compatibility retained state is unavailable"
            )
        self._checks["legacy_anonymous_path_verified"] = True

    def postactivation_audit(self) -> dict[str, object]:
        required = (
            "manager_authenticated",
            "ingress_subscription_verified",
            "canonical_publication_verified",
            "availability_publication_verified",
            "discovery_publication_verified",
            "reconnect_verified",
            "existing_entities_verified",
        )
        checks = {name: self._checks.get(name) is True for name in required}
        checks["baseline_captured"] = self._checks.get("baseline_captured") is True
        verified = all(checks.values())
        return {
            "schema": SCHEMA,
            "checks": checks,
            "manager_identity_migrated": verified,
            "manager_authenticated": checks["manager_authenticated"],
            "ingress_subscription_verified": checks[
                "ingress_subscription_verified"
            ],
            "canonical_publication_verified": checks[
                "canonical_publication_verified"
            ],
            "availability_publication_verified": checks[
                "availability_publication_verified"
            ],
            "discovery_publication_verified": checks[
                "discovery_publication_verified"
            ],
            "reconnect_verified": checks["reconnect_verified"],
            "existing_entities_verified": checks["existing_entities_verified"],
            "rollback_required": not verified,
            "node_credentials_delivered": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "current_services_modified": False,
            "secret_values_included": False,
            "path_values_redacted": True,
        }
