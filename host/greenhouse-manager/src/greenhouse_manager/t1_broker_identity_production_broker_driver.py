from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .dynsec_api import DynsecError, PahoDynsecTransport
from .t1_broker_identity_activation_checks import Runner
from .t1_broker_identity_runtime_binding_manifest import verify_runtime_binding_manifest
from .t1_shadow import PLUGIN_CONFIG_LINE, PLUGIN_LINE, PLUGIN_PASSWORD_INIT_LINE

SCHEMA = "gh.m2.t1-broker-identity-production-broker-driver/1"
_LIST_CLIENTS = ({"command": "listClients"},)

ManifestVerifier = Callable[[str | Path], dict[str, object]]


class BrokerIdentityProductionBrokerDriverError(RuntimeError):
    pass


def _load_paho_mqtt() -> Any:
    try:
        import paho.mqtt.client as mqtt
    except ModuleNotFoundError as error:
        if error.name is None or not error.name.startswith("paho"):
            raise
        raise BrokerIdentityProductionBrokerDriverError(
            "paho-mqtt is required for live Broker activation"
        ) from error
    return mqtt


@dataclass(frozen=True)
class ClientConfig:
    host: str
    port: int
    username: str
    password: str
    client_id: str


class MqttSession(Protocol):
    def execute(
        self,
        commands: Sequence[dict[str, Any]],
    ) -> tuple[dict[str, Any], ...]: ...

    def retained_message(self, topic: str) -> bytes: ...


SessionFactory = Callable[[ClientConfig | None], MqttSession]


class PahoMqttSession:
    def __init__(
        self,
        config: ClientConfig | None,
        *,
        timeout_s: float = 8.0,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("MQTT timeout must be positive")
        self.config = config
        self.timeout_s = timeout_s

    def _connected_client(self) -> tuple[Any, threading.Event]:
        mqtt = _load_paho_mqtt()
        config = self.config
        client_id = (
            config.client_id
            if config is not None
            else f"gh-m2-anonymous-probe-{secrets.token_hex(6)}"
        )
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv5,
        )
        if config is not None:
            client.username_pw_set(config.username, config.password)
        connected = threading.Event()
        failed: list[str] = []

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
                failed.append(str(reason_code))
                connected.set()

        client.on_connect = on_connect
        host = config.host if config is not None else "127.0.0.1"
        port = config.port if config is not None else 1883
        try:
            client.connect(host, port, keepalive=30)
        except OSError as error:
            raise BrokerIdentityProductionBrokerDriverError(
                "MQTT connection could not be started"
            ) from error
        client.loop_start()
        if not connected.wait(self.timeout_s):
            client.disconnect()
            client.loop_stop()
            raise BrokerIdentityProductionBrokerDriverError(
                "MQTT connection timed out"
            )
        if failed:
            client.disconnect()
            client.loop_stop()
            raise BrokerIdentityProductionBrokerDriverError(
                "MQTT connection was rejected"
            )
        return client, connected

    def execute(
        self,
        commands: Sequence[dict[str, Any]],
    ) -> tuple[dict[str, Any], ...]:
        client, _connected = self._connected_client()
        try:
            transport = PahoDynsecTransport(client, timeout_s=self.timeout_s)
            client.on_message = transport.on_message
            return transport.execute(commands)
        finally:
            client.disconnect()
            client.loop_stop()

    def retained_message(self, topic: str) -> bytes:
        mqtt = _load_paho_mqtt()
        if not topic.startswith("gh/"):
            raise ValueError("retained probe topic must be in the gh namespace")
        client, _connected = self._connected_client()
        received = threading.Event()
        payloads: list[bytes] = []

        def on_message(_client: Any, _userdata: Any, message: Any) -> None:
            if message.topic == topic:
                payloads.append(bytes(message.payload))
                received.set()

        client.on_message = on_message
        try:
            result, _mid = client.subscribe(topic, qos=0)
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise BrokerIdentityProductionBrokerDriverError(
                    "MQTT retained probe subscribe failed"
                )
            if not received.wait(self.timeout_s):
                raise BrokerIdentityProductionBrokerDriverError(
                    "MQTT retained probe timed out"
                )
            if not payloads or not payloads[0]:
                raise BrokerIdentityProductionBrokerDriverError(
                    "MQTT retained probe returned an empty payload"
                )
            return payloads[0]
        finally:
            client.disconnect()
            client.loop_stop()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise BrokerIdentityProductionBrokerDriverError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BrokerIdentityProductionBrokerDriverError(
            f"{label} is invalid"
        ) from error
    if not isinstance(value, dict):
        raise BrokerIdentityProductionBrokerDriverError(
            f"{label} must be a JSON object"
        )
    return value


