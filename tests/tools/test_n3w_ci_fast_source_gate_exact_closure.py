from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

HEAVY = {
    "n3w-t1-fresh-bootstrap-deployable-payload-ci.yml": "deployable-payload:",
    "n3w-t1-fresh-install-exact-arm64-ci.yml": "exact-three-image:",
    "n3w-t1-production-stack-staging-payload-ci.yml": "payload:",
    "n3w-t1-s20-production-image-binding-ci.yml": "bind-images:",
}

GATE_SNIPPETS = (
    "workflow_dispatch:",
    "ready_for_review",
    "converted_to_draft",
    "labeled",
    "unlabeled",
    "edited",
    "github.event.pull_request.draft == false",
    "contains(github.event.pull_request.labels.*.name, 'ci-ready')",
    "contains(github.event.pull_request.body, 'CI_READY=true')",
    "concurrency:",
    "cancel-in-progress: ${{ github.event_name == 'pull_request' }}",
)


class CiFastSourceExactClosureContractTest(unittest.TestCase):
    def _workflow(self, name: str) -> str:
        return (WORKFLOWS / name).read_text(encoding="utf-8")

    def test_heavy_workflows_keep_explicit_gate_and_main_path(self) -> None:
        for name, job in HEAVY.items():
            with self.subTest(workflow=name):
                text = self._workflow(name)
                self.assertIn(job, text)
                self.assertIn("pull_request:", text)
                self.assertIn("push:", text)
                self.assertIn("main", text)
                for snippet in GATE_SNIPPETS:
                    self.assertIn(snippet, text)

    def test_exact_arm64_fails_cheap_before_qemu_and_keeps_exact_proof(self) -> None:
        text = self._workflow("n3w-t1-fresh-install-exact-arm64-ci.yml")
        preflight = text.index("Fast source preflight before ARM64 closure")
        qemu = text.index("docker/setup-qemu-action@v3")
        self.assertLess(preflight, qemu)
        self.assertIn("ruff check .", text)
        self.assertIn("pytest -q", text)
        self.assertIn("Upload exact three-image artifact", text)
        self.assertIn("Download uploaded artifact for exact binding", text)
        self.assertIn("Verify uploaded exact binding", text)
        self.assertNotIn('      - "host/greenhouse-manager/**"', text)
        for path in (
            '      - "host/greenhouse-manager/Dockerfile"',
            '      - "host/greenhouse-manager/pyproject.toml"',
            '      - "host/greenhouse-manager/README.md"',
            '      - "host/greenhouse-manager/src/**"',
            '      - "tests/tools/test_n3w_ha_mqtt_bootstrap_isolated_runtime.py"',
        ):
            self.assertIn(path, text)

    def test_fresh_bootstrap_source_contract_precedes_qemu(self) -> None:
        text = self._workflow("n3w-t1-fresh-bootstrap-deployable-payload-ci.yml")
        self.assertLess(
            text.index("Run source contract tests"),
            text.index("docker/setup-qemu-action@v3"),
        )

    def test_production_staging_focused_tests_precede_artifact_work(self) -> None:
        text = self._workflow("n3w-t1-production-stack-staging-payload-ci.yml")
        self.assertLess(
            text.index("Run staging executor focused tests"),
            text.index("Download exact frozen Manager artifact"),
        )

    def test_s20_fixed_source_binding_does_not_follow_current_manager_tree(self) -> None:
        text = self._workflow("n3w-t1-s20-production-image-binding-ci.yml")
        self.assertIn(
            "MANAGER_SOURCE_SHA: 511db028780988a7c07cb9342c8be507380bae0f",
            text,
        )
        self.assertNotIn('      - "host/greenhouse-manager/**"', text)


if __name__ == "__main__":
    unittest.main()
