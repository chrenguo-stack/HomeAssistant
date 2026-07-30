from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g02-target-mac-static-check-passed-20260730-v1.json"
DECISION = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g02-physical-execution-decision-required-20260730-v1.json"


def canonical_sha256(value: dict[str, object], field: str) -> str:
    candidate = dict(value)
    candidate.pop(field, None)
    data = json.dumps(candidate, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(data).hexdigest()


class D217G02TargetMacStaticCheckAcceptanceTests(unittest.TestCase):
    def test_acceptance_binding_and_pass_state(self) -> None:
        value = json.loads(ACCEPTANCE.read_text())
        self.assertEqual(
            canonical_sha256(value, "acceptance_binding_sha256"),
            value["acceptance_binding_sha256"],
        )
        self.assertEqual(value["status"], "PASS")
        self.assertEqual(
            value["state"],
            "TARGET_MAC_STATIC_CHECK_PASSED_AUTHORIZATION_UNCLAIMED_UNCONSUMED",
        )
        self.assertTrue(value["authorization_created"])
        self.assertFalse(value["authorization_claimed"])
        self.assertFalse(value["authorization_consumed"])
        self.assertFalse(value["physical_decision_created"])
        self.assertTrue(value["all_physical_operation_flags_false"])
        self.assertFalse(value["automatic_retry_permitted"])
        self.assertFalse(value["replay_permitted"])

    def test_decision_remains_unauthorized(self) -> None:
        acceptance = json.loads(ACCEPTANCE.read_text())
        value = json.loads(DECISION.read_text())
        self.assertEqual(
            canonical_sha256(value, "decision_required_binding_sha256"),
            value["decision_required_binding_sha256"],
        )
        self.assertEqual(value["acceptance_binding_sha256"], acceptance["acceptance_binding_sha256"])
        self.assertEqual(
            value["state"],
            "AWAITING_EXPLICIT_OPERATOR_PHYSICAL_EXECUTION_AUTHORIZATION",
        )
        self.assertFalse(value["physical_execution_authorized"])
        self.assertFalse(value["claim_authorized"])
        self.assertFalse(value["consume_authorized"])
        self.assertTrue(value["all_physical_operation_authorizations_false"])
        self.assertFalse(value["ready_merge_release_tag_deployment_authorized"])

    def test_public_records_do_not_publish_private_paths_or_content(self) -> None:
        combined = ACCEPTANCE.read_text() + DECISION.read_text()
        self.assertNotIn("/Users/", combined)
        self.assertNotIn("RUNTIME_ROOT", combined)
        self.assertNotIn("TERMINAL_FILE", combined)
        self.assertNotIn("physical-authorization", combined.lower())
        acceptance = json.loads(ACCEPTANCE.read_text())
        decision = json.loads(DECISION.read_text())
        self.assertFalse(acceptance["local_runtime_paths_published"])
        self.assertFalse(acceptance["private_authorization_content_published"])
        self.assertFalse(decision["local_runtime_paths_published"])
        self.assertFalse(decision["private_authorization_content_published"])


if __name__ == "__main__":
    unittest.main()