def _client_config(value: str, label: str) -> ClientConfig:
    options: dict[str, str] = {}
    for raw in value.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or parts[0] not in {"-h", "-p", "-u", "-P", "-i", "-V"}:
            raise BrokerIdentityProductionBrokerDriverError(
                f"{label} contains an unsupported option"
            )
        options[parts[0]] = parts[1]
    required = ("-h", "-u", "-P", "-i")
    if any(not options.get(key) for key in required):
        raise BrokerIdentityProductionBrokerDriverError(
            f"{label} is incomplete"
        )
    if options.get("-V", "5") != "5":
        raise BrokerIdentityProductionBrokerDriverError(
            f"{label} must require MQTT v5"
        )
    try:
        port = int(options.get("-p", "1883"))
    except ValueError as error:
        raise BrokerIdentityProductionBrokerDriverError(
            f"{label} port is invalid"
        ) from error
    if port < 1 or port > 65535:
        raise BrokerIdentityProductionBrokerDriverError(
            f"{label} port is invalid"
        )
    return ClientConfig(
        host=options["-h"],
        port=port,
        username=options["-u"],
        password=options["-P"],
        client_id=options["-i"],
    )


def _homeassistant_config(update: Mapping[str, Any], client_id: str | None = None) -> ClientConfig:
    username = update.get("username")
    password = update.get("password")
    required_id = update.get("required_client_id")
    if not all(
        isinstance(item, str) and item
        for item in (username, password, required_id)
    ):
        raise BrokerIdentityProductionBrokerDriverError(
            "Home Assistant MQTT identity is incomplete"
        )
    return ClientConfig(
        host="127.0.0.1",
        port=1883,
        username=str(username),
        password=str(password),
        client_id=client_id or str(required_id),
    )


def _active_lines(path: Path) -> tuple[str, ...]:
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


