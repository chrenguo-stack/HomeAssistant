from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path

import pytest

from greenhouse_manager.ops import n3w_setup_secret_handoff_capture as capture

HARDWARE_ID = "ghw-c6-98a316a9f350"
PAIRING_ID = "pairing-public-identifier"
PAIRING_SHA256 = hashlib.sha256(PAIRING_ID.encode("ascii")).hexdigest()
SETUP_SECRET = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


class FakeSerial:
    instances: list[FakeSerial] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args, self.kwargs = args, kwargs
        self.port = None
        self.rtscts = True
        self.dsrdtr = True
        self.dtr = True
        self.rts = True
        self.is_open = False
        self.open_count = 0
        self.events: list[tuple[str, object]] = []
        self._chunks = [b"boot log\n", f"GHN3W2:{HARDWARE_ID}:{PAIRING_ID}:{SETUP_SECRET}\n".encode()]
        FakeSerial.instances.append(self)

    def open(self) -> None:
        self.events.append(("open", (self.rtscts, self.dsrdtr, self.dtr, self.rts)))
        self.open_count += 1
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def __enter__(self) -> FakeSerial:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def read(self, size: int) -> bytes:
        return self._chunks.pop(0) if self._chunks else b""


@pytest.fixture(autouse=True)
def reset_instances() -> None:
    FakeSerial.instances.clear()


def _private_directory(tmp_path: Path) -> Path:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    return directory


def _argv(output: Path, *, ack: bool = True) -> list[str]:
    args = [
        "--port", "/dev/fixture", "--output", str(output),
        "--expected-hardware-id", HARDWARE_ID,
        "--expected-pairing-id-sha256", PAIRING_SHA256,
    ]
    if ack:
        args.append("--ack-live-serial-open-risk")
    return args


def test_preopen_control_line_policy_and_single_open(tmp_path: Path, capsys: object) -> None:
    output = _private_directory(tmp_path) / "handoff.private.json"
    assert capture.main(_argv(output), serial_factory=FakeSerial) == 0
    device = FakeSerial.instances[0]
    assert device.events == [("open", (False, False, False, False))]
    assert device.open_count == 1
    assert json.loads(output.read_text())["hardware_id"] == HARDWARE_ID
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    stdout = capsys.readouterr().out
    assert PAIRING_ID not in stdout and SETUP_SECRET not in stdout
    assert "SERIAL_OPEN_NO_RESET_PROVEN=true" not in stdout


def test_default_invocation_fails_before_serial_open(tmp_path: Path, capsys: object) -> None:
    output = _private_directory(tmp_path) / "handoff.private.json"
    assert capture.main(_argv(output, ack=False), serial_factory=FakeSerial) == 1
    assert FakeSerial.instances == []
    assert "LIVE_SERIAL_OPEN_RISK_ACK_REQUIRED" in capsys.readouterr().out


def test_pairing_binding_mismatch_is_fail_closed(tmp_path: Path, capsys: object) -> None:
    output = _private_directory(tmp_path) / "handoff.private.json"
    args = _argv(output)
    args[-2] = "0" * 64
    assert capture.main(args, serial_factory=FakeSerial) == 1
    assert not output.exists()
    assert "PAIRING_ID_BINDING_MISMATCH" in capsys.readouterr().out


def test_identity_mismatch_is_fail_closed(tmp_path: Path) -> None:
    class WrongIdentity(FakeSerial):
        def read(self, size: int) -> bytes:
            return b"GHN3W2:wrong-id:pairing-public-identifier:" + SETUP_SECRET.encode() + b"\n"

    output = _private_directory(tmp_path) / "handoff.private.json"
    assert capture.main(_argv(output), serial_factory=WrongIdentity) == 1
    assert not output.exists()


@pytest.mark.parametrize("bad", ["nonprivate", "existing"])
def test_output_guards_precede_serial_open(tmp_path: Path, capsys: object, bad: str) -> None:
    directory = _private_directory(tmp_path)
    output = directory / "handoff.private.json"
    if bad == "nonprivate":
        directory.chmod(0o755)
    else:
        output.write_text("sentinel")
    assert capture.main(_argv(output), serial_factory=FakeSerial) == 1
    assert FakeSerial.instances == []
    assert (output.read_text() if output.exists() else "") != ("" if bad == "existing" else "x")
