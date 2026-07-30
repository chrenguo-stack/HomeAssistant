from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
FAILURE = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g04-physical-preclaim-private-source-drift-failure-20260730-v1.json"
DECISION = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g04-private-source-dual-binding-repair-20260730-v1.json"
CONTRACT = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_private_source_dual_binding_contract_20260730_v1.py"
BUGGY_PART = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g04_physical_execution_decision_driver_20260730_v1.part2.pyfrag"

def canonical_sha256_without(value: dict, key: str) -> str:
    copy = dict(value)
    copy.pop(key)
    raw = json.dumps(copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()

spec = importlib.util.spec_from_file_location("source_contract", CONTRACT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

class TestG04PrivateSourceDualBindingRepair(unittest.TestCase):
    def test_failure_disposition_binding_and_retirement(self):
        value = json.loads(FAILURE.read_text())
        self.assertEqual(
            value["failure_disposition_binding_sha256"],
            canonical_sha256_without(value, "failure_disposition_binding_sha256"),
        )
        self.assertEqual(value["failure_code"], "TERMINAL_PRIVATE_SOURCE_SHA_DRIFT")
        self.assertFalse(value["authorization_claimed"])
        self.assertFalse(value["authorization_consumed"])
        self.assertFalse(value["replay_permitted"])
        self.assertFalse(value["g04_authorization_reuse_permitted"])
        self.assertTrue(value["all_physical_operation_flags_false"])

    def test_repair_decision_binding(self):
        value = json.loads(DECISION.read_text())
        self.assertEqual(
            value["decision_binding_sha256"],
            canonical_sha256_without(value, "decision_binding_sha256"),
        )
        self.assertTrue(value["source_fields_are_distinct"])
        self.assertTrue(value["cross_field_substitution_forbidden"])
        self.assertTrue(value["g04_retired_no_retry"])

    def test_predecessor_bug_is_exactly_fingerprinted(self):
        text = BUGGY_PART.read_text()
        self.assertIn(
            'terminal.get("private_source_sha") == PR223_HEAD',
            text,
        )
        self.assertIn('"TERMINAL_PRIVATE_SOURCE_SHA_DRIFT"', text)

    def test_correct_layer_bindings_pass(self):
        terminal = {"private_source_sha": module.G04_PRIVATE_SOURCE_SHA}
        result = module.validate_source_bindings(
            terminal,
            acceptance_source_sha=module.G04_ACCEPTANCE_SOURCE_SHA,
            physical_decision_source_sha=module.G04_PHYSICAL_DECISION_SOURCE_SHA,
        )
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["source_fields_are_distinct"])

    def test_cross_field_substitution_is_rejected(self):
        with self.assertRaisesRegex(module.BindingError, "TERMINAL_PRIVATE_SOURCE_SHA_DRIFT"):
            module.validate_source_bindings(
                {"private_source_sha": module.G04_ACCEPTANCE_SOURCE_SHA},
                acceptance_source_sha=module.G04_ACCEPTANCE_SOURCE_SHA,
                physical_decision_source_sha=module.G04_PHYSICAL_DECISION_SOURCE_SHA,
            )
        with self.assertRaisesRegex(module.BindingError, "ACCEPTANCE_SOURCE_SHA_DRIFT"):
            module.validate_source_bindings(
                {"private_source_sha": module.G04_PRIVATE_SOURCE_SHA},
                acceptance_source_sha=module.G04_PRIVATE_SOURCE_SHA,
                physical_decision_source_sha=module.G04_PHYSICAL_DECISION_SOURCE_SHA,
            )
        with self.assertRaisesRegex(module.BindingError, "PHYSICAL_DECISION_SOURCE_SHA_DRIFT"):
            module.validate_source_bindings(
                {"private_source_sha": module.G04_PRIVATE_SOURCE_SHA},
                acceptance_source_sha=module.G04_ACCEPTANCE_SOURCE_SHA,
                physical_decision_source_sha=module.G04_ACCEPTANCE_SOURCE_SHA,
            )

if __name__ == "__main__":
    unittest.main()
