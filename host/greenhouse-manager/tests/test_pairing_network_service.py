from __future__ import annotations

import threading

import pytest

from greenhouse_manager.pairing_network_service import PairingNetworkService


class FakeServer:
    def __init__(self, port: int) -> None:
        self.server_address = ("127.0.0.1", port)
        self.started = threading.Event()
        self.stop = threading.Event()
        self.shutdown_calls = 0
        self.close_calls = 0

    def serve_forever(self) -> None:
        self.started.set()
        self.stop.wait(timeout=5)

    def shutdown(self) -> None:
        self.shutdown_calls += 1
        self.stop.set()

    def server_close(self) -> None:
        self.close_calls += 1
        self.stop.set()


class FakeAdvertiser:
    def __init__(self, *, fail_start: bool = False) -> None:
        self.fail_start = fail_start
        self.start_calls = 0
        self.close_calls = 0

    def start(self) -> None:
        self.start_calls += 1
        if self.fail_start:
            raise RuntimeError("injected advertiser failure")

    def close(self) -> None:
        self.close_calls += 1


def test_network_service_starts_and_closes_as_one_unit() -> None:
    http = FakeServer(8443)
    udp = FakeServer(8444)
    advertiser = FakeAdvertiser()
    service = PairingNetworkService(
        http_server=http,  # type: ignore[arg-type]
        udp_server=udp,  # type: ignore[arg-type]
        advertiser=advertiser,
    )

    started = service.start()
    assert http.started.wait(timeout=1)
    assert udp.started.wait(timeout=1)
    assert started.started is True
    assert service.start().started is True
    assert advertiser.start_calls == 1

    closed = service.close()
    assert closed.started is False
    assert http.shutdown_calls == udp.shutdown_calls == 1
    assert http.close_calls == udp.close_calls == 1
    assert advertiser.close_calls == 1


def test_advertiser_failure_rolls_back_both_servers() -> None:
    http = FakeServer(8443)
    udp = FakeServer(8444)
    advertiser = FakeAdvertiser(fail_start=True)
    service = PairingNetworkService(
        http_server=http,  # type: ignore[arg-type]
        udp_server=udp,  # type: ignore[arg-type]
        advertiser=advertiser,
    )

    with pytest.raises(RuntimeError, match="injected advertiser failure"):
        service.start()

    assert http.close_calls == udp.close_calls == 1
    assert advertiser.close_calls == 1
    with pytest.raises(RuntimeError, match="closed"):
        service.start()
