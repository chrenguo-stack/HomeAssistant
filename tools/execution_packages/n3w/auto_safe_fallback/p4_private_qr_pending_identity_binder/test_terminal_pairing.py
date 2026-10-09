from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import threading
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from bridge_handoff import GateStop, bind_terminal_projection
from terminal_pairing import _private_claim, once

NOW = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)
HARDWARE = "ghw-c6-00000000ff00"
PAIRING = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
SECRET = base64.urlsafe_b64encode(bytes(range(32))).rstrip(b"=").decode()
QR = f"GHN3W2:{HARDWARE}:{PAIRING}:{SECRET}"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


class TerminalFlowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.private = root / "private"
        self.private.mkdir(mode=0o700)
        self.snapshot = self.private / "snapshot.json"
        self.old = sorted(digest(f"ghw-c6-{i:012x}") for i in range(5))
        document = {
            "schema": "n3w.kf050.runtime-identity-snapshot/1",
            "hardware_id_sha256": self.old,
            "hardware_id_count": 5,
            "read_only": True,
            "manager_mutation": False,
            "manager_replay_mutation": False,
        }
        data = json.dumps(document, sort_keys=True).encode()
        self.snapshot.write_bytes(data)
        os.chmod(self.snapshot, 0o600)
        self.snapshot_sha = hashlib.sha256(data).hexdigest()
        self.projection = {
            "schema": "n3w.p4.terminal-pending-readonly/1",
            "historical_count": 5,
            "historical_hardware_hashes": self.old,
            "new_count": 1,
            "hardware_sha256": digest(HARDWARE),
            "pairing_sha256": digest(PAIRING),
            "expires_at": (NOW + timedelta(seconds=120)).isoformat(),
            "pending_state": "pending",
            "first_registration_no_history": True,
            "credential_history_clear": True,
            "replay_linkage_clear": True,
            "read_only": True,
            "read_at": NOW.isoformat(),
        }
        self.sent = []
        self.calls = 0

    def runner(self, cmd, *, capture_output, timeout, check, input=None):
        self.assertTrue(capture_output)
        self.assertFalse(check)
        self.assertEqual(cmd[0:1], ["ssh"])
        self.assertEqual(cmd[6], "root@192.168.20.31")
        self.assertNotIn(SECRET, " ".join(cmd))
        self.calls += 1
        if "p4-pending-readonly" in cmd:
            return subprocess.CompletedProcess(cmd, 0, json.dumps(self.projection).encode(), b"")
        self.assertIn("--payload-stdin", cmd)
        self.assertIn("-i", cmd)
        self.sent.append(input)
        return subprocess.CompletedProcess(
            cmd, 0,
            json.dumps({
                "schema": "gh.pair.setup-secret-import-result/1",
                "accepted": True,
                "code": "accepted",
            }).encode(),
            b"",
        )

    def invoke(self, *, confirm=lambda _: True, runner=None):
        return once(
            "root@192.168.20.31", "greenhouse-manager",
            self.snapshot, self.snapshot_sha, self.private,
            runner=runner or self.runner, read_qr=lambda: QR, confirm=confirm,
            clock=lambda: NOW,
        )

    def test_one_import_then_claim_blocks_duplicate(self):
        self.assertEqual(self.invoke(), "IMPORT_ACCEPTED_NOT_COMMITTED")
        self.assertEqual(self.sent, [(QR + "\n").encode()])
        marker = list(self.private.glob("p4-attempt-*.json"))
        self.assertEqual(len(marker), 1)
        self.assertEqual(marker[0].stat().st_mode & 0o777, 0o600)
        claim = json.loads(marker[0].read_text())
        self.assertEqual(claim["state"], "CLAIMED")
        self.assertNotIn(SECRET, marker[0].read_text())
        with self.assertRaises(GateStop):
            self.invoke()
        self.assertEqual(len(self.sent), 1)

    def test_declined_has_no_claim_and_no_secret_send(self):
        with self.assertRaises(GateStop):
            self.invoke(confirm=lambda _: False)
        self.assertEqual(self.sent, [])
        self.assertEqual(list(self.private.glob("p4-attempt-*.json")), [])

    def test_changed_manager_identity_before_import_stops(self):
        def runner(*args, **kwargs):
            result = self.runner(*args, **kwargs)
            if "p4-pending-readonly" in args[0] and self.calls == 2:
                altered = dict(self.projection)
                altered["pairing_sha256"] = "a" * 64
                return subprocess.CompletedProcess(args[0], 0, json.dumps(altered).encode(), b"")
            return result

        with self.assertRaises(GateStop):
            self.invoke(runner=runner)
        self.assertEqual(self.sent, [])

    def test_stale_projection_stops_without_import(self):
        self.projection["read_at"] = (NOW - timedelta(seconds=11)).isoformat()
        with self.assertRaises(GateStop):
            self.invoke()
        self.assertEqual(self.sent, [])

    def test_expired_projection_stops_without_import(self):
        self.projection["expires_at"] = (NOW + timedelta(seconds=59)).isoformat()
        with self.assertRaises(GateStop):
            self.invoke()
        self.assertEqual(self.sent, [])

    def test_forged_boolean_or_extra_field_is_rejected(self):
        base = frozenset(self.old)
        self.projection["replay_linkage_clear"] = False
        with self.assertRaises(GateStop):
            bind_terminal_projection(QR, self.projection, base, NOW)
        self.projection["replay_linkage_clear"] = True
        self.projection["tls_live_reprobe_pass"] = True
        with self.assertRaises(GateStop):
            bind_terminal_projection(QR, self.projection, base, NOW)

    def test_unknown_ssh_result_claim_remains_and_no_retry(self):
        def timedout(cmd, *, capture_output, timeout, check, input=None):
            if "p4-pending-readonly" in cmd:
                return self.runner(
                    cmd, capture_output=capture_output, timeout=timeout, check=check
                )
            raise subprocess.TimeoutExpired(cmd, timeout)

        self.assertEqual(self.invoke(runner=timedout), "UNKNOWN_STOP")
        self.assertEqual(len(list(self.private.glob("p4-attempt-*.json"))), 1)
        with self.assertRaises(GateStop):
            self.invoke(runner=timedout)

    def test_rejection_is_not_reported_as_commit(self):
        def rejected(cmd, *, capture_output, timeout, check, input=None):
            if "p4-pending-readonly" in cmd:
                return self.runner(
                    cmd, capture_output=capture_output, timeout=timeout, check=check
                )
            return subprocess.CompletedProcess(cmd, 2, json.dumps({
                "schema": "gh.pair.setup-secret-import-result/1",
                "accepted": False,
                "code": "rejected",
            }).encode(), b"")

        self.assertEqual(self.invoke(runner=rejected), "IMPORT_REJECTED_STOP")

    def test_parallel_claim_cannot_create_two_import_attempts(self):
        outcomes = []
        go = threading.Barrier(2)

        def claim():
            go.wait(3)
            try:
                _private_claim(self.private, digest(HARDWARE), digest(PAIRING), NOW)
                outcomes.append("claimed")
            except GateStop:
                outcomes.append("stopped")

        first = threading.Thread(target=claim)
        second = threading.Thread(target=claim)
        first.start()
        second.start()
        first.join(4)
        second.join(4)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(sorted(outcomes), ["claimed", "stopped"])
        self.assertEqual(len(list(self.private.glob("p4-attempt-*.json"))), 1)

    def test_private_claim_directory_permissions_fail_closed(self):
        os.chmod(self.private, 0o755)
        with self.assertRaises(GateStop):
            _private_claim(self.private, digest(HARDWARE), digest(PAIRING), NOW)
        self.assertEqual(list(self.private.glob("p4-attempt-*.json")), [])

    def test_current_ip_can_change_without_frozen_hash(self):
        from terminal_pairing import _command

        first = _command("root@192.168.20.31", "greenhouse-manager", importer=False)
        second = _command("root@192.168.20.49", "greenhouse-manager", importer=False)
        self.assertNotEqual(first, second)
        self.assertIn("p4-pending-readonly", second)


if __name__ == "__main__":
    unittest.main()
