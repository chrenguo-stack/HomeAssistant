from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from .ingest import ProcessResult, PublishMessage, TelemetryProcessor
from .n3w_canonical_ingress import CanonicalIngressDecision, N3wCanonicalIngressCoordinator
from .n3w_compact_relay import CompactRelayIngressCore

RouterStatus = Literal["accepted", "duplicate", "rejected"]
IngressSource = Literal["direct", "relay"]


@dataclass(frozen=True, slots=True)
class MultiIngressResult:
    status: RouterStatus
    source: IngressSource
    node_id: str | None
    messages: tuple[PublishMessage, ...] = ()
    code: str | None = None
    detail: str | None = None
    gateway_id: str | None = None
    dedup_key: tuple[str, str, int] | None = None


class N3wMultiIngressRouter:
    """Direct/Relay Manager router with no PATH lease or path-owner state."""

    def __init__(
        self,
        *,
        processor: TelemetryProcessor,
        canonical: N3wCanonicalIngressCoordinator,
        relay_core: CompactRelayIngressCore,
    ) -> None:
        if processor.system_id != relay_core.system_id:
            raise ValueError("system_id_mismatch")
        self.processor = processor
        self.canonical = canonical
        self.relay_core = relay_core
        self.system_id = processor.system_id
        self._lock = threading.RLock()

    @staticmethod
    def _from_process(source: IngressSource, result: ProcessResult) -> MultiIngressResult:
        return MultiIngressResult(
            status=result.status,
            source=source,
            node_id=result.node_id,
            messages=result.messages,
            code=("canonical_duplicate" if result.status == "duplicate" else None),
            detail=result.reason,
            dedup_key=result.dedup_key,
        )

    @staticmethod
    def _from_canonical(
        decision: CanonicalIngressDecision,
        *,
        dedup_key: tuple[str, str, int],
    ) -> MultiIngressResult:
        return MultiIngressResult(
            status=decision.status,
            source=decision.source,
            node_id=decision.node_id,
            code=decision.code,
            gateway_id=decision.gateway_id,
            dedup_key=dedup_key,
        )

    def _canonical_decision(
        self,
        *,
        source: IngressSource,
        dedup_key: tuple[str, str, int],
        gateway_id: str | None,
        observed_at: datetime,
    ) -> CanonicalIngressDecision:
        return self.canonical.process(
            node_id=dedup_key[0],
            boot_id=dedup_key[1],
            seq=dedup_key[2],
            source=source,
            gateway_id=gateway_id,
            now=observed_at,
        )

    def process_direct(
        self,
        topic: str,
        payload: bytes | str,
        *,
        received_at: datetime | None = None,
    ) -> MultiIngressResult:
        with self._lock:
            observed_at = received_at or datetime.now(UTC)
            candidate = self.processor.prepare(topic, payload, received_at=observed_at)
            if candidate.status == "rejected":
                return MultiIngressResult(
                    status="rejected",
                    source="direct",
                    node_id=candidate.node_id,
                    code="canonical_validation_rejected",
                    detail=candidate.reason,
                    dedup_key=candidate.dedup_key,
                )
            assert candidate.dedup_key is not None
            decision = self._canonical_decision(
                source="direct",
                dedup_key=candidate.dedup_key,
                gateway_id=None,
                observed_at=observed_at,
            )
            if decision.status != "accepted":
                return self._from_canonical(decision, dedup_key=candidate.dedup_key)
            if candidate.status == "duplicate":
                return MultiIngressResult(
                    status="duplicate",
                    source="direct",
                    node_id=candidate.node_id,
                    code="canonical_duplicate_reconciled",
                    detail=candidate.reason,
                    dedup_key=candidate.dedup_key,
                )
            assert candidate.prepared is not None
            return self._from_process("direct", self.processor.commit_prepared(candidate.prepared))

    def process_relay(
        self,
        topic: str,
        payload: bytes | str,
        *,
        received_at: datetime | None = None,
    ) -> MultiIngressResult:
        with self._lock:
            observed_at = received_at or datetime.now(UTC)
            relay = self.relay_core.prepare(topic, payload)
            if relay.status != "ready":
                return MultiIngressResult(
                    status="rejected",
                    source="relay",
                    node_id=relay.node_id,
                    code=relay.code,
                    gateway_id=relay.gateway_id,
                )
            assert relay.ingress_topic is not None
            assert relay.telemetry is not None
            assert relay.node_id is not None
            canonical = self.processor.prepare(
                relay.ingress_topic,
                json.dumps(relay.telemetry, separators=(",", ":"), sort_keys=True),
                received_at=observed_at,
            )
            if canonical.status == "rejected":
                return MultiIngressResult(
                    status="rejected",
                    source="relay",
                    node_id=canonical.node_id or relay.node_id,
                    code="canonical_validation_rejected",
                    detail=canonical.reason,
                    gateway_id=relay.gateway_id,
                    dedup_key=canonical.dedup_key,
                )
            assert canonical.dedup_key is not None
            decision = self._canonical_decision(
                source="relay",
                dedup_key=canonical.dedup_key,
                gateway_id=relay.gateway_id,
                observed_at=observed_at,
            )
            if decision.status != "accepted":
                return self._from_canonical(decision, dedup_key=canonical.dedup_key)
            if canonical.status == "duplicate":
                return MultiIngressResult(
                    status="duplicate",
                    source="relay",
                    node_id=relay.node_id,
                    code="canonical_duplicate_reconciled",
                    detail=canonical.reason,
                    gateway_id=relay.gateway_id,
                    dedup_key=canonical.dedup_key,
                )
            assert canonical.prepared is not None
            result = self.processor.commit_prepared(canonical.prepared)
            converted = self._from_process("relay", result)
            return MultiIngressResult(
                status=converted.status,
                source=converted.source,
                node_id=converted.node_id,
                messages=converted.messages,
                code=converted.code,
                detail=converted.detail,
                gateway_id=relay.gateway_id,
                dedup_key=converted.dedup_key,
            )
