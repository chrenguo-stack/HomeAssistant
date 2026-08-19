from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .n3w_simplified_discovery import (
    SIMPLE_PAIRING_PROTOCOL,
    SimplifiedManagerCandidate,
    SimplifiedPairingUDPServer,
)
from .n3w_simplified_pairing import SimplifiedPairingCoordinator
from .n3w_simplified_pairing_endpoint import SimplifiedPairingEndpointApp
from .pairing_endpoint import make_pairing_http_server
from .pairing_network_service import PairingNetworkService


class _NullAdvertiser:
    def start(self) -> None:
        return

    def close(self) -> None:
        return


@dataclass(frozen=True, slots=True)
class SimplifiedPairingNetworkSettings:
    manager_id: str
    system_id: str
    advertised_host: str
    bind_host: str = "0.0.0.0"
    http_port: int = 47112
    udp_port: int = 47111
    pairing_path: str = "/v2/pairing"
    priority: int = 100
    candidate_ttl_s: int = 30
    expiry_poll_s: float = 1.0

    def validate(self) -> None:
        if not self.manager_id or not self.system_id or not self.advertised_host:
            raise ValueError("simplified pairing identity is incomplete")
        if not 1 <= self.http_port <= 65535 or not 1 <= self.udp_port <= 65535:
            raise ValueError("simplified pairing port is invalid")
        if not self.pairing_path.startswith("/"):
            raise ValueError("simplified pairing path is invalid")
        if not 0 <= self.priority <= 65535:
            raise ValueError("simplified pairing priority is invalid")
        if not 1 <= self.candidate_ttl_s <= 3600:
            raise ValueError("simplified candidate ttl is invalid")
        if self.expiry_poll_s <= 0:
            raise ValueError("simplified expiry poll must be positive")


@dataclass(slots=True)
class SimplifiedPairingRuntimeComponents:
    coordinator: SimplifiedPairingCoordinator
    endpoint_app: SimplifiedPairingEndpointApp
    network_service: PairingNetworkService


class SimplifiedPairingRuntime:
    """Explicit isolated network wrapper for Setup-Secret pairing.

    Construction is source-only: sockets are bound by the server constructors but
    no serving thread is started until `start()`. Normal Manager `app.py` does not
    instantiate this runtime.
    """

    def __init__(
        self,
        settings: SimplifiedPairingNetworkSettings,
        components: SimplifiedPairingRuntimeComponents,
    ) -> None:
        settings.validate()
        self.settings = settings
        self.components = components
        self._stop = threading.Event()
        self._started = False
        self._closed = False
        self._lock = threading.RLock()

    def start(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("simplified pairing runtime is closed")
            if self._started:
                return
            self.components.network_service.start()
            self._started = True

    def run(self) -> None:
        self.start()
        try:
            while not self._stop.wait(self.settings.expiry_poll_s):
                self.expire()
        finally:
            self.close()

    def expire(self, *, now: datetime | None = None) -> dict[str, int]:
        observed_at = now or datetime.now(UTC)
        return {
            "pairing_sessions": self.components.coordinator.expire_sessions(now=observed_at),
            "registrations": self.components.coordinator.registry.expire_pending(now=observed_at),
        }

    def import_setup_secret(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        setup_secret: bytes,
    ) -> None:
        self.components.coordinator.import_setup_secret(
            hardware_id,
            pairing_id,
            setup_secret=setup_secret,
        )

    def request_stop(self) -> None:
        self._stop.set()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._stop.set()
            self.components.network_service.close()
            self._started = False
            self._closed = True

    @property
    def http_address(self) -> tuple[str, int]:
        address = self.components.network_service.http_server.server_address
        return str(address[0]), int(address[1])

    @property
    def udp_address(self) -> tuple[str, int]:
        address = self.components.network_service.udp_server.server_address
        return str(address[0]), int(address[1])


def assemble_simplified_pairing_runtime(
    settings: SimplifiedPairingNetworkSettings,
    coordinator: SimplifiedPairingCoordinator,
) -> SimplifiedPairingRuntime:
    settings.validate()
    endpoint_app = SimplifiedPairingEndpointApp(coordinator)
    http_server: Any = None
    udp_server: Any = None
    try:
        http_server = make_pairing_http_server(
            (settings.bind_host, settings.http_port),
            app=endpoint_app,
        )
        actual_http_port = int(http_server.server_address[1])
        candidate = SimplifiedManagerCandidate(
            schema="gh.manager.candidate/1",
            manager_id=settings.manager_id,
            system_id=settings.system_id,
            host=settings.advertised_host,
            scheme="http",
            port=actual_http_port,
            pairing_path=settings.pairing_path,
            protocol=SIMPLE_PAIRING_PROTOCOL,
            priority=settings.priority,
            ttl_s=settings.candidate_ttl_s,
        )
        udp_server = SimplifiedPairingUDPServer(
            (settings.bind_host, settings.udp_port),
            candidate=candidate,
        )
        network = PairingNetworkService(
            http_server=http_server,
            udp_server=udp_server,
            advertiser=_NullAdvertiser(),
        )
        return SimplifiedPairingRuntime(
            settings,
            SimplifiedPairingRuntimeComponents(
                coordinator=coordinator,
                endpoint_app=endpoint_app,
                network_service=network,
            ),
        )
    except Exception:
        for server in (udp_server, http_server):
            if server is not None:
                server.server_close()
        raise
