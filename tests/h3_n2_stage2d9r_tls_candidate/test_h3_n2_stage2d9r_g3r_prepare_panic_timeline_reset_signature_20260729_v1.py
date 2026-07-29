#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

contract = importlib.import_module(
    "h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_contract_20260729_v1"
)
recorder = importlib.import_module(
    "h3_n2_stage2d9r_g3r_prepare_panic_timeline_recorder_20260729_v1"
)
wrapper = importlib.import_module(
    "h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_physical_d2_wrapper_20260729_v1"
)
serial_repair = importlib.import_module(
    "h3_n2_stage2d9r_serial_handshake_repair_20260727_v1"
)


class FakeHandle:
    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def write(self, value: bytes) -> None:
        self.writes.append(value)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        return None


class ScriptedRealtimeSession(recorder.RealtimeSerialCaptureSession):
    def __init__(self, waits, *, device="synthetic-device") -> None:
        super().__init__(device, 115200, serial_factory=lambda *args, **kwargs: FakeHandle())
        self.waits = list(waits)
        self._handle = FakeHandle()

    def wait_for_any(self, markers, timeout):
        if not self.waits:
            raise RuntimeError("UNEXPECTED_WAIT")
        marker, chunk = self.waits.pop(0)
        if chunk:
            self.ingest(chunk)
        if marker is not None:
            assert marker in markers
        return marker, self.snapshot()


class CoreWithoutHandshakeConstants:
    pass


class FakeRepaired:
    def __init__(self, session):
        self.module = CoreWithoutHandshakeConstants()
        self.session = session
        self.last_session = None
        self.open_calls = []

    def _open_session(self, *, replace):
        self.open_calls.append(replace)
        if self.session is None:
            raise RuntimeError("SYNTHETIC_SESSION_MISSING")


PANIC_REPORT = (
    b"ESP-ROM:esp32c6-test\n"
    b"rst:0xc (SW_CPU),boot:0x13\n"
    b"Guru Meditation Error: Core  0 panic'ed (Load access fault).\n"
    b"Core  0 register dump:\n"
    b"MEPC    : 0x42001234    RA      : 0x42005678\n"
    b"Saved PC: 0x40000010\n"
    b"Stack memory:\n"
    b"Rebooting...\n"
)


