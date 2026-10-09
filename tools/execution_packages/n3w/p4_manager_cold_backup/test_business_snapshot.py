from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import business_snapshot as business
import cold_snapshot as snapshot


def make_db(path: Path, definitions: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.executescript(";\n".join(definitions) + ";\n")
        con.commit()
    finally:
        con.close()


class BusinessFrozenComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.private = Path(self.tmp.name)
        self.cold = self.private / "cold-snapshot"
        self.isolated = self.private / "isolated-restoration"
        self.cold.mkdir()
        self.isolated.mkdir()
        reg = [
            "CREATE TABLE registrations (hardware_id TEXT PRIMARY KEY)",
            "CREATE TABLE pairing_sessions (pairing_id TEXT PRIMARY KEY)",
            "CREATE TABLE registration_node_history (hardware_id TEXT)",
            "CREATE TABLE registration_events (hardware_id TEXT)",
            "CREATE TABLE node_id_leases (node_id TEXT)",
            "CREATE TABLE retirement_outbox (retirement_id INTEGER)",
        ]
        for n in range(5):
            reg.append(f"INSERT INTO registrations (hardware_id) VALUES ('synthetic-{n}')")
            reg.append(f"INSERT INTO registration_node_history (hardware_id) VALUES ('synthetic-{n}')")
        credential = [
            "CREATE TABLE credential_assignments (hardware_id TEXT, state TEXT, active_generation INTEGER)",
            "INSERT INTO credential_assignments VALUES ('synthetic-1', 'active', 3)",
        ]
        replay = [
            "CREATE TABLE n3w_replay_meta (schema_version INTEGER)",
            "CREATE TABLE n3w_replay_state (node_id TEXT, highest_session_hex TEXT)",
            "CREATE TABLE n3w_replay_seen (node_id TEXT, boot_id TEXT, seq INTEGER)",
            "INSERT INTO n3w_replay_state VALUES ('synthetic-1','0000000000000003')",
            "INSERT INTO n3w_replay_seen VALUES ('synthetic-1','synth-boot',43)",
        ]
        for root in (self.cold, self.isolated):
            make_db(root / "registration/registration.sqlite3", reg)
            make_db(root / "n3w/credential-lifecycle.sqlite3", credential)
            make_db(root / "n3w/replay.sqlite3", replay)

    def test_identical_cold_and_restored_business_are_proven(self) -> None:
        business.validate_cold_and_isolated(self.private)
        proof = self.private / "p4-business-restore-evidence-private.json"
        self.assertTrue(proof.exists())
        self.assertEqual(proof.stat().st_mode & 0o777, 0o600)

    def test_missing_one_historical_identity_fails(self) -> None:
        for root in (self.cold, self.isolated):
            con = sqlite3.connect(root / "registration/registration.sqlite3")
            con.execute("DELETE FROM registrations WHERE hardware_id='synthetic-4'")
            con.execute("DELETE FROM registration_node_history WHERE hardware_id='synthetic-4'")
            con.commit()
            con.close()
        with self.assertRaisesRegex(
            snapshot.Stop, "HISTORICAL_FIVE_IDENTITIES_NOT_ESTABLISHED"
        ):
            business.validate_cold_and_isolated(self.private)

    def test_changed_replay_seq_between_copies_fails(self) -> None:
        con = sqlite3.connect(self.isolated / "n3w/replay.sqlite3")
        con.execute("UPDATE n3w_replay_seen SET seq=99")
        con.commit()
        con.close()
        with self.assertRaisesRegex(snapshot.Stop, "FROZEN_CLONE_MISMATCH"):
            business.validate_cold_and_isolated(self.private)

    def test_missing_replay_schema_fails(self) -> None:
        for root in (self.cold, self.isolated):
            con = sqlite3.connect(root / "n3w/replay.sqlite3")
            con.execute("DROP TABLE n3w_replay_state")
            con.commit()
            con.close()
        with self.assertRaisesRegex(snapshot.Stop, "BUSINESS_DB_SCHEMA_MISSING"):
            business.validate_cold_and_isolated(self.private)

    def test_frozen_semantics_does_not_print_identifier(self) -> None:
        result = business.read_frozen_semantics(self.cold)
        self.assertEqual(result["registration"]["all_known_hardware"], 5)
        self.assertEqual(result["credential"]["credential_max_generation"], 3)
        self.assertEqual(result["replay"]["replay_max_seq"], 43)
        self.assertNotIn("synthetic-1", str(result))


if __name__ == "__main__":
    unittest.main()
