from __future__ import annotations

import os
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path

import fresh_state_contract as fresh
from cutover_contract import RW_TARGETS, CutoverStop
from test_cutover_contract import old_manager


class FreshStateContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.paths = {
            dest: str(self.base / ("fresh" + str(i)))
            for i, dest in enumerate(sorted(RW_TARGETS))
        }
        for p in self.paths.values():
            Path(p).mkdir(mode=0o700)
        self.old = old_manager()

    def _create_db(self, path: Path, tables: tuple[str, ...]) -> None:
        con = sqlite3.connect(path)
        try:
            for table in tables:
                con.execute(f'CREATE TABLE "{table}" (id TEXT)')
            con.commit()
        finally:
            con.close()
        path.chmod(0o600)

    def _initialize(self) -> None:
        self._create_db(
            Path(self.paths["/var/lib/greenhouse-manager-registration"]) / fresh.REGISTRATION_DB,
            fresh.REGISTRATION_TABLES,
        )
        root = Path(self.paths["/var/lib/greenhouse-manager/n3w"])
        self._create_db(root / fresh.CREDENTIAL_DB, fresh.CREDENTIAL_TABLES)
        self._create_db(root / fresh.REPLAY_DB, fresh.REPLAY_TABLES)

    def test_fresh_source_isolation_passes_with_three_empty_roots(self):
        mounts = fresh.validate_fresh_sources(self.old, self.paths)
        for dst in RW_TARGETS:
            self.assertEqual(mounts[dst]["Source"], self.paths[dst])

    def test_any_existing_file_blocks_zero_state_claim(self):
        Path(next(iter(self.paths.values())), "legacy.sqlite3").write_bytes(b"old")
        with self.assertRaisesRegex(CutoverStop, "FRESH_ROOT_NOT_EMPTY"):
            fresh.validate_fresh_sources(self.old, self.paths)

    def test_old_state_source_cannot_be_a_fresh_root(self):
        origin = next(m["Source"] for m in self.old["Mounts"] if m["RW"])
        a = next(iter(self.paths))
        self.paths[a] = origin
        with self.assertRaises(CutoverStop):
            fresh.validate_fresh_sources(self.old, self.paths)

    def test_excess_permissions_block(self):
        target = Path(next(iter(self.paths.values())))
        target.chmod(0o755)
        with self.assertRaisesRegex(CutoverStop, "FRESH_DIRECTORY_MODE_UNSAFE"):
            fresh.validate_fresh_sources(self.old, self.paths)

    def test_valid_new_databases_are_empty(self):
        self._initialize()
        fresh.validate_initialized_fresh_state(self.paths)
        self.assertEqual(fresh.accept_fresh_identity_baseline(0, 0, 0)["registrations"], 0)

    def test_old_identity_row_blocks_initialization_claim(self):
        self._initialize()
        p = Path(self.paths["/var/lib/greenhouse-manager-registration"]) / fresh.REGISTRATION_DB
        con = sqlite3.connect(p)
        con.execute("INSERT INTO registrations VALUES ('synthetic-legacy')")
        con.commit()
        con.close()
        with self.assertRaisesRegex(CutoverStop, "FRESH_DB_CONTAINS_LEGACY_ROWS"):
            fresh.validate_initialized_fresh_state(self.paths)

    def test_old_replay_row_blocks_initialization_claim(self):
        self._initialize()
        p = Path(self.paths["/var/lib/greenhouse-manager/n3w"]) / fresh.REPLAY_DB
        con = sqlite3.connect(p)
        con.execute("INSERT INTO n3w_replay_seen VALUES ('synthetic-legacy')")
        con.commit()
        con.close()
        with self.assertRaisesRegex(CutoverStop, "FRESH_DB_CONTAINS_LEGACY_ROWS"):
            fresh.validate_initialized_fresh_state(self.paths)

    def test_old_relay_key_blocks_initialization_claim(self):
        self._initialize()
        p = Path(self.paths["/var/lib/greenhouse-manager/n3w/relay-keys"]) / "legacy.key"
        p.write_bytes(b"synthetic")
        with self.assertRaisesRegex(CutoverStop, "FRESH_RELAY_KEYS_NOT_EMPTY"):
            fresh.validate_initialized_fresh_state(self.paths)

    def test_preboot_identity_count_five_cannot_be_reused(self):
        with self.assertRaisesRegex(CutoverStop, "FRESH_PREBOOT_IDENTITY_BASELINE_MUST_BE_ZERO"):
            fresh.accept_fresh_identity_baseline(5, 0, 0)

    def test_missing_replay_db_cannot_be_empty_pass(self):
        self._initialize()
        (Path(self.paths["/var/lib/greenhouse-manager/n3w"]) / fresh.REPLAY_DB).unlink()
        with self.assertRaisesRegex(CutoverStop, "FRESH_DB_NOT_INITIALIZED"):
            fresh.validate_initialized_fresh_state(self.paths)


if __name__ == "__main__":
    unittest.main()
