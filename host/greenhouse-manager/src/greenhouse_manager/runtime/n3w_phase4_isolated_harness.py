from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from .ingest import TelemetryProcessor
from .n3w_auto_node_id import AutomaticNodeIdApprover
from .n3w_canonical_ingress import N3wCanonicalIngressCoordinator
from .n3w_compact_relay import CompactRelayIngressCore, NodeApplicationKeyProvider
from .n3w_multi_ingress_router import MultiIngressResult, N3wMultiIngressRouter
from .registration import RegistrationRecord, RegistrationRegistry
from .replay_registry import ReplayRegistry


class Phase4IsolatedManagerHarness:
    """Compose only the simplified Phase 4 Manager path for an isolated lab.

    This adapter owns no network listener and mutates no Broker or production runtime.
    It exists so source/cloud CI can prove that a future isolated physical session can
    bind automatic NODE_ID allocation and Direct/Relay multi-ingress without PATH or
    finite gateway grants.
    """

    def __init__(
        self,
        *,
        system_id: str,
        registration: RegistrationRegistry,
        replay: ReplayRegistry,
        keys: NodeApplicationKeyProvider,
        ingress_allowed: Callable[[str], bool] | None = None,
        random_bytes: Callable[[int], bytes] | None = None,
        processor: TelemetryProcessor | None = None,
    ) -> None:
        approver_kwargs = {} if random_bytes is None else {"random_bytes": random_bytes}
        self.approver = AutomaticNodeIdApprover(registration, **approver_kwargs)
        self.processor = processor or TelemetryProcessor(system_id=system_id)
        canonical = N3wCanonicalIngressCoordinator(
            replay_registry=replay,
            ingress_allowed=ingress_allowed or (lambda _node_id: True),
        )
        relay_core = CompactRelayIngressCore(system_id=system_id, keys=keys)
        self.router = N3wMultiIngressRouter(
            processor=self.processor,
            canonical=canonical,
            relay_core=relay_core,
        )

    def approve_registration(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        logical_location_id: str | None = None,
        now: datetime | None = None,
    ) -> RegistrationRecord:
        return self.approver.approve(
            hardware_id,
            pairing_id,
            logical_location_id=logical_location_id,
            now=now,
        )

    def process_direct(
        self,
        topic: str,
        payload: bytes | str,
        *,
        received_at: datetime | None = None,
    ) -> MultiIngressResult:
        return self.router.process_direct(topic, payload, received_at=received_at)

    def process_relay(
        self,
        topic: str,
        payload: bytes | str,
        *,
        received_at: datetime | None = None,
    ) -> MultiIngressResult:
        return self.router.process_relay(topic, payload, received_at=received_at)