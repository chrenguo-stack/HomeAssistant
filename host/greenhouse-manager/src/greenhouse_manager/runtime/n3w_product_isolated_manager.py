from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .n3w_ingress_router import N3wManagerIngressRouter, UnifiedIngressResult
from .n3w_product_peer_authorization import (
    PairAuthorization,
    PeerAuthorizationRequest,
    PeerAuthorizationService,
)


@dataclass(slots=True)
class N3wProductIsolatedManager:
    """Non-live S5 adapter over the existing Manager authorities.

    This object opens no socket, creates no MQTT client, and defines no second
    telemetry or authorization pipeline. Pair authorization delegates to the
    existing S4 ``PeerAuthorizationService`` and relay telemetry delegates to
    the existing unified N3-W ingress router.
    """

    peer_authorization: PeerAuthorizationService
    ingress_router: N3wManagerIngressRouter

    def __post_init__(self) -> None:
        manager_system = self.ingress_router.system_id
        authorization_system = self.peer_authorization.membership.system_id
        if manager_system != authorization_system:
            raise ValueError("system_id_mismatch")

    @property
    def system_id(self) -> str:
        return self.ingress_router.system_id

    def authorize_peer(
        self,
        request: PeerAuthorizationRequest,
        *,
        now_ms: int,
    ) -> PairAuthorization:
        return self.peer_authorization.authorize(request, now_ms=now_ms)

    def ingest_relay_frame(
        self,
        *,
        gateway_id: str,
        node_id: str,
        payload: bytes | str,
        received_at: datetime | None = None,
    ) -> UnifiedIngressResult:
        if not gateway_id or not node_id or "/" in gateway_id or "/" in node_id:
            raise ValueError("relay_identity_invalid")
        topic = (
            f"gh/v1/{self.system_id}/ingress/gateway/"
            f"{gateway_id}/{node_id}/frame"
        )
        return self.ingress_router.process_relay(
            topic,
            payload,
            received_at=received_at,
        )
