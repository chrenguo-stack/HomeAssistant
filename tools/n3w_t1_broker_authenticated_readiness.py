#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import stat
import struct
import time
from pathlib import Path
from typing import Sequence

EXPECTED_BROKER = "127.0.0.1"
EXPECTED_PORT = 1883
EXPECTED_PROTOCOL = "5"
EXPECTED_PASSWORD_TARGET = "/run/secrets/gh_homeassistant_mqtt_password"


class ReadinessError(RuntimeError):
    pass


def _varint(value: int) -> bytes:
    if not 0 <= value <= 268435455:
        raise ReadinessError("mqtt_remaining_length_invalid")
    encoded = bytearray()
    while True:
        digit = value % 128
        value //= 128
        if value:
            digit |= 0x80
        encoded.append(digit)
        if not value:
            return bytes(encoded)


def _utf8(value: str) -> bytes:
    payload = value.encode("utf-8")
    if not payload or len(payload) > 65535 or b"\x00" in payload:
        raise ReadinessError("mqtt_utf8_invalid")
    return struct.pack("!H", len(payload)) + payload


def _binary(value: bytes) -> bytes:
    if not value or len(value) > 65535:
        raise ReadinessError("mqtt_binary_invalid")
    return struct.pack("!H", len(value)) + value


def _connect_packet(client_id: str, username: str, password: str) -> bytes:
    variable = b"\x00\x04MQTT\x05\xc2\x00\x0a\x00"
    payload = (
        _utf8(client_id)
        + _utf8(username)
        + _binary(password.encode("utf-8"))
    )
    body = variable + payload
    return b"\x10" + _varint(len(body)) + body


def _recv_exact(stream: socket.socket, size: int) -> bytes:
    blocks = bytearray()
    while len(blocks) < size:
        block = stream.recv(size - len(blocks))
        if not block:
            raise ReadinessError("mqtt_peer_closed")
        blocks.extend(block)
    return bytes(blocks)


def _recv_varint(stream: socket.socket) -> int:
    multiplier = 1
    value = 0
    for _ in range(4):
        digit = _recv_exact(stream, 1)[0]
        value += (digit & 0x7F) * multiplier
        if not digit & 0x80:
            return value
        multiplier *= 128
    raise ReadinessError("mqtt_remaining_length_invalid")


def _probe(
    *,
    host: str,
    port: int,
    client_id: str,
    username: str,
    password: str,
    timeout: float,
) -> None:
    packet = _connect_packet(client_id, username, password)
    with socket.create_connection((host, port), timeout=timeout) as stream:
        stream.settimeout(timeout)
        stream.sendall(packet)
        packet_type = _recv_exact(stream, 1)[0]
        if packet_type != 0x20:
            raise ReadinessError("mqtt_connack_type_invalid")
        remaining = _recv_varint(stream)
        body = _recv_exact(stream, remaining)
        if len(body) < 3:
            raise ReadinessError("mqtt_connack_invalid")
        if body[1] != 0:
            raise ReadinessError("mqtt_authentication_rejected")
        stream.sendall(b"\xe0\x00")


def _private_password(path: Path) -> str:
    if path.is_symlink():
        raise ReadinessError("password_file_symlink")
    try:
        file_stat = path.stat()
    except OSError as error:
        raise ReadinessError("password_file_unavailable") from error
    if not stat.S_ISREG(file_stat.st_mode):
        raise ReadinessError("password_file_not_regular")
    if stat.S_IMODE(file_stat.st_mode) != 0o600:
        raise ReadinessError("password_file_mode_invalid")
    try:
        value = path.read_text(encoding="utf-8").rstrip("\r\n")
    except (OSError, UnicodeError) as error:
        raise ReadinessError("password_file_unreadable") from error
    if not value:
        raise ReadinessError("password_file_empty")
    return value


def _metadata(path: Path) -> dict[str, object]:
    if path.is_symlink():
        raise ReadinessError("metadata_file_symlink")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReadinessError("metadata_file_invalid") from error
    if not isinstance(document, dict):
        raise ReadinessError("metadata_file_invalid")
    if (
        document.get("broker") != EXPECTED_BROKER
        or document.get("port") != EXPECTED_PORT
        or document.get("protocol") != EXPECTED_PROTOCOL
        or document.get("password_file") != EXPECTED_PASSWORD_TARGET
    ):
        raise ReadinessError("metadata_endpoint_invalid")
    for key in ("username", "client_id"):
        value = document.get(key)
        if not isinstance(value, str) or not value:
            raise ReadinessError("metadata_identity_invalid")
    return document


def wait_for_authenticated_broker(
    *,
    metadata_file: Path,
    password_file: Path,
    timeout_seconds: float,
    retry_seconds: float,
    socket_timeout_seconds: float,
) -> None:
    document = _metadata(metadata_file)
    password = _private_password(password_file)
    deadline = time.monotonic() + timeout_seconds
    last_error = "not_attempted"
    while True:
        try:
            _probe(
                host=EXPECTED_BROKER,
                port=EXPECTED_PORT,
                client_id=str(document["client_id"]),
                username=str(document["username"]),
                password=password,
                timeout=socket_timeout_seconds,
            )
            print("BROKER_AUTHENTICATED_READINESS=PASS", flush=True)
            return
        except (OSError, ReadinessError) as error:
            last_error = (
                error.args[0]
                if isinstance(error, ReadinessError) and error.args
                else "connection_unavailable"
            )
        if time.monotonic() >= deadline:
            raise ReadinessError(str(last_error))
        time.sleep(retry_seconds)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata-file", required=True)
    parser.add_argument("--password-file", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--retry-seconds", type=float, default=2.0)
    parser.add_argument("--socket-timeout-seconds", type=float, default=5.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not 1 <= args.timeout_seconds <= 600:
        print("BROKER_AUTHENTICATED_READINESS=STOP reason=timeout_invalid")
        return 2
    if not 0.1 <= args.retry_seconds <= 30:
        print("BROKER_AUTHENTICATED_READINESS=STOP reason=retry_invalid")
        return 2
    if not 0.1 <= args.socket_timeout_seconds <= 30:
        print("BROKER_AUTHENTICATED_READINESS=STOP reason=socket_timeout_invalid")
        return 2
    try:
        wait_for_authenticated_broker(
            metadata_file=Path(os.path.abspath(args.metadata_file)),
            password_file=Path(os.path.abspath(args.password_file)),
            timeout_seconds=args.timeout_seconds,
            retry_seconds=args.retry_seconds,
            socket_timeout_seconds=args.socket_timeout_seconds,
        )
    except ReadinessError as error:
        reason = error.args[0] if error.args else "readiness_failed"
        print(f"BROKER_AUTHENTICATED_READINESS=STOP reason={reason}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
