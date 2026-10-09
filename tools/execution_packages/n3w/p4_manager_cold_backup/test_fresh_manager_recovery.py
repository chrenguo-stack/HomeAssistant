from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fresh_manager_deploy as deploy
import fresh_manager_recovery as recovery


def origin():
    return {"Id": "old-id", "Image": "old-image", "State": {"Running": True}}


def broker():
    return {"Id": "broker-id", "State": {"Running": True, "StartedAt": "same"}, "RestartCount": 0}


def transaction(**changes):
    value = {
        "schema": "gh.n3w.p4.fresh-manager-deploy/1",
        "committed": False,
        "old_manager_id": "old-id",
        "old_manager_image": "old-image",
        "candidate_image_id": "new-image",
        "candidate_id": "new-id",
    }
    value.update(changes)
    return value


class SimulatedDocker:
    def __init__(self, *, candidate=True, parked=True, running=True):
        self.containers = {}
        if candidate:
            self.containers["greenhouse-manager"] = {
                "Id": "new-id", "Image": "new-image", "State": {"Running": running}
            }
        if parked:
            self.containers[deploy.PARKED_NAME] = {
                "Id": "old-id", "Image": "old-image", "State": {"Running": False}
            }
        self.actions = []
        self.broker_current = broker()
        self.fail_action = ""

    def inspect(self, kind, name):
        assert kind == "container"
        if name == "n3wfc4-broker-1":
            return copy.deepcopy(self.broker_current)
        return copy.deepcopy(self.containers[name])

    def exists(self, name):
        return name in self.containers

    def action(self, *args, timeout=30):
        self.actions.append(args)
        if self.fail_action and args[0] == self.fail_action:
            raise recovery.RecoveryStop("INJECTED_DOCKER_FAILURE")
        if args[0] == "stop":
            self.containers[args[-1]]["State"]["Running"] = False
        elif args[0] == "rename":
            self.containers[args[-1]] = self.containers.pop(args[1])
        else:
            raise AssertionError(args)

    def resume(self, old, saved_broker):
        assert self.containers["greenhouse-manager"]["Id"] == old["Id"]
        self.containers["greenhouse-manager"]["State"]["Running"] = True


class RecoveryFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.private = Path(self.temp.name)
        self.current = SimulatedDocker()
        self.txn = transaction()
        patches = [
            patch.object(recovery.window, "get_private_origin", return_value=(origin(), broker())),
            patch.object(recovery, "load_state", side_effect=lambda _: (
                json.loads((self.private / deploy.STATE_FILE).read_text())
                if (self.private / deploy.STATE_FILE).exists() else self.txn
            )),
            patch.object(recovery.deploy, "container_exists", side_effect=self.current.exists),
            patch.object(recovery.deploy, "docker_json", side_effect=self.current.inspect),
            patch.object(recovery, "_run_docker", side_effect=self.current.action),
            patch.object(recovery.window, "resume_original_manager", side_effect=self.current.resume),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def test_candidate_stopped_parked_original_renamed_and_restarted(self):
        recovery.recover_original(self.private)
        self.assertEqual(self.current.containers["greenhouse-manager"]["Id"], "old-id")
        self.assertTrue(self.current.containers["greenhouse-manager"]["State"]["Running"])
        self.assertEqual(self.current.containers[deploy.FAILED_NAME]["Id"], "new-id")
        self.assertEqual(
            [action[0] for action in self.current.actions],
            ["stop", "rename", "rename"],
        )
        self.assertTrue((self.private / deploy.STATE_FILE).is_file())

    def test_candidate_image_identity_mismatch_blocks_any_mutation(self):
        self.current.containers["greenhouse-manager"]["Image"] = "untrusted"
        with self.assertRaisesRegex(recovery.RecoveryStop, "ROLLBACK_CANDIDATE_IMAGE_MISMATCH"):
            recovery.recover_original(self.private)
        self.assertEqual(self.current.actions, [])

    def test_candidate_container_id_mismatch_blocks_any_mutation(self):
        self.current.containers["greenhouse-manager"]["Id"] = "unexpected-id"
        with self.assertRaisesRegex(recovery.RecoveryStop, "ROLLBACK_CANDIDATE_ID_MISMATCH"):
            recovery.recover_original(self.private)
        self.assertEqual(self.current.actions, [])

    def test_parked_original_missing_prevents_candidate_stop(self):
        del self.current.containers[deploy.PARKED_NAME]
        with self.assertRaisesRegex(recovery.RecoveryStop, "ROLLBACK_PARKED_OLD_MANAGER_MISSING"):
            recovery.recover_original(self.private)
        self.assertEqual(self.current.actions, [])

    def test_candidate_stop_failure_fails_closed(self):
        self.current.fail_action = "stop"
        with self.assertRaisesRegex(recovery.RecoveryStop, "INJECTED_DOCKER_FAILURE"):
            recovery.recover_original(self.private)
        self.assertNotIn(deploy.FAILED_NAME, self.current.containers)

    def test_crash_after_park_before_candidate_create_restores_old(self):
        del self.current.containers["greenhouse-manager"]
        self.txn["candidate_id"] = None
        recovery.recover_original(self.private)
        self.assertEqual([x[0] for x in self.current.actions], ["rename"])
        self.assertTrue(self.current.containers["greenhouse-manager"]["State"]["Running"])

    def test_failure_while_old_stopped_without_rename_resumes_original(self):
        self.current.containers["greenhouse-manager"] = self.current.containers.pop(deploy.PARKED_NAME)
        self.current.containers["greenhouse-manager"]["State"]["Running"] = False
        recovery.recover_original(self.private)
        self.assertEqual(self.current.actions, [])
        self.assertTrue(self.current.containers["greenhouse-manager"]["State"]["Running"])

    def test_old_manager_restart_failure_never_produces_pass(self):
        with patch.object(recovery.window, "resume_original_manager", side_effect=recovery.window.WindowStop("synthetic restart")):
            with self.assertRaisesRegex(recovery.RecoveryStop, "OLD_MANAGER_RESTART_FAILED"):
                recovery.recover_original(self.private)
        self.assertFalse((self.private / deploy.STATE_FILE).exists())

    def test_committed_candidate_crash_in_supervised_stop_post_restores_old(self):
        self.txn["committed"] = True
        self.current.containers["greenhouse-manager"]["State"]["Running"] = False
        with self.assertRaisesRegex(recovery.RecoveryStop, "POST_COMMIT_SUPERVISOR_VERIFICATION_FAILED_ROLLED_BACK"):
            recovery.supervised_stop_post(self.private)
        self.assertEqual(self.current.containers["greenhouse-manager"]["Id"], "old-id")
        self.assertTrue(self.current.containers["greenhouse-manager"]["State"]["Running"])
        saved = json.loads((self.private / deploy.STATE_FILE).read_text())
        self.assertFalse(saved["committed"])
        self.assertTrue(saved["supervised_post_commit_verification_failed"])
        self.assertEqual(saved["rollback_result"], "PASS")

    def test_committed_candidate_is_not_rolled_back(self):
        self.txn["committed"] = True
        recovery.recover_original(self.private)
        self.assertEqual(self.current.actions, [])
        self.assertEqual(self.current.containers["greenhouse-manager"]["Id"], "new-id")

    def test_broker_drift_prevents_rollback_pass(self):
        self.current.broker_current["RestartCount"] = 1
        with self.assertRaisesRegex(deploy.DeployStop, "BROKER_RESTART_COUNT_CHANGED"):
            recovery.recover_original(self.private)
        self.assertEqual(self.current.containers["greenhouse-manager"]["Id"], "old-id")

    def test_no_transaction_does_not_recreate_or_stop(self):
        self.txn = None
        self.current.containers["greenhouse-manager"] = self.current.containers.pop(deploy.PARKED_NAME)
        with patch.object(recovery.window, "check_old_running") as check:
            recovery.recover_original(self.private)
            check.assert_called_once()
        self.assertEqual(self.current.actions, [])


if __name__ == "__main__":
    unittest.main()
