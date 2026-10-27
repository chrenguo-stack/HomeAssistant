from __future__ import annotations

import hashlib
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .n3w_registration_bootstrap import (
    RegistrationBootstrapApp,
    RegistrationBootstrapHTTPServer,
    RegistrationTransactionService,
    bootstrap_certificate_sha256,
    make_registration_bootstrap_tls_server,
)
from .n3w_registration_discovery import (
    RegistrationCandidate,
    RegistrationDiscoveryUDPServer,
    RegistrationMdnsAdvertiser,
    build_registration_mdns_definition,
)
from .n3w_trusted_product_lan import (
    DEFAULT_STATE_PATH,
    TrustedProductLanError,
    TrustedProductLanState,
    load_trusted_product_lan,
    resolve_interface_ipv4,
)
from .pairing_discovery import DiscoveryRejected

_SAFE_BIND_HOST = re.compile(r"^(?:0\.0\.0\.0)$")
MDNS_AUTHORITY_POLL_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class RegistrationNetworkSettings:
    manager_id: str
    system_id: str
    certificate_file: str
    private_key_file: str
    trusted_lan_state_file: str = str(DEFAULT_STATE_PATH)
    bind_host: str = "0.0.0.0"
    bootstrap_port: int = 47110
    discovery_port: int = 47111

    def validate(self) -> None:
        if not self.manager_id or not self.system_id:
            raise ValueError("registration identity incomplete")
        if _SAFE_BIND_HOST.fullmatch(self.bind_host) is None:
            raise ValueError("registration bind host must be 0.0.0.0")
        if self.bootstrap_port != 47110:
            raise ValueError("registration bootstrap port must be 47110")
        if self.discovery_port != 47111:
            raise ValueError("registration discovery port must be 47111")
        for raw_path in (
            self.certificate_file,
            self.private_key_file,
            self.trusted_lan_state_file,
        ):
            path = Path(raw_path)
            if not path.is_absolute():
                raise ValueError("registration runtime path must be absolute")


def _instance_name(system_id: str) -> str:
    suffix = hashlib.sha256(system_id.encode("utf-8")).hexdigest()[:12]
    return f"n3w-registration-{suffix}"


class RegistrationMdnsAuthorityController:
    def __init__(
        self,
        *,
        candidate: RegistrationCandidate,
        system_id: str,
        state_loader: Callable[[], TrustedProductLanState],
        interface_ipv4_resolver: Callable[[], str],
        advertiser_factory: Callable[..., RegistrationMdnsAdvertiser],
    ) -> None:
        self.candidate = candidate
        self.system_id = system_id
        self.state_loader = state_loader
        self.interface_ipv4_resolver = interface_ipv4_resolver
        self.advertiser_factory = advertiser_factory
        self._lock = threading.RLock()
        self._advertiser: RegistrationMdnsAdvertiser | None = None
        self._authority_key: tuple[str, str] | None = None

    @property
    def authority_key(self) -> tuple[str, str] | None:
        with self._lock:
            return self._authority_key

    def refresh(self) -> bool:
        with self._lock:
            try:
                observed = self.state_loader()
            except (TrustedProductLanError, OSError, ValueError):
                self._close_locked()
                return False
            if not observed.available or observed.subnet is None:
                self._close_locked()
                return False

            try:
                interface_ip = self.interface_ipv4_resolver()
                confirmed = self.state_loader()
            except (TrustedProductLanError, OSError, ValueError):
                self._close_locked()
                return False
            if (
                not confirmed.available
                or confirmed.subnet is None
                or confirmed.generation != observed.generation
                or not confirmed.authorizes(interface_ip)
            ):
                self._close_locked()
                return False

            key = (confirmed.generation, interface_ip)
            if self._advertiser is not None and self._authority_key == key:
                return True

            self._close_locked()
            try:
                definition = build_registration_mdns_definition(
                    self.candidate,
                    instance_name=_instance_name(self.system_id),
                    interface_ip=interface_ip,
                    state_loader=lambda: confirmed,
                )
            except (DiscoveryRejected, ValueError):
                return False

            advertiser = self.advertiser_factory(
                definition,
                interface_ip=interface_ip,
            )
            try:
                advertiser.start()
            except Exception:
                advertiser.close()
                raise
            self._advertiser = advertiser
            self._authority_key = key
            return True

    def close(self) -> None:
        with self._lock:
            self._close_locked()

    def _close_locked(self) -> None:
        if self._advertiser is not None:
            self._advertiser.close()
        self._advertiser = None
        self._authority_key = None


@dataclass(slots=True)
class RegistrationRuntimeComponents:
    bootstrap_app: RegistrationBootstrapApp
    bootstrap_server: RegistrationBootstrapHTTPServer
    discovery_server: RegistrationDiscoveryUDPServer
    mdns_controller: RegistrationMdnsAuthorityController


