from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("cold_snapshot.py")
spec = importlib.util.spec_from_file_location("cold_snapshot", SCRIPT)
assert spec is not None and spec.loader is not None
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class ColdSnapshotSyntheticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sources = {}
        for label, dest in tool.RW.items():
            path = self.root / ("source_" + label)
            path.mkdir()
            self.sources[dest] = path
        for label, db in tool.DATABASES:
            connection = sqlite3.connect(self.sources[tool.RW[label]] / db)
            connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, value TEXT)")
            connection.execute("INSERT INTO items (value) VALUES (?)", ("synthetic",))
            connection.commit()
            connection.close()
        (self.sources[tool.RW["relay_keys"]] / "key.synth").write_text("synthetic-not-secret")
        (self.sources[tool.RW["n3w"]] / "state.bin").write_bytes(b"\x00\x11\x22")

    def test_snapshot_and_isolated_restore_preserve_every_file(self) -> None:
        with patch.object(tool, "no_open_db_files", return_value=None):
            tool.capture(self.sources, self.root)
        snapshot = self.root / "cold-snapshot"
        self.assertTrue((snapshot / "registration" / "registration.sqlite3").is_file())
        self.assertTrue((snapshot / "n3w" / "replay.sqlite3").is_file())
        self.assertTrue((snapshot / "relay_keys" / "key.synth").is_file())
        tool.validate_sqlite(self.root / "isolated-restoration")
        self.assertEqual(
            tool.inventory(snapshot),
            tool.inventory(self.root / "isolated-restoration"),
        )
        self.assertEqual(
            (snapshot / "relay_keys" / "key.synth").read_text(),
            "synthetic-not-secret",
        )

    def test_refuse_existing_backup_directory(self) -> None:
        (self.root / "cold-snapshot").mkdir()
        with patch.object(tool, "no_open_db_files", return_value=None):
            with self.assertRaisesRegex(tool.Stop, "SNAPSHOT_ALREADY_EXISTS"):
                tool.capture(self.sources, self.root)

    def test_mounts_reject_missing_rw_nested_bind(self) -> None:
        mounts = [
            {"Destination": key, "Type": "bind", "RW": rw,
             "Source": str(self.sources[key]) if rw else str(self.root / "secret")}
            for key, rw in tool.EXPECTED_MOUNTS.items()
        ]
        (self.root / "secret").write_text("synthetic")
        self.assertEqual(len(tool.mount_sources({"Mounts": mounts})), 6)
        mounts[-1]["Destination"] = "/unexpected"
        with self.assertRaises(tool.Stop):
            tool.mount_sources({"Mounts": mounts})

    def test_runtime_rejects_mount_drift_against_private_inspect(self) -> None:
        mounts = [
            {"Destination": dest, "Type": "bind", "RW": rw,
             "Source": str(self.sources[dest]) if rw else str(self.root / "secret")}
            for dest, rw in tool.EXPECTED_MOUNTS.items()
        ]
        (self.root / "secret").write_text("synthetic")
        initial = {
            "Id": "manager-id", "Image": "image-old",
            "Config": {}, "HostConfig": {}, "Mounts": mounts,
            "State": {"Running": True},
        }
        broker = {
            "Id": "broker-id", "Image": "broker-image",
            "State": {"Running": True},
        }
        with patch.object(tool, "inspect", side_effect=[initial, broker]):
            with patch.object(tool, "assert_no_other_container_writers"):
                self.assertEqual(
                    len(tool.validate_runtime(initial, broker, "preflight")),
                    6,
                )
        altered = {**initial, "Mounts": [dict(m) for m in mounts]}
        altered["Mounts"][0]["Source"] = str(self.root / "changed")
        with patch.object(tool, "inspect", side_effect=[altered, broker]):
            with self.assertRaisesRegex(
                tool.Stop, "MANAGER_MOUNTS_DIFFER_FROM_SAVED_PRIVATE_CONFIG"
            ):
                tool.validate_runtime(initial, broker, "preflight")

    def test_capture_rejects_manager_still_running(self) -> None:
        initial = {
            "Id": "manager-id", "Image": "image-old",
            "Config": {}, "HostConfig": {}, "Mounts": [],
            "State": {"Running": True},
        }
        broker = {
            "Id": "broker-id", "Image": "broker-image",
            "State": {"Running": True},
        }
        with patch.object(tool, "inspect", side_effect=[initial, broker]):
            with self.assertRaisesRegex(tool.Stop, "MANAGER_RUNNING_STATE_BLOCKS_PHASE"):
                tool.validate_runtime(initial, broker, "capture")

    def test_sqlite_corruption_fails_isolated_integrity(self) -> None:
        clone = self.root / "isolation"
        for label, dest in tool.RW.items():
            target = clone / label
            import shutil
            shutil.copytree(self.sources[dest], target)
        (clone / "registration" / "registration.sqlite3").write_bytes(b"not a database")
        with self.assertRaises(sqlite3.DatabaseError):
            tool.validate_sqlite(clone)

    def test_reject_symlinked_persistent_data(self) -> None:
        (self.sources[tool.RW["n3w"]] / "badlink").symlink_to(
            self.sources[tool.RW["relay_keys"]] / "key.synth"
        )
        with patch.object(tool, "no_open_db_files", return_value=None):
            with self.assertRaisesRegex(tool.Stop, "SOURCE_SYMLINK_INSIDE"):
                tool.capture(self.sources, self.root)


if __name__ == "__main__":
    unittest.main()
