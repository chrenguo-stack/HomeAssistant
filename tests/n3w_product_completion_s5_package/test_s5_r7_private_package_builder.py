from __future__ import annotations

import ast
import hashlib
import importlib.util
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "n3w_product_s5_build_private_package_r7.py"
AUTHORIZATION = (
    "D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-R7-PRIVATE-TELEMETRY-STIMULUS-"
    "PACKAGE-BUILDER-CONTRACT-REPAIR-20260816-01"
)
STARTING_HEAD = "9862d7ecbe95439fd36ceb91854505a923cbfea2"


def load_tool():
    spec = importlib.util.spec_from_file_location("s5_r7_private_builder", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_replay(path: Path, *, node_id: str = "node_child01", highest: int | None = None) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE n3w_replay_meta (schema_version INTEGER NOT NULL);
        INSERT INTO n3w_replay_meta(schema_version) VALUES (1);
        CREATE TABLE n3w_replay_state (
            node_id TEXT PRIMARY KEY,
            highest_session_hex TEXT NOT NULL
        );
        CREATE TABLE n3w_replay_seen (
            node_id TEXT NOT NULL,
            boot_id TEXT NOT NULL,
            seq INTEGER NOT NULL,
            committed_at TEXT NOT NULL,
            PRIMARY KEY(node_id, boot_id, seq)
        );
        """
    )
    if highest is not None:
        connection.execute(
            "INSERT INTO n3w_replay_state(node_id, highest_session_hex) VALUES (?, ?)",
            (node_id, f"{highest:016x}"),
        )
    connection.commit()
    connection.close()
    os.chmod(path, 0o600)


def child_credentials() -> dict[str, object]:
    return {
        "system_id": "system001",
        "node_id": "node_child01",
        "credential_generation": 7,
        "key_epoch": 9,
        "application_key_hex": "81" * 32,
        "local_mac": "02:11:22:33:44:55",
    }


def relay_credentials() -> dict[str, object]:
    return {
        "system_id": "system001",
        "node_id": "node_relay01",
        "credential_generation": 11,
        "key_epoch": 13,
        "application_key_hex": "a1" * 32,
        "local_mac": "02:aa:bb:cc:dd:ee",
    }


def network() -> dict[str, object]:
    return {
        "wifi_ssid": "s5-isolated-fixture",
        "wifi_password": "fixture-pass-123",
        "wifi_channel": 6,
        "mqtt_broker": "192.0.2.10",
        "mqtt_port": 1883,
        "mqtt_client_id": "gh-s5-relay-fixture",
        "mqtt_username": "fixture-user",
        "mqtt_password": "fixture-mqtt-pass",
        "mqtt_tls": False,
    }


class S5R7PrivatePackageBuilderTest(unittest.TestCase):
    def test_authorization_and_no_live_import_contract(self) -> None:
        module = load_tool()
        self.assertEqual(module.AUTHORIZATION, AUTHORIZATION)
        self.assertEqual(module.STARTING_HEAD, STARTING_HEAD)
        tree = ast.parse(TOOL.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue({"socket", "serial", "paho", "esptool"}.isdisjoint(imported))

    def test_absent_child_high_water_selects_session_one_without_mutation(self) -> None:
        module = load_tool()
        with tempfile.TemporaryDirectory() as temporary:
            replay = Path(temporary) / "replay.sqlite3"
            create_replay(replay)
            before = hashlib.sha256(replay.read_bytes()).hexdigest()
            stimulus = module._select_replay_safe_stimulus(replay, "node_child01")
            after = hashlib.sha256(replay.read_bytes()).hexdigest()
            self.assertEqual(before, after)
            self.assertIsNone(stimulus["source_highest_session_hex"])
            self.assertEqual(stimulus["boot_session"], 1)
            self.assertEqual(stimulus["boot_id"], "boot_0000000000000001")
            self.assertEqual(stimulus["seq"], 0)
            self.assertTrue(stimulus["replay_snapshot_read_only"])

    def test_child_high_water_increments_strictly_without_mutation(self) -> None:
        module = load_tool()
        with tempfile.TemporaryDirectory() as temporary:
            replay = Path(temporary) / "replay.sqlite3"
            create_replay(replay, highest=7)
            before = hashlib.sha256(replay.read_bytes()).hexdigest()
            stimulus = module._select_replay_safe_stimulus(replay, "node_child01")
            after = hashlib.sha256(replay.read_bytes()).hexdigest()
            self.assertEqual(before, after)
            self.assertEqual(stimulus["source_highest_session_hex"], "0000000000000007")
            self.assertEqual(stimulus["source_highest_session"], 7)
            self.assertEqual(stimulus["boot_session"], 8)
            self.assertEqual(stimulus["boot_id"], "boot_0000000000000008")
            self.assertEqual(stimulus["seq"], 0)

    def test_uint64_max_high_water_fails_closed(self) -> None:
        module = load_tool()
        with tempfile.TemporaryDirectory() as temporary:
            replay = Path(temporary) / "replay.sqlite3"
            create_replay(replay, highest=(1 << 64) - 1)
            with self.assertRaisesRegex(
                module.R7PrivatePackageBuildError,
                "child_replay_boot_session_exhausted",
            ):
                module._select_replay_safe_stimulus(replay, "node_child01")

    def test_child_render_enables_exact_stimulus_and_relay_remains_inert(self) -> None:
        module = load_tool()
        base = module._load_base_builder()
        stimulus = {
            "boot_session": 8,
            "seq": 0,
        }
        child_yaml = module._render_r7_child(
            base,
            stimulus,
            source_root=ROOT,
            build_path=Path("/tmp/s5-r7-child"),
            credentials=child_credentials(),
            pmk_hex="0123456789abcdeffedcba9876543210",
            channel=6,
        )
        relay_yaml = base._render_relay(
            source_root=ROOT,
            build_path=Path("/tmp/s5-r7-relay"),
            credentials=relay_credentials(),
            network=network(),
            pmk_hex="0123456789abcdeffedcba9876543210",
        )
        self.assertEqual(child_yaml.count("telemetry_stimulus_enabled: true"), 1)
        self.assertEqual(child_yaml.count("telemetry_stimulus_boot_session: 8"), 1)
        self.assertEqual(child_yaml.count("telemetry_stimulus_seq: 0"), 1)
        self.assertNotIn("telemetry_stimulus_", relay_yaml)
        self.assertNotIn("node_relay01", child_yaml)
        self.assertNotIn("pair_lmk", child_yaml.lower())


if __name__ == "__main__":
    unittest.main()
