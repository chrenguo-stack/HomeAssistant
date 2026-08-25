from __future__ import annotations

import base64
import socket
import tempfile
from pathlib import Path

import pytest

from greenhouse_manager.ops.n3w_pairing_cli import parser
from greenhouse_manager.runtime.n3w_pairing_local_ipc import (
    ManagerOwnedPairingSocket,
    PairingLocalIpcError,
    import_setup_secret_over_socket,
)

HARDWARE_ID = "ghw-c6-aabbccddeeff"
PAIRING_ID = "ba999b15-e74f-4ef5-bad7-8dcd62c13d66"
SECRET = base64.urlsafe_b64encode(bytes(range(32))).rstrip(b"=").decode()


class Coordinator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bytes]] = []

    def import_setup_secret(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        setup_secret: bytes,
    ) -> None:
        self.calls.append((hardware_id, pairing_id, setup_secret))


def test_manager_owned_socket_imports_without_staging_file() -> None:
    coordinator = Coordinator()
    with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
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
    with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
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
