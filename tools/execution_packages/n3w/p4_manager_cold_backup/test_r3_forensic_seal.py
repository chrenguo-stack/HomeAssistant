from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import r3_forensic_seal as seal


class R3ForensicSealTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.private = Path(self.temp.name)
        base = self.private / "fresh-manager-runtime-state"
        base.mkdir(mode=0o700)
        self.sources = {
            "/var/lib/greenhouse-manager-registration": str(base / "registration"),
            "/var/lib/greenhouse-manager/n3w": str(base / "n3w"),
            "/var/lib/greenhouse-manager/n3w/relay-keys": str(base / "relay-keys"),
        }
        for source in self.sources.values():
            Path(source).mkdir(mode=0o700)
        self.old = {"Id": "original-manager"}
        self.broker = {"Id": "original-broker"}
        self.shadow = {
            "Id": "stopped-shadow-id",
            "Image": "sha256:candidate",
            "State": {"Running": False},
        }
        self.journal = {
            "schema": "gh.n3w.p4.fresh-manager-deploy/1",
            "phase": "FRESH_SOURCES_PREPARED_EMPTY",
            "committed": False,
            "rollback_result": "PASS",
            "rollback_phase": "ORIGINAL_MANAGER_RESTORED",
            "candidate_id": None,
            "old_manager_id": self.old["Id"],
            "broker_id": self.broker["Id"],
            "candidate_image_id": self.shadow["Image"],
            "fresh_sources": self.sources,
            "manager_uid": 123,
            "manager_gid": 456,
        }
        self.r2_state = self.private / seal.R2_STATE_FILE
        self.save_state()
        self.patches = [
            patch.object(seal.deploy, "verify_r5_rollback_authority"),
            patch.object(seal.window, "get_private_origin",
                         return_value=(self.old, self.broker)),
            patch.object(seal.window, "check_old_running"),
            patch.object(seal.deploy, "docker_json", side_effect=self.docker_json),
            patch.object(seal.deploy, "broker_unchanged"),
            patch.object(seal.deploy, "container_exists",
                         side_effect=lambda n: n == seal.R2_SHADOW),
            patch.object(seal.fresh, "validate_fresh_sources"),
            patch.object(seal.contract, "verify_stopped_shadow_matches_origin"),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def docker_json(self, kind, name):
        self.assertEqual(kind, "container")
        return {
            seal.contract.MANAGER_NAME: self.old,
            seal.contract.BROKER_NAME: self.broker,
            seal.R2_SHADOW: self.shadow,
        }[name]

    def save_state(self):
        self.r2_state.write_text(json.dumps(self.journal))
        self.r2_state.chmod(0o600)

    def test_exact_r2_safe_stopped_shadow_can_be_sealed(self):
        seal.seal_r2(self.private)
        saved = self.private / seal.R3_SEAL_FILE
        self.assertTrue(saved.is_file())
        self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
        contents = json.loads(saved.read_text())
        self.assertEqual(contents["schema"], seal.R3_SEAL_SCHEMA)
        self.assertEqual(contents["r2_original_manager_id"], "original-manager")
        self.assertEqual(contents["r2_shadow_container_id"], "stopped-shadow-id")
        seal.require_r3_seal(self.private)

    def test_nonreplayable_seal_does_not_overwrite(self):
        seal.seal_r2(self.private)
        with self.assertRaisesRegex(seal.SealStop, "R3_FORENSIC_SEAL_ALREADY_EXISTS_NO_REPLAY"):
            seal.seal_r2(self.private)

    def test_r2_journal_tampering_blocks_further_use(self):
        seal.seal_r2(self.private)
        self.journal["unexpected"] = "tampered"
        self.save_state()
        with self.assertRaisesRegex(seal.SealStop, "R3_SEAL_R2_EVIDENCE_DRIFT"):
            seal.require_r3_seal(self.private)

    def test_r2_transaction_must_have_safe_rollback_result(self):
        self.journal["rollback_result"] = None
        self.save_state()
        with self.assertRaisesRegex(seal.SealStop, "R2_JOURNAL_NOT_SAFE_FOR_R3"):
            seal.seal_r2(self.private)
        self.assertFalse((self.private / seal.R3_SEAL_FILE).exists())

    def test_r2_transaction_rejects_any_created_candidate_id(self):
        self.journal["candidate_id"] = "candidate-existing"
        self.save_state()
        with self.assertRaisesRegex(seal.SealStop, "R2_JOURNAL_NOT_SAFE_FOR_R3"):
            seal.verify_r2(self.private)

    def test_original_manager_identity_drift_blocks_seal(self):
        self.journal["old_manager_id"] = "wrong"
        self.save_state()
        with self.assertRaisesRegex(seal.SealStop, "R2_JOURNAL_NOT_SAFE_FOR_R3"):
            seal.verify_r2(self.private)

    def test_shadow_must_remain_stopped_and_same_image(self):
        self.shadow["State"]["Running"] = True
        with self.assertRaisesRegex(seal.SealStop, "R2_SHADOW_IMAGE_OR_STATE_CHANGED"):
            seal.verify_r2(self.private)
        self.shadow["State"]["Running"] = False
        self.shadow["Image"] = "sha256:unexpected"
        with self.assertRaisesRegex(seal.SealStop, "R2_SHADOW_IMAGE_OR_STATE_CHANGED"):
            seal.verify_r2(self.private)

    def test_any_r2_parked_original_blocks_seal(self):
        with patch.object(seal.deploy, "container_exists", side_effect=lambda n: True):
            with self.assertRaisesRegex(seal.SealStop, "R2_PARKED_OR_FAILED_CONTAINER_PRESENT"):
                seal.verify_r2(self.private)

    def test_fresh_source_must_remain_inside_original_r2_private_base(self):
        self.journal["fresh_sources"] = dict(self.sources)
        self.journal["fresh_sources"]["/var/lib/greenhouse-manager/n3w"] = "/tmp/untrusted"
        self.save_state()
        with self.assertRaisesRegex(seal.SealStop, "R2_FRESH_SOURCE_OUTSIDE_PRIVATE_BASE"):
            seal.verify_r2(self.private)


if __name__ == "__main__":
    unittest.main()
