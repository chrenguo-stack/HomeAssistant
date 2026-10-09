from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import r4_shadow_stable_fingerprint as fingerprint
from test_cutover_contract import old_manager, stopped_shadow


def fixture_shadow():
    return stopped_shadow(old_manager())


class R4StableFingerprintTests(unittest.TestCase):
    def _synthetic_r4_review(self):
        return {
            "r3_seal_file_sha256": "a" * 64,
            "r2_journal_sha256": "b" * 64,
            "r2_stable_shadow_sha256": "c" * 64,
            "r2_shadow_container_id": "r2-shadow-id",
            "r2_original_manager_id": "original-manager-id",
            "r2_broker_container_id": "broker-id",
            "legacy_full_inspect_digest_mismatch": True,
        }

    def test_r4_seal_cannot_be_overwritten_and_revalidation_rejects_drift(self):
        with tempfile.TemporaryDirectory() as path:
            private = Path(path)
            review = self._synthetic_r4_review()
            with patch.object(fingerprint, "verify_r3_no_cutover_and_history_intact"):
                with patch.object(fingerprint, "verify_legacy_r3_seal_readonly", return_value=review):
                    fingerprint.seal_r3_for_r4(private)
                    saved_path = private / fingerprint.R4_SEAL_FILE
                    original = saved_path.read_bytes()
                    self.assertEqual(saved_path.stat().st_mode & 0o777, 0o600)
                    fingerprint.require_r4_seal(private)
                    with self.assertRaisesRegex(fingerprint.FingerprintStop, "R4_FORENSIC_SEAL_ALREADY_EXISTS_NO_REPLAY"):
                        fingerprint.seal_r3_for_r4(private)
                    self.assertEqual(original, saved_path.read_bytes())
                new_review = dict(review, r2_stable_shadow_sha256="d" * 64)
                with patch.object(fingerprint, "verify_legacy_r3_seal_readonly", return_value=new_review):
                    with self.assertRaisesRegex(fingerprint.FingerprintStop, "R4_SEAL_PROTECTED_STATE_DRIFT"):
                        fingerprint.require_r4_seal(private)
                altered_history = dict(review, r3_seal_file_sha256="e" * 64)
                with patch.object(fingerprint, "verify_legacy_r3_seal_readonly", return_value=altered_history):
                    with self.assertRaisesRegex(fingerprint.FingerprintStop, "R4_SEAL_PROTECTED_STATE_DRIFT"):
                        fingerprint.require_r4_seal(private)
                self.assertEqual(original, saved_path.read_bytes())

    def test_missing_r4_seal_never_allows_deployment_preflight(self):
        with tempfile.TemporaryDirectory() as path:
            private = Path(path)
            with self.assertRaisesRegex(fingerprint.FingerprintStop, "R4_SEAL_NOT_PRESENT_OR_INSECURE"):
                fingerprint.require_r4_seal(private)

    def test_r3_cutover_residue_blocks_r4_with_no_mutation(self):
        with tempfile.TemporaryDirectory() as path:
            private = Path(path)
            stage = private / fingerprint.R3_STAGE
            stage.mkdir(mode=0o700)
            with patch.object(fingerprint.deploy, "container_exists", return_value=False):
                fingerprint.verify_r3_no_cutover_and_history_intact(private)
                (private / fingerprint.R3_TRANSACTION_FILE).write_text("historical")
                with self.assertRaisesRegex(fingerprint.FingerprintStop, "R3_HISTORICAL_TRANSACTION_OR_DATA_UNEXPECTED"):
                    fingerprint.verify_r3_no_cutover_and_history_intact(private)
                (private / fingerprint.R3_TRANSACTION_FILE).unlink()
                (private / fingerprint.R3_FRESH_BASE).mkdir()
                with self.assertRaisesRegex(fingerprint.FingerprintStop, "R3_HISTORICAL_TRANSACTION_OR_DATA_UNEXPECTED"):
                    fingerprint.verify_r3_no_cutover_and_history_intact(private)
                (private / fingerprint.R3_FRESH_BASE).rmdir()
            with patch.object(fingerprint.deploy, "container_exists", side_effect=lambda name: name == fingerprint.R3_FAILED):
                with self.assertRaisesRegex(fingerprint.FingerprintStop, "R3_HISTORICAL_DEPLOYMENT_CONTAINER_EXISTS"):
                    fingerprint.verify_r3_no_cutover_and_history_intact(private)

    def test_dynamic_docker_inspect_fields_do_not_change_fingerprint(self):
        shadow = fixture_shadow()
        before = fingerprint.stable_shadow_sha256(shadow)
        changed = copy.deepcopy(shadow)
        changed["Created"] = "new-timestamp"
        changed["State"]["ExitCode"] = 137
        changed["State"]["StartedAt"] = "different-timestamp"
        changed["State"]["FinishedAt"] = "different-timestamp"
        changed["NetworkSettings"] = {"Networks": {"dynamic": "changed"}}
        changed["GraphDriver"] = {"Data": {"runtime-private": "new"}}
        changed["RestartCount"] = 55
        self.assertEqual(before, fingerprint.stable_shadow_sha256(changed))

    def test_oom_unset_vs_false_is_same_stable_configuration(self):
        shadow = fixture_shadow()
        other = copy.deepcopy(shadow)
        other["HostConfig"]["OomKillDisable"] = False
        self.assertEqual(
            fingerprint.stable_shadow_sha256(shadow),
            fingerprint.stable_shadow_sha256(other),
        )

    def test_true_oom_override_fails_closed(self):
        shadow = fixture_shadow()
        shadow["HostConfig"]["OomKillDisable"] = True
        with self.assertRaisesRegex(
            fingerprint.FingerprintStop, "SHADOW_OOM_OVERRIDE_FORBIDDEN"
        ):
            fingerprint.stable_shadow_sha256(shadow)

    def test_identity_security_mount_log_and_secrets_drift_changes_digest(self):
        original = fixture_shadow()
        before = fingerprint.stable_shadow_sha256(original)
        edits = (
            lambda s: s.__setitem__("Id", "wrong-shadow"),
            lambda s: s.__setitem__("Image", "sha256:wrong-image"),
            lambda s: s["HostConfig"].__setitem__("ReadonlyRootfs", False),
            lambda s: s["HostConfig"].__setitem__("NetworkMode", "bridge"),
            lambda s: s["HostConfig"]["LogConfig"]["Config"].__setitem__("max-file", "9"),
            lambda s: s["Config"]["Env"].append("GH_NEW_SECRET=changed"),
            lambda s: s["Mounts"][0].__setitem__("Source", "/wrong-source"),
            lambda s: s["HostConfig"]["RestartPolicy"].__setitem__("Name", "always"),
        )
        for edit in edits:
            with self.subTest(edit=repr(edit)):
                altered = copy.deepcopy(original)
                edit(altered)
                self.assertNotEqual(before, fingerprint.stable_shadow_sha256(altered))

    def test_legacy_seal_readonly_accepts_only_full_inspect_hash_difference(self):
        original = fixture_shadow()
        saved = {
            "schema": "gh.n3w.p4.r3-r2-forensic-seal/1",
            "r2_journal_sha256": "1" * 64,
            "r2_shadow_inspect_sha256": "2" * 64,
            "r2_shadow_container_id": "shadow-identity",
            "r2_original_manager_id": "old-manager-id",
            "r2_broker_container_id": "broker-id",
            "r2_original_manager_still_running": True,
            "r2_rollback_result": "PASS",
            "r2_phase": "FRESH_SOURCES_PREPARED_EMPTY",
            "r2_shadow_stopped": True,
            "r3_fresh_state_must_be_independent": True,
        }
        live = dict(saved, r2_shadow_inspect_sha256="3" * 64)
        with tempfile.TemporaryDirectory() as tmp:
            private = Path(tmp)
            with patch.object(fingerprint.r3, "_private_json", return_value=(saved, b"synthetic-private-raw")):
                with patch.object(fingerprint.r3, "verify_r2", return_value=live):
                    with patch.object(fingerprint.deploy, "docker_json", return_value=original):
                        result = fingerprint.verify_legacy_r3_seal_readonly(private)
            self.assertTrue(result["legacy_full_inspect_digest_mismatch"])
            self.assertTrue(result["r2_shadow_full_contract_reverified"])
            self.assertEqual(result["r2_stable_shadow_sha256"], fingerprint.stable_shadow_sha256(original))
            self.assertFalse((private / "new-seal").exists())
            for key, value in (
                ("r2_journal_sha256", "4" * 64),
                ("r2_shadow_container_id", "other-shadow"),
                ("r2_original_manager_id", "other-manager"),
                ("r2_broker_container_id", "other-broker"),
                ("r2_rollback_result", "FAIL"),
            ):
                with self.subTest(key=key):
                    drift = dict(live, **{key: value})
                    with patch.object(fingerprint.r3, "_private_json", return_value=(saved, b"synthetic-private-raw")):
                        with patch.object(fingerprint.r3, "verify_r2", return_value=drift):
                            with self.assertRaisesRegex(
                                fingerprint.FingerprintStop, "R3_LEGACY_SEAL_PROTECTED_EVIDENCE_DRIFT"
                            ):
                                fingerprint.verify_legacy_r3_seal_readonly(private)

    def test_legacy_seal_additional_field_or_malformed_digest_stops(self):
        base = {
            "r2_shadow_inspect_sha256": "a" * 64,
            "r2_journal_sha256": "b" * 64,
        }
        for saved, live, expected_error in (
            (dict(base, injected="unknown"), base, "R3_LEGACY_SEAL_FIELD_SET_DRIFT"),
            (dict(base, r2_shadow_inspect_sha256="unsafe"), base, "R3_LEGACY_RAW_HASH_FORMAT_INVALID"),
        ):
            with self.subTest(error=expected_error):
                with patch.object(fingerprint.r3, "_private_json", return_value=(saved, b"private")):
                    with patch.object(fingerprint.r3, "verify_r2", return_value=live):
                        with self.assertRaisesRegex(fingerprint.FingerprintStop, expected_error):
                            fingerprint.verify_legacy_r3_seal_readonly(Path("/synthetic"))


if __name__ == "__main__":
    unittest.main()
