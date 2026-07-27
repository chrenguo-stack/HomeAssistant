#!/usr/bin/env python3
from __future__ import annotations

from collections import deque
import importlib.util
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/h3_n2_stage2d9r_serial_handshake_repair_20260727_v1.py"
COMPONENT = (
    ROOT
    / "firmware/esphome_rc/components/greenhouse_profile_isolated_device_g3r_ready_repeater"
)
CPP_PATH = COMPONENT / "stage2d9r_g3r_ready_repeater_20260727_v1.cpp"
HEADER_PATH = COMPONENT / "stage2d9r_g3r_ready_repeater_20260727_v1.h"
INIT_PATH = COMPONENT / "__init__.py"
FROZEN_V1_HEADER = (
    ROOT
    / "firmware/esphome_rc/components/greenhouse_profile_isolated_device_g3r_executor"
    / "stage2d9r_g3r_prepare_executor_20260723_v1.h"
)
REPAIR_CONFIG = (
    ROOT
    / "firmware/esphome_rc/board_lab/h3_profile_isolated_device_g3r_tls_prepare"
    / "greenhouse_profile_isolated_device_g3r_serial_handshake_repair_20260727_v2.yml"
)


def load_module():
    spec = importlib.util.spec_from_file_location("stage2d9r_handshake_repair", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REPAIR = load_module()


class FakeExecutionError(RuntimeError):
    pass


class FakeSerial:
    def __init__(self, factory, device, baud, timeout, write_timeout):
        self.factory = factory
        self.device = device
        self.baud = baud
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.closed = False
        self.factory.events.append("serial_open")

    def read(self, size):
        if self.closed:
            raise OSError("closed")
        if self.factory.chunks:
            return self.factory.chunks.popleft()
        time.sleep(0.005)
        return b""

    def write(self, value):
        self.factory.events.append("serial_write")
        self.factory.writes.append(value)
        return len(value)

    def flush(self):
        self.factory.events.append("serial_flush")

    def close(self):
        self.closed = True
        self.factory.events.append("serial_close")


class FakeSerialFactory:
    def __init__(self, chunks=()):
        self.chunks = deque(chunks)
        self.events = []
        self.writes = []

    def __call__(self, device, baud, timeout, write_timeout):
        return FakeSerial(self, device, baud, timeout, write_timeout)


class HandshakeRepairTests(unittest.TestCase):
    def fake_module(self, factory):
        events = factory.events

        def select_serial(_authorization):
            return types.SimpleNamespace(device="/dev/test-c6")

        def start_broker(_mosquitto, _private, _log):
            events.append("broker_start")
            return object()

        def stop_broker(_process):
            events.append("broker_stop")

        return types.SimpleNamespace(
            select_serial=select_serial,
            start_broker=start_broker,
            stop_broker=stop_broker,
            wait_serial_line=lambda *_args, **_kwargs: None,
            SERIAL_BAUD=115200,
            SERIAL_PASS_TIMEOUT_S=0.05,
            ExecutionError=FakeExecutionError,
        )

    def test_firmware_repeats_prepare_and_verify_ready_markers(self):
        cpp = CPP_PATH.read_text(encoding="utf-8")
        header = HEADER_PATH.read_text(encoding="utf-8")
        init = INIT_PATH.read_text(encoding="utf-8")
        config = REPAIR_CONFIG.read_text(encoding="utf-8")
        self.assertIn("repeat_interval_ms_{1000}", header)
        self.assertIn("repeat_window_ms_{180000}", header)
        self.assertIn("stage2d9r_command_ready=PREPARE", cpp)
        self.assertIn("stage2d9r_command_ready=VERIFY", cpp)
        self.assertIn("stage2d9r_ready_repeat=true", cpp)
        self.assertIn("Stage2D9RG3RReadyRepeaterV1", init)
        self.assertIn("greenhouse_profile_isolated_device_g3r_executor:", config)
        self.assertIn("greenhouse_profile_isolated_device_g3r_ready_repeater:", config)
        self.assertIn("final : public Component", FROZEN_V1_HEADER.read_text())
        self.assertNotIn("write_flash", cpp)
        self.assertNotIn("nvs_set_", cpp)

    def test_serial_capture_is_open_before_broker_start(self):
        factory = FakeSerialFactory()
        module = self.fake_module(factory)
        controller = REPAIR.install_repaired_handshake(
            module, serial_factory=factory
        )
        controller.select_serial({})
        controller.start_broker(Path("mosquitto"), Path("private"), Path("broker.log"))
        self.assertLess(
            factory.events.index("serial_open"),
            factory.events.index("broker_start"),
        )
        controller.stop_broker(object())

    def test_prepare_ready_timeout_retains_redacted_transcript(self):
        factory = FakeSerialFactory(
            [b"booting\nGH2D9R_PREPARE_V1 secret material\n"]
        )
        module = self.fake_module(factory)
        controller = REPAIR.install_repaired_handshake(
            module, serial_factory=factory
        )
        controller.select_serial({})
        controller.start_broker(Path("mosquitto"), Path("private"), Path("broker.log"))
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "prepare.log"
            with self.assertRaisesRegex(
                FakeExecutionError, "PREPARE_READY_MARKER_TIMEOUT"
            ):
                controller.wait_serial_line(
                    "/dev/test-c6",
                    b"stage2d9r_command_ready=PREPARE",
                    0.05,
                    b"GH2D9R_PREPARE_V1 private-command\n",
                    log,
                )
            transcript = log.read_bytes()
            self.assertIn(b"booting", transcript)
            self.assertIn(b"[REDACTED_COMMAND_MATERIAL]", transcript)
            self.assertNotIn(b"secret material", transcript)
            self.assertEqual(log.stat().st_mode & 0o777, 0o600)
        controller.stop_broker(object())

    def test_prepare_result_timeout_is_distinct_and_retained(self):
        factory = FakeSerialFactory(
            [b"stage2d9r_command_ready=PREPARE expected_schema=GH2D9R_PREPARE_V1\n"]
        )
        module = self.fake_module(factory)
        controller = REPAIR.install_repaired_handshake(
            module, serial_factory=factory
        )
        controller.select_serial({})
        controller.start_broker(Path("mosquitto"), Path("private"), Path("broker.log"))
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "prepare.log"
            with self.assertRaisesRegex(FakeExecutionError, "PREPARE_RESULT_TIMEOUT"):
                controller.wait_serial_line(
                    "/dev/test-c6",
                    b"stage2d9r_command_ready=PREPARE",
                    0.1,
                    b"GH2D9R_PREPARE_V1 private-command\n",
                    log,
                )
            self.assertEqual(factory.writes, [b"GH2D9R_PREPARE_V1 private-command\n"])
            self.assertIn(b"stage2d9r_command_ready=PREPARE", log.read_bytes())
        controller.stop_broker(object())

    def test_verify_ready_timeout_has_verify_specific_code(self):
        factory = FakeSerialFactory()
        module = self.fake_module(factory)
        controller = REPAIR.install_repaired_handshake(
            module, serial_factory=factory
        )
        controller.select_serial({})
        controller.start_broker(Path("mosquitto"), Path("private"), Path("broker.log"))
        controller.select_serial({})
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "verify.log"
            with self.assertRaisesRegex(
                FakeExecutionError, "VERIFY_READY_MARKER_TIMEOUT"
            ):
                controller.wait_serial_line(
                    "/dev/test-c6",
                    b"stage2d9r_command_ready=VERIFY",
                    0.05,
                    b"GH2D9R_VERIFY_V1 private-command\n",
                    log,
                )
            self.assertTrue(log.is_file())
        controller.stop_broker(object())

    def test_source_module_is_inert_without_new_exact_d2_package(self):
        self.assertEqual(
            REPAIR.SOURCE_STATE,
            "SOURCE_ONLY_REQUIRES_NEW_EXACT_D2_PACKAGE",
        )


if __name__ == "__main__":
    unittest.main()
