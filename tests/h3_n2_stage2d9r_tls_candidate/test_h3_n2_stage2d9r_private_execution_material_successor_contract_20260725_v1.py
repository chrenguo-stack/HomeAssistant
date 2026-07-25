#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

REPOSITORY = Path(__file__).resolve().parents[2]
CONTRACT = (
    REPOSITORY
    / "tools"
    / "h3_n2_stage2d9r_private_execution_material_successor_contract_20260725_v1.py"
)
SPEC = importlib.util.spec_from_file_location("stage2d9r_successor_contract", CONTRACT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SuccessorExecutionMaterialContractTests(unittest.TestCase):
    def test_password_database_must_match_retained_preimage(self) -> None:
        password = "a" * 64
        salt = b"stage2d9r12"
        iterations = 101
        digest = hashlib.pbkdf2_hmac("sha512", password.encode(), salt, iterations)
        line = (
            MODULE.MQTT_USERNAME
            + ":$7$"
            + str(iterations)
            + "$"
            + base64.b64encode(salt).decode()
            + "$"
            + base64.b64encode(digest).decode()
        )
        self.assertTrue(MODULE.verify_mosquitto_sha512_pbkdf2(password, line))
        self.assertFalse(MODULE.verify_mosquitto_sha512_pbkdf2("b" * 64, line))

    def test_password_database_rejects_wrong_user_and_shape(self) -> None:
        self.assertFalse(MODULE.verify_mosquitto_sha512_pbkdf2("a" * 64, "other:$7$1$QQ==$QQ=="))
        self.assertFalse(MODULE.verify_mosquitto_sha512_pbkdf2("a" * 64, MODULE.MQTT_USERNAME + ":$6$1$QQ==$QQ=="))

    def test_candidate_material_includes_exact_successor_identity(self) -> None:
        password = "c" * 64
        ca = "test-ca"
        material = MODULE.candidate_material(password, ca).decode()
        self.assertIn("gh-test-system-tlsvalid02", material)
        self.assertIn("gh-test-node-tlsvalid02", material)
        self.assertIn(MODULE.HOST, material)
        self.assertIn(password, material)

    def test_zero_secrets_are_rejected(self) -> None:
        with self.assertRaisesRegex(MODULE.ContractError, "MQTT_PASSWORD_INVALID"):
            MODULE.candidate_material("0" * 64, "ca")

    def test_private_inventory_requires_password_and_persistence_key(self) -> None:
        materials = {
            name: {"relative_path": name, "mode": "0600", "sha256": "1" * 64}
            for name in MODULE.REQUIRED_PRIVATE_FILES
        }
        digest = MODULE.private_material_digest(materials)
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        materials.pop("mqtt-password.hex")
        with self.assertRaisesRegex(MODULE.ContractError, "PRIVATE_INVENTORY_MISMATCH"):
            MODULE.private_material_digest(materials)

    def test_private_inventory_rejects_mode_and_path_drift(self) -> None:
        materials = {
            name: {"relative_path": name, "mode": "0600", "sha256": "2" * 64}
            for name in MODULE.REQUIRED_PRIVATE_FILES
        }
        materials["persistence-key.hex"]["mode"] = "0644"
        with self.assertRaisesRegex(MODULE.ContractError, "PRIVATE_MODE_MISMATCH"):
            MODULE.private_material_digest(materials)
        materials["persistence-key.hex"]["mode"] = "0600"
        materials["persistence-key.hex"]["relative_path"] = "other"
        with self.assertRaisesRegex(MODULE.ContractError, "PRIVATE_RELATIVE_PATH_MISMATCH"):
            MODULE.private_material_digest(materials)

    def test_public_descriptor_contains_only_digests_and_false_authorizations(self) -> None:
        descriptor = MODULE.build_public_descriptor(
            "1" * 40,
            "2" * 64,
            "3" * 64,
            "4" * 64,
            "5" * 64,
            "6" * 64,
            "7" * 64,
        )
        encoded = json.dumps(descriptor, sort_keys=True)
        self.assertNotIn("mqtt-password.hex", encoded)
        self.assertNotIn("persistence-key.hex", encoded)
        self.assertFalse(descriptor["execution_authorized"])
        self.assertFalse(descriptor["board_operation_authorized"])
        self.assertFalse(descriptor["network_operation_authorized"])
        self.assertFalse(descriptor["prepare_authorized"])
        self.assertFalse(descriptor["verify_authorized"])
        self.assertFalse(descriptor["activate_authorized"])
        self.assertFalse(descriptor["cleanup_authorized"])

    def test_source_contains_no_execution_apis(self) -> None:
        source = CONTRACT.read_text(encoding="utf-8")
        for forbidden in (
            "serial.Serial",
            "esptool",
            "socket.socket",
            "subprocess",
            "mosquitto_pub",
            "mosquitto_sub",
            "erase_flash",
            "write_flash",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
