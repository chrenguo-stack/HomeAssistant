from __future__ import annotations

import ast
import importlib.util
import json
import os
import stat
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "n3w_product_s5_prepare_physical_package.py"
LAUNCHER = (
    ROOT
    / "host"
    / "greenhouse-manager"
    / "src"
    / "greenhouse_manager"
    / "runtime"
    / "n3w_product_isolated_app.py"
)
DECISION = (
    ROOT
    / "docs"
    / "decisions"
    / "n3w-product-completion-s5-full-two-board-isolated-physical-e2e-preparation-20260814.json"
)
STARTING_HEAD = "eb2fdc795850fedd4f49ce3fbba8cd03a4548de9"
HISTORICAL_RUNTIME_HEAD = "660acf72b701d9ff8e3a881e97e5d15357286786"
PRIVATE_RUNTIME_HEAD = "e06c8bc90b08987a17783a1a113ea1aaa81b81c0"
AUTH = (
    "D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-FULL-TWO-BOARD-ISOLATED-"
    "PHYSICAL-E2E-PREPARATION-20260814-01"
)
NEXT_GATE = (
    "D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-ISOLATED-MANAGER-TRANSPORT-"
    "HOST-COMPILE-IMPLEMENTATION-20260814-01"
)


def load_tool():
    spec = importlib.util.spec_from_file_location("s5_prepare", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def private_write(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    os.chmod(path, 0o600)


def fixture_mac(*octets: int) -> str:
    return ":".join(f"{value:02x}" for value in octets)


def network_fixture(*, channel: int = 6) -> dict[str, object]:
    return {
        "wifi_ssid": "s5-isolated-fixture",
        "wifi_password": "fixture-pass-123",
        "wifi_channel": channel,
        "mqtt_broker": "192.0.2.10",
        "mqtt_port": 1883,
        "mqtt_client_id": "gh-s5-relay-fixture",
        "mqtt_username": "fixture-user",
        "mqtt_password": "fixture-mqtt-pass",
        "mqtt_tls": False,
    }


class S5PhysicalPreparationTest(unittest.TestCase):
    def test_decision_contract(self) -> None:
        document = json.loads(DECISION.read_text(encoding="utf-8"))
        self.assertEqual(document["authorization"], AUTH)
        self.assertEqual(document["starting_head"], STARTING_HEAD)
        self.assertEqual(document["runtime_implementation_head"], HISTORICAL_RUNTIME_HEAD)
        self.assertEqual(
            document["status"],
            "PUBLIC_PREPARATION_BLOCKED_MANAGER_TRANSPORT_IMPLEMENTATION_REQUIRED",
        )
        self.assertEqual(document["classification"]["s5_full_two_board_e2e"], "PENDING")
        self.assertEqual(
            document["classification"]["s5_physical_preparation_public_contract"],
            "PASS_WITH_IMPLEMENTATION_BLOCKER",
        )
        self.assertFalse(document["preparation_scope"]["private_package_materialization_ready"])
        self.assertFalse(document["preparation_scope"]["physical_execution_authorization_ready"])
        self.assertFalse(document["preparation_scope"]["physical_execution_authorized"])
        self.assertFalse(document["readiness_audit"]["concrete_board_s5_manager_transport_present"])
        self.assertFalse(document["readiness_audit"]["isolated_manager_opens_network_transport"])
        self.assertFalse(
            document["readiness_audit"]["concrete_relay_to_isolated_manager_telemetry_transport_present"]
        )
        self.assertFalse(
            document["readiness_audit"][
                "physical_package_can_currently_execute_required_manager_grant_and_telemetry_path"
            ]
        )
        self.assertEqual({item["id"] for item in document["blocking_findings"]}, {"S5-PREP-B01", "S5-PREP-B02"})
        self.assertEqual(document["required_successor_repair"]["scope"], "HOST_COMPILE_ONLY_NO_LIVE_EXECUTION")
        self.assertEqual(document["next_gate"], NEXT_GATE)
        for key in (
            "espnow_rf",
            "flash",
            "serial",
            "usb_jtag_board_access",
            "wifi_connection",
            "real_mqtt_network_e2e",
            "production_t1",
        ):
            self.assertTrue(document["not_authorized"][key], key)
        matrix = set(document["physical_acceptance_matrix"])
        for required in {
            "relay_advertisement_is_observed_only_as_untrusted_hint",
            "child_and_relay_independently_derive_same_nonzero_pair_specific_16_byte_lmk",
            "child_relayframe_reaches_isolated_manager_using_existing_gh_relay_1_and_gh_telemetry_1_contracts",
            "node_id_boot_id_sequence_dedup_and_home_assistant_device_identity_continuity",
            "finite_grant_expiry_removes_dynamic_peer",
            "exact_authorization_id_revoke_removes_dynamic_peer",
            "both_boards_finish_in_rom_bootloader_with_rf_stopped",
        }:
            self.assertIn(required, matrix)

    def test_generator_has_no_live_execution_imports_or_process_launch(self) -> None:
        tree = ast.parse(TOOL.read_text(encoding="utf-8"))
        imported: set[str] = set()
        calls: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
        self.assertTrue({"subprocess", "socket", "serial", "paho"}.isdisjoint(imported))
        self.assertTrue({"system", "popen", "execv", "execve", "spawnv"}.isdisjoint(calls))

    def test_private_package_generator_itself_remains_non_executable_fresh_and_permission_restricted(self) -> None:
        module = load_tool()
        self.assertEqual(module.RUNTIME_IMPLEMENTATION_HEAD, PRIVATE_RUNTIME_HEAD)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "child.json"
            relay = root / "relay.json"
            network = root / "network.json"
            child_fw = root / "child.bin"
            relay_fw = root / "relay.bin"
            manager = root / "manager.bundle"
            private_write(
                child,
                json.dumps(
                    {
                        "system_id": "system001",
                        "node_id": "node_child01",
                        "credential_generation": 7,
                        "key_epoch": 9,
                        "application_key_hex": "81" * 32,
                        "local_mac": fixture_mac(2, 17, 34, 51, 68, 85),
                    }
                ).encode(),
            )
            private_write(
                relay,
                json.dumps(
                    {
                        "system_id": "system001",
                        "node_id": "node_relay01",
                        "credential_generation": 11,
                        "key_epoch": 13,
                        "application_key_hex": "a1" * 32,
                        "local_mac": fixture_mac(2, 170, 187, 204, 221, 238),
                    }
                ).encode(),
            )
            private_write(network, json.dumps(network_fixture()).encode())
            private_write(child_fw, b"child-firmware-fixture")
            private_write(relay_fw, b"relay-firmware-fixture")
            private_write(manager, b"isolated-manager-state-fixture")

            secrets_seen: set[str] = set()
            for index in (1, 2):
                output = root / f"package-{index}"
                result = module.prepare(
                    Namespace(
                        preparation_head="1" * 40,
                        runtime_head=PRIVATE_RUNTIME_HEAD,
                        child_credentials=str(child),
                        relay_credentials=str(relay),
                        isolated_network=str(network),
                        espnow_channel=6,
                        child_firmware=str(child_fw),
                        relay_firmware=str(relay_fw),
                        manager_bundle=str(manager),
                        manager_launcher_source=str(LAUNCHER),
                        output=str(output),
                    )
                )
                self.assertFalse(result["execution_authorized"])
                self.assertTrue(result["ready_for_readonly_binding_review"])
                self.assertEqual(result["private_runtime_component"], "greenhouse_n3w_s5_private_runtime")
                self.assertEqual(
                    result["isolated_manager_launcher_module"],
                    "greenhouse_manager.runtime.n3w_product_isolated_app",
                )
                self.assertEqual(result["network_binding"]["wifi_channel"], 6)
                self.assertEqual(result["espnow_channel"], 6)
                manifest = json.loads((output / "manifest.json").read_text())
                secret = json.loads((output / "private_secrets.json").read_text())
                packaged_network = json.loads((output / "isolated_network.json").read_text())
                self.assertEqual(manifest["schema"], "gh.n3w-product-s5-private-physical-e2e-package/2")
                self.assertFalse(manifest["execution_authorized"])
                self.assertIsNone(manifest["physical_execution_authorization"])
                self.assertTrue(manifest["radio_binding"]["channels_match"])
                self.assertEqual(manifest["radio_binding"]["espnow_channel"], 6)
                self.assertEqual(packaged_network, network_fixture())
                self.assertFalse(secret["execution_authorized"])
                self.assertIsNone(secret["physical_execution_authorization"])
                self.assertEqual(len(bytes.fromhex(secret["espnow_pmk_hex"])), 16)
                self.assertNotEqual(bytes.fromhex(secret["espnow_pmk_hex"]), bytes(16))
                secrets_seen.add(secret["espnow_pmk_hex"])
                self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)
                for name in (
                    "manifest.json",
                    "private_secrets.json",
                    "isolated_network.json",
                    "cleanup_contract.json",
                    "READ_ONLY_GATE.txt",
                ):
                    self.assertEqual(stat.S_IMODE((output / name).stat().st_mode), 0o600)
                    self.assertFalse(bool((output / name).stat().st_mode & stat.S_IXUSR))
            self.assertEqual(len(secrets_seen), 2)

    def test_cross_system_non_private_or_channel_mismatch_fails_closed(self) -> None:
        module = load_tool()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "child.json"
            relay = root / "relay.json"
            network = root / "network.json"
            fw1 = root / "c.bin"
            fw2 = root / "r.bin"
            manager = root / "manager.bundle"
            base = {
                "node_id": "node_child01",
                "credential_generation": 1,
                "key_epoch": 1,
                "application_key_hex": "11" * 32,
                "local_mac": fixture_mac(2, 17, 34, 51, 68, 85),
            }
            private_write(child, json.dumps({"system_id": "system001", **base}).encode())
            relay_value = {
                "system_id": "system002",
                **base,
                "node_id": "node_relay01",
                "local_mac": fixture_mac(2, 170, 187, 204, 221, 238),
            }
            private_write(relay, json.dumps(relay_value).encode())
            private_write(network, json.dumps(network_fixture()).encode())
            private_write(fw1, b"c")
            private_write(fw2, b"r")
            private_write(manager, b"m")
            common = dict(
                preparation_head="2" * 40,
                runtime_head=PRIVATE_RUNTIME_HEAD,
                child_credentials=str(child),
                relay_credentials=str(relay),
                isolated_network=str(network),
                espnow_channel=6,
                child_firmware=str(fw1),
                relay_firmware=str(fw2),
                manager_bundle=str(manager),
                manager_launcher_source=str(LAUNCHER),
                output=str(root / "out"),
            )
            with self.assertRaisesRegex(ValueError, "same system"):
                module.prepare(Namespace(**common))
            os.chmod(child, 0o644)
            with self.assertRaisesRegex(ValueError, "permissions"):
                module._load_credentials(child, "child_credentials")

            os.chmod(child, 0o600)
            private_write(relay, json.dumps({"system_id": "system001", **relay_value, "system_id": "system001"}).encode())
            private_write(network, json.dumps(network_fixture(channel=11)).encode())
            common["output"] = str(root / "out-channel")
            with self.assertRaisesRegex(ValueError, "must equal"):
                module.prepare(Namespace(**common))


if __name__ == "__main__":
    unittest.main()
