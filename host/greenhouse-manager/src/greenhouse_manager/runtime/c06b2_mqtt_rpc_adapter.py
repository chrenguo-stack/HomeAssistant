from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import paho.mqtt.client as mqtt

from .c06b2_ha_projection_protocol import (
    HomeAssistantProjectionRequest,
    ProjectionProtocolError,
    build_projection_request,
    parse_and_bind_projection_result,
    projection_request_topic,
    projection_result_topic,
)
from .history_projection_contract import AdapterDispatchResult, ProjectionBatch

_LOGGER = logging.getLogger(__name__)


class ProjectionRpcTransportError(RuntimeError):
    """Raised when the MQTT transport cannot satisfy the RPC contract."""


MessageCallback = Callable[[str, bytes], None]
LifecycleCallback = Callable[[], None]


class ProjectionRpcTransport(Protocol):
    """Minimal transport boundary used by the synchronous projection adapter."""

    def set_callbacks(
        self,
        *,
        on_message: MessageCallback,
        on_connect: LifecycleCallback,
        on_disconnect: LifecycleCallback,
    ) -> None: ...

    def start(self) -> None: ...

    def publish(
        self,
        *,
        topic: str,
        payload: bytes,
        qos: int,
        retain: bool,
    ) -> bool: ...

    def stop(self) -> None: ...


@dataclass(slots=True)
class _InflightRequest:
    request: HomeAssistantProjectionRequest
    completed: threading.Event
    result: AdapterDispatchResult | None = None
    publish_armed: bool = False


