from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from b1i1_contract import GateStop
from b1i1_journal import Journal
from b1i1_recovery import controlled_recovery, read_only_reconcile
from b1i1_transaction import execute
from test_b1i1_transaction import FakeOps, authority, budget


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)

    def sample(self):
        return Journal.create(self.root, authority(), "e" * 48)

    def test_unauthorized_recovery_can_never_mutate(self):
        ops = FakeOps()
        state = self.sample()
        with self.assertRaisesRegex(GateStop, "RECOVERY_NOT_AUTHORIZED"):
            controlled_recovery(state, authority(), ops, exact_recovery_authorized=False)
        self.assertEqual(ops.calls, [])

    def test_readonly_unknown_uncommitted_never_mutates(self):
        ops = FakeOps()
        state = self.sample()
        status = read_only_reconcile(state, authority(), ops)
        self.assertEqual(status.status, "UNKNOWN_FROZEN")
        self.assertEqual(ops.calls, [])

    def test_rollback_success_requires_stable_original_and_broker(self):
        ops = FakeOps(failure="health")
        self.assertEqual(
            execute(self.root, authority(), ops, budget(), transaction_token="f" * 48).status,
            "FAIL_ROLLED_BACK",
        )
        state = Journal.load(self.root)
        self.assertEqual(read_only_reconcile(state, authority(), ops).status, "VERIFIED_ROLLED_BACK")
        ops.old_health = False
        self.assertEqual(read_only_reconcile(state, authority(), ops).status, "UNKNOWN_FROZEN")
        ops.old_health = True
        ops.broker_unchanged = False
        self.assertEqual(read_only_reconcile(state, authority(), ops).status, "UNKNOWN_FROZEN")

    def test_recovery_no_automatic_replay_after_success(self):
        ops = FakeOps()
        self.assertEqual(
            execute(self.root, authority(), ops, budget(), transaction_token="a" * 48).status,
            "PASS",
        )
        state = Journal.load(self.root)
        status = controlled_recovery(state, authority(), ops, exact_recovery_authorized=True)
        self.assertEqual(status.status, "VERIFIED_COMMITTED")
        self.assertNotIn("restore", ops.calls)
        self.assertNotIn("quarantine", ops.calls)

    def test_private_root_0700_and_file_0600_are_required(self):
        state = self.sample()
        state.path.chmod(0o644)
        with self.assertRaisesRegex(GateStop, "JOURNAL_MODE_INVALID"):
            Journal.load(self.root)
        state.path.chmod(0o600)
        self.root.chmod(0o755)
        with self.assertRaisesRegex(GateStop, "PRIVATE_ROOT_PERMISSIONS_INVALID"):
            Journal.load(self.root)

    def test_symlink_journal_is_rejected(self):
        state = self.sample()
        actual = self.root / "saved"
        state.path.rename(actual)
        state.path.symlink_to(actual)
        with self.assertRaisesRegex(GateStop, "JOURNAL_MISSING"):
            Journal.load(self.root)

    def test_authentication_snapshot_drift_rejected_without_ops(self):
        state = self.sample()
        orig = authority()
        from b1i1_contract import Authority
        drift = Authority(
            old_manager_id="attacker", old_image=orig.old_image,
            broker_id=orig.broker_id, broker_started_at=orig.broker_started_at,
            broker_restart_count=orig.broker_restart_count,
            candidate_image_id=orig.candidate_image_id,
            source_ref=orig.source_ref,
            fresh_mounts=orig.fresh_mounts, ro_mounts=orig.ro_mounts,
        )
        ops = FakeOps()
        with self.assertRaisesRegex(GateStop, "JOURNAL_AUTHORITY_DRIFT"):
            read_only_reconcile(state, drift, ops)
        self.assertEqual(ops.calls, [])

    def test_forged_committed_without_candidate_id_rejected(self):
        state = self.sample()
        state.save(phase="FINALIZED", committed=True)
        with self.assertRaisesRegex(GateStop, "COMMITTED_CANDIDATE_NOT_BOUND"):
            Journal.load(self.root)

    def test_invalid_transaction_phase_and_rollback_flag_rejected(self):
        state = self.sample()
        state.save(phase="IMPOSSIBLE_PHASE")
        with self.assertRaisesRegex(GateStop, "JOURNAL_PHASE_INVALID"):
            Journal.load(self.root)
        state.save(phase="FAIL_ROLLED_BACK", rollback_result="INCOMPLETE")
        with self.assertRaisesRegex(GateStop, "JOURNAL_ROLLBACK_RESULT_DRIFT"):
            Journal.load(self.root)

    def test_durable_intent_is_persisted_before_docker_stop(self):
        ops = FakeOps()
        def kill_before_stop(a):
            recorded = Journal.load(self.root)
            self.assertEqual(recorded.doc["phase"], "OLD_STOP_INTENT")
            raise SystemExit("simulated abrupt death")
        ops.stop_old = kill_before_stop
        with self.assertRaises(SystemExit):
            execute(self.root, authority(), ops, budget(), transaction_token="d" * 48)
        self.assertTrue(ops.original_running)
        self.assertEqual(Journal.load(self.root).doc["phase"], "OLD_STOP_INTENT")

    def test_crash_unknown_container_never_modifies_candidate(self):
        ops = FakeOps(failure="create_candidate", after_side_effect=True)
        def killed(name):
            if name == "create_candidate":
                raise SystemExit(9)
        ops.end = killed
        with self.assertRaises(SystemExit):
            execute(self.root, authority(), ops, budget(), transaction_token="d" * 48)
        state = Journal.load(self.root)
        ops.candidate_owned = False
        result = controlled_recovery(state, authority(), ops, exact_recovery_authorized=True)
        self.assertEqual(result.status, "FAIL_ROLLBACK_INCOMPLETE")
        self.assertNotIn("quarantine", ops.calls)
        self.assertFalse(ops.original_running)

    def test_partial_journal_write_failure_freezes_all_future_mutations(self):
        import b1i1_journal as journal_module
        state = self.sample()
        real_write = journal_module._write

        def write_then_uncertain(path, doc, *, create):
            real_write(path, doc, create=create)
            if not create:
                raise OSError("fsync completion uncertain")

        with patch.object(journal_module, "_write", side_effect=write_then_uncertain):
            with self.assertRaisesRegex(GateStop, "JOURNAL_DURABILITY_UNKNOWN_FROZEN"):
                state.intent("OLD_STOP_INTENT")
        self.assertTrue(state.uncertain)
        self.assertEqual(state.doc["phase"], "PREPARE_INTENT")
        self.assertEqual(Journal.load(self.root).doc["phase"], "OLD_STOP_INTENT")
        with self.assertRaisesRegex(GateStop, "JOURNAL_DURABILITY_UNKNOWN_FROZEN"):
            state.intent("OLD_PARK_INTENT")
        ops = FakeOps()
        self.assertEqual(
            read_only_reconcile(state, authority(), ops).status,
            "UNKNOWN_FROZEN",
        )
        with self.assertRaisesRegex(GateStop, "JOURNAL_DURABILITY_UNKNOWN_FROZEN"):
            controlled_recovery(state, authority(), ops, exact_recovery_authorized=True)
        self.assertEqual(ops.calls, [])

    def test_post_stop_journal_failure_does_not_attempt_unsafe_inline_rollback(self):
        import b1i1_journal as journal_module
        original = journal_module._write
        ops = FakeOps()
        def broken_after_old_stop(path, doc, *, create):
            original(path, doc, create=create)
            if doc.get("phase") == "OLD_PARK_INTENT":
                raise OSError("record persisted but fsync unknown")
        with patch.object(journal_module, "_write", side_effect=broken_after_old_stop):
            result = execute(
                self.root, authority(), ops, budget(),
                transaction_token="c" * 48,
            )
        self.assertEqual(result.status, "UNKNOWN_FROZEN")
        self.assertEqual(result.reason, "JOURNAL_DURABILITY_UNKNOWN_FROZEN")
        self.assertFalse(ops.original_running)
        self.assertNotIn("restore", ops.calls)
        self.assertNotIn("quarantine", ops.calls)
        self.assertEqual(Journal.load(self.root).doc["phase"], "OLD_PARK_INTENT")

    def test_prepare_journal_failure_does_not_claim_normal_stop(self):
        import b1i1_journal as journal_module
        original = journal_module._write
        ops = FakeOps("prepare")
        def broken_prepare(path, doc, *, create):
            original(path, doc, create=create)
            if doc.get("phase") == "PREPARE_STOP":
                raise OSError("write report lost after replace")
        with patch.object(journal_module, "_write", side_effect=broken_prepare):
            result = execute(
                self.root, authority(), ops, budget(),
                transaction_token="c" * 48,
            )
        self.assertEqual(result.status, "UNKNOWN_FROZEN")
        self.assertTrue(ops.original_running)
        self.assertNotIn("stop_old", ops.calls)

    def test_source_only_no_docker_or_ssh_entrypoint(self):
        import b1i1_transaction
        import b1i1_supervisor
        import b1i1_recovery
        self.assertFalse(hasattr(b1i1_transaction, "main"))
        self.assertFalse(hasattr(b1i1_supervisor, "main"))
        self.assertFalse(hasattr(b1i1_recovery, "main"))


if __name__ == "__main__":
    unittest.main()
