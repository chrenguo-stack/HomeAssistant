#!/usr/bin/env python3
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import h3_n2_stage2d9r_g3r_repaired_private_material_contract_20260728_v1 as contract
import h3_n2_stage2d9r_g3r_repaired_private_material_generator_20260728_v1 as generator
import h3_n2_stage2d9r_g3r_repaired_successor_chain_contract_20260728_v1 as chain

GENERATOR = TOOLS / "h3_n2_stage2d9r_g3r_repaired_private_material_generator_20260728_v1.py"


def digest(name: str) -> str:
    return hashlib.sha256(("tlsvalid03:" + name).encode()).hexdigest()


def fake_ca() -> str:
    body = "\n".join(["A" * 64 for _ in range(5)])
    return f"-----BEGIN CERTIFICATE-----\n{body}\n-----END CERTIFICATE-----\n"


def mosquitto_line(password: str, iterations: int = 1000) -> str:
    salt = b"fixed-repaired-salt"
    observed = hashlib.pbkdf2_hmac(
        "sha512", password.encode(), salt, iterations, dklen=64
    )
    return (
        f"{contract.MQTT_USERNAME}:$7${iterations}$"
        f"{base64.b64encode(salt).decode()}$"
        f"{base64.b64encode(observed).decode()}"
    )


