from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from b1i1_contract import Authority, FRESH_RW, EXISTING_RO, GateStop
from b1i1_journal import Journal
from b1i1_recovery import controlled_recovery, read_only_reconcile
from b1i1_supervisor import Budget, Deadline, HostOwnedPlan, require_host_owned_transaction
from b1i1_transaction import execute


def authority():
    return Authority(
        old_manager_id="original-container-id", old_image="sha256:original",
        broker_id="broker-id", broker_started_at="2026-10-09T00:00:00Z",
        broker_restart_count=0, candidate_image_id="sha256:candidate",
        source_ref="a" * 40, fresh_mounts=FRESH_RW, ro_mounts=EXISTING_RO,
    )


def budget():
    return Budget(total=950, forward_after_old_stop=280, rollback_reserve=300,
                  evidence_reserve=60, outer_grace=100)


class FakeOps:
    def __init__(self, failure=None, after_side_effect=False):
        self.failure = failure
        self.after_side_effect = after_side_effect
        self.calls = []
        self.original_running = True
        self.parked = False
        self.candidate = None
        self.candidate_running = False
        self.candidate_owned = True
        self.broker_unchanged = True
        self.old_health = True
        self.unknown_name_collision = False
        self.verify_final_count = 0

    def step(self, name):
        self.calls.append(name)
        if self.failure == name and not self.after_side_effect:
            self.failure = None
            raise GateStop("INJECTED_" + name.upper())

    def end(self, name):
        if self.failure == name and self.after_side_effect:
            self.failure = None
            raise GateStop("INJECTED_" + name.upper())

    def preflight(self, a):
        self.step("preflight")
        self.end("preflight")

    def prepare_fresh_and_shadow(self, a):
        self.step("prepare")
        self.end("prepare")

    def verify_pre_stop(self, a):
        self.step("pre_stop")
        if not self.original_running or not self.broker_unchanged:
            raise GateStop("PRESTOP_CHANGED")
        self.end("pre_stop")

    def stop_old(self, a):
        self.step("stop_old")
        self.original_running = False
        self.end("stop_old")

    def park_old(self, a):
        self.step("park_old")
        self.parked = True
        self.end("park_old")

    def create_candidate(self, a, token):
        self.step("create_candidate")
        self.candidate = "candidate-id"
        self.candidate_token = token
        self.end("create_candidate")
        return self.candidate

    def inspect_candidate(self, a, token):
        self.calls.append("inspect_candidate")
        if self.unknown_name_collision:
            return "foreign-container"
        return self.candidate

    def verify_candidate_ownership(self, a, token, candidate_id):
        self.calls.append("verify_candidate_ownership")
        return (
            self.candidate_owned and self.candidate == candidate_id
            and getattr(self, "candidate_token", None) == token
        )

    def start_candidate(self, a, candidate_id):
        self.step("start_candidate")
        self.candidate_running = True
        self.end("start_candidate")

    def verify_candidate_health(self, cid, checks):
        self.step("health")
        assert "healthz" in checks and "tcp47112" in checks and "udp47111" in checks
        self.end("health")

    def verify_fresh_zero_state(self, a):
        self.step("zero")
        self.end("zero")

    def verify_candidate_mounts_and_security(self, a, candidate_id):
        self.step("mounts")
        self.end("mounts")

    def verify_broker_ha_r5(self, a):
        self.step("broker")
        if not self.broker_unchanged:
            raise GateStop("BROKER_IDENTITY_CHANGED")
        self.end("broker")

    def verify_old_stopped_and_parked(self, a):
        self.step("parked_check")
        if self.original_running or not self.parked:
            raise GateStop("OLD_NOT_PARKED")
        self.end("parked_check")

    def quarantine_owned_candidate(self, a, cid):
        self.step("quarantine")
        assert cid == self.candidate
        self.candidate_running = False
        self.candidate = None
        self.end("quarantine")

    def restore_old_exact_id(self, a):
        self.step("restore")
        self.original_running = True
        self.parked = False
        self.end("restore")

    def verify_old_healthy_and_unchanged(self, a):
        self.step("old_health")
        if not self.original_running or not self.old_health:
            raise GateStop("ORIGINAL_NOT_HEALTHY")
        self.end("old_health")

    def verify_finalized(self, a, cid):
        self.verify_final_count += 1
        self.step("final")
        if self.candidate != cid or not self.candidate_running:
            raise GateStop("CANDIDATE_NOT_RUNNING")
        if not self.parked:
            raise GateStop("ORIGINAL_NOT_PARKED")
        self.end("final")


class InlineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)

    def run_tx(self, ops, **kw):
        return execute(self.root, authority(), ops, budget(),
                       transaction_token="d" * 48, **kw)

    def test_success_is_verified_and_keeps_old_parked(self):
        ops = FakeOps()
        result = self.run_tx(ops)
        self.assertEqual(result.status, "PASS")
        state = Journal.load(self.root)
        self.assertTrue(state.doc["committed"])
        self.assertEqual(state.doc["phase"], "FINALIZED")
        self.assertEqual(state.doc["candidate_id"], "candidate-id")
        self.assertFalse(ops.original_running)
        self.assertTrue(ops.parked)
        self.assertTrue(ops.candidate_running)
        self.assertNotIn("quarantine", ops.calls)
        self.assertEqual(ops.verify_final_count, 2)

    def test_prepare_failure_never_stops_old(self):
        for failure in ("prepare", "pre_stop"):
            with self.subTest(failure=failure):
                with tempfile.TemporaryDirectory() as path:
                    self.root = Path(path)
                    self.root.chmod(0o700)
                    ops = FakeOps(failure)
                    out = self.run_tx(ops)
                    self.assertEqual(out.status, "STOP_PREPARE")
                    self.assertTrue(ops.original_running)
                    self.assertFalse(ops.parked)
                    self.assertNotIn("stop_old", ops.calls)

    def test_preflight_failure_creates_no_journal(self):
        ops = FakeOps("preflight")
        with self.assertRaisesRegex(GateStop, "INJECTED_PREFLIGHT"):
            self.run_tx(ops)
        self.assertFalse((self.root / "b1i1-private-transaction.json").exists())

    def test_each_mutation_phase_fail_recovers_original(self):
        for failure in (
            "stop_old", "park_old", "create_candidate", "start_candidate",
            "health", "zero", "mounts", "broker", "parked_check", "final"
        ):
            with self.subTest(failure=failure):
                with tempfile.TemporaryDirectory() as path:
                    self.root = Path(path)
                    self.root.chmod(0o700)
                    ops = FakeOps(failure)
                    result = self.run_tx(ops)
                    self.assertEqual(result.status, "FAIL_ROLLED_BACK")
                    self.assertTrue(ops.original_running)
                    self.assertFalse(ops.parked)
                    self.assertEqual(Journal.load(self.root).doc["rollback_result"], "PASS")

    def test_after_side_effect_failure_uses_actual_inspection(self):
        for failure in ("stop_old", "park_old", "create_candidate", "start_candidate"):
            with self.subTest(failure=failure):
                with tempfile.TemporaryDirectory() as path:
                    self.root = Path(path)
                    self.root.chmod(0o700)
                    ops = FakeOps(failure, after_side_effect=True)
                    result = self.run_tx(ops)
                    self.assertEqual(result.status, "FAIL_ROLLED_BACK")
                    self.assertTrue(ops.original_running)
                    self.assertIsNone(ops.candidate)

    def test_create_then_crash_without_id_durable_recovers_owned_candidate(self):
        ops = FakeOps("create_candidate", after_side_effect=True)
        original_end = ops.end
        def simulate_kill(name):
            if name == "create_candidate":
                raise SystemExit(13)
            original_end(name)
        ops.end = simulate_kill
        with self.assertRaises(SystemExit):
            self.run_tx(ops)
        state = Journal.load(self.root)
        self.assertEqual(state.doc["phase"], "CANDIDATE_CREATE_INTENT")
        self.assertIsNone(state.doc["candidate_id"])
        self.assertEqual(ops.candidate, "candidate-id")
        self.assertTrue(ops.parked)
        before = read_only_reconcile(state, authority(), ops)
        self.assertEqual(before.status, "UNKNOWN_FROZEN")
        with self.assertRaisesRegex(GateStop, "RECOVERY_NOT_AUTHORIZED"):
            controlled_recovery(state, authority(), ops, exact_recovery_authorized=False)
        result = controlled_recovery(state, authority(), ops, exact_recovery_authorized=True)
        self.assertEqual(result.status, "FAIL_ROLLED_BACK")
        self.assertEqual(Journal.load(self.root).doc["candidate_id"], "candidate-id")
        self.assertTrue(ops.original_running)

    def test_unknown_candidate_ownership_freezes_and_never_quarantines(self):
        ops = FakeOps("create_candidate", after_side_effect=True)
        ops.candidate_owned = False
        result = self.run_tx(ops)
        self.assertEqual(result.status, "FAIL_ROLLBACK_INCOMPLETE")
        self.assertNotIn("quarantine", ops.calls)
        self.assertFalse(ops.original_running)
        self.assertTrue(ops.parked)
        self.assertEqual(Journal.load(self.root).doc["rollback_result"], "INCOMPLETE")

    def test_foreign_name_collision_freezes_and_never_quarantines(self):
        ops = FakeOps("create_candidate")
        ops.unknown_name_collision = True
        result = self.run_tx(ops)
        self.assertEqual(result.status, "FAIL_ROLLBACK_INCOMPLETE")
        self.assertNotIn("quarantine", ops.calls)

    def test_rollback_operative_failure_not_pass(self):
        ops = FakeOps("health")
        original = ops.restore_old_exact_id
        def blocked(a):
            ops.calls.append("restore")
            raise OSError("synthetic error")
        ops.restore_old_exact_id = blocked
        result = self.run_tx(ops)
        self.assertEqual(result.status, "FAIL_ROLLBACK_INCOMPLETE")
        self.assertEqual(Journal.load(self.root).doc["rollback_result"], "INCOMPLETE")
        self.assertFalse(ops.original_running)

    def test_replay_denied_and_journal_mode_0600(self):
        ops = FakeOps()
        self.assertEqual(self.run_tx(ops).status, "PASS")
        file = self.root / "b1i1-private-transaction.json"
        self.assertEqual(file.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            self.run_tx(FakeOps())
        self.assertTrue(Journal.load(self.root).doc["committed"])

    def test_commit_then_final_check_failure_never_rolls_back(self):
        ops = FakeOps()
        original = ops.verify_finalized
        def final(a, cid):
            original(a, cid)
            if ops.verify_final_count == 2:
                raise GateStop("FINAL_READONLY_UNVERIFIED")
        ops.verify_finalized = final
        result = self.run_tx(ops)
        self.assertEqual(result.status, "UNKNOWN_FROZEN")
        self.assertTrue(Journal.load(self.root).doc["committed"])
        self.assertNotIn("quarantine", ops.calls)
        self.assertTrue(ops.candidate_running)

    def test_commit_after_ssh_disconnection_readonly_reconcile(self):
        ops = FakeOps()
        self.assertEqual(self.run_tx(ops).status, "PASS")
        original_calls = len(ops.calls)
        result = read_only_reconcile(Journal.load(self.root), authority(), ops)
        self.assertEqual(result.status, "VERIFIED_COMMITTED")
        self.assertNotIn("quarantine", ops.calls[original_calls:])
        self.assertNotIn("restore", ops.calls[original_calls:])

    def test_broker_drift_prevents_rollback_pass(self):
        ops = FakeOps("zero")
        original = ops.verify_broker_ha_r5
        def drift(a):
            ops.broker_unchanged = False
            original(a)
        ops.verify_broker_ha_r5 = drift
        result = self.run_tx(ops)
        self.assertEqual(result.status, "FAIL_ROLLBACK_INCOMPLETE")

    def test_deadline_refuses_old_stop_without_reserve(self):
        ops = FakeOps()
        ticks = iter([0, 50, 200, 350, 400])
        out = self.run_tx(ops, now=lambda: next(ticks))
        self.assertEqual(out.status, "STOP_PREPARE")
        self.assertNotIn("stop_old", ops.calls)

    def test_budget_guards_cannot_be_disabled(self):
        with self.assertRaisesRegex(GateStop, "BUDGET_OVERCOMMITTED"):
            Budget(100, 80, 80, 20, 10).validate()
        with self.assertRaisesRegex(GateStop, "BUDGET_INVALID"):
            Budget(0, 1, 1, 1, 1).validate()
        d = Deadline(budget(), lambda: 0)
        d.enter_rollback()
        with self.assertRaisesRegex(GateStop, "FORWARD_AFTER_ROLLBACK_FORBIDDEN"):
            d.require_forward()

    def test_authority_mount_drift_rejected(self):
        a = authority()
        broken = Authority(
            old_manager_id=a.old_manager_id, old_image=a.old_image,
            broker_id=a.broker_id, broker_started_at=a.broker_started_at,
            broker_restart_count=0, candidate_image_id=a.candidate_image_id,
            source_ref=a.source_ref, fresh_mounts=tuple(reversed(FRESH_RW)),
            ro_mounts=a.ro_mounts,
        )
        with self.assertRaisesRegex(GateStop, "FRESH_RW_MOUNT_DRIFT"):
            broken.validate()

    def test_host_ownership_contract_never_allows_ssh_as_transaction_owner(self):
        with self.assertRaisesRegex(GateStop, "HOST_OWNER_NOT_PROVEN"):
            require_host_owned_transaction(ssh_is_owner=True, host_unit_verified=True)
        HostOwnedPlan(
            service_name="n3w-p4-b1i1-job", user_authorization="explicit-only",
            source_ref="a" * 40, stage_name="p4-manager-b1i1-stage",
            journal_name="b1i1-private-transaction.json"
        ).validate()
        with self.assertRaisesRegex(GateStop, "AUTOMATIC_REPLAY_FORBIDDEN"):
            HostOwnedPlan(
                service_name="n3w-p4-b1i1-job", user_authorization="x",
                source_ref="a" * 40, stage_name="p4-manager-b1i1-stage",
                journal_name="b1i1-private-transaction.json", restart="always"
            ).validate()

    def test_uncommitted_manual_recovery_requires_authorization(self):
        ops = FakeOps("start_candidate")
        self.assertEqual(self.run_tx(ops).status, "FAIL_ROLLED_BACK")
        journal = Journal.load(self.root)
        with self.assertRaisesRegex(GateStop, "RECOVERY_NOT_AUTHORIZED"):
            controlled_recovery(journal, authority(), ops, exact_recovery_authorized=False)
        self.assertEqual(read_only_reconcile(journal, authority(), ops).status, "VERIFIED_ROLLED_BACK")

    def test_new_business_state_does_not_imply_broker_dynsec_cleared(self):
        ops = FakeOps()
        self.assertEqual(self.run_tx(ops).status, "PASS")
        self.assertEqual(ops.calls.count("zero"), 1)
        self.assertIn("broker", ops.calls)
        self.assertNotIn("clear_broker", ops.calls)


if __name__ == "__main__":
    unittest.main()
