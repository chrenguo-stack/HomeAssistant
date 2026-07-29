#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import stat
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract = load("evidence_contract", "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_repair_contract_20260729_v1.py")
recorder = load("evidence_recorder", "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_recorder_20260729_v1.py")


def fixture_identifiers() -> tuple[str, str, str]:
    address = ".".join(("10", "2", "3", "4"))
    hardware = ":".join(("aa", "bb", "cc", "dd", "ee", "ff"))
    device = "/" + "/".join(("dev", "cu.usbmodem123"))
    return address, hardware, device


class PrepareTimeoutEvidenceRepairTests(unittest.TestCase):
    def test_01_terminal_disposition_exact(self):
        value = contract.d2_terminal_disposition()
        contract.validate_disposition(value)
        self.assertEqual(value["status"], "CONSUMED_FAILED")
        self.assertEqual(value["terminal_state"], "LOCKED_RECOVERY_COMPLETED")
        self.assertEqual(value["failure_code"], "PREPARE_RESULT_TIMEOUT")
        self.assertFalse(value["replay_permitted"])

    def test_02_source_contract_has_no_new_request(self):
        value = contract.source_contract("1" * 40)
        self.assertFalse(value["new_physical_request_created"])
        self.assertFalse(value["authorization_created"])
        self.assertFalse(value["board_operation"])

    def test_03_command_material_redacted(self):
        text = recorder.redact_text("GH2D9R_PREPARE_V2 secret-token raw-command")
        self.assertEqual(text, "GH2D9R_PREPARE_V2 [REDACTED_COMMAND_MATERIAL]")
        self.assertNotIn("secret-token", text)

    def test_04_identifiers_redacted(self):
        address, hardware, device = fixture_identifiers()
        text = recorder.redact_text(
            f"peer={address} mac={hardware} dev={device} password=hunter2"
        )
        self.assertIn("[REDACTED_IP]", text)
        self.assertIn("[REDACTED_MAC]", text)
        self.assertIn("[REDACTED_PATH]", text)
        self.assertIn("[REDACTED_SECRET]", text)
        self.assertNotIn("hunter2", text)

    def test_05_safe_stage_marker_retained(self):
        event = recorder.serial_event("stage2d9r_command_ready=PREPARE", at="2026-07-29T00:00:00Z", phase="prepare")
        self.assertEqual(event["kind"], "STAGE_MARKER")
        self.assertEqual(event["marker"], "stage2d9r_command_ready=PREPARE")

    def test_06_unknown_line_hash_only(self):
        event = recorder.serial_event("arbitrary diagnostic with internal value", at="2026-07-29T00:00:00Z", phase="prepare")
        self.assertEqual(event["kind"], "UNCLASSIFIED_LINE")
        self.assertNotIn("arbitrary", json.dumps(event))
        self.assertRegex(event["line_sha256"], r"^[0-9a-f]{64}$")

    def test_07_classify_no_result(self):
        events = [{"at": "2026-07-29T00:00:00Z", "kind": "PREPARE_COMMAND_SENT"}]
        self.assertEqual(recorder.classify_prepare_outcome(events, deadline_at="2026-07-29T00:00:10Z"), "NO_RESULT")

    def test_08_classify_serial_reset(self):
        events = [
            {"at": "2026-07-29T00:00:00Z", "kind": "PREPARE_COMMAND_SENT"},
            {"at": "2026-07-29T00:00:02Z", "kind": "DEVICE_RESET_OBSERVED"},
        ]
        self.assertEqual(recorder.classify_prepare_outcome(events, deadline_at="2026-07-29T00:00:10Z"), "SERIAL_RESET")

    def test_09_classify_broker_disconnect(self):
        events = [
            {"at": "2026-07-29T00:00:00Z", "kind": "PREPARE_COMMAND_SENT"},
            {"at": "2026-07-29T00:00:02Z", "kind": "BROKER_DISCONNECT"},
        ]
        self.assertEqual(recorder.classify_prepare_outcome(events, deadline_at="2026-07-29T00:00:10Z"), "BROKER_DISCONNECT")

    def test_10_classify_late_and_unrecognized(self):
        late = [
            {"at": "2026-07-29T00:00:00Z", "kind": "PREPARE_COMMAND_SENT"},
            {"at": "2026-07-29T00:00:11Z", "kind": "PREPARE_PASS"},
        ]
        self.assertEqual(recorder.classify_prepare_outcome(late, deadline_at="2026-07-29T00:00:10Z"), "LATE_RESULT")
        unknown = [
            {"at": "2026-07-29T00:00:00Z", "kind": "PREPARE_COMMAND_SENT"},
            {"at": "2026-07-29T00:00:01Z", "kind": "UNRECOGNIZED_RESULT"},
        ]
        self.assertEqual(recorder.classify_prepare_outcome(unknown, deadline_at="2026-07-29T00:00:10Z"), "UNRECOGNIZED_RESULT")

    def test_11_journal_persists_modes_and_no_raw_values(self):
        address, hardware, _ = fixture_identifiers()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "evidence"
            journal = recorder.EvidenceJournal(root)
            journal.initialize()
            journal.record_timeline("PREPARE_COMMAND_SENT")
            journal.record_serial("GH2D9R_PREPARE_V2 password=secret", "prepare")
            journal.record_serial("stage2d9r_command_ready=PREPARE", "prepare")
            journal.record_broker(
                f"New connection from {address} client {hardware}", "prepare"
            )
            manifest = journal.persist(classification="NO_RESULT", terminal=True)
            self.assertTrue(manifest["terminal"])
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            for path in root.iterdir():
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                payload = path.read_text(encoding="utf-8")
                self.assertNotIn("password=secret", payload)
                self.assertNotIn(address, payload)
                self.assertNotIn(hardware, payload)

    def test_12_policy_and_payloads_frozen(self):
        policy = contract.evidence_policy()
        self.assertTrue(policy["persist_before_recovery"])
        self.assertFalse(policy["new_physical_request_created"])
        self.assertEqual(contract.IMMUTABLE_PAYLOAD_TAR_SHA256, "3a3e96c267fd53723e7cbe6cbce959a90d2bf3f08adedcf97255395f91adc4ea")
        self.assertEqual(contract.RECOVERY_PAYLOAD_TAR_SHA256, "08cff687947c2f9b9cbd2df09f16b14b95beeacf2de5683055d6572fafd6cf8f")


if __name__ == "__main__":
    unittest.main()
