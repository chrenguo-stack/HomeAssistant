from __future__ import annotations

import base64
import socket
import tempfile
from pathlib import Path

import pytest

import greenhouse_manager.runtime.n3w_pairing_local_ipc as ipc
from greenhouse_manager.ops.n3w_pairing_cli import parser
from greenhouse_manager.runtime.n3w_pairing_local_ipc import (
    ManagerOwnedPairingSocket,
    PairingLocalIpcError,
    authorize_repair_over_socket,
    import_setup_secret_over_socket,
)

HARDWARE_ID = "ghw-c6-aabbccddeeff"
PAIRING_ID = "ba999b15-e74f-4ef5-bad7-8dcd62c13d66"
SECRET = base64.urlsafe_b64encode(bytes(range(32))).rstrip(b"=").decode()
SHORT_TEMP_ROOT = Path(tempfile.gettempdir()).resolve()


class Coordinator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bytes]] = []
        self.repair_calls: list[tuple[str, str]] = []

    def import_setup_secret(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        setup_secret: bytes,
    ) -> None:
        self.calls.append((hardware_id, pairing_id, setup_secret))

    def authorize_repair(
        self,
        hardware_id: str,
        pairing_id: str,
    ) -> None:
        self.repair_calls.append((hardware_id, pairing_id))


def test_manager_owned_socket_imports_without_staging_file() -> None:
    coordinator = Coordinator()
    with tempfile.TemporaryDirectory(dir=SHORT_TEMP_ROOT) as directory:
        socket_path = Path(directory) / "pairing.sock"
        server = ManagerOwnedPairingSocket(coordinator, socket_path)
        server.start()
        try:
            result = import_setup_secret_over_socket(
                socket_path,
                hardware_id=HARDWARE_ID,
                pairing_id=PAIRING_ID,
                setup_secret=SECRET,
            )
        finally:
            server.stop()
        assert list(Path(directory).iterdir()) == []

    assert result == {
        "accepted": True,
        "code": "accepted",
        "schema": "gh.pair.setup-secret-import-result/1",
    }
    assert coordinator.calls == [(HARDWARE_ID, PAIRING_ID, bytes(range(32)))]


def test_socket_rejects_malformed_and_oversized_requests() -> None:
    coordinator = Coordinator()
    with tempfile.TemporaryDirectory(dir=SHORT_TEMP_ROOT) as directory:
        socket_path = Path(directory) / "pairing.sock"
        server = ManagerOwnedPairingSocket(coordinator, socket_path)
        server.start()
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(str(socket_path))
                client.sendall(b"{" + b"x" * 5000)
                response = client.recv(4097)
            assert b'"accepted":false' in response
            assert coordinator.calls == []
        finally:
            server.stop()


def test_socket_refuses_symlink_ambiguity(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)

    with pytest.raises(PairingLocalIpcError, match="pairing_socket_path_invalid"):
        ManagerOwnedPairingSocket(Coordinator(), link / "pairing.sock")


def test_cli_does_not_accept_setup_secret_in_process_arguments() -> None:
    options = parser()
    assert "--setup-secret " not in options.format_help()
    with pytest.raises(SystemExit):
        options.parse_args(
            [
                "import",
                "--hardware-id",
                HARDWARE_ID,
                "--pairing-id",
                PAIRING_ID,
                "--setup-secret",
                SECRET,
            ]
        )

def test_manager_owned_socket_authorizes_bounded_repair() -> None:
    coordinator = Coordinator()

    with tempfile.TemporaryDirectory(
        dir=SHORT_TEMP_ROOT
    ) as directory:
        socket_path = Path(directory) / "pairing.sock"
        server = ManagerOwnedPairingSocket(
            coordinator,
            socket_path,
        )
        server.start()
        try:
            result = authorize_repair_over_socket(
                socket_path,
                hardware_id=HARDWARE_ID,
                pairing_id=PAIRING_ID,
            )
        finally:
            server.stop()

    assert result == {
        "accepted": True,
        "code": "repair_authorized",
        "schema": "gh.pair.repair-authorize-result/1",
    }
    assert coordinator.repair_calls == [
        (HARDWARE_ID, PAIRING_ID)
    ]
    assert coordinator.calls == []

def test_cli_socket_default_tracks_manager_runtime_environment(
    monkeypatch,
) -> None:
    socket_path = "/tmp/greenhouse-manager/pairing.sock"

    monkeypatch.setenv(
        "GH_N3W_PAIRING_SOCKET_PATH",
        socket_path,
    )

    options = parser()
    args = options.parse_args(
        [
            "authorize-repair",
            "--hardware-id",
            HARDWARE_ID,
            "--pairing-id",
            PAIRING_ID,
        ]
    )

    assert args.socket == socket_path

def _valid_repair_response() -> bytes:
    return (
        b'{"accepted":true,"code":"repair_authorized",'
        b'"schema":"gh.pair.repair-authorize-result/1"}'
    )


