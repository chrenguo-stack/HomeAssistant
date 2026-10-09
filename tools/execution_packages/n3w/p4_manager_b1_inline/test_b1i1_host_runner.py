from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from b1i1_contract import GateStop
from b1i1_host_runner import HOST_ATTEMPT_MARKER, execute_host_owned
from b1i1_supervisor import HostOwnedPlan
from test_b1i1_transaction import FakeOps, authority, budget


def plan():
    return HostOwnedPlan(
        service_name="n3w-p4-b1i1-source-only-owner",
        user_authorization="NEW_B1I1_EXPLICIT_ONLY",
        source_ref="a" * 40,
        stage_name="p4-manager-b1i1-isolated-stage",
        journal_name="b1i1-private-transaction.json",
    )


class HostOwnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)

    def run_host(self, **kw):
        return execute_host_owned(
            self.root, authority(), kw.pop("ops", FakeOps()),
            budget(), plan(),
            authorization_id=kw.pop("authorization_id", "NEW_B1I1_EXPLICIT_ONLY"),
            ssh_is_owner=kw.pop("ssh_is_owner", False),
            host_unit_verified=kw.pop("host_unit_verified", True),
            now=lambda: 0,
        )

    def test_exact_authorization_and_host_ownership_required(self):
        with self.assertRaisesRegex(GateStop, "LIVE_AUTHORIZATION_ID_MISMATCH"):
            self.run_host(authorization_id="R4_OLD_AUTH")
        with self.assertRaisesRegex(GateStop, "HOST_OWNER_NOT_PROVEN"):
            self.run_host(ssh_is_owner=True)
        with self.assertRaisesRegex(GateStop, "HOST_OWNER_NOT_PROVEN"):
            self.run_host(host_unit_verified=False)
        self.assertFalse((self.root / HOST_ATTEMPT_MARKER).exists())

    def test_host_claim_is_nonreplayable_and_no_old_stop_before_authorized(self):
        self.assertEqual(self.run_host().status, "PASS")
        marker = self.root / HOST_ATTEMPT_MARKER
        self.assertTrue(marker.exists())
        self.assertEqual(marker.stat().st_mode & 0o777, 0o600)
        ops = FakeOps()
        with self.assertRaises(FileExistsError):
            self.run_host(ops=ops)
        self.assertNotIn("stop_old", ops.calls)

    def test_failed_preflight_keeps_attempt_record_and_blocks_retry(self):
        ops = FakeOps("preflight")
        with self.assertRaises(GateStop):
            self.run_host(ops=ops)
        self.assertTrue((self.root / HOST_ATTEMPT_MARKER).exists())
        with self.assertRaises(FileExistsError):
            self.run_host()
        self.assertNotIn("stop_old", ops.calls)

    def test_host_plan_cannot_refer_to_r4_old_source_ref(self):
        a = authority()
        modified_plan = HostOwnedPlan(
            service_name="n3w-p4-b1i1-host", user_authorization="NEW_B1I1_EXPLICIT_ONLY",
            source_ref="b" * 40, stage_name="p4-manager-b1i1-stage",
            journal_name="b1i1-private-transaction.json",
        )
        with self.assertRaisesRegex(GateStop, "EXACT_SOURCE_BINDING_MISMATCH"):
            execute_host_owned(
                self.root, a, FakeOps(), budget(), modified_plan,
                authorization_id="NEW_B1I1_EXPLICIT_ONLY",
                ssh_is_owner=False, host_unit_verified=True, now=lambda: 0,
            )
        self.assertFalse((self.root / HOST_ATTEMPT_MARKER).exists())


if __name__ == "__main__":
    unittest.main()
