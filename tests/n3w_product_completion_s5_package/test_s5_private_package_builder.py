from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "n3w_product_s5_build_private_package.py"
AUTH = (
    "D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-PRIVATE-PACKAGE-RENDER-BUILD-"
    "AND-BINDING-HOST-COMPILE-IMPLEMENTATION-20260815-01"
)
START = "15510ac3dbf3f8639f63e9dfa5146a27b52eb0d0"


def load_tool():
    spec = importlib.util.spec_from_file_location("s5_private_builder", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def private_dir(path: Path) -> None:
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)


def private_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")
    os.chmod(path, 0o600)


def fixture_mac(*octets: int) -> str:
    return ":".join(f"{value:02x}" for value in octets)


def child_fixture() -> dict[str, object]:
    return {
        "system_id": "system001",
        "node_id": "node_child01",
        "credential_generation": 7,
        "key_epoch": 9,
        "application_key_hex": "81" * 32,
        "local_mac": fixture_mac(2, 17, 34, 51, 68, 85),
    }


def relay_fixture() -> dict[str, object]:
    return {
        "system_id": "system001",
        "node_id": "node_relay01",
        "credential_generation": 11,
        "key_epoch": 13,
        "application_key_hex": "a1" * 32,
        "local_mac": fixture_mac(2, 170, 187, 204, 221, 238),
    }


def network_fixture() -> dict[str, object]:
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


def create_manager_state(root: Path, *, static_grant: bool = False) -> None:
    private_dir(root)
    key_dir = root / "relay-keys"
    private_dir(key_dir)
    child = child_fixture()
    relay = relay_fixture()
    for filename, value in (("child.key", child), ("relay.key", relay)):
        path = key_dir / filename
        path.write_bytes(bytes.fromhex(str(value["application_key_hex"])))
        os.chmod(path, 0o600)

    pairing = root / "registration.sqlite3"
    connection = sqlite3.connect(pairing)
    connection.executescript(
        """
        CREATE TABLE pairing_sessions (
            pairing_id TEXT PRIMARY KEY,
            hardware_id TEXT NOT NULL,
            state TEXT NOT NULL
        );
        CREATE TABLE registrations (
            hardware_id TEXT PRIMARY KEY,
            current_pairing_id TEXT NOT NULL,
            node_id TEXT UNIQUE,
            retired_at TEXT
        );
        CREATE TABLE credential_assignments (
            hardware_id TEXT NOT NULL,
            node_id TEXT,
            active_generation INTEGER NOT NULL,
            state TEXT NOT NULL
        );
        """
    )
    for role, credential in (("child", child), ("relay", relay)):
        hardware = f"ghw-s5-{role}-001122334455"
        pairing_id = f"pair-{role}-0001"
        connection.execute(
            "INSERT INTO pairing_sessions(pairing_id, hardware_id, state) VALUES (?, ?, 'approved')",
            (pairing_id, hardware),
        )
        connection.execute(
            "INSERT INTO registrations(hardware_id, current_pairing_id, node_id, retired_at) VALUES (?, ?, ?, NULL)",
            (hardware, pairing_id, credential["node_id"]),
        )
        connection.execute(
            "INSERT INTO credential_assignments(hardware_id, node_id, active_generation, state) VALUES (?, ?, ?, 'active')",
            (hardware, credential["node_id"], credential["credential_generation"]),
        )
    connection.commit()
    connection.close()
    os.chmod(pairing, 0o600)

    replay = root / "replay.sqlite3"
    connection = sqlite3.connect(replay)
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
    connection.commit()
    connection.close()
    os.chmod(replay, 0o600)

    relay_auth = root / "relay-authorization.sqlite3"
    connection = sqlite3.connect(relay_auth)
    connection.executescript(
        """
        CREATE TABLE n3w_relay_meta (schema_version INTEGER NOT NULL);
        INSERT INTO n3w_relay_meta(schema_version) VALUES (2);
        CREATE TABLE n3w_relay_nodes (node_id TEXT PRIMARY KEY, active INTEGER NOT NULL);
        CREATE TABLE n3w_relay_gateway_nodes (
            gateway_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            enabled INTEGER NOT NULL
        );
        CREATE TABLE n3w_relay_key_epochs (
            node_id TEXT NOT NULL,
            key_epoch INTEGER NOT NULL,
            key_file TEXT NOT NULL,
            enabled INTEGER NOT NULL,
            state TEXT NOT NULL,
            key_sha256 TEXT
        );
        CREATE TABLE n3w_relay_operations (status TEXT NOT NULL);
        """
    )
    for filename, credential in (("child.key", child), ("relay.key", relay)):
        key = bytes.fromhex(str(credential["application_key_hex"]))
        connection.execute(
            "INSERT INTO n3w_relay_nodes(node_id, active) VALUES (?, 1)",
            (credential["node_id"],),
        )
        connection.execute(
            """
            INSERT INTO n3w_relay_key_epochs(
                node_id, key_epoch, key_file, enabled, state, key_sha256
            ) VALUES (?, ?, ?, 1, 'ACTIVE', ?)
            """,
            (
                credential["node_id"],
                credential["key_epoch"],
                filename,
                hashlib.sha256(key).hexdigest(),
            ),
        )
    if static_grant:
        connection.execute(
            "INSERT INTO n3w_relay_gateway_nodes(gateway_id, node_id, enabled) VALUES (?, ?, 1)",
            (relay["node_id"], child["node_id"]),
        )
    connection.commit()
    connection.close()
    os.chmod(relay_auth, 0o600)