class RepairedPrivateMaterialTests(unittest.TestCase):
    def test_default_cli_is_inert_without_tool_probe(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(GENERATOR)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
            timeout=15,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        value = json.loads(completed.stdout)
        self.assertEqual(value["status"], "SOURCE_ONLY_REQUIRES_NEW_EXACT_U1")
        self.assertEqual(value["run_suffix"], "tlsvalid03")
        for key in (
            "authorization_created",
            "authorization_claimed",
            "authorization_consumed",
            "secret_generation",
            "private_material_created",
            "board_operation",
            "usb_enumeration",
            "serial_operation",
            "flash_operation",
            "physical_nvs_operation",
            "network_operation",
            "broker_started",
            "prepare_executed",
            "verify_executed",
            "replay_permitted",
            "automatic_retry_permitted",
            "private_paths_included",
            "secret_values_included",
        ):
            self.assertIs(value[key], False, key)

    def test_fixed_material_cross_binding_and_protocol_parse(self) -> None:
        password = "11" * 32
        persistence = "22" * 32
        unlock = "33" * 32
        prepare, verify, candidate, unlock_digest = contract.render_commands(
            unlock, persistence, password, fake_ca()
        )
        self.assertTrue(prepare.startswith("GH2D9R_PREPARE_V1 tlsvalid03 "))
        self.assertTrue(verify.startswith("GH2D9R_VERIFY_V1 tlsvalid03 "))
        self.assertRegex(candidate, r"^[0-9a-f]{64}$")
        self.assertEqual(unlock_digest, hashlib.sha256(bytes.fromhex(unlock)).hexdigest())
        self.assertNotIn(chain.REPAIR_SOURCE_BINDING, prepare)

    def test_password_database_cross_binding(self) -> None:
        password = "44" * 32
        line = mosquitto_line(password)
        self.assertTrue(contract.verify_mosquitto_sha512_pbkdf2(password, line))
        self.assertFalse(contract.verify_mosquitto_sha512_pbkdf2("55" * 32, line))

    def test_public_descriptor_binds_repair_source_but_not_final_binding(self) -> None:
        values = {
            name: digest(name)
            for name in (
                "generator_sha256",
                "contract_sha256",
                "chain_contract_sha256",
                "protocol_sha256",
                "mqtt_password_sha256",
                "unlock_digest_sha256",
                "persistence_key_file_sha256",
                "ca_pem_sha256",
                "broker_certificate_der_sha256",
                "broker_spki_sha256",
                "candidate_digest_sha256",
                "prepare_command_sha256",
                "verify_command_sha256",
                "private_package_sha256",
            )
        }
        value = contract.build_public_descriptor(source_sha="a" * 40, **values)
        self.assertEqual(value["repair_source_binding"], chain.REPAIR_SOURCE_BINDING)
        self.assertFalse(value["repair_source_binding_is_final_execution_binding"])
        self.assertFalse(value["final_execution_binding_ready"])
        self.assertFalse(value["secret_values_included"])
        self.assertFalse(value["private_paths_included"])

    def test_public_descriptor_rejects_retired_digest(self) -> None:
        values = {
            name: digest(name)
            for name in (
                "generator_sha256",
                "contract_sha256",
                "chain_contract_sha256",
                "protocol_sha256",
                "mqtt_password_sha256",
                "unlock_digest_sha256",
                "persistence_key_file_sha256",
                "ca_pem_sha256",
                "broker_certificate_der_sha256",
                "broker_spki_sha256",
                "candidate_digest_sha256",
                "prepare_command_sha256",
                "verify_command_sha256",
                "private_package_sha256",
            )
        }
        values["candidate_digest_sha256"] = next(iter(chain.RETIRED_DIGESTS))
        with self.assertRaisesRegex(chain.ContractError, "RETIRED_REUSE"):
            contract.build_public_descriptor(source_sha="a" * 40, **values)

    def test_exact_authorization_validation_is_one_shot_and_two_hour_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            source_sha = "a" * 40
            toolchain = generator.Toolchain(
                generator_sha256=digest("generator"),
                contract_sha256=digest("contract"),
                chain_contract_sha256=digest("chain"),
                protocol_sha256=digest("protocol"),
                python_executable_sha256=digest("python"),
                python_version="test",
                openssl_path=Path("/bin/true"),
                openssl_executable_sha256=digest("openssl"),
                openssl_version="test",
                mosquitto_passwd_path=Path("/bin/true"),
                mosquitto_passwd_executable_sha256=digest("mosquitto"),
                mosquitto_passwd_version="test",
            )
            now = datetime.now(timezone.utc)
            record = {
                "schema": generator.AUTH_SCHEMA,
                "stage": chain.STAGE,
                "decision_id": chain.DECISION_ID,
                "authorization_id": generator.AUTH_PREFIX + "20260728-01",
                "operation": generator.AUTH_OPERATION,
                "authorized": True,
                "one_shot": True,
                "replay_permitted": False,
                "automatic_retry_permitted": False,
                "run_suffix": chain.RUN_SUFFIX,
                "custody_root_selection_rule": chain.CUSTODY_SELECTION_RULE,
                "current_main_sha": chain.CURRENT_MAIN_SHA,
                "base_head_sha": chain.BASE_HEAD_SHA,
                "repair_source_binding": chain.REPAIR_SOURCE_BINDING,
                "source_sha": source_sha,
                "generator_sha256": toolchain.generator_sha256,
                "contract_sha256": toolchain.contract_sha256,
                "chain_contract_sha256": toolchain.chain_contract_sha256,
                "protocol_sha256": toolchain.protocol_sha256,
                "python_executable_sha256": toolchain.python_executable_sha256,
                "openssl_executable_sha256": toolchain.openssl_executable_sha256,
                "mosquitto_passwd_executable_sha256": toolchain.mosquitto_passwd_executable_sha256,
                "custody_root_digest_sha256": generator.sha256_bytes(
                    str(generator.default_custody_root(home)).encode()
                ),
                "issued_at": (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
                "expires_at": (now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
            }
            record["record_sha256"] = generator.authorization_record_digest(record)
            authorization_id, marker, observed = generator.validate_authorization(
                record, source_sha, toolchain, home, now
            )
            self.assertEqual(authorization_id, record["authorization_id"])
            self.assertFalse(marker.exists())
            self.assertEqual(observed, record["record_sha256"])
            record["current_main_sha"] = chain.PREVIOUS_MAIN_SHA
            record["record_sha256"] = generator.authorization_record_digest(record)
            with self.assertRaisesRegex(generator.GenerationError, "AUTH_MAIN_SHA_MISMATCH"):
                generator.validate_authorization(record, source_sha, toolchain, home, now)

    def test_private_root_must_be_unique_outside_shared_temp(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            home = Path(temp)
            root = generator.default_custody_root(home)
            generator.validate_private_root(root, home, None)
            root.parent.mkdir(parents=True)
            root.mkdir()
            with self.assertRaisesRegex(generator.GenerationError, "ALREADY_EXISTS"):
                generator.validate_private_root(root, home, None)


if __name__ == "__main__":
    unittest.main()