class PreparePanicTimelineRepairTests(unittest.TestCase):
    def make_controller(self, waits):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name) / "evidence"
        session = ScriptedRealtimeSession(waits)
        repaired = FakeRepaired(session)
        controller = wrapper.PanicTimelineEvidenceExecutionController(repaired, root)
        controller._test_temp = temp
        return controller, session, root

    def assert_error_code(self, callable_obj, expected):
        with self.assertRaises(wrapper.core.ExecutionError) as context:
            callable_obj()
        self.assertEqual(str(context.exception), expected)

    def test_01_successor_identity_and_terminal_predecessor(self):
        self.assertTrue(contract.REQUEST_09_ID.endswith("-09"))
        self.assertTrue(contract.D2_08_ID.endswith("-08"))
        self.assertEqual(contract.D2_08_STATUS, "CONSUMED_FAILED")
        self.assertEqual(contract.D2_08_FAILURE_CODE, "PREPARE_RESULT_TIMEOUT")
        self.assertEqual(contract.D2_08_CLASSIFICATION, "SERIAL_RESET")

    def test_02_source_modules_are_inert(self):
        for name in (
            "h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_contract_20260729_v1.py",
            "h3_n2_stage2d9r_g3r_prepare_panic_timeline_recorder_20260729_v1.py",
            "h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_physical_d2_wrapper_20260729_v1.py",
        ):
            result = subprocess.run(
                [sys.executable, str(TOOLS / name)],
                check=True,
                capture_output=True,
                text=True,
            )
            value = json.loads(result.stdout)
            self.assertFalse(value.get("physical_authorization_created", value.get("authorization_created")))
            self.assertFalse(value["board_operation"])
            self.assertFalse(value["network_operation"])

    def test_03_byte_receipt_timestamps_and_phase_partition(self):
        session = recorder.RealtimeSerialCaptureSession(
            "synthetic", 115200, serial_factory=lambda *args, **kwargs: FakeHandle()
        )
        session.ingest(b"startup line\n", at="2026-07-29T00:00:00Z", monotonic_ns=100, phase="startup")
        session.ingest(
            b"stage2d9r_command_ready=PREPARE\n",
            at="2026-07-29T00:00:01Z",
            monotonic_ns=200,
            phase="ready_observed",
        )
        session.ingest(b"post command\n", at="2026-07-29T00:00:02Z", monotonic_ns=300, phase="post_command")
        events = session.line_events()
        self.assertEqual([event["monotonic_ns"] for event in events], [100, 200, 300])
        self.assertEqual([event["phase"] for event in events], ["startup", "ready_observed", "post_command"])

    def test_04_one_panic_report_yields_one_reset_signature(self):
        session = recorder.RealtimeSerialCaptureSession(
            "synthetic", 115200, serial_factory=lambda *args, **kwargs: FakeHandle()
        )
        session.ingest(PANIC_REPORT, at="2026-07-29T00:00:03Z", monotonic_ns=400, phase="post_command")
        signatures = session.reset_signatures()
        self.assertEqual(len(signatures), 1)
        signature = signatures[0]
        self.assertTrue(signature["post_command"])
        self.assertEqual(signature["core"], 0)
        self.assertEqual(signature["mepc"], "0x42001234")
        self.assertEqual(signature["ra"], "0x42005678")
        self.assertEqual(signature["saved_pc"], "0x40000010")
        self.assertIn("SW_CPU", signature["reset_reason"])
        self.assertTrue(signature["reboot_marker_observed"])

    def test_05_two_boots_yield_two_reset_events_not_line_count(self):
        session = recorder.RealtimeSerialCaptureSession(
            "synthetic", 115200, serial_factory=lambda *args, **kwargs: FakeHandle()
        )
        session.ingest(PANIC_REPORT, at="2026-07-29T00:00:03Z", monotonic_ns=400, phase="post_command")
        session.ingest(PANIC_REPORT, at="2026-07-29T00:00:04Z", monotonic_ns=500, phase="post_command")
        signatures = session.reset_signatures()
        self.assertEqual(len(signatures), 2)
        self.assertEqual([value["cycle_index"] for value in signatures], [1, 2])
        with tempfile.TemporaryDirectory() as td:
            manifest = session.persist_evidence(
                Path(td), controller_timeline=[], classification="SERIAL_RESET", terminal=True
            )
            self.assertEqual(manifest["reset_loop_count"], 2)
            self.assertEqual(manifest["post_command_reset_count"], 2)

    def test_06_precommand_reset_does_not_misclassify_postcommand_timeout(self):
        ready = b"stage2d9r_command_ready=PREPARE"
        controller, session, root = self.make_controller([
            (ready, ready + b"\n"),
            (None, b""),
            (None, b""),
        ])
        session.ingest(PANIC_REPORT, at="2026-07-29T00:00:00Z", monotonic_ns=10, phase="startup")
        self.assert_error_code(
            lambda: controller.wait_serial_line(
                "synthetic-device", ready, 1.0, b"cmd\n", root / "capture.log"
            ),
            serial_repair.RESULT_TIMEOUT_CODES[ready],
        )
        self.assertEqual(controller._classification(), "NO_RESULT")

    def test_07_command_post_panic_loop_classifies_serial_reset(self):
        ready = b"stage2d9r_command_ready=PREPARE"
        controller, session, root = self.make_controller([
            (ready, ready + b"\n"),
            (None, PANIC_REPORT),
            (None, b""),
        ])
        self.assert_error_code(
            lambda: controller.wait_serial_line(
                "synthetic-device", ready, 1.0, b"cmd\n", root / "capture.log"
            ),
            serial_repair.RESULT_TIMEOUT_CODES[ready],
        )
        self.assertEqual(controller._classification(), "SERIAL_RESET")
        self.assertEqual(len(session._handle.writes), 1)
        self.assertEqual(len(session.reset_signatures()), 1)
        kinds = [event["kind"] for event in controller.journal.timeline]
        self.assertIn("PREPARE_READY_MARKER_OBSERVED", kinds)
        self.assertIn("PREPARE_COMMAND_SENT", kinds)
        self.assertIn("PREPARE_LATE_WINDOW_STARTED", kinds)
        self.assertIn("PREPARE_RESULT_TIMEOUT", kinds)

    def test_08_ready_and_result_pass_remains_success(self):
        ready = b"stage2d9r_command_ready=PREPARE"
        passed = serial_repair.RESULT_MARKERS[ready]
        controller, session, root = self.make_controller([
            (ready, ready + b"\n"),
            (passed, passed + b"\n"),
        ])
        value = controller.wait_serial_line(
            "synthetic-device", ready, 1.0, b"cmd\n", root / "capture.log"
        )
        self.assertIn(passed, value)
        self.assertEqual(controller._classification(), "PREPARE_PASS")
        self.assertEqual(session._handle.writes, [b"cmd\n"])

    def test_09_realtime_evidence_files_and_permissions(self):
        session = recorder.RealtimeSerialCaptureSession(
            "synthetic", 115200, serial_factory=lambda *args, **kwargs: FakeHandle()
        )
        session.ingest(PANIC_REPORT, phase="post_command")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "evidence"
            manifest = session.persist_evidence(
                root, controller_timeline=[{"kind": "PREPARE_COMMAND_SENT"}],
                classification="SERIAL_RESET", terminal=True,
            )
            for name in (
                recorder.REALTIME_SERIAL_FILE,
                recorder.RESET_SIGNATURE_FILE,
                recorder.REALTIME_TIMELINE_FILE,
                recorder.MANIFEST_FILE,
            ):
                path = root / name
                self.assertTrue(path.is_file())
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            self.assertFalse(manifest["real_board_evidence_in_public_artifact"])

    def test_10_command_material_is_not_retained(self):
        session = recorder.RealtimeSerialCaptureSession(
            "synthetic", 115200, serial_factory=lambda *args, **kwargs: FakeHandle()
        )
        session.ingest(
            b"GH2D9R_PREPARE_V1 " + b"sec" + b"ret=" + b"synthetic-" + b"private-value\n",
            phase="post_command",
        )
        serialized = json.dumps(session.line_events(), sort_keys=True)
        self.assertNotIn("synthetic-" + "private-value", serialized)
        self.assertIn("COMMAND_MATERIAL_REDACTED", serialized)

    def test_11_package_and_request_when_artifact_supplied(self):
        artifact = os.environ.get("PR202_REVIEW_ARTIFACT")
        if not artifact:
            self.skipTest("PR202_REVIEW_ARTIFACT not supplied")
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "review"
            subprocess.run([
                sys.executable,
                str(TOOLS / "h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_packager_20260729_v1.py"),
                "--source-root", str(ROOT),
                "--upstream-artifact", artifact,
                "--source-sha", "5" * 40,
                "--output", str(output),
            ], check=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            package = output / "prepare-panic-timeline-reset-signature-physical-d2-execution-package"
            request = json.loads((output / "PHYSICAL_D2_REQUEST_09.json").read_text())
            contract.validate_physical_request(request, package)
            self.assertFalse(request["authorized"])
            self.assertEqual(request["predecessor_evidence_classification"], "SERIAL_RESET")
            self.assertTrue(request["realtime_byte_receipt_timestamps"])
            self.assertTrue(request["one_reset_event_per_boot"])

    def test_12_synthetic_authorization_and_predecessor_rejection(self):
        artifact = os.environ.get("PR202_REVIEW_ARTIFACT")
        if not artifact:
            self.skipTest("PR202_REVIEW_ARTIFACT not supplied")
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "review"
            subprocess.run([
                sys.executable,
                str(TOOLS / "h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_packager_20260729_v1.py"),
                "--source-root", str(ROOT),
                "--upstream-artifact", artifact,
                "--source-sha", "6" * 40,
                "--output", str(output),
            ], check=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True)
            package = output / "prepare-panic-timeline-reset-signature-physical-d2-execution-package"
            request = json.loads((output / "PHYSICAL_D2_REQUEST_09.json").read_text())
            now = datetime.now(timezone.utc)
            authorization = {
                **contract.authorization_contract_required(request, package),
                "authorized": True,
                "one_shot": True,
                "replay_permitted": False,
                "automatic_retry_permitted": False,
                "activate_authorized": False,
                "cleanup_authorized": False,
                "issued_at": now.isoformat().replace("+00:00", "Z"),
                "expires_at": (now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
            }
            authorization["authorization_record_sha256"] = contract.canonical_sha256(authorization)
            contract.validate_authorization_contract(authorization, request, package, now=now)
            wrong = dict(authorization)
            wrong["d2_request_id"] = contract.D2_08_ID
            without = dict(wrong)
            without.pop("authorization_record_sha256", None)
            wrong["authorization_record_sha256"] = contract.canonical_sha256(without)
            with self.assertRaises(contract.ContractError):
                contract.validate_authorization_contract(wrong, request, package, now=now)


if __name__ == "__main__":
    unittest.main()
