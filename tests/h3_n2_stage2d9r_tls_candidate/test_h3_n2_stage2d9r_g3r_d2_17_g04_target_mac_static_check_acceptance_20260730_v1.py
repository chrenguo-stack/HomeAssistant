from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g04-target-mac-static-check-passed-20260730-v1.json"
DECISION = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g04-physical-execution-decision-required-20260730-v1.json"


def canonical_sha256(value: dict[str, object], field: str) -> str:
    candidate = dict(value)
    candidate.pop(field, None)
    data = json.dumps(candidate, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(data).hexdigest()


class D217G04TargetMacStaticCheckAcceptanceTests(unittest.TestCase):
    def test_acceptance_binding_and_pass_state(self) -> None:
        value = json.loads(ACCEPTANCE.read_text())
        self.assertEqual(canonical_sha256(value, "acceptance_binding_sha256"), value["acceptance_binding_sha256"])
        self.assertEqual(value["status"], "PASS")
        self.assertIsNone(value["failure_code"])
        self.assertEqual(value["package_generation"], "G04")
        self.assertEqual(value["state"], "TARGET_MAC_STATIC_CHECK_PASSED_AUTHORIZATION_UNCLAIMED_UNCONSUMED")
        self.assertTrue(value["authorization_created"])
        self.assertFalse(value["authorization_claimed"])
        self.assertFalse(value["authorization_consumed"])
        self.assertFalse(value["physical_decision_created"])
        self.assertTrue(value["all_physical_operation_flags_false"])
        self.assertFalse(value["automatic_retry_permitted"])
        self.assertFalse(value["replay_permitted"])
        self.assertFalse(value["g01_private_material_reused"])
        self.assertFalse(value["g02_private_material_reused"])
        self.assertFalse(value["g03_private_material_reused"])
        self.assertEqual(value["terminal_record_digest_semantics"], "CANONICAL_JSON_WITH_TERMINAL_RECORD_SHA256_REMOVED")

    def test_exact_load_bearing_bindings(self) -> None:
        value = json.loads(ACCEPTANCE.read_text())
        self.assertEqual(value["base_pr"], 222)
        self.assertEqual(value["base_head_sha"], "0691b3c85cf3ee018cd07cf038138cbf4dcd1f34")
        self.assertEqual(value["public_execution_artifact_id"], 8752919376)
        self.assertEqual(value["semantic_repair_artifact_id"], 8757007857)
        self.assertEqual(value["nested_set_repair_artifact_id"], 8760604398)
        self.assertEqual(value["authorization_record_sha256"], "be4fa360d122350cece9bc312bf781be8d9f7879cb08bf2330f5e01e8be612ef")
        self.assertEqual(value["terminal_record_sha256"], "1a8b2f02d17e780304673edc6e85761903d698d60a8412f4befcb27d9403ff8d")

    def test_decision_remains_unauthorized(self) -> None:
        acceptance = json.loads(ACCEPTANCE.read_text())
        value = json.loads(DECISION.read_text())
        self.assertEqual(canonical_sha256(value, "decision_required_binding_sha256"), value["decision_required_binding_sha256"])
        self.assertEqual(value["acceptance_binding_sha256"], acceptance["acceptance_binding_sha256"])
        self.assertEqual(value["state"], "AWAITING_EXPLICIT_OPERATOR_PHYSICAL_EXECUTION_AUTHORIZATION")
        self.assertFalse(value["physical_execution_authorized"])
        self.assertFalse(value["claim_authorized"])
        self.assertFalse(value["consume_authorized"])
        self.assertTrue(value["all_physical_operation_authorizations_false"])
        self.assertFalse(value["ready_merge_release_tag_deployment_authorized"])
        self.assertTrue(value["drift_requires_new_decision"])
        self.assertTrue(value["authorization_expiry_requires_new_generation"])

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
