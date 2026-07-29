from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

import h3_n2_stage2d9r_g3r_d2_10_forensic_terminal_closure_20260729_v1 as closure
import h3_n2_stage2d9r_g3r_d2_10_forensic_terminal_closure_contract_20260729_v1 as contract
import h3_n2_stage2d9r_g3r_executor_terminalization_repair_20260729_v1 as repair
import h3_n2_stage2d9r_successor_d2_execute_20260727_v1 as core_module


def json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, indent=2).encode() + b"\n"


class ForensicFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.marker = root / contract.MARKER_NAME
        self.contract_check = root / "contract-check.json"
        self.terminal_output = root / "terminal-output.txt"
        self.evidence = root / "evidence"
        self.evidence.mkdir()
        marker_value = {
            "schema": contract.ORIGINAL_MARKER_SCHEMA,
            "stage": contract.STAGE,
            "d2_request_id": contract.D2_REQUEST_ID,
            "status": "CLAIMED",
            "authorization_record_sha256": contract.AUTHORIZATION_RECORD_SHA256,
            "request_binding_sha256": contract.REQUEST_BINDING_SHA256,
            "claimed_at": "2026-07-29T09:51:02.581896Z",
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
        }
        contract_value = {
            "status": "PASS",
            "d2_request_id": contract.D2_REQUEST_ID,
            "request_binding_sha256": contract.REQUEST_BINDING_SHA256,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
            "authorization_claimed": False,
            "authorization_consumed": False,
        }
        terminal_value = {
            "status": "FAIL",
            "failure_code": "KeyError",
            "d2_request_id": contract.D2_REQUEST_ID,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
        }
        timeline = {
            "schema": "gh.h3.n2.stage2d9r-g3r-prepare-timeout-timeline/1",
            "events": [
                {"kind": "BROKER_STARTED"},
                {"kind": "PREPARE_COMMAND_SENT"},
                {"kind": "PREPARE_RESULT_TIMEOUT"},
                {"kind": "BROKER_STOPPED"},
                {
                    "kind": "TERMINAL_EVIDENCE_PERSIST_REQUESTED",
                    "before_recovery": True,
                    "failure_code": "PREPARE_RESULT_TIMEOUT",
                },
            ],
        }
        self.marker.write_bytes(json_bytes(marker_value))
        self.contract_check.write_bytes(json_bytes(contract_value))
        self.terminal_output.write_bytes(json.dumps(terminal_value).encode() + b"\n")
        evidence_values = {
            "broker.redacted.jsonl": b'{"kind":"BROKER_LINE"}\n',
            "prepare-evidence-manifest.json": b"{}\n",
            "prepare-panic-evidence-manifest.json": b"{}\n",
            "prepare-reset-signatures.json": b"{}\n",
            "prepare-serial.realtime.redacted.jsonl": b'{"kind":"LINE"}\n',
            "prepare-serial.redacted.jsonl": b"",
            "prepare-timeline.json": json_bytes(timeline),
            "prepare-timeline.realtime.json": b"{}\n",
        }
        for name, data in evidence_values.items():
            (self.evidence / name).write_bytes(data)
        self.patch = mock.patch.multiple(
            contract,
            MARKER_FILE_SHA256=contract.sha256_file(self.marker),
            CONTRACT_CHECK_FILE_SHA256=contract.sha256_file(self.contract_check),
            TERMINAL_OUTPUT_FILE_SHA256=contract.sha256_file(self.terminal_output),
            EVIDENCE_DIGESTS={
                name: contract.sha256_file(self.evidence / name)
                for name in evidence_values
            },
        )

    def args(self) -> argparse.Namespace:
        return argparse.Namespace(
            marker=self.marker,
            contract_check=self.contract_check,
            terminal_output=self.terminal_output,
            evidence_root=self.evidence,
        )


