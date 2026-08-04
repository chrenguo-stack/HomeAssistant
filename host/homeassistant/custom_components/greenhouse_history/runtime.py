from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, ClassVar

from .const import request_topic, result_topic
from .entity_resolver import (
    EntityDescriptor,
    EntityResolutionError,
    EntityResolver,
)
from .ledger import (
    LedgerCapacityError,
    LedgerCorruptionError,
    LedgerError,
    ResolvedSeries,
    TargetLedger,
)
from .mqtt_bridge import MqttProjectionBridge
from .protocol import (
    ProjectionRequest,
    ProtocolError,
    ResultStatus,
    canonical_json,
    parse_request,
    result_document,
)
from .recorder_adapter import (
    HomeAssistantRecorderAdapter,
    RecorderAdapter,
    RecorderAdapterError,
    projection_writes,
    verify_readback,
)

Clock = Callable[[], datetime]
ResolverFactory = Callable[[], EntityResolver]


def _utc_text(clock: Clock) -> str:
    value = clock()
    if value.tzinfo is None:
        raise ValueError("runtime clock must return a timezone-aware timestamp")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace(
        "+00:00",
        "Z",
    )


class ProjectionRequestProcessor:
    """Monotonic ledger, entity resolution, Recorder import, and readback pipeline."""

    _BLOCKED_RECORDER_CODES: ClassVar[set[str]] = {
        "recorder_api_unavailable",
        "target_statistic_id_invalid",
        "target_statistic_shape_invalid",
        "target_timestamp_invalid",
        "target_unit_missing",
        "target_unit_mismatch",
    }

    def __init__(
        self,
        *,
        system_id: str,
        ledger: TargetLedger,
        resolver_factory: ResolverFactory,
        recorder: RecorderAdapter,
        clock: Clock | None = None,
    ) -> None:
        self.system_id = system_id
        self.ledger = ledger
        self.resolver_factory = resolver_factory
        self.recorder = recorder
        self.clock = clock or (lambda: datetime.now(UTC))
        self.request_topic = request_topic(system_id)

    @staticmethod
    def _payload(document: dict[str, Any]) -> bytes:
        return canonical_json(document).encode("utf-8")

    def _result(
        self,
        request: ProjectionRequest,
        *,
        status: ResultStatus,
        verified_at: str | None = None,
        code: str | None = None,
        detail: str | None = None,
    ) -> bytes:
        return self._payload(
            result_document(
                request=request,
                status=status,
                monotonic_revision_enforced=True,
                verified_at=verified_at,
                code=code,
                detail=detail[:512] if detail is not None else None,
            )
        )

    async def _record_failure(
        self,
        request: ProjectionRequest,
        *,
        reconciled_at: str,
        code: str,
    ) -> None:
        try:
            await self.ledger.async_record_failure(
                request,
                reconciled_at=reconciled_at,
                code=code,
            )
        except (LedgerError, OSError):
            return

    async def _reconcile(
        self,
        request: ProjectionRequest,
        *,
        reconciled_at: str,
    ) -> bytes:
        try:
            resolved = self.resolver_factory().resolve_projection(request.projection)
            writes = projection_writes(
                sample_hour=str(request.projection["sample_hour"]),
                resolved=resolved,
            )
            await self.recorder.async_import_statistics(writes)
            readback = await self.recorder.async_read_statistics(
                tuple(item.statistic_id for item in writes),
                start=str(request.projection["sample_hour"]),
            )
            verify_readback(writes, readback)
            verified = await self.ledger.async_mark_verified(
                request,
                verified_at=reconciled_at,
                resolved_series=tuple(
                    ResolvedSeries(
                        measurement_key=item.measurement_key,
                        entity_unique_id=item.entity_unique_id,
                        entity_id=item.entity_id,
                        unit_of_measurement=item.unit_of_measurement,
                        mean=item.mean,
                        minimum=item.minimum,
                        maximum=item.maximum,
                    )
                    for item in resolved
                ),
            )
            return self._result(
                request,
                status="verified",
                verified_at=verified.verified_at,
            )
        except EntityResolutionError as exc:
            code, detail, status = exc.code, exc.detail, "blocked"
        except RecorderAdapterError as exc:
            code, detail = exc.code, exc.detail
            status = "blocked" if code in self._BLOCKED_RECORDER_CODES else "retry"
        except (LedgerCapacityError, LedgerCorruptionError) as exc:
            code, detail, status = "target_ledger_failure", str(exc), "blocked"
        except OSError as exc:
            code = "target_ledger_persist_failed"
            detail = f"{type(exc).__name__}: {exc}"
            status = "retry"
        except LedgerError as exc:
            code, detail, status = "target_ledger_failure", str(exc), "retry"
        except Exception as exc:  # noqa: BLE001 - preserve a durable retry state
            code = "target_reconcile_failed"
            detail = f"{type(exc).__name__}: {exc}"
            status = "retry"

        await self._record_failure(
            request,
            reconciled_at=reconciled_at,
            code=code,
        )
        return self._result(
            request,
            status=status,
            code=code,
            detail=detail,
        )

    async def async_process(
        self,
        *,
        topic: str,
        payload: bytes,
        qos: int,
        retain: bool,
    ) -> bytes | None:
        if topic != self.request_topic:
            return None
        try:
            request = parse_request(payload, configured_system_id=self.system_id)
        except ProtocolError:
            return None

        if qos != 1:
            return self._result(
                request,
                status="retry",
                code="mqtt_qos_invalid",
                detail="projection requests require MQTT QoS 1",
            )
        if retain:
            return self._result(
                request,
                status="retry",
                code="mqtt_retained_request_rejected",
                detail="projection requests must use retain=false",
            )

        accepted_at = _utc_text(self.clock)
        try:
            decision = await self.ledger.async_prepare(
                request,
                accepted_at=accepted_at,
            )
        except (LedgerCapacityError, LedgerCorruptionError) as exc:
            return self._result(
                request,
                status="blocked",
                code="target_ledger_failure",
                detail=str(exc),
            )
        except OSError as exc:
            return self._result(
                request,
                status="retry",
                code="target_ledger_persist_failed",
                detail=f"{type(exc).__name__}: {exc}",
            )
        except LedgerError as exc:
            return self._result(
                request,
                status="retry",
                code="target_ledger_failure",
                detail=str(exc),
            )

        if decision.status == "verified":
            if decision.entry is None or decision.entry.verified_at is None:
                return self._result(
                    request,
                    status="blocked",
                    code="target_ledger_failure",
                    detail="verified ledger decision has no verified timestamp",
                )
            return self._result(
                request,
                status="verified",
                verified_at=decision.entry.verified_at,
            )
        if decision.status in {"retry", "blocked"}:
            return self._result(
                request,
                status=decision.status,
                code=decision.code,
                detail=decision.code.replace("_", " "),
            )
        return await self._reconcile(request, reconciled_at=accepted_at)