def test_response_reader_accepts_fragmented_newline_frame() -> None:
    reader, writer = socket.socketpair()

    try:
        reader.settimeout(0.1)
        payload = _valid_repair_response()

        writer.sendall(payload[:17])
        writer.sendall(payload[17:] + b"\n")
        writer.shutdown(socket.SHUT_WR)

        frame = ipc._read_frame(
            reader,
            max_bytes=ipc.MAX_RESPONSE_BYTES,
            timeout_code="response_timeout",
            too_large_code="response_too_large",
            invalid_code="response_frame_invalid",
        )

        document = ipc._decode_response(
            frame,
            response_schema=(
                ipc.REPAIR_RESPONSE_SCHEMA
            ),
        )

        assert document["accepted"] is True
        assert (
            document["code"]
            == "repair_authorized"
        )

    finally:
        reader.close()
        writer.close()


def test_response_reader_accepts_valid_eof_frame() -> None:
    reader, writer = socket.socketpair()

    try:
        reader.settimeout(0.1)

        writer.sendall(
            _valid_repair_response()
        )
        writer.shutdown(
            socket.SHUT_WR
        )

        frame = ipc._read_frame(
            reader,
            max_bytes=ipc.MAX_RESPONSE_BYTES,
            timeout_code="response_timeout",
            too_large_code="response_too_large",
            invalid_code="response_frame_invalid",
        )

        document = ipc._decode_response(
            frame,
            response_schema=(
                ipc.REPAIR_RESPONSE_SCHEMA
            ),
        )

        assert document["accepted"] is True

    finally:
        reader.close()
        writer.close()


def test_response_reader_rejects_truncated_eof_json() -> None:
    reader, writer = socket.socketpair()

    try:
        reader.settimeout(0.1)

        writer.sendall(
            b'{"accepted":true'
        )
        writer.shutdown(
            socket.SHUT_WR
        )

        frame = ipc._read_frame(
            reader,
            max_bytes=ipc.MAX_RESPONSE_BYTES,
            timeout_code="response_timeout",
            too_large_code="response_too_large",
            invalid_code="response_frame_invalid",
        )

        with pytest.raises(
            PairingLocalIpcError,
            match="response_invalid",
        ):
            ipc._decode_response(
                frame,
                response_schema=(
                    ipc.REPAIR_RESPONSE_SCHEMA
                ),
            )

    finally:
        reader.close()
        writer.close()


def test_response_reader_rejects_oversize_timeout_and_second_frame() -> None:
    reader, writer = socket.socketpair()

    try:
        reader.settimeout(0.1)
        writer.sendall(
            b"x"
            * (
                ipc.MAX_RESPONSE_BYTES
                + 1
            )
        )

        with pytest.raises(
            PairingLocalIpcError,
            match="response_too_large",
        ):
            ipc._read_frame(
                reader,
                max_bytes=ipc.MAX_RESPONSE_BYTES,
                timeout_code="response_timeout",
                too_large_code="response_too_large",
                invalid_code="response_frame_invalid",
            )

    finally:
        reader.close()
        writer.close()

    reader, writer = socket.socketpair()

    try:
        reader.settimeout(0.01)

        with pytest.raises(
            PairingLocalIpcError,
            match="response_timeout",
        ):
            ipc._read_frame(
                reader,
                max_bytes=ipc.MAX_RESPONSE_BYTES,
                timeout_code="response_timeout",
                too_large_code="response_too_large",
                invalid_code="response_frame_invalid",
            )

    finally:
        reader.close()
        writer.close()

    reader, writer = socket.socketpair()

    try:
        reader.settimeout(0.1)
        writer.sendall(
            _valid_repair_response()
            + b"\n"
        )
        writer.sendall(
            b'{"accepted":false}'
        )
        writer.shutdown(socket.SHUT_WR)

        with pytest.raises(
            PairingLocalIpcError,
            match="response_frame_invalid",
        ):
            ipc._read_frame(
                reader,
                max_bytes=ipc.MAX_RESPONSE_BYTES,
                timeout_code="response_timeout",
                too_large_code="response_too_large",
                invalid_code="response_frame_invalid",
            )

    finally:
        reader.close()
        writer.close()

class RejectingRepairCoordinator(Coordinator):
    def authorize_repair(
        self,
        hardware_id: str,
        pairing_id: str,
    ) -> None:
        raise RuntimeError(
            "synthetic_repair_rejection"
        )


def test_repair_rejection_keeps_repair_response_schema() -> None:
    coordinator = RejectingRepairCoordinator()

    with tempfile.TemporaryDirectory(
        dir=SHORT_TEMP_ROOT
    ) as directory:
        socket_path = Path(directory) / "pairing.sock"
        server = ManagerOwnedPairingSocket(
            coordinator,
            socket_path,
        )
        server.start()

        try:
            result = authorize_repair_over_socket(
                socket_path,
                hardware_id=HARDWARE_ID,
                pairing_id=PAIRING_ID,
            )
        finally:
            server.stop()

    assert result == {
        "accepted": False,
        "code": "rejected",
        "schema": (
            "gh.pair.repair-authorize-result/1"
        ),
    }
