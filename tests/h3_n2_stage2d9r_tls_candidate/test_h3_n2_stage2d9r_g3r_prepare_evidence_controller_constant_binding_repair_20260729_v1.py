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
    "h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_contract_20260729_v1"
)
wrapper = importlib.import_module(
    "h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_physical_d2_wrapper_20260729_v1"
)
serial_repair = importlib.import_module(
    "h3_n2_stage2d9r_serial_handshake_repair_20260727_v1"
)


class FakeSession:
    def __init__(self, waits, *, device="synthetic-device", snapshot=b"") -> None:
        self.device = device
        self.waits = list(waits)
        self.writes = []
        self.snapshot_value = snapshot
        self.persisted = []

    def wait_for_any(self, markers, timeout):
        if not self.waits:
            raise RuntimeError("UNEXPECTED_WAIT")
        value = self.waits.pop(0)
        if isinstance(value, BaseException):
            raise value
        marker, captured = value
        if marker is not None:
            assert marker in markers
        self.snapshot_value = captured
        return marker, captured

    def write(self, value):
        self.writes.append(value)

    def snapshot(self):
        return self.snapshot_value

    def persist_redacted(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.snapshot_value)
        self.persisted.append(path)


class CoreWithoutHandshakeConstants:
    pass


class FakeRepaired:
    def __init__(self, session):
        self.module = CoreWithoutHandshakeConstants()
        self.session = session
        self.open_calls = []

    def _open_session(self, *, replace):
        self.open_calls.append(replace)
        if self.session is None:
            raise RuntimeError("SYNTHETIC_SESSION_MISSING")


