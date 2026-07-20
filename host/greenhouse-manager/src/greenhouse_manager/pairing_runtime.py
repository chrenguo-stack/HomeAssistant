from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .pairing_discovery import (
    SECURE_PAIRING_PROTOCOL,
    ManagerCandidate,
    MdnsAdvertiser,
    PairingUDPServer,
    build_mdns_service_definition,
)
from .pairing_endpoint import (
    PairingEndpointApp,
    PendingOfferRegistry,
    make_pairing_http_server,
)
from .pairing_network_service import PairingNetworkService
from .pairing_runtime_config import PairingRuntimeSettings
from .pairing_secure_transport import (
    SecurePairingCoordinator,
    SecurePairingOffer,
)
from .pairing_service import NodeIdentityProvisioner, PairingSessionManager
from .registration import RegistrationRegistry

_LOGGER = logging.getLogger(__name__)


class PairingRuntimeError(RuntimeError):
    pass


class PairingRuntimeDisabled(PairingRuntimeError):
    pass


class PairingAdvertiserFactory(Protocol):
    def __call__(self, definition: Any) -> MdnsAdvertiser: ...


@dataclass(frozen=True, slots=True)
class PairingRuntimeSnapshot:
    schema: str
    started: bool
    closed: bool
    pairing_service_enabled: bool
    http_address: tuple[str, int] | None
    udp_address: tuple[str, int] | None
    secret_values_included: bool


@dataclass(slots=True)
class PairingRuntimeComponents:
    registration_registry: RegistrationRegistry
    session_manager: PairingSessionManager
    secure_coordinator: SecurePairingCoordinator
    pending_offers: PendingOfferRegistry
    endpoint_app: PairingEndpointApp
    network_service: PairingNetworkService


class PairingRuntime:
    def __init__(
        self,
        settings: PairingRuntimeSettings,
        components: PairingRuntimeComponents,
    ) -> None:
        self.settings = settings
        self.components = components
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._started = False
        self._closed = False

    def start(self) -> PairingRuntimeSnapshot:
        with self._lock:
            if self._closed:
                raise PairingRuntimeError("pairing runtime is closed")
            if self._started:
                return self.snapshot()
            self.components.network_service.start()
            self._started = True
            return self.snapshot()

    def run(self) -> None:
        self.start()
        try:
            while not self._stop_event.wait(self.settings.expiry_poll_s):
                self.expire()
        finally:
            self.close()

    def request_stop(self) -> None:
        self._stop_event.set()

    def expire(self, *, now: datetime | None = None) -> dict[str, int]:
        observed_at = now or datetime.now(UTC)
        secure_expired = self.components.secure_coordinator.expire_sessions(
            now=observed_at
        )
        registration_expired = (
            self.components.registration_registry.expire_pending(
                now=observed_at
            )
        )
        if secure_expired or registration_expired:
            _LOGGER.info(
                "Pairing expiry secure=%d registration=%d",
                secure_expired,
                registration_expired,
            )
        return {
            "secure_sessions": secure_expired,
            "registrations": registration_expired,
        }

    def import_scanned_pairing(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        pairing_secret: str,
        now: datetime | None = None,
    ) -> SecurePairingOffer:
        if not self._started:
            raise PairingRuntimeError(
                "pairing runtime must be started before QR import"
            )
        return self.components.pending_offers.import_scanned_pairing(
            hardware_id,
            pairing_id,
            pairing_secret=pairing_secret,
            now=now,
        )

    def close(self) -> PairingRuntimeSnapshot:
        with self._lock:
            if self._closed:
                return self.snapshot()
            self._stop_event.set()
            try:
                self.components.network_service.close()
            finally:
                self.components.registration_registry.close()
                self._started = False
                self._closed = True
            return self.snapshot()

    def snapshot(self) -> PairingRuntimeSnapshot:
        with self._lock:
            network = self.components.network_service.snapshot()
            return PairingRuntimeSnapshot(
                schema="gh.pair.runtime-status/1",
                started=self._started,
                closed=self._closed,
                pairing_service_enabled=self.settings.enabled,
                http_address=network.http_address,
                udp_address=network.udp_address,
                secret_values_included=False,
            )


def assemble_pairing_runtime(
    settings: PairingRuntimeSettings,
    provisioner: NodeIdentityProvisioner,
    *,
    advertiser_factory: PairingAdvertiserFactory | None = None,
) -> PairingRuntime:
    if not settings.enabled:
        raise PairingRuntimeDisabled(
            "pairing service is disabled by configuration"
        )
    settings.validate(enforce_deployment_contract=False)

    registry: RegistrationRegistry | None = None
    http_server: Any = None
    udp_server: Any = None
    advertiser: MdnsAdvertiser | None = None
    try:
        database = Path(settings.registration_db_path)
        database.parent.mkdir(parents=True, exist_ok=True)
        registry = RegistrationRegistry(
            database,
            pending_ttl_s=settings.registration_pending_ttl_s,
        )
        session_manager = PairingSessionManager(
            registry,
            provisioner,
            system_id=settings.system_id,
            broker_host=settings.broker_host,
            broker_port=settings.broker_port,
            ca_pem=settings.read_broker_ca_pem(),
            broker_tls_server_name=settings.broker_tls_server_name,
            session_ttl_s=settings.session_ttl_s,
            max_proof_attempts=settings.max_proof_attempts,
        )
        coordinator = SecurePairingCoordinator(session_manager)
        pending = PendingOfferRegistry(
            coordinator,
            manager_id=settings.manager_id,
        )
        endpoint_app = PairingEndpointApp(pending)
        http_server = make_pairing_http_server(
            (settings.bind_host, settings.http_port),
            app=endpoint_app,
        )
        actual_http_port = int(http_server.server_address[1])
        candidate = ManagerCandidate(
            schema="gh.manager.candidate/1",
            manager_id=settings.manager_id,
            system_id=settings.system_id,
            host=settings.advertised_host,
            scheme="http",
            port=actual_http_port,
            pairing_path=settings.pairing_path,
            protocol=SECURE_PAIRING_PROTOCOL,
            priority=settings.priority,
            ttl_s=settings.candidate_ttl_s,
        )
        udp_server = PairingUDPServer(
            (settings.bind_host, settings.udp_port),
            candidate=candidate,
        )
        definition = build_mdns_service_definition(
            candidate,
            instance_name=settings.mdns_instance_name,
            addresses=(settings.advertised_ipv4,),
        )
        advertiser = (
            advertiser_factory(definition)
            if advertiser_factory is not None
            else MdnsAdvertiser(definition)
        )
        network = PairingNetworkService(
            http_server=http_server,
            udp_server=udp_server,
            advertiser=advertiser,
        )
        return PairingRuntime(
            settings,
            PairingRuntimeComponents(
                registration_registry=registry,
                session_manager=session_manager,
                secure_coordinator=coordinator,
                pending_offers=pending,
                endpoint_app=endpoint_app,
                network_service=network,
            ),
        )
    except Exception:
        if advertiser is not None:
            advertiser.close()
        for server in (udp_server, http_server):
            if server is not None:
                server.server_close()
        if registry is not None:
            registry.close()
        raise
