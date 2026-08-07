from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from .ingest import ProcessResult, PublishMessage, TelemetryProcessor
from .n3w_relay_ingress import N3wRelayIngressCore
from .replay_registry import ReplayRegistry, ReplayRegistryUnavailable

RouterStatus = Literal["accepted", "duplicate", "rejected"]
IngressSource = Literal["direct", "relay"]


@dataclass(frozen=True, slots=True)
class UnifiedIngressResult:
    status: RouterStatus
    source: IngressSource
    node_id: str | None
    messages: tuple[PublishMessage, ...] = ()
    code: str | None = None
    detail: str | None = None
    dedup_key: tuple[str, str, int] | None = None


class N3wManagerIngressRouter:
    """Non-live direct/relay ingress composition over one replay registry.

    The router contains no MQTT client and publishes nothing. Both paths perform
    complete canonical telemetry validation before the persistent replay/high-water
    transition. Canonical in-memory state is committed only after replay acceptance.
    """

    def __init__(
        self,
        *,
        processor: TelemetryProcessor,
        replay_registry: ReplayRegistry,
        relay_core: N3wRelayIngressCore,
    ) -> None:
        if processor.system_id != relay_core.system_id:
            raise ValueError("system_id_mismatch")
        if relay_core.replay_registry is not replay_registry:
            raise ValueError("replay_registry_must_be_shared")
        self.processor = processor
        self.replay_registry = replay_registry
        self.relay_core = relay_core
        self.system_id = processor.system_id
        self._lock = threading.RLock()

    @staticmethod
    def _from_process(source: IngressSource, result: ProcessResult) -> UnifiedIngressResult:
        return UnifiedIngressResult(
            status=result.status,
            source=source,
            node_id=result.node_id,
            messages=result.messages,
            code=(
                "canonical_duplicate"
                if result.status == "duplicate"
                else "canonical_validation_rejected"
                if result.status == "rejected"
                else None
            ),
            detail=result.reason,
            dedup_key=result.dedup_key,
        )

    def process_direct(
        self,
        topic: str,
        payload: bytes | str,
        *,
        received_at: datetime | None = None,
    ) -> UnifiedIngressResult:
        with self._lock:
            candidate = self.processor.prepare(topic, payload, received_at=received_at)
            if candidate.status != "accepted":
                return UnifiedIngressResult(
                    status=candidate.status,
                    source="direct",
                    node_id=candidate.node_id,
                    code=(
                        "canonical_duplicate"
                        if candidate.status == "duplicate"
                        else "canonical_validation_rejected"
                    ),
                    detail=candidate.reason,
                    dedup_key=candidate.dedup_key,
                )
            assert candidate.prepared is not None
            prepared = candidate.prepared

            try:
                replay = self.replay_registry.commit(
                    node_id=prepared.node_id,
                    boot_id=prepared.dedup_key[1],
                    seq=prepared.dedup_key[2],
                )
            except ReplayRegistryUnavailable:
                return UnifiedIngressResult(
                    status="rejected",
                    source="direct",
                    node_id=prepared.node_id,
                    code="replay_registry_unavailable",
                    dedup_key=prepared.dedup_key,
                )
            except ValueError as exc:
                return UnifiedIngressResult(
                    status="rejected",
                    source="direct",
                    node_id=prepared.node_id,
                    code=str(exc),
                    dedup_key=prepared.dedup_key,
                )

            if replay.status == "duplicate":
                return UnifiedIngressResult(
                    status="duplicate",
                    source="direct",
                    node_id=prepared.node_id,
                    code="duplicate_node_boot_seq",
                    dedup_key=prepared.dedup_key,
                )
            if replay.status == "stale_boot_session":
                return UnifiedIngressResult(
                    status="rejected",
                    source="direct",
                    node_id=prepared.node_id,
                    code="stale_boot_session",
                    dedup_key=prepared.dedup_key,
                )

            return self._from_process("direct", self.processor.commit_prepared(prepared))

    def process_relay(
        self,
        topic: str,
        payload: bytes | str,
        *,
        received_at: datetime | None = None,
    ) -> UnifiedIngressResult:
        with self._lock:
            relay = self.relay_core.prepare(topic, payload)
            if relay.status != "ready":
                return UnifiedIngressResult(
                    status="rejected",
                    source="relay",
                    node_id=relay.node_id,
                    code=relay.code,
                )
            assert relay.ingress_topic is not None
            assert relay.telemetry is not None
            assert relay.node_id is not None

            canonical = self.processor.prepare(
                relay.ingress_topic,
                json.dumps(relay.telemetry, separators=(",", ":"), sort_keys=True),
                received_at=received_at,
            )
            if canonical.status == "rejected":
                return UnifiedIngressResult(
                    status="rejected",
                    source="relay",
                    node_id=canonical.node_id or relay.node_id,
                    code="canonical_validation_rejected",
                    detail=canonical.reason,
                    dedup_key=canonical.dedup_key,
                )

            replay = self.relay_core.commit(relay)
            if replay.status == "duplicate":
                return UnifiedIngressResult(
                    status="duplicate",
                    source="relay",
                    node_id=relay.node_id,
                    code=replay.code,
                    dedup_key=canonical.dedup_key,
                )
            if replay.status == "rejected":
                return UnifiedIngressResult(
                    status="rejected",
                    source="relay",
                    node_id=relay.node_id,
                    code=replay.code,
                    dedup_key=canonical.dedup_key,
                )

            if canonical.status == "duplicate":
                return UnifiedIngressResult(
                    status="duplicate",
                    source="relay",
                    node_id=relay.node_id,
                    code="canonical_duplicate_reconciled",
                    detail=canonical.reason,
                    dedup_key=canonical.dedup_key,
                )

            assert canonical.prepared is not None
            return self._from_process(
                "relay",
                self.processor.commit_prepared(canonical.prepared),
            )