class ControllerConstantBindingRepairTests(unittest.TestCase):
    def make_controller(self, waits):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name) / "evidence"
        session = FakeSession(waits)
        repaired = FakeRepaired(session)
        controller = wrapper.ConstantBindingRepairEvidenceExecutionController(repaired, root)
        controller._test_temp = temp
        return controller, session, root

    def assert_error_code(self, callable_obj, expected):
        with self.assertRaises(wrapper.core.ExecutionError) as context:
            callable_obj()
        self.assertEqual(str(context.exception), expected)

    def test_01_successor_and_predecessor_identity(self):
        self.assertTrue(contract.REQUEST_08_ID.endswith("-08"))
        self.assertTrue(contract.D2_07_ID.endswith("-07"))
        self.assertEqual(contract.D2_07_STATUS, "CONSUMED_FAILED")
        self.assertEqual(contract.D2_07_FAILURE_CODE, "AttributeError")
        self.assertFalse(contract.REQUEST_08_ID == contract.D2_07_ID)

    def test_02_source_contract_is_inert(self):
        result = subprocess.run(
            [sys.executable, str(TOOLS / "h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_contract_20260729_v1.py")],
            check=True,
            capture_output=True,
            text=True,
        )
        value = json.loads(result.stdout)
        self.assertFalse(value["physical_request_created"])
        self.assertFalse(value["physical_authorization_created"])
        self.assertFalse(value["board_operation"])

    def test_03_wrapper_is_inert_without_execute(self):
        result = subprocess.run(
            [sys.executable, str(TOOLS / "h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_physical_d2_wrapper_20260729_v1.py")],
            check=True,
            capture_output=True,
            text=True,
        )
        value = json.loads(result.stdout)
        self.assertTrue(value["controller_constant_binding_repaired"])
        self.assertFalse(value["authorization_created"])
        self.assertFalse(value["board_operation"])

    def test_04_prepare_ready_and_result_pass_without_core_constants(self):
        ready = b"stage2d9r_command_ready=PREPARE"
        passed = serial_repair.RESULT_MARKERS[ready]
        controller, session, root = self.make_controller([
            (ready, ready + b"\n"),
            (passed, ready + b"\n" + passed + b"\n"),
        ])
        output = controller.wait_serial_line(
            "synthetic-device", ready, 1.0, b"synthetic-command\n", root / "capture.log"
        )
        self.assertIn(passed, output)
        self.assertEqual(session.writes, [b"synthetic-command\n"])
        kinds = [event["kind"] for event in controller.journal.timeline]
        self.assertIn("PREPARE_READY_WAIT_STARTED", kinds)
        self.assertIn("PREPARE_READY_MARKER_OBSERVED", kinds)
        self.assertIn("PREPARE_COMMAND_SENT", kinds)
        self.assertIn("PREPARE_PASS", kinds)

    def test_05_ready_failure_marker(self):
        ready = b"stage2d9r_command_ready=PREPARE"
        controller, _, root = self.make_controller([
            (serial_repair.DEVICE_FAILURE_MARKER, serial_repair.DEVICE_FAILURE_MARKER),
        ])
        self.assert_error_code(
            lambda: controller.wait_serial_line(
                "synthetic-device", ready, 1.0, b"cmd\n", root / "capture.log"
            ),
            "DEVICE_EXECUTOR_FAILED",
        )

    def test_06_ready_timeout_uses_serial_repair_constant(self):
        ready = b"stage2d9r_command_ready=PREPARE"
        controller, _, root = self.make_controller([(None, b"")])
        self.assert_error_code(
            lambda: controller.wait_serial_line(
                "synthetic-device", ready, 1.0, b"cmd\n", root / "capture.log"
            ),
            serial_repair.READY_TIMEOUT_CODES[ready],
        )

    def test_07_result_failure_marker(self):
        ready = b"stage2d9r_command_ready=PREPARE"
        controller, _, root = self.make_controller([
            (ready, ready),
            (serial_repair.DEVICE_FAILURE_MARKER, serial_repair.DEVICE_FAILURE_MARKER),
        ])
        self.assert_error_code(
            lambda: controller.wait_serial_line(
                "synthetic-device", ready, 1.0, b"cmd\n", root / "capture.log"
            ),
            "DEVICE_EXECUTOR_FAILED",
        )

    def test_08_result_timeout_and_late_window_do_not_resend(self):
        ready = b"stage2d9r_command_ready=PREPARE"
        controller, session, root = self.make_controller([
            (ready, ready),
            (None, ready),
            (None, ready),
        ])
        self.assert_error_code(
            lambda: controller.wait_serial_line(
                "synthetic-device", ready, 1.0, b"cmd\n", root / "capture.log"
            ),
            serial_repair.RESULT_TIMEOUT_CODES[ready],
        )
        self.assertEqual(session.writes, [b"cmd\n"])

    def test_09_late_pass_is_recorded_but_still_times_out(self):
        ready = b"stage2d9r_command_ready=PREPARE"
        passed = serial_repair.RESULT_MARKERS[ready]
        controller, _, root = self.make_controller([
            (ready, ready),
            (None, ready),
            (passed, ready + b"\n" + passed),
        ])
        self.assert_error_code(
            lambda: controller.wait_serial_line(
                "synthetic-device", ready, 1.0, b"cmd\n", root / "capture.log"
            ),
            serial_repair.RESULT_TIMEOUT_CODES[ready],
        )
        late = [
            event for event in controller.journal.timeline
            if event["kind"] == "PREPARE_PASS" and event.get("late") is True
        ]
        self.assertEqual(len(late), 1)

    def test_10_unexpected_wait_exception_maps_to_stable_code(self):
        ready = b"stage2d9r_command_ready=PREPARE"
        controller, _, root = self.make_controller([RuntimeError("private diagnostic")])
        self.assert_error_code(
            lambda: controller.wait_serial_line(
                "synthetic-device", ready, 1.0, b"cmd\n", root / "capture.log"
            ),
            "PREPARE_EVIDENCE_CONTROLLER_READY_WAIT_INTERNAL_ERROR",
        )
        events = [
            event for event in controller.journal.timeline
            if event["kind"] == "EVIDENCE_CONTROLLER_INTERNAL_ERROR"
        ]
        self.assertEqual(events[0]["site"], "READY_WAIT")
        self.assertEqual(events[0]["error_class"], "RuntimeError")
        self.assertNotIn("private diagnostic", json.dumps(events))

    def test_11_verify_reopens_session(self):
        ready = b"stage2d9r_command_ready=VERIFY"
        passed = serial_repair.RESULT_MARKERS[ready]
        controller, session, root = self.make_controller([
            (ready, ready),
            (passed, ready + passed),
        ])
        controller.wait_serial_line(
            "synthetic-device", ready, 1.0, b"verify\n", root / "capture.log"
        )
        self.assertEqual(controller.repaired.open_calls, [True])
        self.assertEqual(session.writes, [b"verify\n"])

    def test_12_unsupported_marker_fails_closed(self):
        controller, _, root = self.make_controller([])
        self.assert_error_code(
            lambda: controller.wait_serial_line(
                "synthetic-device", b"unsupported", 1.0, None, root / "capture.log"
            ),
            "SERIAL_EXPECTED_MARKER_UNSUPPORTED",
        )

    def test_13_package_and_request_when_artifact_supplied(self):
        artifact = os.environ.get("PR201_REVIEW_ARTIFACT")
        if not artifact:
            self.skipTest("PR201_REVIEW_ARTIFACT not supplied")
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "review"
            subprocess.run(
                [
                    sys.executable,
                    str(TOOLS / "h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_packager_20260729_v1.py"),
                    "--source-root", str(ROOT),
                    "--upstream-artifact", artifact,
                    "--source-sha", "3" * 40,
                    "--output", str(output),
                ],
                check=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            package = output / "prepare-evidence-controller-repair-physical-d2-execution-package"
            request = json.loads((output / "PHYSICAL_D2_REQUEST_08.json").read_text())
            contract.validate_physical_request(request, package)
            self.assertFalse(request["authorized"])
            self.assertEqual(request["predecessor_failure_code"], "AttributeError")
            self.assertEqual(request["prepare_max_count"], 1)
            self.assertEqual(request["verify_max_count"], 1)

    def test_14_synthetic_authorization_contract_and_predecessor_rejection(self):
        artifact = os.environ.get("PR201_REVIEW_ARTIFACT")
        if not artifact:
            self.skipTest("PR201_REVIEW_ARTIFACT not supplied")
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "review"
            subprocess.run(
                [
                    sys.executable,
                    str(TOOLS / "h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_packager_20260729_v1.py"),
                    "--source-root", str(ROOT),
                    "--upstream-artifact", artifact,
                    "--source-sha", "4" * 40,
                    "--output", str(output),
                ],
                check=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
            )
            package = output / "prepare-evidence-controller-repair-physical-d2-execution-package"
            request = json.loads((output / "PHYSICAL_D2_REQUEST_08.json").read_text())
            now = datetime.now(timezone.utc)
            authorization = {
                **contract.authorization_contract_required(request, package),
                "authorized": True,
                "one_shot": True,
                "replay_permitted": False,
                "automatic_retry_permitted": False,
                "activate_authorized": False,
                "cleanup_authorized": False,
                "locked_recovery_authorized": True,
                "issued_at": now.isoformat().replace("+00:00", "Z"),
                "expires_at": (now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
            }
            authorization["authorization_record_sha256"] = contract.canonical_sha256(authorization)
            contract.validate_authorization_contract(
                authorization, request, package, now=now
            )
            wrong = dict(authorization)
            wrong["d2_request_id"] = contract.D2_07_ID
            without = dict(wrong)
            without.pop("authorization_record_sha256", None)
            wrong["authorization_record_sha256"] = contract.canonical_sha256(without)
            with self.assertRaises(contract.ContractError):
                contract.validate_authorization_contract(wrong, request, package, now=now)


if __name__ == "__main__":
    unittest.main()
