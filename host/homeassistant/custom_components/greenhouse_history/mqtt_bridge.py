from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from .const import C06B2_MAX_REQUEST_BYTES, C06B2_MQTT_QUEUE_CAPACITY

_LOGGER = logging.getLogger(__name__)


class ProjectionMessageProcessor(Protocol):
    async def async_process(
        self,
        *,
        topic: str,
        payload: bytes,
        qos: int,
        retain: bool,
    ) -> bytes | None: ...


SubscribeCallback = Callable[[Any], None]
UnsubscribeCallback = Callable[[], Any]
SubscribeCallable = Callable[
    [str, SubscribeCallback, int],
    Awaitable[UnsubscribeCallback],
]
PublishCallable = Callable[[str, bytes, int, bool], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class InboundProjectionMessage:
    topic: str
    payload: bytes
    qos: int
    retain: bool


@dataclass(slots=True)
class BridgeHealth:
    enqueued: int = 0
    processed: int = 0
    published: int = 0
    dropped_queue_full: int = 0
    invalid_envelope: int = 0
    oversized_payload: int = 0
    processing_failures: int = 0


class MqttProjectionBridge:
    """Bounded Home Assistant MQTT bridge with one non-callback worker."""

    def __init__(
        self,
        *,
        request_topic: str,
        result_topic: str,
        processor: ProjectionMessageProcessor,
        subscribe: SubscribeCallable,
        publish: PublishCallable,
        queue_capacity: int = C06B2_MQTT_QUEUE_CAPACITY,
        max_payload_bytes: int = C06B2_MAX_REQUEST_BYTES,
    ) -> None:
        if queue_capacity < 1:
            raise ValueError("MQTT bridge queue capacity must be positive")
        if max_payload_bytes < 1:
            raise ValueError("MQTT bridge payload bound must be positive")
        self.request_topic = request_topic
        self.result_topic = result_topic
        self.processor = processor
        self.max_payload_bytes = max_payload_bytes
        self._subscribe = subscribe
        self._publish = publish
        self._queue: asyncio.Queue[InboundProjectionMessage] = asyncio.Queue(
            maxsize=queue_capacity
        )
        self._worker: asyncio.Task[None] | None = None
        self._unsubscribe: UnsubscribeCallback | None = None
        self.health = BridgeHealth()

    @property
    def active(self) -> bool:
        return bool(
            self._worker
            and not self._worker.done()
            and self._unsubscribe is not None
        )

    def _message_envelope(self, message: Any) -> InboundProjectionMessage:
        topic = getattr(message, "topic", None)
        payload = getattr(message, "payload", None)
        qos = getattr(message, "qos", 1)
        retain = getattr(message, "retain", False)
        if not isinstance(topic, str):
            raise TypeError("MQTT message topic is invalid")
        try:
            if len(payload) > self.max_payload_bytes:
                raise OverflowError("MQTT request payload exceeds the configured bound")
        except TypeError as exc:
            raise TypeError("MQTT message payload is invalid") from exc
        if isinstance(payload, str):
            payload_bytes = payload.encode("utf-8")
        elif isinstance(payload, bytes):
            payload_bytes = payload
        else:
            try:
                payload_bytes = bytes(payload)
            except (TypeError, ValueError) as exc:
                raise TypeError("MQTT message payload is invalid") from exc
        if len(payload_bytes) > self.max_payload_bytes:
            raise OverflowError("MQTT request payload exceeds the configured bound")
        if type(qos) is not int:
            raise TypeError("MQTT message QoS is invalid")
        return InboundProjectionMessage(topic, payload_bytes, qos, bool(retain))

    def _on_message(self, message: Any) -> None:
        """Copy one envelope only; never touch Recorder or the target ledger."""

        try:
            envelope = self._message_envelope(message)
        except OverflowError:
            self.health.oversized_payload += 1
            return
        except TypeError:
            self.health.invalid_envelope += 1
            return
        try:
            self._queue.put_nowait(envelope)
        except asyncio.QueueFull:
            self.health.dropped_queue_full += 1
            return
        self.health.enqueued += 1

    async def _run_worker(self) -> None:
        while True:
            envelope = await self._queue.get()
            try:
                payload = await self.processor.async_process(
                    topic=envelope.topic,
                    payload=envelope.payload,
                    qos=envelope.qos,
                    retain=envelope.retain,
                )
                self.health.processed += 1
                if payload is not None:
                    await self._publish(self.result_topic, payload, 1, False)
                    self.health.published += 1
            except asyncio.CancelledError:
                raise
            except Exception:
                self.health.processing_failures += 1
                _LOGGER.exception("C06-B2 Home Assistant projection worker failed")
            finally:
                self._queue.task_done()

    async def async_start(self) -> None:
        if self.active:
            return
        if self._worker is not None or self._unsubscribe is not None:
            raise RuntimeError(
                "MQTT projection bridge is in an inconsistent lifecycle state"
            )
        self._worker = asyncio.create_task(
            self._run_worker(),
            name="greenhouse-history-projection-worker",
        )
        try:
            self._unsubscribe = await self._subscribe(
                self.request_topic,
                self._on_message,
                1,
            )
        except Exception:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)
            self._worker = None
            raise

    async def async_stop(self) -> None:
        unsubscribe = self._unsubscribe
        self._unsubscribe = None
        if unsubscribe is not None:
            result = unsubscribe()
            if inspect.isawaitable(result):
                await result

        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)

        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                self._queue.task_done()