class LiveProductionBrokerDriver:
    def __init__(
        self,
        runtime_binding_manifest_file: str | Path,
        *,
        runner: Runner,
        timeout_s: float = 30.0,
        mqtt_timeout_s: float = 8.0,
        manifest_verifier: ManifestVerifier = verify_runtime_binding_manifest,
        session_factory: SessionFactory | None = None,
    ) -> None:
        if timeout_s <= 0 or mqtt_timeout_s <= 0:
            raise ValueError("driver timeouts must be positive")
        self.manifest_path = Path(
            runtime_binding_manifest_file
        ).expanduser().resolve()
        self.manifest = _read_private_json(
            self.manifest_path,
            "runtime binding manifest",
        )
        result = manifest_verifier(self.manifest_path)
        if result.get("verified") is not True:
            raise BrokerIdentityProductionBrokerDriverError(
                "runtime binding manifest verification is incomplete"
            )
        runtime = self.manifest.get("runtime")
        paths = self.manifest.get("paths")
        if not isinstance(runtime, dict) or not isinstance(paths, dict):
            raise BrokerIdentityProductionBrokerDriverError(
                "runtime binding manifest is incomplete"
            )
        self.container_id = runtime.get("container_id")
        self.image_id = runtime.get("image_id")
        if not all(
            isinstance(item, str) and item
            for item in (self.container_id, self.image_id)
        ):
            raise BrokerIdentityProductionBrokerDriverError(
                "runtime container binding is incomplete"
            )
        self.config_file = self._bound_path(paths, "config_file", must_exist=True)
        self.state_file = self._bound_path(
            paths,
            "dynamic_security_state_file",
            must_exist=False,
        )
        baseline = self.manifest.get("baseline_config_sha256")
        if not isinstance(baseline, str):
            raise BrokerIdentityProductionBrokerDriverError(
                "runtime baseline configuration binding is missing"
            )
        self.baseline_config_sha256 = baseline
        self.runner = runner
        self.timeout_s = timeout_s
        self.mqtt_timeout_s = mqtt_timeout_s
        self.session_factory = session_factory or (
            lambda config: PahoMqttSession(config, timeout_s=self.mqtt_timeout_s)
        )

    @staticmethod
    def _bound_path(
        paths: Mapping[str, Any],
        name: str,
        *,
        must_exist: bool,
    ) -> Path:
        raw = paths.get(name)
        if not isinstance(raw, str):
            raise BrokerIdentityProductionBrokerDriverError(
                f"runtime path binding is missing: {name}"
            )
        path = Path(raw).expanduser()
        if not path.is_absolute() or path.is_symlink():
            raise BrokerIdentityProductionBrokerDriverError(
                f"runtime path binding is unsafe: {name}"
            )
        path = path.resolve(strict=False)
        if must_exist and not path.is_file():
            raise BrokerIdentityProductionBrokerDriverError(
                f"runtime file is missing: {name}"
            )
        return path

    def _inspect(self) -> dict[str, Any]:
        code, output = self.runner.run(("docker", "inspect", "mosquitto"))
        if code != 0:
            raise BrokerIdentityProductionBrokerDriverError(
                "live Mosquitto container cannot be inspected"
            )
        try:
            values = json.loads(output)
        except json.JSONDecodeError as error:
            raise BrokerIdentityProductionBrokerDriverError(
                "live Mosquitto inspect returned invalid JSON"
            ) from error
        if (
            not isinstance(values, list)
            or len(values) != 1
            or not isinstance(values[0], dict)
        ):
            raise BrokerIdentityProductionBrokerDriverError(
                "live Mosquitto inspect returned an unexpected document"
            )
        return values[0]

    def _validate_runtime(self, document: Mapping[str, Any]) -> None:
        state = document.get("State")
        if (
            document.get("Id") != self.container_id
            or document.get("Image") != self.image_id
            or not isinstance(state, dict)
            or state.get("Status") != "running"
        ):
            raise BrokerIdentityProductionBrokerDriverError(
                "live Mosquitto runtime identity has drifted"
            )

    def restart_mosquitto(self) -> None:
        self._validate_runtime(self._inspect())
        code, output = self.runner.run(("docker", "restart", "mosquitto"))
        if code != 0 or output.strip() not in {"", "mosquitto"}:
            raise BrokerIdentityProductionBrokerDriverError(
                "Mosquitto restart failed"
            )
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            try:
                document = self._inspect()
                self._validate_runtime(document)
            except BrokerIdentityProductionBrokerDriverError:
                time.sleep(0.2)
                continue
            return
        raise BrokerIdentityProductionBrokerDriverError(
            "Mosquitto did not return to the bound running state"
        )

    def wait_for_dynamic_security_state(self, state_file: Path) -> None:
        if state_file.resolve(strict=False) != self.state_file:
            raise BrokerIdentityProductionBrokerDriverError(
                "Dynamic Security state waiter path is not bound"
            )
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            if self.state_file.is_file() and self.state_file.stat().st_size > 0:
                return
            time.sleep(0.2)
        raise BrokerIdentityProductionBrokerDriverError(
            "Dynamic Security state was not created before timeout"
        )

    def _session(self, config_text: str, label: str) -> MqttSession:
        return self.session_factory(_client_config(config_text, label))

    def apply_exact_request(
        self,
        commands: Sequence[dict[str, Any]],
        bootstrap_config: str,
    ) -> None:
        if not commands:
            raise BrokerIdentityProductionBrokerDriverError(
                "Dynamic Security request is empty"
            )
        self._session(bootstrap_config, "bootstrap client configuration").execute(
            commands
        )

    def verify_provisioning_identity(self, provisioning_config: str) -> None:
        responses = self._session(
            provisioning_config,
            "provisioning client configuration",
        ).execute(_LIST_CLIENTS)
        if (
            not responses
            or responses[0].get("command") != "listClients"
            or responses[0].get("error")
        ):
            raise BrokerIdentityProductionBrokerDriverError(
                "provisioning identity verification failed"
            )

    def delete_bootstrap_admin(self, provisioning_config: str) -> None:
        responses = self._session(
            provisioning_config,
            "provisioning client configuration",
        ).execute(({"command": "deleteClient", "username": "admin"},))
        if (
            not responses
            or responses[0].get("command") != "deleteClient"
            or responses[0].get("error")
        ):
            raise BrokerIdentityProductionBrokerDriverError(
                "bootstrap administrator deletion failed"
            )

    def verify_bootstrap_rejected(self, bootstrap_config: str) -> None:
        try:
            self._session(
                bootstrap_config,
                "bootstrap client configuration",
            ).execute(_LIST_CLIENTS)
        except (BrokerIdentityProductionBrokerDriverError, DynsecError):
            return
        raise BrokerIdentityProductionBrokerDriverError(
            "bootstrap administrator remained usable"
        )

    def _retained_readable(self, config: ClientConfig | None, topic: str) -> bool:
        try:
            return bool(self.session_factory(config).retained_message(topic))
        except (BrokerIdentityProductionBrokerDriverError, DynsecError):
            return False

    def _control_denied(self, config: ClientConfig | None) -> bool:
        try:
            self.session_factory(config).execute(_LIST_CLIENTS)
        except (BrokerIdentityProductionBrokerDriverError, DynsecError):
            return True
        return False

    def postactivation_audit(
        self,
        *,
        expected_retained_topic: str,
        homeassistant_update: Mapping[str, Any],
        provisioning_config: str,
        bootstrap_config: str,
    ) -> dict[str, object]:
        self._validate_runtime(self._inspect())
        lines = _active_lines(self.config_file)
        correct = _homeassistant_config(homeassistant_update)
        wrong = _homeassistant_config(
            homeassistant_update,
            f"{correct.client_id}-wrong",
        )
        provisioning = _client_config(
            provisioning_config,
            "provisioning client configuration",
        )
        bootstrap = _client_config(
            bootstrap_config,
            "bootstrap client configuration",
        )
        checks = {
            "mosquitto_runtime_bound_running": True,
            "broker_config_changed_from_baseline": (
                _sha256_path(self.config_file) != self.baseline_config_sha256
            ),
            "dynamic_security_plugin_configured": all(
                line in lines
                for line in (
                    PLUGIN_LINE,
                    PLUGIN_CONFIG_LINE,
                    PLUGIN_PASSWORD_INIT_LINE,
                )
            ),
            "dynamic_security_state_present_private": (
                self.state_file.is_file()
                and self.state_file.stat().st_mode & 0o777 == 0o600
            ),
            "anonymous_compatibility_enabled": _anonymous_enabled(lines),
            "anonymous_retained_state_readable": self._retained_readable(
                None,
                expected_retained_topic,
            ),
            "homeassistant_identity_retained_state_readable": (
                self._retained_readable(correct, expected_retained_topic)
            ),
            "homeassistant_wrong_client_id_rejected": not self._retained_readable(
                wrong,
                expected_retained_topic,
            ),
            "provisioning_control_readable": not self._control_denied(provisioning),
            "bootstrap_admin_rejected": self._control_denied(bootstrap),
            "anonymous_control_denied": self._control_denied(None),
        }
        verified = all(checks.values())
        return {
            "schema": SCHEMA,
            "checks": checks,
            "activation_verified": verified,
            "rollback_required": not verified,
            "broker_identity_activated": verified,
            "ready_for_homeassistant_reconfigure_handoff": verified,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "current_services_modified": True,
            "path_values_redacted": True,
            "secret_values_included": False,
        }

    def restart_after_rollback(self) -> None:
        self.restart_mosquitto()

    def verify_anonymous_retained_state(self, topic: str) -> None:
        if not self._retained_readable(None, topic):
            raise BrokerIdentityProductionBrokerDriverError(
                "anonymous retained state is not readable after rollback"
            )
