#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_execution_binding_contract_20260729_v1 as contract
import h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_physical_d2_wrapper_20260729_v1 as wrapper
import h3_n2_stage2d9r_g3r_prepare_transport_pacing_repair_20260729_v1 as pacing


class Handle:
    def __init__(self, *, short_at: int | None = None) -> None:
        self.short_at = short_at
        self.writes: list[bytes] = []
        self.flushes = 0

    def write(self, value: bytes) -> int:
        index = len(self.writes)
        self.writes.append(value)
        if self.short_at == index:
            return max(0, len(value) - 1)
        return len(value)

    def flush(self) -> None:
        self.flushes += 1

    def read(self, size: int) -> bytes:
        return b""


def session_class() -> type[object]:
    class Session:
        def __init__(self, handle: Handle) -> None:
            self._handle = handle

        def write(self, value: bytes) -> None:
            raise AssertionError("legacy burst write must be replaced")

    return Session


class BindingTests(unittest.TestCase):
    def test_decision_binding_and_frozen_predecessor(self) -> None:
        path = (
            ROOT
            / "docs/decisions/"
            "h3-n2-stage2d9r-g3r-d2-11-prepare-transport-pacing-"
            "execution-binding-20260729-v1.json"
        )
        value = json.loads(path.read_text(encoding="utf-8"))
        supplied = value.pop("decision_binding_sha256")
        self.assertEqual(contract.canonical_sha256(value), supplied)
        self.assertEqual(value["base_head_sha"], contract.BASE_HEAD_SHA)
        self.assertEqual(
            value["predecessor_terminal_result_sha256"],
            contract.D2_10_TERMINAL_RESULT_SHA256,
        )
        self.assertEqual(
            value["predecessor_locked_recovery_outcome"], "UNKNOWN"
        )
        self.assertFalse(value["replay_permitted"])

    def test_source_status_is_inert_and_unauthorized(self) -> None:
        status = wrapper.source_status()
        self.assertEqual(
            status["status"],
            "SOURCE_ONLY_REQUIRES_NEW_EXACT_D2_11_AUTHORIZATION",
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
        self.assertEqual(status["predecessor_locked_recovery_outcome"], "UNKNOWN")

    def test_paced_success_preserves_exact_bytes_once(self) -> None:
        cls = session_class()
        sleeps: list[float] = []
        wrapper._install_tracked_pacing(cls, sleep=sleeps.append)
        handle = Handle()
        session = cls(handle)
        command = pacing.PREPARE_SCHEMA + b"a" * 950 + b"\n"
        session.write(command)
        self.assertEqual(b"".join(handle.writes), command)
        self.assertEqual(max(map(len, handle.writes)), 64)
        self.assertEqual(handle.flushes, len(handle.writes))
        self.assertEqual(len(sleeps), len(handle.writes) - 1)
        self.assertTrue(all(value == 0.1 for value in sleeps))
        evidence = session._stage2d9r_transport_delivery_evidence
        self.assertEqual(evidence["command_sha256"], hashlib.sha256(command).hexdigest())
        self.assertTrue(evidence["exact_write_confirmed"])
        self.assertFalse(evidence["raw_command_included"])

    def test_short_write_fails_once_and_persists_redacted_leaf_evidence(self) -> None:
        cls = session_class()
        wrapper._install_tracked_pacing(cls, sleep=lambda _: None)
        handle = Handle(short_at=1)
        session = cls(handle)
        command = pacing.PREPARE_SCHEMA + b"b" * 200 + b"\n"
        with self.assertRaisesRegex(
            pacing.TransportRepairError, "SERIAL_COMMAND_SHORT_WRITE"
        ):
            session.write(command)
        self.assertEqual(len(handle.writes), 2)
        failure = session._stage2d9r_transport_delivery_failure
        self.assertEqual(failure["failure_code"], "SERIAL_COMMAND_SHORT_WRITE")
        self.assertEqual(failure["attempted_chunk_count"], 2)
        self.assertEqual(failure["completed_chunk_count"], 1)
        self.assertEqual(failure["failed_chunk_index"], 1)
        self.assertFalse(failure["exact_write_confirmed"])
        self.assertNotIn(command.decode("ascii"), json.dumps(failure))

    def test_transport_exception_text_is_never_persisted(self) -> None:
        private_path = "/" + "dev/" + "cu.private-device"

        class FailingHandle(Handle):
            def write(self, value: bytes) -> int:
                raise OSError(f"write failed on {private_path}")

        cls = session_class()
        wrapper._install_tracked_pacing(cls, sleep=lambda _: None)
        session = cls(FailingHandle())
        command = pacing.PREPARE_SCHEMA + b"private" + b"\n"
        with self.assertRaises(OSError):
            session.write(command)
        serialized = json.dumps(
            session._stage2d9r_transport_delivery_failure,
            sort_keys=True,
        )
        self.assertEqual(
            session._stage2d9r_transport_delivery_failure["failure_code"],
            "OSError",
        )
        self.assertNotIn(private_path, serialized)
        self.assertNotIn("write failed", serialized)
        self.assertNotIn(command.decode("ascii"), serialized)

    def test_delivery_controller_persists_success_and_result_binding(self) -> None:
        cls = session_class()
        wrapper._install_tracked_pacing(cls, sleep=lambda _: None)
        session = cls(Handle())
        command = pacing.VERIFY_SCHEMA + b"c" * 300 + b"\n"

        module = types.SimpleNamespace()
        module.canonical_sha256 = contract.canonical_sha256

        def wait_serial_line(
            device: str,
            expected: bytes,
            timeout: float,
            supplied: bytes | None,
            log_path: Path,
        ) -> bytes:
            assert supplied is not None
            session.write(supplied)
            return b"pass"

        module.wait_serial_line = wait_serial_line
        module.result_object = lambda **_: {"status": "CONSUMED_SUCCEEDED"}
        panic = types.SimpleNamespace(_current_session=lambda: session)
        with tempfile.TemporaryDirectory() as td:
            controller = wrapper.PacedDeliveryEvidenceController(
                module, panic, Path(td)
            )
            controller.install()
            self.assertEqual(
                module.wait_serial_line(
                    "/not/opened",
                    b"GH2D9R_VERIFY",
                    1.0,
                    command,
                    Path(td) / "serial.log",
                ),
                b"pass",
            )
            saved = json.loads(
                (Path(td) / "verify-transport-delivery.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(saved["status"], "DELIVERED")
            self.assertFalse(saved["raw_command_included"])
            result = module.result_object()
            self.assertEqual(
                result["verify_transport_delivery_sha256"],
                saved["delivery_evidence_sha256"],
            )
            self.assertFalse(result["transport_command_retry_added"])

    def test_delivery_controller_persists_failure_without_raw_command(self) -> None:
        cls = session_class()
        wrapper._install_tracked_pacing(cls, sleep=lambda _: None)
        session = cls(Handle(short_at=0))
        command = pacing.PREPARE_SCHEMA + b"d" * 100 + b"\n"
        module = types.SimpleNamespace()
        module.canonical_sha256 = contract.canonical_sha256
        module.ExecutionError = RuntimeError

        def wait_serial_line(
            device: str,
            expected: bytes,
            timeout: float,
            supplied: bytes | None,
            log_path: Path,
        ) -> bytes:
            assert supplied is not None
            session.write(supplied)
            raise AssertionError("unreachable")

        module.wait_serial_line = wait_serial_line
        module.result_object = lambda **_: {"status": "CONSUMED_FAILED"}
        panic = types.SimpleNamespace(_current_session=lambda: session)
        with tempfile.TemporaryDirectory() as td:
            controller = wrapper.PacedDeliveryEvidenceController(
                module, panic, Path(td)
            )
            controller.install()
            with self.assertRaisesRegex(
                RuntimeError, "SERIAL_COMMAND_SHORT_WRITE"
            ):
                module.wait_serial_line(
                    "/not/opened",
                    b"GH2D9R_PREPARE",
                    1.0,
                    command,
                    Path(td) / "serial.log",
                )
            saved_text = (
                Path(td) / "prepare-transport-delivery.json"
            ).read_text(encoding="utf-8")
            saved = json.loads(saved_text)
            self.assertEqual(saved["status"], "FAILED")
            self.assertEqual(
                saved["failure_code"], "SERIAL_COMMAND_SHORT_WRITE"
            )
            self.assertNotIn(command.decode("ascii"), saved_text)

    def test_missing_delivery_evidence_fails_closed(self) -> None:
        session = types.SimpleNamespace()
        command = pacing.PREPARE_SCHEMA + b"e" * 100 + b"\n"
        module = types.SimpleNamespace()
        module.canonical_sha256 = contract.canonical_sha256
        module.ExecutionError = RuntimeError
        module.wait_serial_line = lambda *args: b"unexpected-success"
        module.result_object = lambda **_: {"status": "CONSUMED_FAILED"}
        panic = types.SimpleNamespace(_current_session=lambda: session)
        with tempfile.TemporaryDirectory() as td:
            controller = wrapper.PacedDeliveryEvidenceController(
                module, panic, Path(td)
            )
            controller.install()
            with self.assertRaisesRegex(RuntimeError, "DELIVERY_EVIDENCE_MISSING"):
                module.wait_serial_line(
                    "/not/opened",
                    b"GH2D9R_PREPARE",
                    1.0,
                    command,
                    Path(td) / "serial.log",
                )
            saved = json.loads(
                (Path(td) / "prepare-transport-delivery.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(saved["status"], "NOT_DELIVERED")

    def test_terminalization_controller_is_constructed_and_installed_last(self) -> None:
        source = inspect.getsource(wrapper.configure_core)
        ordered = [
            "_install_tracked_pacing",
            "panic_controller.install()",
            "delivery_controller.install()",
            "terminalization.TerminalizationSafetyController",
            "terminal_controller.install()",
        ]
        positions = [source.index(token) for token in ordered]
        self.assertEqual(positions, sorted(positions))

    def test_old_d2_10_identifiers_are_explicitly_non_reusable(self) -> None:
        self.assertNotEqual(
            contract.D2_REQUEST_ID,
            contract.D2_10_ID,
        )
        self.assertNotEqual(
            contract.D2_10_REQUEST_BINDING_SHA256,
            contract.D2_10_TERMINAL_RESULT_SHA256,
        )
        self.assertNotEqual(
            contract.D2_10_AUTHORIZATION_RECORD_SHA256,
            contract.D2_10_TERMINAL_MARKER_SHA256,
        )


if __name__ == "__main__":
    unittest.main()
