#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import h3_n2_stage2d9r_g3r_prepare_transport_pacing_repair_20260729_v1 as repair


def prepare_command(size: int = 1025) -> bytes:
    prefix = b"GH2D9R_PREPARE_V1 "
    return prefix + b"a" * (size - len(prefix) - 1) + b"\n"


class BufferedDevice:
    """256-byte RX ring with a 128-byte consumer between paced host writes."""

    def __init__(self, capacity: int = 256, drain: int = 128) -> None:
        self.capacity = capacity
        self.drain = drain
        self.ring = bytearray()
        self.received = bytearray()
        self.writes: list[bytes] = []
        self.flushes = 0

    def write(self, value: bytes) -> int:
        self.writes.append(value)
        available = self.capacity - len(self.ring)
        self.ring.extend(value[:available])
        return len(value)

    def flush(self) -> None:
        self.flushes += 1

    def device_loop(self, _: float) -> None:
        consumed = self.ring[: self.drain]
        del self.ring[: self.drain]
        self.received.extend(consumed)

    def finish(self) -> bytes:
        self.received.extend(self.ring)
        self.ring.clear()
        return bytes(self.received)


class ShortWriteHandle(BufferedDevice):
    def write(self, value: bytes) -> int:
        super().write(value)
        return max(0, len(value) - 1)


class Session:
    def __init__(self, handle: object) -> None:
        self._handle = handle

    def write(self, value: bytes) -> None:
        raise AssertionError("legacy write must be replaced")


class TransportRepairTests(unittest.TestCase):
    def test_d2_10_legacy_burst_reproduces_missing_terminator(self) -> None:
        command = prepare_command()
        device = BufferedDevice()
        device.write(command)
        device.flush()
        observed = device.finish()
        self.assertEqual(len(observed), 256)
        self.assertNotIn(b"\n", observed)
        self.assertNotEqual(observed, command)

    def test_paced_delivery_preserves_exact_command_once(self) -> None:
        command = prepare_command()
        device = BufferedDevice()
        evidence = repair.write_command_paced(
            device,
            command,
            sleep=device.device_loop,
        )
        observed = device.finish()
        self.assertEqual(observed, command)
        self.assertEqual(b"".join(device.writes), command)
        self.assertEqual(command.count(b"\n"), 1)
        self.assertEqual(evidence.command_bytes, len(command))
        self.assertEqual(evidence.chunk_bytes, 64)
        self.assertTrue(evidence.exact_write_confirmed)
        self.assertFalse(evidence.raw_command_included)

    def test_short_write_fails_closed_without_retry(self) -> None:
        device = ShortWriteHandle()
        with self.assertRaisesRegex(
            repair.TransportRepairError,
            "SERIAL_COMMAND_SHORT_WRITE",
        ):
            repair.write_command_paced(
                device,
                prepare_command(),
                sleep=device.device_loop,
            )
        self.assertEqual(len(device.writes), 1)

    def test_framing_and_size_contracts_fail_closed(self) -> None:
        invalid = (
            b"GH2D9R_PREPARE_V1 no-newline",
            b"GH2D9R_PREPARE_V1 two\nlines\n",
            b"UNKNOWN value\n",
            b"GH2D9R_PREPARE_V1 " + b"a" * repair.MAX_COMMAND_BYTES + b"\n",
        )
        for command in invalid:
            with self.subTest(command=command[:32]):
                with self.assertRaises(repair.TransportRepairError):
                    repair.validate_command(command)

    def test_install_is_explicit_and_records_only_public_evidence(self) -> None:
        original = repair.install_on_session_class(
            Session,
            sleep=lambda _: None,
        )
        device = BufferedDevice(capacity=8192)
        session = Session(device)
        command = prepare_command()
        session.write(command)
        self.assertEqual(device.finish(), command)
        evidence = session._stage2d9r_transport_delivery_evidence
        self.assertEqual(evidence["command_bytes"], len(command))
        self.assertNotIn(command.decode(), str(evidence))
        self.assertEqual(original.__name__, "write")
        with self.assertRaisesRegex(
            repair.TransportRepairError,
            "TRANSPORT_REPAIR_ALREADY_INSTALLED",
        ):
            repair.install_on_session_class(Session)

    def test_source_status_is_inert(self) -> None:
        status = repair.source_status()
        self.assertEqual(
            status["status"],
            "SOURCE_ONLY_REQUIRES_NEW_EXACT_D2_EXECUTION_BINDING",
        )
        for key in (
            "physical_request_created",
            "physical_authorization_created",
            "board_operation",
            "usb_enumeration",
            "serial_operation",
            "esptool_operation",
            "flash_operation",
            "network_operation",
        ):
            self.assertFalse(status[key])

    def test_minimum_prepare_command_exceeds_default_rx_buffer(self) -> None:
        schema = len("GH2D9R_PREPARE_V1")
        minimum_base64url_ca = (repair.MIN_CA_PEM_BYTES * 8 + 5) // 6
        minimum = schema + 8 + (5 * 64) + minimum_base64url_ca + 7 + 1
        self.assertEqual(minimum, 695)
        self.assertGreater(
            minimum,
            repair.USB_SERIAL_JTAG_DEFAULT_RX_BYTES,
        )


if __name__ == "__main__":
    unittest.main()