class RegistrationNetworkRuntime:
    def __init__(
        self,
        settings: RegistrationNetworkSettings,
        components: RegistrationRuntimeComponents,
    ) -> None:
        settings.validate()
        self.settings = settings
        self.components = components
        self._lock = threading.RLock()
        self._started = False
        self._closed = False
        self._bootstrap_thread: threading.Thread | None = None
        self._discovery_thread: threading.Thread | None = None
        self._mdns_thread: threading.Thread | None = None
        self._mdns_stop = threading.Event()

    def start(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("registration network runtime is closed")
            if self._started:
                return
            self._bootstrap_thread = threading.Thread(
                target=self.components.bootstrap_server.serve_forever,
                name="greenhouse-registration-bootstrap",
                daemon=True,
            )
            self._discovery_thread = threading.Thread(
                target=self.components.discovery_server.serve_forever,
                name="greenhouse-registration-discovery",
                daemon=True,
            )
            try:
                self._bootstrap_thread.start()
                self._discovery_thread.start()
                self.components.mdns_controller.refresh()
                self._mdns_stop.clear()
                self._mdns_thread = threading.Thread(
                    target=self._mdns_loop,
                    name="greenhouse-registration-mdns-authority",
                    daemon=True,
                )
                self._mdns_thread.start()
            except Exception:
                self.components.mdns_controller.close()
                self._stop_servers_locked()
                raise
            self._started = True

    def close(self) -> None:
        mdns_thread = None
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._mdns_stop.set()
            mdns_thread = self._mdns_thread
            self.components.mdns_controller.close()
            self._stop_servers_locked()
            self._started = False
        if mdns_thread is not None:
            mdns_thread.join(timeout=5)

    def _mdns_loop(self) -> None:
        while not self._mdns_stop.wait(MDNS_AUTHORITY_POLL_SECONDS):
            try:
                self.components.mdns_controller.refresh()
            except Exception:
                self.components.mdns_controller.close()

    def _stop_servers_locked(self) -> None:
        for server, thread in (
            (self.components.bootstrap_server, self._bootstrap_thread),
            (self.components.discovery_server, self._discovery_thread),
        ):
            if thread is not None and thread.is_alive():
                server.shutdown()
            server.server_close()
            if thread is not None:
                thread.join(timeout=5)


def assemble_registration_network_runtime(
    settings: RegistrationNetworkSettings,
    *,
    state_loader: Callable[[], TrustedProductLanState] | None = None,
    interface_ipv4_resolver: Callable[[], str] | None = None,
    advertiser_factory: Callable[..., RegistrationMdnsAdvertiser] = (
        RegistrationMdnsAdvertiser
    ),
    transaction_service: RegistrationTransactionService | None = None,
) -> RegistrationNetworkRuntime:
    settings.validate()
    state_path = Path(settings.trusted_lan_state_file)

    def load_state() -> TrustedProductLanState:
        if state_loader is not None:
            return state_loader()
        return load_trusted_product_lan(state_path)

    def interface_ipv4() -> str:
        if interface_ipv4_resolver is not None:
            return interface_ipv4_resolver()
        return resolve_interface_ipv4(state_path=state_path)

    fingerprint = bootstrap_certificate_sha256(settings.certificate_file)
    base_candidate = RegistrationCandidate(
        manager_id=settings.manager_id,
        system_id=settings.system_id,
        system_id_hint=settings.system_id[-8:].upper(),
        host="auto",
        bootstrap_tls_sha256=fingerprint,
    )
    bootstrap_app = RegistrationBootstrapApp(
        manager_id=settings.manager_id,
        system_id=settings.system_id,
        state_loader=load_state,
        transaction_service=transaction_service,
    )

    bootstrap_server = None
    discovery_server = None
    try:
        bootstrap_server = make_registration_bootstrap_tls_server(
            (settings.bind_host, settings.bootstrap_port),
            app=bootstrap_app,
            certificate_file=settings.certificate_file,
            private_key_file=settings.private_key_file,
        )
        discovery_server = RegistrationDiscoveryUDPServer(
            (settings.bind_host, settings.discovery_port),
            candidate=base_candidate,
            state_loader=load_state,
        )
        mdns_controller = RegistrationMdnsAuthorityController(
            candidate=base_candidate,
            system_id=settings.system_id,
            state_loader=load_state,
            interface_ipv4_resolver=interface_ipv4,
            advertiser_factory=advertiser_factory,
        )
        return RegistrationNetworkRuntime(
            settings,
            RegistrationRuntimeComponents(
                bootstrap_app=bootstrap_app,
                bootstrap_server=bootstrap_server,
                discovery_server=discovery_server,
                mdns_controller=mdns_controller,
            ),
        )
    except Exception:
        for server in (discovery_server, bootstrap_server):
            if server is not None:
                server.server_close()
        raise