class S5PrivatePackageBuilderTest(unittest.TestCase):
    def test_authorization_and_no_live_command_contract(self) -> None:
        module = load_tool()
        self.assertEqual(module.AUTHORIZATION, AUTH)
        self.assertEqual(module.AUTHORIZATION_START_HEAD, START)
        self.assertEqual(module.ESPHOME_VERSION, "2026.4.3")
        self.assertEqual(module.ALLOWED_ESPHOME_ACTIONS, ("config", "compile"))
        tree = ast.parse(TOOL.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue({"socket", "serial", "paho", "esptool"}.isdisjoint(imported))
        self.assertNotIn("firmware/esphome_rc/board_lab/n3w_product_completion_s5/child.yml", module.SOURCE_BINDING_PATHS)
        self.assertNotIn("firmware/esphome_rc/board_lab/n3w_product_completion_s5/relay.yml", module.SOURCE_BINDING_PATHS)

    def test_fresh_pmk_and_private_inputs_render_into_both_exact_configs(self) -> None:
        module = load_tool()
        pmk = "0123456789abcdeffedcba9876543210"
        child = child_fixture()
        relay = relay_fixture()
        network = network_fixture()
        child_yaml = module._render_child(
            source_root=ROOT,
            build_path=Path("/tmp/s5-child-build"),
            credentials=child,
            pmk_hex=pmk,
            channel=6,
        )
        relay_yaml = module._render_relay(
            source_root=ROOT,
            build_path=Path("/tmp/s5-relay-build"),
            credentials=relay,
            network=network,
            pmk_hex=pmk,
        )
        self.assertEqual(child_yaml.count(pmk), 1)
        self.assertEqual(relay_yaml.count(pmk), 1)
        self.assertIn('node_id: "node_child01"', child_yaml)
        self.assertIn('node_id: "node_relay01"', relay_yaml)
        self.assertIn('ssid: "s5-isolated-fixture"', relay_yaml)
        self.assertIn('channel: 6', relay_yaml)
        self.assertIn('broker: "192.0.2.10"', relay_yaml)
        self.assertIn('client_id: "gh-s5-relay-fixture"', relay_yaml)
        self.assertNotIn("node_relay01", child_yaml)
        self.assertNotIn("node_child01", relay_yaml)
        self.assertNotIn("pair_lmk", child_yaml.lower())
        self.assertNotIn("pair_lmk", relay_yaml.lower())

    def test_manager_state_is_copied_bound_and_static_pair_preseed_is_rejected(self) -> None:
        module = load_tool()
        child = child_fixture()
        relay = relay_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source-state"
            target = root / "package-state"
            create_manager_state(source)
            result = module._copy_and_validate_manager_state(source, target, child, relay)
            self.assertEqual(
                result["registration"]["child"]["credential_generation"],
                child["credential_generation"],
            )
            self.assertEqual(
                result["registration"]["relay"]["credential_generation"],
                relay["credential_generation"],
            )
            self.assertEqual(result["relay_authorization"]["enabled_gateway_grant_count"], 0)
            self.assertFalse(result["relay_authorization"]["dynamic_ingress_authority_persisted"])
            self.assertEqual(result["replay"]["schema_version"], 1)
            self.assertIn("registration.sqlite3", result["file_sha256"])
            self.assertIn("relay-keys/child.key", result["file_sha256"])
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o700)
            for path in target.rglob("*"):
                expected = 0o700 if path.is_dir() else 0o600
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), expected)

            preseed = root / "preseed-state"
            create_manager_state(preseed, static_grant=True)
            with self.assertRaisesRegex(module.PrivatePackageBuildError, "static_gateway_child_preseed"):
                module._copy_and_validate_manager_state(
                    preseed,
                    root / "preseed-target",
                    child,
                    relay,
                )

    def test_tls_without_explicit_ca_contract_fails_closed(self) -> None:
        module = load_tool()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "network.json"
            value = network_fixture()
            value["mqtt_tls"] = True
            private_json(path, value)
            with self.assertRaisesRegex(
                module.PrivatePackageBuildError,
                "mqtt_tls_requires_separate_ca_contract",
            ):
                module._load_network(path)


if __name__ == "__main__":
    unittest.main()