def homeassistant_entity_resolver(hass: Any) -> EntityResolver:
    """Build a resolver from the supported Home Assistant entity registry API."""

    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    descriptors: list[EntityDescriptor] = []
    for entry in registry.entities.values():
        if not isinstance(entry.unique_id, str) or not entry.unique_id:
            continue
        state = hass.states.get(entry.entity_id)
        attributes = {} if state is None else state.attributes
        descriptors.append(
            EntityDescriptor(
                entity_id=entry.entity_id,
                domain=entry.entity_id.split(".", 1)[0],
                platform=entry.platform,
                unique_id=entry.unique_id,
                disabled=entry.disabled_by is not None,
                unit_of_measurement=attributes.get("unit_of_measurement"),
                state_class=attributes.get("state_class"),
            )
        )
    return EntityResolver(descriptors)


class HomeAssistantProjectionRuntime:
    """Actual HA MQTT/Recorder wiring, constructed only after explicit opt-in."""

    def __init__(self, *, bridge: MqttProjectionBridge) -> None:
        self.bridge = bridge

    @property
    def active(self) -> bool:
        return self.bridge.active

    @classmethod
    def create(
        cls,
        *,
        hass: Any,
        system_id: str,
        ledger: TargetLedger,
        queue_capacity: int = 32,
    ) -> HomeAssistantProjectionRuntime:
        from homeassistant.components import mqtt

        processor = ProjectionRequestProcessor(
            system_id=system_id,
            ledger=ledger,
            resolver_factory=lambda: homeassistant_entity_resolver(hass),
            recorder=HomeAssistantRecorderAdapter(hass),
        )

        async def subscribe(topic: str, callback: Any, qos: int) -> Any:
            return await mqtt.async_subscribe(hass, topic, callback, qos)

        async def publish(
            topic: str,
            payload: bytes,
            qos: int,
            retain: bool,
        ) -> None:
            await mqtt.async_publish(
                hass,
                topic,
                payload,
                qos=qos,
                retain=retain,
            )

        return cls(
            bridge=MqttProjectionBridge(
                request_topic=request_topic(system_id),
                result_topic=result_topic(system_id),
                processor=processor,
                subscribe=subscribe,
                publish=publish,
                queue_capacity=queue_capacity,
            )
        )

    async def async_start(self) -> None:
        await self.bridge.async_start()

    async def async_stop(self) -> None:
        await self.bridge.async_stop()
