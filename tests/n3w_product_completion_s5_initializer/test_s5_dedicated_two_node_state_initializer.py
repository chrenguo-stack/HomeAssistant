from __future__ import annotations

import ast
import importlib.util
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] if "tests" in Path(__file__).parts else Path.cwd()
TOOL = ROOT / "tools" / "n3w_product_s5_initialize_dedicated_two_node_state.py"
AUTHORIZATION = (
    "D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-DEDICATED-TWO-NODE-STATE-"
    "INITIALIZER-HOSTONLY-CONTRACT-AND-SYNTHETIC-VALIDATION-20260815-01"
)


def load_tool():
    spec = importlib.util.spec_from_file_location("s5_state_initializer", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture() -> dict[str, object]:
    return {
        "schema": "gh.n3w-product-s5-dedicated-two-node-state-synthetic/1",
        "synthetic_only": True,
        "synthetic_marker": "S5-SYNTHETIC-ONLY-NOT-REAL-CREDENTIALS",
        "system_id": "system001",
        "child": {
            "role": "child",
            "hardware_id": "ghw-s5child-021122334455",
            "pairing_id": "pair_child_0001",
            "pairing_epoch": 7,
            "node_id": "node_child01",
            "credential_generation": 7,
            "key_epoch": 9,
            "application_key_hex": "81" * 32,
            "local_mac": "02:11:22:33:44:55",
            "capabilities": ["telemetry", "n3w-product-relay"],
        },
        "relay": {
            "role": "relay",
            "hardware_id": "ghw-s5relay-02aabbccddee",
            "pairing_id": "pair_relay_0001",
            "pairing_epoch": 11,
            "node_id": "node_relay01",
            "credential_generation": 11,
            "key_epoch": 13,
            "application_key_hex": "a1" * 32,
            "local_mac": "02:aa:bb:cc:dd:ee",
            "capabilities": ["telemetry", "n3w-product-relay"],
        },
    }


class DedicatedTwoNodeStateInitializerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_tool()

    def test_authorization_and_hostonly_static_boundary(self) -> None:
        self.assertEqual(self.module.AUTHORIZATION, AUTHORIZATION)
        tree = ast.parse(TOOL.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(
            {
                "socket",
                "serial",
                "paho",
                "esptool",
                "requests",
                "urllib",
                "subprocess",
                "secrets",
            }.isdisjoint(imported)
        )
        text = TOOL.read_text(encoding="utf-8").lower()
        self.assertNotIn("docker ", text)
        self.assertNotIn("colima ", text)
        self.assertNotIn("esp_now", text)
        self.assertNotIn("esphome compile", text)

    def test_synthetic_two_node_closure_is_builder_shaped(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture_path = root / "fixture.json"
            output = root / "output"
            fixture_path.write_text(json.dumps(fixture()), encoding="utf-8")
            result = self.module.initialize(fixture_path, output)

            self.assertTrue(result["synthetic_only"])
            self.assertTrue(result["output_contract_verified"])
            self.assertEqual(result["target_node_count"], 2)
            self.assertEqual(result["gateway_relation_row_count"], 0)
            self.assertEqual(result["relay_operation_row_count"], 0)
            self.assertEqual(result["replay_state_row_count"], 0)
            self.assertFalse(result["pair_lmk_present"])
            self.assertFalse(result["pmk_present"])

            self.assertEqual(
                {p.name for p in (output / "manager_state").iterdir()},
                {
                    "registration.sqlite3",
                    "replay.sqlite3",
                    "relay-authorization.sqlite3",
                    "relay-keys",
                },
            )
            self.assertEqual(
                {p.name for p in (output / "manager_state" / "relay-keys").iterdir()},
                {"child.key", "relay.key"},
            )
            self.assertEqual(
                {p.name for p in (output / "credentials").iterdir()},
                {"child.json", "relay.json"},
            )

            reg = sqlite3.connect(output / "manager_state" / "registration.sqlite3")
            try:
                rows = reg.execute(
                    "SELECT node_id, pairing_epoch FROM registrations ORDER BY node_id"
                ).fetchall()
                self.assertEqual(
                    rows,
                    [("node_child01", 7), ("node_relay01", 11)],
                )
                lifecycle = reg.execute(
                    "SELECT node_id, active_generation, state "
                    "FROM credential_assignments ORDER BY node_id"
                ).fetchall()
                self.assertEqual(
                    lifecycle,
                    [
                        ("node_child01", 7, "active"),
                        ("node_relay01", 11, "active"),
                    ],
                )
            finally:
                reg.close()

            auth = sqlite3.connect(
                output / "manager_state" / "relay-authorization.sqlite3"
            )
            try:
                self.assertEqual(
                    auth.execute(
                        "SELECT COUNT(*) FROM n3w_relay_gateway_nodes"
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    auth.execute(
                        "SELECT node_id,key_epoch,state FROM n3w_relay_key_epochs "
                        "ORDER BY node_id"
                    ).fetchall(),
                    [
                        ("node_child01", 9, "ACTIVE"),
                        ("node_relay01", 13, "ACTIVE"),
                    ],
                )
            finally:
                auth.close()

    def test_rejects_real_materialization_and_identity_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            realish = fixture()
            realish["synthetic_only"] = False
            path = root / "realish.json"
            path.write_text(json.dumps(realish), encoding="utf-8")
            with self.assertRaisesRegex(
                self.module.SyntheticStateError,
                "real_materialization_rejected",
            ):
                self.module.initialize(path, root / "out-realish")

            collision = fixture()
            collision["relay"]["node_id"] = collision["child"]["node_id"]
            path = root / "collision.json"
            path.write_text(json.dumps(collision), encoding="utf-8")
            with self.assertRaisesRegex(
                self.module.SyntheticStateError,
                "child_relay_node_id_collision",
            ):
                self.module.initialize(path, root / "out-collision")

    def test_requires_generation_from_pairing_semantics_and_relay_capability(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            generation = fixture()
            generation["relay"]["credential_generation"] = 12
            path = root / "generation.json"
            path.write_text(json.dumps(generation), encoding="utf-8")
            with self.assertRaisesRegex(
                self.module.SyntheticStateError,
                "credential_generation_pairing_epoch_mismatch",
            ):
                self.module.initialize(path, root / "out-generation")

            capability = fixture()
            capability["relay"]["capabilities"] = ["telemetry"]
            path = root / "capability.json"
            path.write_text(json.dumps(capability), encoding="utf-8")
            with self.assertRaisesRegex(
                self.module.SyntheticStateError,
                "relay_relay_capability_missing",
            ):
                self.module.initialize(path, root / "out-capability")

            child_capability = fixture()
            child_capability["child"]["capabilities"] = ["telemetry"]
            path = root / "child-capability.json"
            path.write_text(json.dumps(child_capability), encoding="utf-8")
            with self.assertRaisesRegex(
                self.module.SyntheticStateError,
                "child_relay_capability_missing",
            ):
                self.module.initialize(path, root / "out-child-capability")

            mac_binding = fixture()
            mac_binding["child"]["hardware_id"] = "ghw-s5child-021122334456"
            path = root / "mac-binding.json"
            path.write_text(json.dumps(mac_binding), encoding="utf-8")
            with self.assertRaisesRegex(
                self.module.SyntheticStateError,
                "child_hardware_mac_binding_mismatch",
            ):
                self.module.initialize(path, root / "out-mac-binding")


if __name__ == "__main__":
    unittest.main()
