from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from .ingest import ProcessResult, PublishMessage, TelemetryProcessor
from .n3w_path_lease import N3wPathLeaseCoordinator, PathLeaseDecision, PathOwner
from .n3w_relay_ingress import N3wRelayIngressCore, parse_relay_topic
from .replay_registry import ReplayRegistry

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
    """Non-live Direct/Relay composition over one replay/path transaction boundary.

    The router contains no MQTT client and publishes nothing. Both ingress paths
    complete canonical validation before the persistent path-lease/replay/cursor
    transition. Canonical in-memory state is committed only after that transaction
    accepts the frame.
    """

    def __init__(
        self,
        *,
        processor: TelemetryProcessor,
        replay_registry: ReplayRegistry,
        relay_core: N3wRelayIngressCore,
        path_lease: N3wPathLeaseCoordinator,
    ) -> None:
        if processor.system_id != relay_core.system_id:
            raise ValueError("system_id_mismatch")
        if relay_core.replay_registry is not replay_registry:
            raise ValueError("replay_registry_must_be_shared")
        if path_lease.replay_registry is not replay_registry:
            raise ValueError("path_lease_replay_registry_must_be_shared")
        self.processor = processor
        self.replay_registry = replay_registry
        self.relay_core = relay_core
        self.path_lease = path_lease
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

    @staticmethod
    def _from_path(
        source: IngressSource,
        decision: PathLeaseDecision,
        *,
        dedup_key: tuple[str, str, int] | None,
    ) -> UnifiedIngressResult:
        return UnifiedIngressResult(
            status=decision.status,
            source=source,
            node_id=decision.node_id,
            code=decision.code,
            dedup_key=dedup_key,
        )

    def _commit_path(
        self,
        *,
        owner: PathOwner,
        dedup_key: tuple[str, str, int],
        observed_at: datetime,
    ) -> PathLeaseDecision:
        return self.path_lease.process(
            node_id=dedup_key[0],
            boot_id=dedup_key[1],
            seq=dedup_key[2],
            owner=owner,
            now=observed_at,
        )

    def process_direct(
        self,
        topic: str,
        payload: bytes | str,
        *,
        received_at: datetime | None = None,
    ) -> UnifiedIngressResult:
        with self._lock:
            observed_at = received_at or datetime.now(UTC)
            candidate = self.processor.prepare(topic, payload, received_at=observed_at)
            if candidate.status == "rejected":
                return UnifiedIngressResult(
                    status="rejected",
                    source="direct",
                    node_id=candidate.node_id,
                    code="canonical_validation_rejected",
                    detail=candidate.reason,
                    dedup_key=candidate.dedup_key,
                )
            assert candidate.dedup_key is not None
            path = self._commit_path(
                owner=PathOwner("direct"),
                dedup_key=candidate.dedup_key,
                observed_at=observed_at,
            )
            if path.status == "rejected":
                return self._from_path("direct", path, dedup_key=candidate.dedup_key)
            if path.status == "duplicate":
                return self._from_path("direct", path, dedup_key=candidate.dedup_key)
            if candidate.status == "duplicate":
                return UnifiedIngressResult(
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
    ) -> UnifiedIngressResult:
        with self._lock:
            observed_at = received_at or datetime.now(UTC)
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
                received_at=observed_at,
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
            assert canonical.dedup_key is not None
            gateway_id = parse_relay_topic(topic).gateway_id
            path = self._commit_path(
                owner=PathOwner("relay", gateway_id),
                dedup_key=canonical.dedup_key,
                observed_at=observed_at,
            )
            if path.status == "rejected":
                return self._from_path("relay", path, dedup_key=canonical.dedup_key)
            if path.status == "duplicate":
                return self._from_path("relay", path, dedup_key=canonical.dedup_key)
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