class PahoProjectionRpcTransport:
    """Paho MQTT v5 transport with fixed subscription and reconnect behavior."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        client_id: str,
        result_topic: str,
        username: str | None = None,
        password: str | None = None,
        tls_enabled: bool = False,
        ca_file: str | None = None,
        connect_timeout_seconds: float = 15.0,
    ) -> None:
        if not host.strip():
            raise ValueError("MQTT host cannot be empty")
        if not 1 <= port <= 65_535:
            raise ValueError("MQTT port must be between 1 and 65535")
        if connect_timeout_seconds <= 0:
            raise ValueError("connect timeout must be positive")
        if bool(username) != bool(password):
            raise ValueError("MQTT username and password must be configured together")
        if tls_enabled and not ca_file:
            raise ValueError("CA file is required when MQTT TLS is enabled")

        self._host = host
        self._port = port
        self._result_topic = result_topic
        self._connect_timeout_seconds = connect_timeout_seconds
        self._connected = threading.Event()
        self._started = False
        self._start_lock = threading.Lock()
        self._on_message: MessageCallback | None = None
        self._on_connect_callback: LifecycleCallback | None = None
        self._on_disconnect_callback: LifecycleCallback | None = None

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv5,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._handle_message
        self._client.reconnect_delay_set(min_delay=1, max_delay=15)
        self._client.enable_logger(_LOGGER)
        if username and password:
            self._client.username_pw_set(username, password)
        if tls_enabled:
            self._client.tls_set(ca_certs=ca_file)

    def set_callbacks(
        self,
        *,
        on_message: MessageCallback,
        on_connect: LifecycleCallback,
        on_disconnect: LifecycleCallback,
    ) -> None:
        self._on_message = on_message
        self._on_connect_callback = on_connect
        self._on_disconnect_callback = on_disconnect

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        del userdata, flags, properties
        if reason_code.is_failure:
            _LOGGER.error("C06-B2 MQTT connection rejected: %s", reason_code)
            return
        result, _mid = client.subscribe(self._result_topic, qos=1)
        if result != mqtt.MQTT_ERR_SUCCESS:
            _LOGGER.error(
                "C06-B2 result subscription failed topic=%s rc=%s",
                self._result_topic,
                result,
            )
            return
        self._connected.set()
        callback = self._on_connect_callback
        if callback is not None:
            callback()

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: object,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        del client, userdata, disconnect_flags, properties
        self._connected.clear()
        if reason_code.is_failure:
            _LOGGER.warning("C06-B2 MQTT disconnected unexpectedly: %s", reason_code)
        callback = self._on_disconnect_callback
        if callback is not None:
            callback()

    def _handle_message(
        self,
        client: mqtt.Client,
        userdata: object,
        message: mqtt.MQTTMessage,
    ) -> None:
        del client, userdata
        callback = self._on_message
        if callback is None:
            return
        try:
            payload = (
                message.payload
                if isinstance(message.payload, bytes)
                else bytes(message.payload)
            )
        except (TypeError, ValueError):
            _LOGGER.warning("Ignored C06-B2 MQTT result with invalid payload type")
            return
        callback(message.topic, payload)

    def start(self) -> None:
        with self._start_lock:
            if self._started:
                if not self._connected.wait(self._connect_timeout_seconds):
                    raise ProjectionRpcTransportError("MQTT transport is not connected")
                return
            self._started = True
            try:
                self._client.connect(self._host, self._port, keepalive=60)
                self._client.loop_start()
            except Exception:
                self._started = False
                self._connected.clear()
                try:
                    self._client.disconnect()
                finally:
                    self._client.loop_stop()
                raise
        if not self._connected.wait(self._connect_timeout_seconds):
            self.stop()
            raise ProjectionRpcTransportError("MQTT connection timed out")

    def publish(
        self,
        *,
        topic: str,
        payload: bytes,
        qos: int,
        retain: bool,
    ) -> bool:
        if qos != 1 or retain:
            raise ProjectionRpcTransportError(
                "projection RPC requires QoS 1 and retain=false"
            )
        if not self._connected.is_set():
            return False
        info = self._client.publish(topic, payload=payload, qos=qos, retain=retain)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            return False
        try:
            info.wait_for_publish(timeout=10)
        except (RuntimeError, ValueError):
            return False
        is_published = getattr(info, "is_published", None)
        return not callable(is_published) or bool(is_published())

    def stop(self) -> None:
        with self._start_lock:
            if not self._started:
                return
            self._started = False
            self._connected.clear()
            try:
                self._client.disconnect()
            finally:
                self._client.loop_stop()


class MqttProjectionRpcAdapter:
    """Single-inflight Manager adapter for the fixed C06-B2 MQTT RPC topics."""

    kind = "home-assistant-mqtt-rpc"
    version = "1"

    def __init__(
        self,
        *,
        system_id: str,
        transport: ProjectionRpcTransport,
        timeout_seconds: float = 25.0,
        request_id_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("RPC timeout must be positive")
        self.system_id = system_id
        self.request_topic = projection_request_topic(system_id)
        self.result_topic = projection_result_topic(system_id)
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self._request_id_factory = request_id_factory or (lambda: uuid.uuid4().hex)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._dispatch_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._inflight: _InflightRequest | None = None
        self._started = False
        self.ignored_result_count = 0
        self.republish_count = 0
        self.disconnect_count = 0
        transport.set_callbacks(
            on_message=self._on_message,
            on_connect=self._on_connect,
            on_disconnect=self._on_disconnect,
        )

    @staticmethod
    def _retry(code: str, detail: str) -> AdapterDispatchResult:
        return AdapterDispatchResult(status="retry", code=code, detail=detail)

    def _ensure_started(self) -> None:
        with self._state_lock:
            if self._started:
                return
        self.transport.start()
        with self._state_lock:
            self._started = True

    def _publish_current(self, *, republish: bool) -> bool:
        with self._state_lock:
            inflight = self._inflight
            if inflight is None or inflight.completed.is_set():
                return False
            request = inflight.request
        published = self.transport.publish(
            topic=self.request_topic,
            payload=request.as_payload(),
            qos=1,
            retain=False,
        )
        if published:
            with self._state_lock:
                current = self._inflight
                if current is inflight:
                    current.publish_armed = True
                    if republish:
                        self.republish_count += 1
        return published

    def _on_connect(self) -> None:
        with self._state_lock:
            inflight = self._inflight
            should_republish = bool(
                inflight is not None
                and inflight.publish_armed
                and not inflight.completed.is_set()
            )
        if should_republish and not self._publish_current(republish=True):
            _LOGGER.warning("C06-B2 reconnect republish could not be acknowledged")

    def _on_disconnect(self) -> None:
        with self._state_lock:
            self.disconnect_count += 1

    def _on_message(self, topic: str, payload: bytes) -> None:
        with self._state_lock:
            inflight = self._inflight
        if inflight is None or inflight.completed.is_set():
            with self._state_lock:
                self.ignored_result_count += 1
            return
        try:
            result = parse_and_bind_projection_result(
                payload,
                expected_request=inflight.request,
                actual_topic=topic,
                expected_system_id=self.system_id,
            )
        except ProjectionProtocolError:
            with self._state_lock:
                self.ignored_result_count += 1
            return

        if result.status == "verified":
            dispatch_result = AdapterDispatchResult(
                status="verified",
                verified_projection_hash=result.projection_hash,
                verified_revision=result.revision,
                verified_idempotency_key=result.idempotency_key,
                monotonic_revision_enforced=result.monotonic_revision_enforced,
            )
        else:
            dispatch_result = AdapterDispatchResult(
                status=result.status,
                code=result.code,
                detail=result.detail,
                monotonic_revision_enforced=result.monotonic_revision_enforced,
            )
        with self._state_lock:
            if self._inflight is not inflight or inflight.completed.is_set():
                self.ignored_result_count += 1
                return
            inflight.result = dispatch_result
            inflight.completed.set()

    def dispatch(self, batch: ProjectionBatch) -> AdapterDispatchResult:
        """Publish one exact request and wait for its bound result."""

        with self._dispatch_lock:
            try:
                self._ensure_started()
            except Exception as exc:  # noqa: BLE001 - transport boundary is retryable
                return self._retry(
                    "mqtt_transport_start_failed",
                    f"{type(exc).__name__}: {exc}",
                )

            request = build_projection_request(
                batch=batch,
                system_id=self.system_id,
                request_id=self._request_id_factory(),
                sent_at=self._clock(),
            )
            inflight = _InflightRequest(
                request=request,
                completed=threading.Event(),
            )
            with self._state_lock:
                if self._inflight is not None:
                    return self._retry(
                        "mqtt_rpc_inflight_conflict",
                        "another projection request is already in flight",
                    )
                self._inflight = inflight

            try:
                if not self._publish_current(republish=False):
                    return self._retry(
                        "mqtt_publish_failed",
                        "projection request was not acknowledged by the MQTT client",
                    )
                deadline = time.monotonic() + self.timeout_seconds
                remaining = max(0.0, deadline - time.monotonic())
                if not inflight.completed.wait(remaining):
                    return self._retry(
                        "mqtt_rpc_timeout",
                        "no exact Home Assistant projection result arrived before timeout",
                    )
                return inflight.result or self._retry(
                    "mqtt_rpc_result_missing",
                    "projection completion was signalled without a result",
                )
            finally:
                with self._state_lock:
                    if self._inflight is inflight:
                        self._inflight = None

    def stop(self) -> None:
        with self._state_lock:
            self._started = False
            inflight = self._inflight
            if inflight is not None and not inflight.completed.is_set():
                inflight.result = self._retry(
                    "mqtt_transport_stopped",
                    "projection transport stopped while a request was pending",
                )
                inflight.completed.set()
        self.transport.stop()
