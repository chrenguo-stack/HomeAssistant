from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

MODULE = "h3_n2_stage2d9r_g3r_d2_17_private_package_manifest_coverage_contract_20260730_v1"


class PrivatePackageManifestCoverageRepairTests(unittest.TestCase):
    def contract(self):
        return importlib.import_module(MODULE)

    def make_tree(self, root: Path) -> None:
        (root / "payload/deep").mkdir(parents=True)
        (root / "ordinary.txt").write_text("ordinary\n", encoding="utf-8")
        (root / "payload/SHA256SUMS").write_text("nested-one\n", encoding="utf-8")
        (root / "payload/deep/SHA256SUMS").write_text("nested-two\n", encoding="utf-8")
        (root / "payload/deep/data.bin").write_bytes(b"data")

    def test_nested_sha256sums_are_covered(self) -> None:
        contract = self.contract()
        with tempfile.TemporaryDirectory(prefix="d2 17 g02 nested ") as temporary:
            root = Path(temporary)
            self.make_tree(root)
            contract.write_root_sha256sums(root)
            result = contract.verify_root_sha256sums(root)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["nested_sha256sums_count"], 2)
            self.assertEqual(
                result["nested_sha256sums_paths"],
                ["payload/SHA256SUMS", "payload/deep/SHA256SUMS"],
            )
            manifest = (root / "SHA256SUMS").read_text(encoding="utf-8")
            self.assertIn("  payload/SHA256SUMS\n", manifest)
            self.assertIn("  payload/deep/SHA256SUMS\n", manifest)
            self.assertNotIn("  SHA256SUMS\n", manifest)

    def test_g01_basename_filter_is_rejected_by_coverage(self) -> None:
        contract = self.contract()
        with tempfile.TemporaryDirectory(prefix="d2 17 g01 defect ") as temporary:
            root = Path(temporary)
            self.make_tree(root)
            defective = []
            for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
                if path.is_file() and path.name != "SHA256SUMS":
                    defective.append(
                        f"{contract.sha256_file(path)}  {path.relative_to(root).as_posix()}"
                    )
            (root / "SHA256SUMS").write_text("\n".join(defective) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                contract.CoverageError,
                "PRIVATE_SHA256SUMS_COVERAGE_MISMATCH",
            ):
                contract.verify_root_sha256sums(root)
            snapshot = contract.coverage_snapshot(root)
            self.assertEqual(
                snapshot["missing_paths"],
                ["payload/SHA256SUMS", "payload/deep/SHA256SUMS"],
            )

    def test_member_tamper_preserves_leaf_path(self) -> None:
        contract = self.contract()
        with tempfile.TemporaryDirectory(prefix="d2 17 g02 tamper ") as temporary:
            root = Path(temporary)
            self.make_tree(root)
            contract.write_root_sha256sums(root)
            (root / "payload/deep/data.bin").write_bytes(b"tampered")
            with self.assertRaisesRegex(
                contract.CoverageError,
                "PRIVATE_MEMBER_DIGEST_MISMATCH:payload/deep/data.bin",
            ):
                contract.verify_root_sha256sums(root)

    def test_bound_records_validate(self) -> None:
        contract = self.contract()
        decision = json.loads(
            (ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-private-sha256-coverage-repair-20260730-v1.json").read_text(encoding="utf-8")
        )
        supplied = decision.pop("decision_binding_sha256")
        self.assertEqual(contract.canonical_sha256(decision), supplied)
        disposition = json.loads(
            (ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g01-private-package-failure-disposition-20260730-v1.json").read_text(encoding="utf-8")
        )
        supplied = disposition.pop("failure_disposition_binding_sha256")
        self.assertEqual(contract.canonical_sha256(disposition), supplied)


if __name__ == "__main__":
    unittest.main()