class ForensicClosureTests(unittest.TestCase):
    def test_plan_is_read_only_for_stale_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fixture = ForensicFixture(Path(td))
            before = fixture.marker.read_bytes()
            with fixture.patch:
                args = fixture.args()
                args.output = Path(td) / "plan"
                result, marker = closure.build(args)
                plan = closure.write_plan(args.output, result, marker)
            self.assertEqual(before, fixture.marker.read_bytes())
            self.assertEqual(
                plan["status"], "FORENSIC_TERMINAL_CLOSURE_PLANNED_NOT_APPLIED"
            )
            self.assertEqual(result["status"], "CONSUMED_FAILED")
            self.assertEqual(result["prepare_count"], 1)
            self.assertEqual(result["verify_count"], 0)
            self.assertIsNone(result["locked_recovery_succeeded"])
            self.assertFalse(plan["closure_authorization_created"])
            self.assertEqual(
                {path.name for path in args.output.iterdir()},
                {
                    closure.RESULT_NAME,
                    closure.MARKER_NAME,
                    closure.PLAN_NAME,
                    closure.SUMS_NAME,
                },
            )

    def test_close_requires_exact_separate_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fixture = ForensicFixture(Path(td))
            with fixture.patch:
                args = fixture.args()
                result, marker = closure.build(args)
                tool_sha = contract.sha256_file(Path(closure.__file__))
                authorization = {
                    "schema": contract.CLOSURE_AUTH_SCHEMA,
                    "decision_id": contract.DECISION_ID,
                    "d2_request_id": contract.D2_REQUEST_ID,
                    "authorized": True,
                    "one_shot": True,
                    "replay_permitted": False,
                    "physical_operation_authorized": False,
                    "issued_at": "2026-07-29T10:00:00Z",
                    "expires_at": "2026-07-29T11:00:00Z",
                    "stale_marker_sha256": contract.MARKER_FILE_SHA256,
                    "terminal_result_sha256": result["terminal_result_sha256"],
                    "terminal_marker_sha256": contract.canonical_sha256(marker),
                    "closure_tool_sha256": tool_sha,
                    "request_binding_sha256": contract.REQUEST_BINDING_SHA256,
                    "authorization_record_sha256": (
                        contract.AUTHORIZATION_RECORD_SHA256
                    ),
                }
                authorization["closure_authorization_sha256"] = (
                    contract.canonical_sha256(authorization)
                )
                auth_path = Path(td) / "closure-authorization.json"
                auth_path.write_bytes(json_bytes(authorization))
                args.closure_authorization = auth_path
                args.result_output = Path(td) / "terminal-result.json"
                args.now = "2026-07-29T10:30:00Z"
                self.assertEqual(closure.close(args), 0)
            closed = json.loads(fixture.marker.read_text())
            self.assertEqual(closed["status"], "CONSUMED_FAILED")
            self.assertFalse(closed["replay_permitted"])
            self.assertEqual(closed["verify_count"], 0)

    def test_changed_stale_marker_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fixture = ForensicFixture(Path(td))
            fixture.marker.write_text("{}\n")
            with fixture.patch, self.assertRaises(contract.ContractError):
                closure.build(fixture.args())


class ExecutorRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.core = importlib.reload(core_module)

    def _run(self, recovery_failure: bool = False, finish_failure: bool = False):
        stack = tempfile.TemporaryDirectory()
        self.addCleanup(stack.cleanup)
        root = Path(stack.name)
        for name in ("package", "immutable", "recovery", "home", "state"):
            (root / name).mkdir()
        merged = root / "merged.bin"
        erased = root / "erased.bin"
        merged.write_bytes(b"firmware")
        erased.write_bytes(b"erased")
        authorization = {
            "request_binding_sha256": "1" * 64,
            "authorization_record_sha256": "2" * 64,
            "source_sha": "3" * 40,
            "repository_head_sha": "4" * 40,
            "board_identity_sha256": "5" * 64,
            "serial_identity_sha256": "6" * 64,
            "baseline_state_sha256": "7" * 64,
            "execution_marker_name_sha256": self.core.sha256_bytes(
                (
                    self.core.sha256_bytes(
                        self.core.D2_REQUEST_ID.encode("utf-8")
                    )
                    + ".json"
                ).encode("utf-8")
            ),
            "locked_recovery_max_count": 1,
            "locked_recovery_authorized": True,
        }
        auth_path = root / "authorization.json"
        auth_path.write_bytes(json_bytes(authorization))
        args = types.SimpleNamespace(
            package_root=root / "package",
            immutable_root=root / "immutable",
            recovery_root=root / "recovery",
            home=root / "home",
            state_root=root / "state",
            result_output=root / "result.json",
            authorization_record=auth_path,
            openssl=None,
            esptool=None,
            mosquitto=None,
        )
        selected = types.SimpleNamespace(device="/dev/synthetic")
        calls: list[str] = []

        def wait_serial_line(
            device: str,
            expected: bytes,
            timeout: float,
            command: bytes | None,
            log_path: Path,
        ) -> bytes:
            calls.append(expected.decode())
            log_path.write_bytes(b"prepare-timeout")
            raise self.core.ExecutionError("PREPARE_RESULT_TIMEOUT")

        def locked_recovery(*unused: object) -> bool:
            calls.append("LOCKED_RECOVERY")
            if recovery_failure:
                raise self.core.ExecutionError("LOCKED_RECOVERY_WRITE_FAILED")
            return True

        def finish_marker(*unused: object, **unused_kw: object) -> None:
            if finish_failure:
                raise self.core.ExecutionError("TERMINAL_MARKER_WRITE_FAILED")
            return original_finish(*unused, **unused_kw)

        original_finish = self.core.finish_marker
        patches = mock.patch.multiple(
            self.core,
            verify_sums=mock.DEFAULT,
            executable=mock.DEFAULT,
            validate_public_inputs=mock.DEFAULT,
            validate_private_metadata=mock.DEFAULT,
            validate_authorization=mock.DEFAULT,
            read_private_commands=mock.DEFAULT,
            select_serial=mock.DEFAULT,
            baseline=mock.DEFAULT,
            flash_firmware=mock.DEFAULT,
            start_broker=mock.DEFAULT,
            stop_broker=mock.DEFAULT,
            wait_serial_line=wait_serial_line,
            locked_recovery=locked_recovery,
            finish_marker=finish_marker,
        )
        with patches as mocked:
            mocked["verify_sums"].return_value = None
            mocked["executable"].return_value = Path("/bin/true")
            mocked["validate_public_inputs"].return_value = (merged, erased)
            mocked["validate_private_metadata"].return_value = root / "home"
            mocked["validate_authorization"].return_value = authorization
            mocked["read_private_commands"].return_value = (
                b"GH2D9R_PREPARE_V2 test\n",
                b"GH2D9R_VERIFY_V2 test\n",
            )
            mocked["select_serial"].return_value = selected
            mocked["baseline"].return_value = {"baseline": "ok"}
            mocked["flash_firmware"].return_value = None
            mocked["start_broker"].return_value = object()
            mocked["stop_broker"].return_value = None
            controller = repair.TerminalizationSafetyController(
                self.core, root / "durable-evidence"
            )
            controller.install()
            with self.assertRaises(self.core.ExecutionError) as caught:
                self.core.execute(args)
        self.assertIn(
            str(caught.exception),
            {"PREPARE_RESULT_TIMEOUT", "TERMINAL_MARKER_WRITE_FAILED"},
        )
        result = json.loads(args.result_output.read_text())
        marker_name = self.core.sha256_bytes(
            self.core.D2_REQUEST_ID.encode()
        ) + ".json"
        marker = json.loads((args.state_root / marker_name).read_text())
        recovery = json.loads(controller.recovery_path.read_text())
        return result, marker, recovery, calls, controller

    def test_prepare_timeout_recovery_success_terminalizes(self) -> None:
        result, marker, recovery, calls, _ = self._run()
        self.assertEqual(result["failure_code"], "PREPARE_RESULT_TIMEOUT")
        self.assertEqual(result["secondary_failure_code"], "KeyError")
        self.assertTrue(result["terminalization_fallback_used"])
        self.assertEqual(result["repository_head_sha"], "4" * 40)
        self.assertEqual(result["main_sha"], "4" * 40)
        self.assertEqual(result["prepare_count"], 1)
        self.assertEqual(result["verify_count"], 0)
        self.assertEqual(calls.count("LOCKED_RECOVERY"), 1)
        self.assertEqual(len([v for v in calls if v.endswith("VERIFY")]), 0)
        self.assertEqual(marker["status"], "CONSUMED_FAILED")
        self.assertEqual(recovery["status"], "COMPLETED")
        self.assertTrue(recovery["succeeded"])

    def test_recovery_failure_is_persisted_and_terminalizes(self) -> None:
        result, marker, recovery, calls, _ = self._run(recovery_failure=True)
        self.assertEqual(result["failure_code"], "PREPARE_RESULT_TIMEOUT")
        self.assertFalse(result["recovery_succeeded"])
        self.assertEqual(
            result["recovery_failure_code"], "LOCKED_RECOVERY_WRITE_FAILED"
        )
        self.assertEqual(recovery["status"], "FAILED")
        self.assertEqual(marker["status"], "CONSUMED_FAILED")
        self.assertEqual(calls.count("LOCKED_RECOVERY"), 1)

    def test_finish_marker_failure_cannot_leave_claimed(self) -> None:
        result, marker, _, _, controller = self._run(finish_failure=True)
        self.assertEqual(result["failure_code"], "PREPARE_RESULT_TIMEOUT")
        self.assertEqual(marker["status"], "CONSUMED_FAILED")
        guard = json.loads(controller.guard_path.read_text())
        self.assertEqual(guard["status"], "TERMINALIZED")

    def test_arbitrary_result_generator_error_uses_fallback(self) -> None:
        fake = types.SimpleNamespace(
            execute=lambda args: None,
            result_object=lambda **kwargs: (_ for _ in ()).throw(
                ValueError("synthetic")
            ),
            locked_recovery=lambda *args: True,
            canonical_sha256=contract.canonical_sha256,
            RESULT_SCHEMA="result/1",
            STAGE="test",
            D2_REQUEST_ID="request",
        )
        with tempfile.TemporaryDirectory() as td:
            controller = repair.TerminalizationSafetyController(fake, Path(td))
            controller.install()
            value = fake.result_object(
                authorization={
                    "repository_head_sha": "a" * 40,
                    "request_binding_sha256": "b" * 64,
                },
                failure_code="PREPARE_RESULT_TIMEOUT",
                recovery_attempted=False,
                recovery_succeeded=False,
            )
        self.assertTrue(value["terminalization_fallback_used"])
        self.assertEqual(value["secondary_failure_code"], "ValueError")


if __name__ == "__main__":
    unittest.main()
