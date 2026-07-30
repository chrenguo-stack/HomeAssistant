from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools import h3_n2_stage2d9r_g3r_d2_17_terminal_record_semantic_digest_contract_20260730_v1 as contract


class TerminalRecordSemanticDigestRepairTests(unittest.TestCase):
    def make_record(self) -> dict[str, object]:
        value: dict[str, object] = {
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-target-mac-static-check-terminal/1",
            "status": "PASS",
            "terminal_state": "TARGET_MAC_STATIC_CHECK_PASSED_AUTHORIZATION_UNCLAIMED_UNCONSUMED",
            "decision_id": "D1-H3N2-STAGE2D9R-G3R-D2-17-G02-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260730-01",
            "d2_request_id": "D2-H3N2-STAGE2D9R-G3R-EXECUTION-IDENTITY-FROZEN-PREFLIGHT-STABILIZED-PHYSICAL-20260730-17",
            "authorization_created": True,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "physical_decision_created": False,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
        }
        value["terminal_record_sha256"] = contract.canonical_sha256(value)
        return value

    def test_semantic_digest_accepts_distinct_json_presentations(self) -> None:
        record = self.make_record()
        expected = str(record["terminal_record_sha256"])
        required = {
            "status": "PASS",
            "authorization_claimed": False,
            "authorization_consumed": False,
            "board_operation": False,
        }
        with tempfile.TemporaryDirectory(prefix="d2 17 semantic terminal ") as raw:
            root = Path(raw)
            pretty = root / "pretty terminal.json"
            compact = root / "compact terminal.json"
            pretty.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            compact.write_text(json.dumps(record, separators=(",", ":")), encoding="utf-8")
            self.assertNotEqual(contract.sha256_file(pretty), contract.sha256_file(compact))
            self.assertEqual(contract.verify_terminal_record(pretty, expected_record_sha256=expected, required_fields=required)["status"], "PASS")
            self.assertEqual(contract.verify_terminal_record(compact, expected_record_sha256=expected, required_fields=required)["status"], "PASS")

    def test_retired_g02_byte_check_reproduces_leaf_error(self) -> None:
        record = self.make_record()
        semantic = str(record["terminal_record_sha256"])
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "terminal.json"
            path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            self.assertNotEqual(contract.sha256_file(path), semantic)
            with self.assertRaisesRegex(contract.TerminalRecordContractError, "TERMINAL_FILE_DIGEST_DRIFT"):
                contract.reproduce_retired_g02_byte_digest_check(path, mistaken_expected_file_sha256=semantic)

    def test_semantic_tamper_preserves_leaf_error(self) -> None:
        record = self.make_record()
        expected = str(record["terminal_record_sha256"])
        tampered = copy.deepcopy(record)
        tampered["authorization_claimed"] = True
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "terminal.json"
            path.write_text(json.dumps(tampered, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(contract.TerminalRecordContractError, "TERMINAL_RECORD_DIGEST_DRIFT"):
                contract.verify_terminal_record(path, expected_record_sha256=expected, required_fields={"authorization_claimed": False})

    def test_embedded_digest_substitution_is_rejected(self) -> None:
        record = self.make_record()
        expected = str(record["terminal_record_sha256"])
        record["terminal_record_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "terminal.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(contract.TerminalRecordContractError, "TERMINAL_RECORD_DIGEST_BINDING_DRIFT"):
                contract.verify_terminal_record(path, expected_record_sha256=expected, required_fields={})

    def test_public_failure_and_decision_bindings(self) -> None:
        cases = (
            (
                Path("docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g02-physical-preclaim-terminal-digest-failure-20260730-v1.json"),
                "disposition_binding_sha256",
            ),
            (
                Path("docs/decisions/h3-n2-stage2d9r-g3r-d2-17-terminal-record-semantic-digest-repair-20260730-v1.json"),
                "decision_binding_sha256",
            ),
        )
        for path, field in cases:
            value = json.loads(path.read_text(encoding="utf-8"))
            expected = value.pop(field)
            self.assertEqual(contract.canonical_sha256(value), expected)


if __name__ == "__main__":
    unittest.main()
