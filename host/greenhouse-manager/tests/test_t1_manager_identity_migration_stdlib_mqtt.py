from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

import greenhouse_manager.t1_manager_identity_migration_stdlib_mqtt as module
from greenhouse_manager.t1_manager_identity_migration_stdlib_mqtt import (
    ManagerStdlibMqttError,
    StdlibAnonymousRetainedReader,
    verify_stdlib_retained_reader,
)

TOPIC = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
PAYLOAD = b'{"schema":"gh.telemetry/1"}'


class FakeSocket:
    def __init__(self, responses: bytes | None = None, *, timeout: bool = False) -> None:
        self.responses = bytearray(responses or b"")
        self.timeout = timeout
        self.sent: list[bytes] = []
        self.timeout_value: float | None = None
        self.closed = False

    def settimeout(self, value: float | None) -> None:
        self.timeout_value = value

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, size: int) -> bytes:
        if self.timeout:
            raise TimeoutError
        if not self.responses:
            return b""
        chunk = bytes(self.responses[:size])
        del self.responses[:size]
        return chunk

    def close(self) -> None:
        self.closed = True


def _success_packets(payload: bytes = PAYLOAD) -> bytes:
    connack = module._packet(0x20, b"\x00\x00")
    suback = module._packet(0x90, b"\x00\x01\x00")
    publish = module._packet(0x31, module._mqtt_utf8(TOPIC) + payload)
    return connack + suback + publish


def test_stdlib_reader_connects_subscribes_and_never_publishes() -> None:
    connection = FakeSocket(_success_packets())
    addresses: list[tuple[tuple[str, int], float]] = []

    def factory(address: tuple[str, int], timeout: float) -> FakeSocket:
        addresses.append((address, timeout))
        return connection

    reader = StdlibAnonymousRetainedReader(
        port=1883,
        timeout_s=3.0,
        socket_factory=factory,
    )

    assert reader.read(TOPIC) == PAYLOAD
    assert addresses == [(('127.0.0.1', 1883), 3.0)]
    assert connection.timeout_value == 3.0
    assert connection.closed is True
    assert connection.sent[0][0] == 0x10
    assert connection.sent[1][0] == 0x82
    assert connection.sent[-1] == b"\xe0\x00"
    assert all(packet[0] >> 4 != 3 for packet in connection.sent)


def test_stdlib_reader_rejects_topic_before_opening_socket() -> None:
    called = False

    def factory(_address: tuple[str, int], _timeout: float) -> FakeSocket:
        nonlocal called
        called = True
        return FakeSocket()

    reader = StdlibAnonymousRetainedReader(socket_factory=factory)

    with pytest.raises(ValueError, match="outside the allowed namespaces"):
        reader.read("other/#")

    assert called is False


def test_stdlib_reader_rejects_broker_connack() -> None:
    connection = FakeSocket(module._packet(0x20, b"\x00\x05"))
    reader = StdlibAnonymousRetainedReader(
        socket_factory=lambda _address, _timeout: connection
    )

    with pytest.raises(ManagerStdlibMqttError, match="was rejected"):
        reader.read(TOPIC)

    assert connection.closed is True


def test_stdlib_reader_reports_timeout() -> None:
    connection = FakeSocket(timeout=True)
    reader = StdlibAnonymousRetainedReader(
        socket_factory=lambda _address, _timeout: connection
    )

    with pytest.raises(ManagerStdlibMqttError, match="timed out"):
        reader.read(TOPIC)

    assert connection.closed is True


def test_stdlib_reader_rejects_empty_retained_payload() -> None:
    connection = FakeSocket(_success_packets(b""))
    reader = StdlibAnonymousRetainedReader(
        socket_factory=lambda _address, _timeout: connection
    )

    with pytest.raises(ManagerStdlibMqttError, match="empty payload"):
        reader.read(TOPIC)


def test_preflight_is_secret_free_and_read_only() -> None:
    connection = FakeSocket(_success_packets())
    report = verify_stdlib_retained_reader(
        TOPIC,
        reader_factory=lambda: StdlibAnonymousRetainedReader(
            socket_factory=lambda _address, _timeout: connection
        ),
    )

    assert report["stdlib_mqtt_reader_ready"] is True
    assert report["retained_payload_verified"] is True
    assert report["publish_performed"] is False
    assert report["retained_state_modified"] is False
    assert report["current_services_modified"] is False
    assert report["payload_included"] is False
    assert PAYLOAD.decode() not in json.dumps(report)


def test_execution_tool_injects_stdlib_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    tool_path = (
        Path(__file__).resolve().parents[1]
        / "tools/run_t1_manager_identity_migration_production_execution_packet.py"
    )
    spec = importlib.util.spec_from_file_location("manager_execution_tool", tool_path)
    assert spec is not None and spec.loader is not None
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    captured: dict[str, object] = {}

    def fake_execute(*_args: object, **kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        reader_factory = kwargs.get("reader_factory")
        assert callable(reader_factory)
        assert isinstance(reader_factory(), StdlibAnonymousRetainedReader)
        return {"production_execution_completed": True}

    monkeypatch.setattr(tool.packet, "execute_manager_identity_production_packet", fake_execute)
    rc = tool.main(
        [
            str(tmp_path / "authorization.json"),
            str(tmp_path / "execution"),
            str(tmp_path / "driver.json"),
            str(tmp_path / "preparation"),
            str(tmp_path / "transactions"),
            "--system-id",
            "greenhouse",
            "--node-id",
            "gh-n1-a9f2f8",
            "--discovery-topic",
            "homeassistant/device/gh-n1-a9f2f8/config",
            "--execution-confirmation",
            "EXECUTE-M2-MANAGER-MIGRATION:0123456789abcdef01234567:aaaaaaaaaaaaaaaa:bbbbbbbbbbbbbbbb:cccccccccccccccc",
            "--target",
            "greenhouse-manager",
            "--execute-manager-migration",
            "--enable-production-execution",
        ]
    )

    assert rc == 0
    assert captured["reader_factory"] is not None
    assert json.loads(capsys.readouterr().out)["production_execution_completed"] is True
