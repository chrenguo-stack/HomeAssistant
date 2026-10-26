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
    TrustedProductLanState,
    load_trusted_product_lan,
    resolve_interface_ipv4,
)

_SAFE_BIND_HOST = re.compile(r"^(?:0\.0\.0\.0)$")


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


@dataclass(slots=True)
class RegistrationRuntimeComponents:
    bootstrap_app: RegistrationBootstrapApp
    bootstrap_server: RegistrationBootstrapHTTPServer
    discovery_server: RegistrationDiscoveryUDPServer
    advertiser: RegistrationMdnsAdvertiser


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
                self.components.advertiser.start()
            except Exception:
                self._stop_locked()
                raise
            self._started = True

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._stop_locked()
            self._closed = True

    def _stop_locked(self) -> None:
        for server, thread in (
            (self.components.bootstrap_server, self._bootstrap_thread),
            (self.components.discovery_server, self._discovery_thread),
        ):
            if thread is not None and thread.is_alive():
                server.shutdown()
            server.server_close()
            if thread is not None:
                thread.join(timeout=5)
        self.components.advertiser.close()
        self._started = False


def _instance_name(system_id: str) -> str:
    suffix = hashlib.sha256(system_id.encode("utf-8")).hexdigest()[:12]
    return f"n3w-registration-{suffix}"


def assemble_registration_network_runtime(
    settings: RegistrationNetworkSettings,
    *,
    state_loader: Callable[[], TrustedProductLanState] | None = None,
    interface_ipv4_resolver: Callable[[], str] | None = None,
    advertiser_factory: Callable[..., RegistrationMdnsAdvertiser] = (
        RegistrationMdnsAdvertiser
    ),
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
    )

    bootstrap_server = None
    discovery_server = None
    advertiser = None
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
        advertised_ip = interface_ipv4()
        definition = build_registration_mdns_definition(
            base_candidate,
            instance_name=_instance_name(settings.system_id),
            interface_ip=advertised_ip,
            state_loader=load_state,
        )
        advertiser = advertiser_factory(
            definition,
            interface_ip=advertised_ip,
        )
        return RegistrationNetworkRuntime(
            settings,
            RegistrationRuntimeComponents(
                bootstrap_app=bootstrap_app,
                bootstrap_server=bootstrap_server,
                discovery_server=discovery_server,
                advertiser=advertiser,
            ),
        )
    except Exception:
        if advertiser is not None:
            advertiser.close()
        for server in (discovery_server, bootstrap_server):
            if server is not None:
                server.server_close()
        raise
