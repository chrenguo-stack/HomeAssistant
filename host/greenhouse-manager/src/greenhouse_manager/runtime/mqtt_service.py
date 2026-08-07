from __future__ import annotations

import json
import logging
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt

from .config import Settings
from .ha_discovery import HomeAssistantDiscovery
from .history_replay import HistoryReplayProcessor, HistoryReplayResult
from .history_store import HistoryStore
from .history_worker import HistoryReplayWorker, HistoryWorkItem
from .ingest import PublishMessage, TelemetryProcessor
from .pairing_intake import (
    PAIRING_HELLO_SUBSCRIPTION,
    PairingHelloProcessor,
    redacted_hardware_id,
    redacted_pairing_id,
)
from .registration import NodeIdLeaseState, RegistrationRegistry
from .topics import (
    canonical_telemetry_subscription,
    diagnostic_topic,
    history_replay_subscription,
    ingress_subscription,
    parse_canonical_telemetry_topic,
    parse_history_replay_topic,
    parse_node_telemetry_topic,
)

_LOGGER = logging.getLogger(__name__)


def _payload_bytes(payload: dict[str, Any] | bytes | str) -> bytes:
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _now_text() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class ManagerMqttService:
    def __init__(self, settings: Settings) -> None:
        settings.validate()
        self.settings = settings
        self._lifecycle_lock = threading.RLock()
        self.processor = TelemetryProcessor(
            system_id=settings.system_id,
            dedup_capacity=settings.dedup_capacity,
            stale_after_s=settings.stale_after_s,
        )
        self.discovery = HomeAssistantDiscovery(
            system_id=settings.system_id,
            prefix=settings.ha_discovery_prefix,
            device_name_prefix=settings.ha_device_name_prefix,
            enabled=settings.ha_discovery_enabled,
        )
        self.registration_registry: RegistrationRegistry | None = None
        self.pairing_processor: PairingHelloProcessor | None = None
        registration_path = Path(settings.pairing_db_path)
        if settings.pairing_intake_enabled or registration_path.exists():
            self.registration_registry = RegistrationRegistry(
                registration_path,
                pending_ttl_s=settings.pairing_pending_ttl_s,
            )
        if settings.pairing_intake_enabled:
            assert self.registration_registry is not None
            self.pairing_processor = PairingHelloProcessor(self.registration_registry)

        self.history_store: HistoryStore | None = None
        self.history_processor: HistoryReplayProcessor | None = None
        self.history_worker: HistoryReplayWorker | None = None
        if settings.history_replay_enabled:
            self.history_store = HistoryStore(
                settings.history_db_path,
                retention_days=settings.history_retention_days,
                max_records=settings.history_max_records,
                max_db_bytes=settings.history_max_db_bytes,
            )
            self.history_processor = HistoryReplayProcessor(
                system_id=settings.system_id,
                store=self.history_store,
                retention_days=settings.history_retention_days,
                max_future_skew_s=settings.history_max_future_skew_s,
                max_records_per_page=settings.history_max_records_per_page,
                max_payload_bytes=settings.history_max_payload_bytes,
            )
            self.history_worker = HistoryReplayWorker(
                processor=self.history_processor,
                on_result=self._handle_history_result,
                queue_capacity=settings.history_queue_capacity,
                max_pages_per_minute=settings.history_max_pages_per_minute,
                rate_state_capacity=settings.history_rate_state_capacity,
                rate_state_ttl_s=settings.history_rate_state_ttl_s,
                prune_interval_s=settings.history_prune_interval_s,
            )

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt_client_id,
            protocol=mqtt.MQTTv5,
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=15)
        self.client.enable_logger(_LOGGER)

        if settings.mqtt_username and settings.mqtt_password:
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        if settings.mqtt_tls:
            self.client.tls_set(ca_certs=settings.mqtt_ca_file)

    def _publish(
        self,
        message: PublishMessage,
        *,
        wait_for_ack: bool = False,
    ) -> bool:
        info = self.client.publish(
            message.topic,
            payload=_payload_bytes(message.payload),
            qos=message.qos,
            retain=message.retain,
        )
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            _LOGGER.error("MQTT publish failed topic=%s rc=%s", message.topic, info.rc)
            return False
        if wait_for_ack:
            try:
                info.wait_for_publish(timeout=10)
            except (RuntimeError, ValueError) as error:
                _LOGGER.error(
                    "MQTT publish acknowledgement failed topic=%s error=%s",
                    message.topic,
                    type(error).__name__,
                )
                return False
            is_published = getattr(info, "is_published", None)
            if callable(is_published) and not is_published():
                _LOGGER.error(
                    "MQTT publish acknowledgement timed out topic=%s",
                    message.topic,
                )
                return False
        return True

    def _publish_discovery(self, document: dict[str, Any]) -> None:
        with self._lifecycle_lock:
            messages = self.discovery.messages_for_telemetry(document)
        for outgoing in messages:
            self._publish(outgoing)
            _LOGGER.info(
                "Published Home Assistant discovery node=%s topic=%s",
                document.get("node_id"),
                outgoing.topic,
            )

    def _process_retirement_jobs(self) -> None:
        if self.registration_registry is None:
            return
        for job in self.registration_registry.list_retirement_jobs(
            ready_for_runtime_cleanup_only=True
        ):
            with self._lifecycle_lock:
                messages = (
                    *self.discovery.retirement_messages(job.node_id),
                    *self.processor.retirement_messages(job.node_id),
                )
            if not all(
                self._publish(message, wait_for_ack=True) for message in messages
            ):
                self.registration_registry.record_retirement_failure(
                    job.retirement_id,
                    "mqtt_tombstone_publish_failed",
                )
                _LOGGER.warning(
                    "Deferred node retirement cleanup retirement_id=%d node=%s",
                    job.retirement_id,
                    job.node_id,
                )
                continue
            with self._lifecycle_lock:
                self.processor.clear_node_state(job.node_id)
                self.discovery.clear_node_cache(job.node_id)
            completed = self.registration_registry.mark_runtime_cleanup_complete(
                job.retirement_id
            )
            _LOGGER.info(
                "Completed runtime retirement cleanup retirement_id=%d node=%s state=%s",
                completed.retirement_id,
                completed.node_id,
                completed.state,
            )

    def _publish_diagnostic(self, node_id: str, reason: str) -> None:
        self._publish(
            PublishMessage(
                topic=diagnostic_topic(self.settings.system_id, node_id),
                payload={
                    "schema": "gh.diagnostic/1",
                    "node_id": node_id,
                    "state": "invalid_telemetry",
                    "message": reason[:512],
                    "updated_at": _now_text(),
                },
            )
        )

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        if reason_code.is_failure:
            _LOGGER.error("MQTT connection rejected: %s", reason_code)
            return

        topics = [
            ingress_subscription(self.settings.system_id),
            canonical_telemetry_subscription(self.settings.system_id),
        ]
        if self.history_processor is not None:
            topics.append(history_replay_subscription(self.settings.system_id))
        if self.pairing_processor is not None:
            topics.append(PAIRING_HELLO_SUBSCRIPTION)
        for topic in topics:
            result, _mid = client.subscribe(topic, qos=1)
            if result != mqtt.MQTT_ERR_SUCCESS:
                _LOGGER.error("MQTT subscribe failed topic=%s rc=%s", topic, result)
                continue
            _LOGGER.info("Subscribed to %s", topic)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        if reason_code.is_failure:
            _LOGGER.warning("Unexpected MQTT disconnect: %s", reason_code)
        else:
            _LOGGER.info("MQTT disconnected")

    def _handle_history_result(self, result: HistoryReplayResult) -> None:
        for outgoing in result.messages:
            self._publish(outgoing)
        if result.status in {"accepted", "duplicate"}:
            _LOGGER.info(
                "History replay status=%s node=%s batch=%s page=%s",
                result.status,
                result.node_id,
                result.batch_id,
                result.page_index,
            )
        elif result.status == "retry":
            _LOGGER.error(
                "Deferred history replay without ACK node=%s batch=%s page=%s reason=%s",
                result.node_id,
                result.batch_id,
                result.page_index,
                result.reason,
            )
        else:
            _LOGGER.warning(
                "Rejected history replay node=%s batch=%s page=%s reason=%s",
                result.node_id,
                result.batch_id,
                result.page_index,
                result.reason,
            )

    def _on_history_message(self, message: mqtt.MQTTMessage) -> bool:
        if self.history_worker is None:
            return False
        try:
            history_topic = parse_history_replay_topic(message.topic)
        except ValueError:
            return False

        payload = message.payload
        try:
            payload_size = len(payload)
        except TypeError:
            _LOGGER.warning(
                "Deferred history replay without ACK node=%s reason=invalid_payload",
                history_topic.node_id,
            )
            return True
        if payload_size > self.settings.history_max_payload_bytes:
            _LOGGER.warning(
                "Deferred history replay without ACK node=%s reason=payload_too_large",
                history_topic.node_id,
            )
            return True

        qos = getattr(message, "qos", 1)
        if type(qos) is int and qos != 1:
            _LOGGER.warning(
                "Deferred history replay without ACK node=%s reason=qos_must_be_1",
                history_topic.node_id,
            )
            return True

        try:
            payload_bytes = payload if isinstance(payload, bytes) else bytes(payload)
        except (TypeError, ValueError):
            _LOGGER.warning(
                "Deferred history replay without ACK node=%s reason=invalid_payload",
                history_topic.node_id,
            )
            return True

        node_allowed = True
        if self.registration_registry is not None:
            node_allowed = (
                self.registration_registry.node_id_lease_state(history_topic.node_id)
                is NodeIdLeaseState.ACTIVE
            )
        status = self.history_worker.submit(
            HistoryWorkItem(
                node_id=history_topic.node_id,
                topic=message.topic,
                payload=payload_bytes,
                retained=bool(message.retain),
                node_allowed=node_allowed,
                received_at=datetime.now(UTC),
            )
        )
        if status != "queued":
            _LOGGER.warning(
                "Deferred history replay without ACK node=%s reason=%s",
                history_topic.node_id,
                status,
            )
        return True

    def _on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        if self.pairing_processor is not None and message.topic.startswith("gh/bootstrap/v1/node/"):
            result = self.pairing_processor.process(message.topic, message.payload)
            log_values = (
                result.status,
                redacted_hardware_id(result.hardware_id),
                redacted_pairing_id(result.pairing_id),
                result.state,
            )
            if result.status in {"created", "duplicate", "superseded"}:
                _LOGGER.info(
                    "Pairing hello status=%s hardware_suffix=%s pairing_prefix=%s state=%s",
                    *log_values,
                )
            else:
                _LOGGER.warning(
                    "Rejected pairing hello reason=%s hardware_suffix=%s pairing_prefix=%s",
                    result.reason,
                    redacted_hardware_id(result.hardware_id),
                    redacted_pairing_id(result.pairing_id),
                )
            return

        if self._on_history_message(message):
            return

        canonical_prefix = f"gh/v1/{self.settings.system_id}/state/"
        if message.topic.startswith(canonical_prefix) and message.topic.endswith("/telemetry"):
            try:
                canonical = parse_canonical_telemetry_topic(message.topic)
            except ValueError:
                canonical = None
            if not message.payload:
                if canonical is not None:
                    with self._lifecycle_lock:
                        self.processor.clear_node_state(canonical.node_id)
                        self.discovery.clear_node_cache(canonical.node_id)
                return
            if (
                canonical is not None
                and self.registration_registry is not None
                and not self.registration_registry.is_node_id_ingress_allowed(
                    canonical.node_id
                )
            ):
                with self._lifecycle_lock:
                    self.processor.clear_node_state(canonical.node_id)
                    self.discovery.clear_node_cache(canonical.node_id)
                _LOGGER.warning(
                    "Ignored retained canonical state for retired or unassigned node=%s",
                    canonical.node_id,
                )
                return
            with self._lifecycle_lock:
                restored = self.processor.restore_canonical(message.topic, message.payload)
            if restored.status == "restored":
                _LOGGER.debug(
                    "Restored canonical telemetry node=%s key=%s last_seen=%s",
                    restored.node_id,
                    restored.dedup_key,
                    restored.last_seen,
                )
                try:
                    document = json.loads(message.payload.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    document = None
                if isinstance(document, dict):
                    self._publish_discovery(document)
            else:
                _LOGGER.warning(
                    "Rejected canonical telemetry recovery node=%s reason=%s",
                    restored.node_id,
                    restored.reason,
                )
            return

        if self.registration_registry is not None:
            try:
                ingress = parse_node_telemetry_topic(message.topic)
            except ValueError:
                ingress = None
            if (
                ingress is not None
                and not self.registration_registry.is_node_id_ingress_allowed(
                    ingress.node_id
                )
            ):
                _LOGGER.warning(
                    "Rejected telemetry for retired or unassigned node=%s",
                    ingress.node_id,
                )
                return

        with self._lifecycle_lock:
            result = self.processor.process(message.topic, message.payload)

        if result.status == "accepted":
            canonical_document: dict[str, Any] | None = None
            for outgoing in result.messages:
                self._publish(outgoing)
                if outgoing.topic.endswith("/telemetry"):
                    canonical_document = outgoing.payload
            if canonical_document is not None:
                self._publish_discovery(canonical_document)
            _LOGGER.info("Accepted telemetry node=%s key=%s", result.node_id, result.dedup_key)
            return

        if result.status == "duplicate":
            _LOGGER.debug("Ignored duplicate telemetry node=%s key=%s", result.node_id, result.dedup_key)
            return

        _LOGGER.warning("Rejected telemetry node=%s reason=%s", result.node_id, result.reason)
        if result.node_id:
            self._publish_diagnostic(result.node_id, result.reason or "unknown validation error")

    def run(self) -> None:
        _LOGGER.info(
            "Starting greenhouse-manager system_id=%s broker=%s:%d "
            "ha_discovery=%s pairing_intake=%s history_replay=%s",
            self.settings.system_id,
            self.settings.mqtt_host,
            self.settings.mqtt_port,
            self.settings.ha_discovery_enabled,
            self.settings.pairing_intake_enabled,
            self.settings.history_replay_enabled,
        )
        loop_started = False
        try:
            if self.history_worker is not None:
                self.history_worker.start()
            self.client.connect(
                self.settings.mqtt_host,
                self.settings.mqtt_port,
                keepalive=60,
            )
            self.client.loop_start()
            loop_started = True
            while True:
                time.sleep(5)
                if self.history_worker is not None and not self.history_worker.is_alive:
                    health = self.history_worker.health
                    _LOGGER.error(
                        "C-06 history worker stopped; restarting failures=%d "
                        "last_stage=%s last_type=%s",
                        health.failure_count,
                        health.last_failure_stage,
                        health.last_failure_type,
                    )
                    self.history_worker.start()
                if self.pairing_processor is not None:
                    expired = self.pairing_processor.expire_pending()
                    if expired:
                        _LOGGER.info("Expired pairing registrations count=%d", expired)
                self._process_retirement_jobs()
                with self._lifecycle_lock:
                    stale_messages = self.processor.stale_messages()
                for message in stale_messages:
                    if self._publish(message):
                        _LOGGER.info("Published unavailable state topic=%s", message.topic)
                        continue

                    node_id = message.payload.get("node_id")
                    if isinstance(node_id, str):
                        with self._lifecycle_lock:
                            self.processor.mark_unavailable_publish_failed(node_id)
                    _LOGGER.warning("Deferred unavailable state topic=%s; will retry", message.topic)
        except KeyboardInterrupt:
            _LOGGER.info("Stopping greenhouse-manager")
        finally:
            self.client.disconnect()
            if loop_started:
                self.client.loop_stop()
            if self.history_worker is not None:
                self.history_worker.stop()
            if self.history_store is not None:
                self.history_store.close()
            if self.registration_registry is not None:
                self.registration_registry.close()
