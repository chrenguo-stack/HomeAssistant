from __future__ import annotations

import unittest
from pathlib import Path

from tools import h3_rc2_shared_packages_compatibility as runner


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/h3-rc2-shared-packages-compatibility-ci.yml"
LEGACY = {
    "d2": ".github/workflows/h3-n2-stage2d2-candidate-mqtt-validator-ci.yml",
    "d3": ".github/workflows/h3-n2-stage2d3-activation-transaction-ci.yml",
    "d4": ".github/workflows/h3-n2-stage2d4-profile-lifecycle-integration-ci.yml",
}
SHARED = ("core", "control", "buses", "sensors", "display")


class H3CompatibilitySourceContract(unittest.TestCase):
    def test_all_three_stages_and_exact_legacy_sources(self) -> None:
        self.assertEqual(set(runner.STAGES), set(LEGACY))
        for stage_name, legacy_path in LEGACY.items():
            with self.subTest(stage=stage_name):
                stage = runner.STAGES[stage_name]
                legacy = (ROOT / legacy_path).read_text(encoding="utf-8")
                self.assertGreaterEqual(len(stage.host_sources), 2)
                for filename in stage.host_sources:
                    self.assertIn(filename, legacy)
                    self.assertTrue((ROOT / runner.COMPONENT / filename).is_file())
                self.assertIn(stage.minimal_config, legacy)
                self.assertIn(stage.product_config, legacy)
                self.assertIn(stage.component_object, legacy)
                self.assertIn(stage.lab_object, legacy)
                self.assertEqual(stage.link_crypto, stage_name == "d4")
                if stage.link_crypto:
                    self.assertIn("-lcrypto", legacy)

    def test_three_minimal_and_full_board_targets_exist(self) -> None:
        for stage_name, stage in runner.STAGES.items():
            with self.subTest(stage=stage_name):
                minimal = ROOT / stage.minimal_dir / stage.minimal_config
                product = runner.RC2 / stage.product_config
                self.assertTrue(minimal.is_file())
                self.assertTrue(product.is_file())
                content = product.read_text(encoding="utf-8")
                for package in SHARED:
                    self.assertIn(f"!include packages/{package}.yml", content)

    def test_exact_workflow_trigger_and_pr_supersession(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for name in SHARED:
            self.assertEqual(
                workflow.count(f'"firmware/esphome_rc/f1_0_rc2/packages/{name}.yml"'),
                2,
            )
        self.assertNotIn("packages/**", workflow)
        self.assertIn("max-parallel: 2", workflow)
        self.assertIn("stage: [d2, d3, d4]", workflow)
        self.assertIn("fail-fast: false", workflow)
        self.assertIn("timeout-minutes: 55", workflow)
        self.assertIn("github.event.pull_request.number || github.run_id", workflow)
        self.assertIn("github.event_name == 'pull_request'", workflow)

    def test_old_scope_gates_are_not_bypassed_or_invoked(self) -> None:
        source = (ROOT / "tools/h3_rc2_shared_packages_compatibility.py").read_text(
            encoding="utf-8"
        )
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("h3_n2_stage2d2_candidate_mqtt_boundary_gate", source + workflow)
        self.assertNotIn("h3_n2_stage2d3_activation_boundary_gate", source + workflow)
        self.assertNotIn("h3_n2_stage2d4_profile_lifecycle_boundary_gate", source + workflow)
        self.assertIn("verify_compile(stage, (minimal_log, product_log), ephemeral)", source)
        self.assertIn("secrets_file.unlink(missing_ok=True)", source)
        self.assertIn("INFO Successfully compiled program.", source)
        self.assertIn("node_pairing_wifi_ssid", source)
        self.assertIn("node_pairing_wifi_password", source)
        self.assertNotIn("continue-on-error:", workflow)
        self.assertNotIn("if: always()", workflow)

    def test_host_invocation_matches_original_contract(self) -> None:
        for stage_name, stage in runner.STAGES.items():
            with self.subTest(stage=stage_name):
                command = runner.host_command(stage, Path("/tmp/h3-contract-test"))
                self.assertIn("-std=gnu++20", command)
                self.assertIn("-Werror", command)
                self.assertIn(runner.COMPONENT, command)
                self.assertEqual("-lcrypto" in command, stage_name == "d4")
                self.assertTrue(command[-2:] == ["-o", "/tmp/h3-contract-test"])


if __name__ == "__main__":
    unittest.main()
