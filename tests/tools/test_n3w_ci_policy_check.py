from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.n3w_ci_policy_check import audit


ROOT = Path(__file__).resolve().parents[2]


class N3wCiPolicyCheckTest(unittest.TestCase):
    def test_repository_policy_alignment(self) -> None:
        result = audit(ROOT)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["workflow_count"], 67)

    def test_unregistered_workflow_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".github/workflows").mkdir(parents=True)
            (root / "docs").mkdir()
            (root / ".github/workflows/a.yml").write_text(
                "name: a\non:\n  pull_request:\njobs:\n  a:\n    timeout-minutes: 5\n",
                encoding="utf-8",
            )
            (root / "docs/policy.md").write_text(
                "N3W_CI_POLICY_REVISION=R1\n",
                encoding="utf-8",
            )
            manifest = {
                "schema": "gh.n3w-ci-policy-manifest/1",
                "policy_revision": "R1",
                "authority_documents": ["docs/policy.md"],
                "valid_classes": ["FAST", "MODEL", "BUILD", "EVIDENCE", "EXACT", "LIVE"],
                "valid_draft_policies": ["run", "ci-ready", "legacy-run", "manual-or-push"],
                "workflows": {},
            }
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            result = audit(root, path)
            self.assertIn("unregistered workflow: a.yml", result["errors"])

    def test_qemu_cannot_hide_in_fast_class(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".github/workflows").mkdir(parents=True)
            (root / "docs").mkdir()
            workflow = """name: qemu
on:
  pull_request:
concurrency:
  group: x
  cancel-in-progress: true
jobs:
  qemu:
    timeout-minutes: 5
    steps:
      - uses: docker/setup-qemu-action@v3
"""
            (root / ".github/workflows/q.yml").write_text(workflow, encoding="utf-8")
            (root / "docs/policy.md").write_text(
                "N3W_CI_POLICY_REVISION=R1\n",
                encoding="utf-8",
            )
            manifest = {
                "schema": "gh.n3w-ci-policy-manifest/1",
                "policy_revision": "R1",
                "authority_documents": ["docs/policy.md"],
                "valid_classes": ["FAST", "MODEL", "BUILD", "EVIDENCE", "EXACT", "LIVE"],
                "valid_draft_policies": ["run", "ci-ready", "legacy-run", "manual-or-push"],
                "workflows": {
                    "q.yml": {
                        "class": "FAST",
                        "draft_policy": "run",
                        "exceptions": {
                            "heavy_draft_execution": "Temporary explicit heavy Draft debt for test fixture only."
                        },
                    }
                },
            }
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            result = audit(root, path)
            self.assertTrue(
                any("cannot be classified as FAST" in error for error in result["errors"])
            )


if __name__ == "__main__":
    unittest.main()
