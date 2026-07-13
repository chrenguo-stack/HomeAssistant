from __future__ import annotations

import argparse
import json
import secrets
import socket
import sys
from collections.abc import Callable, Sequence
from contextlib import suppress
from typing import Protocol

SCHEMA = "gh.m2.t1-manager-identity-stdlib-mqtt-preflight/1"
_MAX_REMAINING_LENGTH = 268_435_455


class ManagerStdlibMqttError(RuntimeError):
    pass


class SocketLike(Protocol):
    def settimeout(self, value: float | None) -> None: ...

    def sendall(self, data: bytes) -> None: ...

    def recv(self, size: int) -> bytes: ...

    def close(self) -> None: ...


SocketFactory = Callable[[tuple[str, int], float], SocketLike]


def _socket_factory(address: tuple[str, int], timeout_s: float) -> SocketLike:
    return socket.create_connection(address, timeout_s)


def _remaining_length(value: int) -> bytes:
    if value < 0 or value > _MAX_REMAINING_LENGTH:
        raise ValueError("MQTT remaining length is invalid")
    encoded = bytearray()
    while True:
        digit = value % 128
        value //= 128
        if value:
            digit |= 0x80
        encoded.append(digit)
        if not value:
            return bytes(encoded)


def _mqtt_utf8(value: str) -> bytes:
    encoded = value.encode("utf-8")
    if not encoded or len(encoded) > 65_535 or b"\x00" in encoded:
        raise ValueError("MQTT UTF-8 value is invalid")
    return len(encoded).to_bytes(2, "big") + encoded


def _read_exact(connection: SocketLike, size: int) -> bytes:
    result = bytearray()
    while len(result) < size:
        chunk = connection.recv(size - len(result))
        if not chunk:
            raise ManagerStdlibMqttError("MQTT connection closed unexpectedly")
        result.extend(chunk)
    return bytes(result)


def _read_packet(connection: SocketLike) -> tuple[int, bytes]:
    header = _read_exact(connection, 1)[0]
    multiplier = 1
    remaining = 0
    for _index in range(4):
        digit = _read_exact(connection, 1)[0]
        remaining += (digit & 0x7F) * multiplier
        if digit & 0x80 == 0:
            return header, _read_exact(connection, remaining)
        multiplier *= 128
    raise ManagerStdlibMqttError("MQTT remaining length encoding is invalid")


def _packet(header: int, body: bytes = b"") -> bytes:
    return bytes((header,)) + _remaining_length(len(body)) + body


def _publish_payload(header: int, body: bytes, expected_topic: str) -> bytes | None:
    if header >> 4 != 3:
        return None
    if len(body) < 2:
        raise ManagerStdlibMqttError("MQTT PUBLISH packet is truncated")
    topic_length = int.from_bytes(body[:2], "big")
    topic_end = 2 + topic_length
    if topic_length == 0 or topic_end > len(body):
        raise ManagerStdlibMqttError("MQTT PUBLISH topic is invalid")
    try:
        topic = body[2:topic_end].decode("utf-8")
    except UnicodeDecodeError as error:
        raise ManagerStdlibMqttError("MQTT PUBLISH topic is not UTF-8") from error
    qos = (header >> 1) & 0x03
    if qos == 3:
        raise ManagerStdlibMqttError("MQTT PUBLISH QoS is invalid")
    payload_offset = topic_end
    if qos:
        if payload_offset + 2 > len(body):
            raise ManagerStdlibMqttError("MQTT PUBLISH packet identifier is missing")
        payload_offset += 2
    if topic != expected_topic:
        return None
    if header & 0x01 == 0:
        raise ManagerStdlibMqttError("MQTT retained probe received a non-retained message")
    payload = body[payload_offset:]
    if not payload:
        raise ManagerStdlibMqttError("MQTT retained probe returned an empty payload")
    return payload


class StdlibAnonymousRetainedReader:
    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 1883,
        timeout_s: float = 8.0,
        socket_factory: SocketFactory = _socket_factory,
    ) -> None:
        if not host or not 1 <= port <= 65_535 or timeout_s <= 0:
            raise ValueError("retained reader configuration is invalid")
        self.host = host
        self.port = port
        self.timeout_s = timeout_s
        self.socket_factory = socket_factory

    @staticmethod
    def _allowed_topic(topic: str) -> bool:
        return (
            topic.startswith("gh/") or topic.startswith("homeassistant/")
        ) and "+" not in topic and "#" not in topic and "\x00" not in topic

    def read(self, topic: str) -> bytes:
        if not self._allowed_topic(topic):
            raise ValueError("retained probe topic is outside the allowed namespaces")
        try:
            connection = self.socket_factory((self.host, self.port), self.timeout_s)
        except OSError as error:
            raise ManagerStdlibMqttError(
                "anonymous retained probe could not connect"
            ) from error
        connection.settimeout(self.timeout_s)
        client_id = f"gh-m2-read-{secrets.token_hex(6)}"
        connect_body = (
            b"\x00\x04MQTT"
            + b"\x04"
            + b"\x02"
            + b"\x00\x1e"
            + _mqtt_utf8(client_id)
        )
        subscribe_body = b"\x00\x01" + _mqtt_utf8(topic) + b"\x00"
        try:
            connection.sendall(_packet(0x10, connect_body))
            header, body = _read_packet(connection)
            if header != 0x20 or len(body) != 2:
                raise ManagerStdlibMqttError("anonymous retained probe CONNACK is invalid")
            if body[1] != 0:
                raise ManagerStdlibMqttError("anonymous retained probe was rejected")

            connection.sendall(_packet(0x82, subscribe_body))
            header, body = _read_packet(connection)
            if (
                header != 0x90
                or len(body) < 3
                or body[:2] != b"\x00\x01"
                or body[2] == 0x80
            ):
                raise ManagerStdlibMqttError("anonymous retained probe SUBACK is invalid")

            while True:
                header, body = _read_packet(connection)
                payload = _publish_payload(header, body, topic)
                if payload is not None:
                    return payload
        except TimeoutError as error:
            raise ManagerStdlibMqttError("anonymous retained probe timed out") from error
        except OSError as error:
            raise ManagerStdlibMqttError(
                "anonymous retained probe connection failed"
            ) from error
        finally:
            with suppress(OSError):
                connection.sendall(_packet(0xE0))
            connection.close()


def verify_stdlib_retained_reader(
    topic: str,
    *,
    host: str = "127.0.0.1",
    port: int = 1883,
    timeout_s: float = 8.0,
    reader_factory: Callable[[], StdlibAnonymousRetainedReader] | None = None,
) -> dict[str, object]:
    reader = (
        reader_factory()
        if reader_factory is not None
        else StdlibAnonymousRetainedReader(
            host=host,
            port=port,
            timeout_s=timeout_s,
        )
    )
    payload = reader.read(topic)
    return {
        "schema": SCHEMA,
        "stdlib_mqtt_reader_ready": True,
        "anonymous_connect_verified": True,
        "exact_topic_subscribe_verified": True,
        "retained_payload_verified": bool(payload),
        "publish_performed": False,
        "retained_state_modified": False,
        "current_services_modified": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "payload_included": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the dependency-free read-only MQTT retained reader before creating "
            "short-lived manager migration authorization materials."
        )
    )
    parser.add_argument("--topic", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    args = parser.parse_args(argv)
    try:
        result = verify_stdlib_retained_reader(
            args.topic,
            host=args.host,
            port=args.port,
            timeout_s=args.timeout_seconds,
        )
    except (ManagerStdlibMqttError, OSError, UnicodeError, ValueError) as error:
        print(f"T1 manager stdlib MQTT preflight failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
