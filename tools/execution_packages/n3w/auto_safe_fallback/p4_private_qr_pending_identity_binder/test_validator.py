import base64
import hashlib
import importlib.util
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("validator", Path(__file__).with_name("validator.py"))
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

PRE = [f"ghw-c6-{i:012x}" for i in range(1, 6)]
NEW = "ghw-c6-123456789abc"
ALT = "ghw-c6-222222222222"
PAIR = "12345678-1234-4234-8234-123456789abc"
SECRET = base64.urlsafe_b64encode(bytes(range(32))).decode().rstrip("=")
QR = f"GHN3W2:{NEW}:{PAIR}:{SECRET}"
NOW = datetime(2026, 10, 8, 10, 0, tzinfo=UTC)


class BinderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.reg, self.cred, self.replay = [root / x for x in ("registration.sqlite3", "credential.sqlite3", "replay.sqlite3")]
        with sqlite3.connect(self.reg) as db:
            db.executescript("""
            CREATE TABLE registrations (hardware_id TEXT, current_pairing_id TEXT, pairing_epoch INTEGER, node_id TEXT, retired_at TEXT);
            CREATE TABLE pairing_sessions (pairing_id TEXT, hardware_id TEXT, pairing_epoch INTEGER, state TEXT, expires_at TEXT);
            CREATE TABLE registration_events (hardware_id TEXT, pairing_id TEXT, node_id TEXT, event TEXT);
            CREATE TABLE registration_node_history (hardware_id TEXT, node_id TEXT);
            CREATE TABLE node_id_leases (hardware_id TEXT, node_id TEXT);
            CREATE TABLE retirement_outbox (hardware_id TEXT, pairing_id TEXT, node_id TEXT);
            """)
            for i, h in enumerate(PRE):
                db.execute("INSERT INTO registrations VALUES (?, ?, 1, ?, NULL)", (h, f"old-{i}", f"node-{i}"))
            db.execute("INSERT INTO registrations VALUES (?,?,1,NULL,NULL)", (NEW, PAIR))
            db.execute("INSERT INTO pairing_sessions VALUES (?,?,?,?,?)", (PAIR, NEW, 1, "pending", (NOW + timedelta(seconds=100)).isoformat()))
            db.execute("INSERT INTO registration_events VALUES (?,?,NULL,'hello_created')", (NEW, PAIR))
        with sqlite3.connect(self.cred) as db:
            db.execute("CREATE TABLE credential_assignments (hardware_id TEXT, pairing_id TEXT, node_id TEXT, last_node_id TEXT, state TEXT)")
        with sqlite3.connect(self.replay) as db:
            db.execute("CREATE TABLE n3w_replay_state (node_id TEXT)")
        self.baseline = frozenset(validator.digest(x) for x in PRE)

    def insert(self, path, stmt, args=()):
        with sqlite3.connect(path) as db:
            db.execute(stmt, args)

    def verify(self, qr=QR, **kwargs):
        return validator.verify_sqlite_pairing(self.reg, self.cred, self.replay, self.baseline, qr, now=NOW, runtime_authority_pass=True, **kwargs)

    def code(self, expected, qr=QR, **kwargs):
        with self.assertRaises(validator.BinderInvalid) as exc:
            self.verify(qr, **kwargs)
        self.assertEqual(exc.exception.code, expected)
        self.assertNotIn(SECRET, str(exc.exception))
        self.assertNotIn(NEW, str(exc.exception))

    def test_happy_readonly_and_no_secret_in_result(self):
        def hashdb():
            return [hashlib.sha256(x.read_bytes()).hexdigest() for x in (self.reg, self.cred, self.replay)]
        before = hashdb()
        result = self.verify()
        self.assertEqual(result["status"], "BINDER_PASS_NO_IMPORT")
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn(NEW, json.dumps(result))
        self.assertEqual(before, hashdb())

    def test_zero_added(self):
        self.insert(self.reg, "DELETE FROM registration_events WHERE hardware_id=?", (NEW,))
        self.insert(self.reg, "DELETE FROM pairing_sessions WHERE hardware_id=?", (NEW,))
        self.insert(self.reg, "DELETE FROM registrations WHERE hardware_id=?", (NEW,))
        self.code("INVALID_UNIQUE_IDENTITY")

    def test_two_added(self):
        self.insert(self.reg, "INSERT INTO registrations VALUES (?,'p',1,NULL,NULL)", (ALT,))
        self.code("INVALID_UNIQUE_IDENTITY")

    def test_old_missing(self):
        self.insert(self.reg, "DELETE FROM registrations WHERE hardware_id=?", (PRE[0],))
        self.code("INVALID_SNAPSHOT_DRIFT")

    def test_wrong_qr_hardware(self):
        self.code("INVALID_QR_PENDING_BINDING", QR.replace(NEW, ALT))

    def test_wrong_pairing(self):
        self.code("INVALID_QR_PENDING_BINDING", QR.replace(PAIR, "12345678-1234-4234-8234-123456789abd"))

    def test_expired_and_low_margin(self):
        self.code("INVALID_PENDING_LIFECYCLE", minimum_remaining_seconds=101)
        self.insert(self.reg, "UPDATE pairing_sessions SET expires_at=? WHERE hardware_id=?", ((NOW - timedelta(seconds=1)).isoformat(), NEW))
        self.code("INVALID_PENDING_LIFECYCLE")

    def test_not_pending(self):
        self.insert(self.reg, "UPDATE pairing_sessions SET state='approved' WHERE hardware_id=?", (NEW,))
        self.code("INVALID_PENDING_LIFECYCLE")

    def test_existing_node(self):
        self.insert(self.reg, "UPDATE registrations SET node_id='node-old' WHERE hardware_id=?", (NEW,))
        self.code("INVALID_PRIOR_HISTORY")

    def test_old_sessions(self):
        self.insert(self.reg, "INSERT INTO pairing_sessions VALUES ('x',?,1,'expired','x')", (NEW,))
        self.code("INVALID_PRIOR_HISTORY")

    def test_credential_revoked_history(self):
        self.insert(self.cred, "INSERT INTO credential_assignments VALUES (?,'old',NULL,'retired','revoked')", (NEW,))
        self.code("INVALID_PRIOR_HISTORY")

    def test_lease_and_retirement(self):
        self.insert(self.reg, "INSERT INTO node_id_leases VALUES (?,'node')", (NEW,))
        self.code("INVALID_PRIOR_HISTORY")
        self.insert(self.reg, "DELETE FROM node_id_leases")
        self.insert(self.reg, "INSERT INTO retirement_outbox VALUES (?,'p','node')", (NEW,))
        self.code("INVALID_PRIOR_HISTORY")

    def test_old_replay_state_is_not_a_new_product_identity(self):
        self.insert(self.replay, "INSERT INTO n3w_replay_state VALUES ('node-1')")
        self.assertEqual(self.verify()["status"], "BINDER_PASS_NO_IMPORT")

    def test_multiple_hello_events(self):
        self.insert(self.reg, "INSERT INTO registration_events VALUES (?,?,NULL,'hello_created')", (NEW, PAIR))
        self.code("INVALID_PRIOR_HISTORY")

    def test_historical_assignment_active(self):
        self.insert(self.cred, "INSERT INTO credential_assignments VALUES (?,?,'node-stale','node-stale','active')", (NEW, PAIR))
        self.code("INVALID_PRIOR_HISTORY")

    def test_hello_repair_event(self):
        self.insert(self.reg, "UPDATE registration_events SET event='hello_superseded' WHERE hardware_id=?", (NEW,))
        self.code("INVALID_PRIOR_HISTORY")

    def assert_change_is_detected(self, path, sql, params=()):
        original = validator._hardware_union
        counter = [0]

        def concurrent_mutation(registration, credential):
            result = original(registration, credential)
            counter[0] += 1
            if counter[0] == 2:
                with sqlite3.connect(path) as db:
                    db.execute(sql, params)
            return result

        with patch.object(validator, "_hardware_union", concurrent_mutation):
            self.code("INVALID_BINDING_STATE_DRIFT")
        self.assertEqual(counter[0], 2)

    def test_concurrent_pairing_rejected_after_first_read(self):
        self.assert_change_is_detected(
            self.reg,
            "UPDATE pairing_sessions SET state='rejected' WHERE hardware_id=?",
            (NEW,),
        )

    def test_concurrent_pairing_deadline_shrinks_after_first_read(self):
        self.assert_change_is_detected(
            self.reg,
            "UPDATE pairing_sessions SET expires_at=? WHERE hardware_id=?",
            ((NOW - timedelta(seconds=1)).isoformat(), NEW),
        )

    def test_concurrent_credential_assignment_after_first_read(self):
        self.assert_change_is_detected(
            self.cred,
            "INSERT INTO credential_assignments VALUES (?,'old',NULL,'old','revoked')",
            (NEW,),
        )

    def test_concurrent_node_lease_after_first_read(self):
        self.assert_change_is_detected(
            self.reg,
            "INSERT INTO node_id_leases VALUES (?,'old-node')",
            (NEW,),
        )

    def test_qr_invalid_and_multiline(self):
        self.code("INVALID_QR_FORMAT", QR + "\nmore")
        self.code("INVALID_QR_FORMAT", QR[:-1] + "!")
        self.code("INVALID_QR_FORMAT", QR * 20)

    def test_no_runtime_authority(self):
        with self.assertRaises(validator.BinderInvalid) as exc:
            validator.verify_sqlite_pairing(self.reg, self.cred, self.replay, self.baseline, QR, now=NOW)
        self.assertEqual(exc.exception.code, "INVALID_RUNTIME_AUTHORITY")

    def test_missing_schema(self):
        self.insert(self.reg, "DROP TABLE retirement_outbox")
        self.code("INVALID_RUNTIME_AUTHORITY")

    def test_baseline_shape_and_private_file_permissions(self):
        doc = {
            "schema": validator.BASELINE_SCHEMA,
            "hardware_id_sha256": sorted(self.baseline),
            "hardware_id_count": 5,
            "read_only": True,
            "manager_mutation": False,
            "manager_replay_mutation": False,
        }
        self.assertEqual(validator.validate_baseline_document(doc), self.baseline)
        path = Path(self.tmp.name) / "baseline.json"
        raw = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        os.chmod(path, 0o600)
        self.assertEqual(validator.read_private_baseline(path, hashlib.sha256(raw).hexdigest()), self.baseline)
        os.chmod(path, 0o644)
        with self.assertRaises(validator.BinderInvalid):
            validator.read_private_baseline(path, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    unittest.main(verbosity=2)
