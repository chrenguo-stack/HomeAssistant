from __future__ import annotations

import json
from pathlib import Path
import unittest

from tools import h3_n2_stage2d9r_g3r_d2_17_nested_sha256sums_set_contract_20260730_v1 as contract


EXPECTED = ['public-review/SHA256SUMS', 'public-review/d2-17-execution-identity-frozen-physical-d2-execution-package/SHA256SUMS', 'sha256-coverage-repair-review/SHA256SUMS', 'sha256-coverage-repair-review/synthetic private package/SHA256SUMS', 'sha256-coverage-repair-review/synthetic private package/public-review/SHA256SUMS', 'sha256-coverage-repair-review/synthetic private package/public-review/execution package/SHA256SUMS', 'terminal-record-semantic-digest-repair-review/SHA256SUMS']


class NestedSha256SumsSetRepairTests(unittest.TestCase):
    def test_exact_g03_members_pass_after_set_normalization(self) -> None:
        observed = set(reversed(EXPECTED))
        result = contract.verify_nested_sha256sums(
            observed_nested=observed,
            root_manifest_names=EXPECTED + ["other/file"],
            expected_nested=tuple(EXPECTED),
        )
        self.assertEqual(result, set(EXPECTED))

    def test_retired_g03_set_tuple_comparison_reproduces_failure(self) -> None:
        with self.assertRaisesRegex(
            contract.NestedSha256SumsContractError,
            "PRIVATE_NESTED_SHA256SUMS_SET_INVALID",
        ):
            contract.reproduce_retired_g03_comparison(
                observed_nested=set(EXPECTED),
                expected_nested_tuple=tuple(EXPECTED),
            )

    def test_missing_root_coverage_preserves_leaf_error(self) -> None:
        with self.assertRaisesRegex(
            contract.NestedSha256SumsContractError,
            "PRIVATE_NESTED_SHA256SUMS_NOT_COVERED",
        ):
            contract.verify_nested_sha256sums(
                observed_nested=EXPECTED,
                root_manifest_names=EXPECTED[:-1],
                expected_nested=EXPECTED,
            )

    def test_missing_or_extra_member_preserves_set_error(self) -> None:
        for observed in (EXPECTED[:-1], EXPECTED + ["unexpected/SHA256SUMS"]):
            with self.assertRaisesRegex(
                contract.NestedSha256SumsContractError,
                "PRIVATE_NESTED_SHA256SUMS_SET_INVALID",
            ):
                contract.verify_nested_sha256sums(
                    observed_nested=observed,
                    root_manifest_names=observed,
                    expected_nested=EXPECTED,
                )

    def test_public_bindings(self) -> None:
        root = Path(__file__).resolve().parents[2]
        failure = json.loads((root / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g03-private-nested-sha256sums-failure-20260730-v1.json").read_text())
        decision = json.loads((root / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g03-nested-sha256sums-set-normalization-repair-20260730-v1.json").read_text())
        self.assertEqual(failure["disposition_binding_sha256"], "55272153f68b362c611ae0ebac943819953385a608616490fdd72a4e2dc1f352")
        self.assertEqual(decision["decision_binding_sha256"], "b103368a1fdd2a2ce4fb6fd642635f5c6019729e61bcf3778d208ba2184aaa30")
        self.assertFalse(decision["g04_private_package_authorized"])
        self.assertFalse(decision["physical_execution_authorized"])


if __name__ == "__main__":
    unittest.main()
