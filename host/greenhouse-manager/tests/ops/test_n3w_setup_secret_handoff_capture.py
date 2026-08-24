from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path

from greenhouse_manager.ops import n3w_setup_secret_handoff_capture as capture

HARDWARE_ID = "ghw-c6-98a316a9f350"
PAIRING_ID = "pairing-public-identifier"
PAIRING_SHA256 = hashlib.sha256(PAIRING_ID.encode("ascii")).hexdigest()
SETUP_SECRET = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


class FakeSerial:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self._chunks = [
            b"boot log without private fields\n",
            f"GHN3W2:{HARDWARE_ID}:{PAIRING_ID}:{SETUP_SECRET}\n".encode(),
        ]

    def __enter__(self) -> FakeSerial:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int) -> bytes:
        return self._chunks.pop(0) if self._chunks else b""


def _private_directory(tmp_path: Path) -> Path:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    return directory


def test_cli_call_chain_writes_bound_mode_0600_handoff_without_logging_secret(
    tmp_path: Path, capsys: object
) -> None:
    output = _private_directory(tmp_path) / "handoff.private.json"

    result = capture.main(
        [
            "--port",
            "/dev/fixture",
            "--output",
            str(output),
            "--expected-hardware-id",
            HARDWARE_ID,
            "--expected-pairing-id-sha256",
            PAIRING_SHA256,
        ],
        serial_factory=FakeSerial,
    )

    assert result == 0
    document = json.loads(output.read_text())
    assert document == {
        "schema": "gh.pair.setup-secret-import/1",
        "hardware_id": HARDWARE_ID,
        "pairing_id": PAIRING_ID,
        "setup_secret": SETUP_SECRET,
    }
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    stdout = capsys.readouterr().out
    assert "PRIVATE_PAIRING_PAYLOAD=CAPTURED" in stdout
    assert "SECRET_VALUE_EXPOSED=false" in stdout
    assert PAIRING_ID not in stdout
    assert SETUP_SECRET not in stdout


def test_cli_fails_closed_on_pairing_binding_mismatch(tmp_path: Path, capsys: object) -> None:
    output = _private_directory(tmp_path) / "handoff.private.json"

    result = capture.main(
        [
            "--port",
            "/dev/fixture",
            "--output",
            str(output),
            "--expected-hardware-id",
            HARDWARE_ID,
            "--expected-pairing-id-sha256",
            "0" * 64,
        ],
        serial_factory=FakeSerial,
    )

    assert result == 1
    assert not output.exists()
    stdout = capsys.readouterr().out
    assert "CAPTURE_RESULT=FAIL:PAIRING_ID_BINDING_MISMATCH" in stdout
    assert PAIRING_ID not in stdout
    assert SETUP_SECRET not in stdout


def test_cli_rejects_nonprivate_parent_before_opening_serial(
    tmp_path: Path, capsys: object
) -> None:
    tmp_path.chmod(0o755)
    output = tmp_path / "handoff.private.json"

    result = capture.main(
        [
            "--port",
            "/dev/fixture",
            "--output",
            str(output),
            "--expected-hardware-id",
            HARDWARE_ID,
            "--expected-pairing-id-sha256",
            PAIRING_SHA256,
        ],
        serial_factory=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("serial must not be opened")
        ),
    )

    assert result == 1
    assert not output.exists()
    assert "CAPTURE_RESULT=FAIL:OUTPUT_PARENT_NOT_PRIVATE" in capsys.readouterr().out


def test_cli_refuses_to_overwrite_existing_output(tmp_path: Path, capsys: object) -> None:
    output = _private_directory(tmp_path) / "handoff.private.json"
    output.write_text("sentinel")

    result = capture.main(
        [
            "--port",
            "/dev/fixture",
            "--output",
            str(output),
            "--expected-hardware-id",
            HARDWARE_ID,
            "--expected-pairing-id-sha256",
            PAIRING_SHA256,
        ],
        serial_factory=FakeSerial,
    )

    assert result == 1
    assert output.read_text() == "sentinel"
    assert "CAPTURE_RESULT=FAIL:OUTPUT_ALREADY_EXISTS" in capsys.readouterr().out
