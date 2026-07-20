from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Protocol

from .pairing_discovery import PairingUDPServer
from .pairing_endpoint import BoundedThreadingHTTPServer


class ClosableAdvertiser(Protocol):
    def start(self) -> None: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class PairingNetworkSnapshot:
    schema: str
    started: bool
    http_address: tuple[str, int]
    udp_address: tuple[str, int]
    http_thread_alive: bool
    udp_thread_alive: bool


class PairingNetworkService:
    """Own the bounded HTTP, UDP fallback and mDNS lifecycle as one unit."""

    def __init__(
        self,
        *,
        http_server: BoundedThreadingHTTPServer,
        udp_server: PairingUDPServer,
        advertiser: ClosableAdvertiser,
    ) -> None:
        self.http_server = http_server
        self.udp_server = udp_server
        self.advertiser = advertiser
        self._lock = threading.RLock()
        self._started = False
        self._closed = False
        self._http_thread: threading.Thread | None = None
        self._udp_thread: threading.Thread | None = None

    def start(self) -> PairingNetworkSnapshot:
        with self._lock:
            if self._closed:
                raise RuntimeError("pairing network service is closed")
            if self._started:
                return self.snapshot()
            self._http_thread = threading.Thread(
                target=self.http_server.serve_forever,
                name="greenhouse-pairing-http",
                daemon=True,
            )
            self._udp_thread = threading.Thread(
                target=self.udp_server.serve_forever,
                name="greenhouse-pairing-udp",
                daemon=True,
            )
            try:
                self._http_thread.start()
                self._udp_thread.start()
                self.advertiser.start()
            except Exception:
                self._stop_servers_locked()
                try:
                    self.advertiser.close()
                finally:
                    self._closed = True
                raise
            self._started = True
            return self.snapshot()

    def close(self) -> PairingNetworkSnapshot:
        with self._lock:
            if self._closed:
                return self.snapshot()
            self._stop_servers_locked()
            self.advertiser.close()
            self._started = False
            self._closed = True
            return self.snapshot()

    def snapshot(self) -> PairingNetworkSnapshot:
        with self._lock:
            return PairingNetworkSnapshot(
                schema="gh.pair.network-status/1",
                started=self._started,
                http_address=(
                    str(self.http_server.server_address[0]),
                    int(self.http_server.server_address[1]),
                ),
                udp_address=(
                    str(self.udp_server.server_address[0]),
                    int(self.udp_server.server_address[1]),
                ),
                http_thread_alive=(
                    self._http_thread is not None
                    and self._http_thread.is_alive()
                ),
                udp_thread_alive=(
                    self._udp_thread is not None
                    and self._udp_thread.is_alive()
                ),
            )

    def _stop_servers_locked(self) -> None:
        for server, thread in (
            (self.http_server, self._http_thread),
            (self.udp_server, self._udp_thread),
        ):
            if thread is not None and thread.is_alive():
                server.shutdown()
            server.server_close()
            if thread is not None:
                thread.join(timeout=5)
