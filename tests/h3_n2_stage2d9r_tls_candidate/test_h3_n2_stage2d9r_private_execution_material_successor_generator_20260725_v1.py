#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPOSITORY = Path(__file__).resolve().parents[2]
CONTRACT = REPOSITORY / "tools" / "h3_n2_stage2d9r_private_execution_material_successor_contract_20260725_v1.py"
PROTOCOL = REPOSITORY / "tools" / "h3_n2_stage2d9r_prepare_command_protocol_20260723_v1.py"
GENERATOR = REPOSITORY / "tools" / "h3_n2_stage2d9r_private_execution_material_successor_generator_20260725_v1.py"

for name, path in (
    ("h3_n2_stage2d9r_private_execution_material_successor_contract_20260725_v1", CONTRACT),
    ("h3_n2_stage2d9r_prepare_command_protocol_20260723_v1", PROTOCOL),
):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

spec = importlib.util.spec_from_file_location("stage2d9r_successor_generator", GENERATOR)
assert spec is not None and spec.loader is not None
GEN = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = GEN
spec.loader.exec_module(GEN)
CONTRACT_MODULE = sys.modules[
    "h3_n2_stage2d9r_private_execution_material_successor_contract_20260725_v1"
]
PROTOCOL_MODULE = sys.modules[
    "h3_n2_stage2d9r_prepare_command_protocol_20260723_v1"
]


class SuccessorGeneratorTests(unittest.TestCase):
    def toolchain(self) -> object:
        return GEN.Toolchain(
            generator_sha256="1" * 64,
            contract_sha256="2" * 64,
            protocol_sha256="3" * 64,
            python_executable_sha256="4" * 64,
            python_version="Python 3.11",
            openssl_path=Path("/usr/bin/openssl"),
            openssl_executable_sha256="5" * 64,
            openssl_version="OpenSSL test",
            mosquitto_passwd_path=Path("/usr/bin/mosquitto_passwd"),
            mosquitto_passwd_executable_sha256="6" * 64,
            mosquitto_passwd_version="mosquitto_passwd test",
        )

    def authorization(self, home: Path, now: datetime) -> dict[str, object]:
        toolchain = self.toolchain()
        root = GEN.default_custody_root(home)
        record: dict[str, object] = {
            "schema": GEN.AUTH_SCHEMA,
            "stage": GEN.STAGE,
            "authorization_id": GEN.AUTH_PREFIX + "20260725-01",
            "operation": GEN.AUTH_OPERATION,
            "authorized": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "run_suffix": CONTRACT_MODULE.RUN_SUFFIX,
            "custody_root_selection_rule": GEN.CUSTODY_RULE,
            "custody_root_digest_sha256": GEN.sha256_bytes(str(root).encode("utf-8")),
            "source_sha": "7" * 40,
            "generator_sha256": toolchain.generator_sha256,
            "contract_sha256": toolchain.contract_sha256,
            "protocol_sha256": toolchain.protocol_sha256,
            "python_executable_sha256": toolchain.python_executable_sha256,
            "openssl_executable_sha256": toolchain.openssl_executable_sha256,
            "mosquitto_passwd_executable_sha256": toolchain.mosquitto_passwd_executable_sha256,
            "issued_at": (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
        }
        record["record_sha256"] = GEN.authorization_record_digest(record)
        return record

    def test_default_root_is_unique_private_successor_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            root = GEN.default_custody_root(home)
            self.assertTrue(root.is_relative_to(home))
            self.assertIn("tlsvalid02", str(root))
            self.assertNotEqual(
                root,
                home / ".local/state/greenhouse-stage2d9r/private-pki-tlsvalid01",
            )

    def test_valid_authorization_passes_before_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            now = datetime.now(timezone.utc)
            record = self.authorization(home, now)
            authorization_id, marker, record_sha = GEN.validate_authorization(
                record, "7" * 40, self.toolchain(), home, now
            )
            self.assertEqual(authorization_id, record["authorization_id"])
            self.assertFalse(marker.exists())
            self.assertEqual(record_sha, record["record_sha256"])

    def test_expired_authorization_rejected_before_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            now = datetime.now(timezone.utc)
            record = self.authorization(home, now)
            record["issued_at"] = (now - timedelta(hours=3)).isoformat().replace("+00:00", "Z")
            record["expires_at"] = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
            record["record_sha256"] = GEN.authorization_record_digest(record)
            with self.assertRaisesRegex(GEN.GenerationError, "AUTH_NOT_CURRENT"):
                GEN.validate_authorization(record, "7" * 40, self.toolchain(), home, now)
            marker = GEN.default_consumed_marker(home, str(record["authorization_id"]))
            self.assertFalse(marker.exists())

    def test_toolchain_or_protocol_drift_rejected_before_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            now = datetime.now(timezone.utc)
            record = self.authorization(home, now)
            record["protocol_sha256"] = "9" * 64
            record["record_sha256"] = GEN.authorization_record_digest(record)
            with self.assertRaisesRegex(GEN.GenerationError, "AUTH_PROTOCOL_SHA256_MISMATCH"):
                GEN.validate_authorization(record, "7" * 40, self.toolchain(), home, now)

    def test_claim_and_success_finalize_are_one_shot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            authorization_id = GEN.AUTH_PREFIX + "20260725-02"
            marker = GEN.default_consumed_marker(home, authorization_id)
            GEN.claim_authorization(marker, authorization_id, "a" * 64)
            self.assertEqual(oct(marker.stat().st_mode & 0o777), "0o600")
            GEN.finalize_authorization(
                marker,
                "CONSUMED",
                public_descriptor_sha256="b" * 64,
            )
            payload = json.loads(marker.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "CONSUMED")
            self.assertIsNone(payload["failure_code"])
            self.assertFalse(payload["replay_permitted"])
            self.assertFalse(payload["automatic_retry_permitted"])

    def test_contract_and_protocol_render_parse_cross_binding(self) -> None:
        ca = (
            "-----BEGIN CERTIFICATE-----\n"
            + "\n".join(["A" * 64] * 4)
            + "\n-----END CERTIFICATE-----\n"
        )
        unlock = "a" * 64
        persistence = "b" * 64
        password = "c" * 64
        prepare, verify, candidate = CONTRACT_MODULE.render_commands(
            unlock, persistence, password, ca
        )
        unlock_digest = hashlib.sha256(bytes.fromhex(unlock)).hexdigest()
        self.assertEqual(
            prepare,
            PROTOCOL_MODULE.render_prepare(
                CONTRACT_MODULE.RUN_SUFFIX,
                unlock,
                persistence,
                password,
                ca,
            )
            + "\n",
        )
        self.assertEqual(
            verify,
            PROTOCOL_MODULE.render_verify(
                CONTRACT_MODULE.RUN_SUFFIX,
                unlock,
                persistence,
                candidate,
            )
            + "\n",
        )
        parsed_prepare = PROTOCOL_MODULE.parse_prepare(prepare, unlock_digest)
        parsed_verify = PROTOCOL_MODULE.parse_verify(verify, unlock_digest)
        self.assertEqual(parsed_prepare.authorization_digest, password)
        self.assertEqual(parsed_prepare.candidate_digest, candidate)
        self.assertEqual(parsed_verify.candidate_digest, candidate)

    def test_private_inventory_contains_all_execution_preimages(self) -> None:
        self.assertEqual(
            set(GEN.PRIVATE_FILENAMES.values()),
            set(CONTRACT_MODULE.REQUIRED_PRIVATE_FILES),
        )
        for required in (
            "mqtt-password.hex",
            "persistence-key.hex",
            "unlock-token.hex",
            "prepare-command.txt",
            "verify-command.txt",
        ):
            self.assertIn(required, CONTRACT_MODULE.REQUIRED_PRIVATE_FILES)

    def test_public_toolchain_summary_omits_paths_and_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            summary = GEN.toolchain_public_summary(
                self.toolchain(), Path(temporary).resolve()
            )
        payload = json.dumps(summary, sort_keys=True)
        self.assertNotIn("/usr/bin", payload)
        self.assertFalse(summary["private_paths_included"])
        self.assertFalse(summary["secret_values_included"])
        self.assertFalse(summary["authorization_claimed"])
        self.assertFalse(summary["network_operation"])
        self.assertFalse(summary["board_operation"])
        self.assertFalse(summary["prepare_executed"])
        self.assertFalse(summary["verify_executed"])

    def test_source_has_no_runtime_or_hardware_execution_api(self) -> None:
        source = GENERATOR.read_text(encoding="utf-8")
        for forbidden in (
            "serial.Serial",
            "socket.socket",
            "esptool",
            "mosquitto_pub",
            "mosquitto_sub",
            "erase_flash",
            "write_flash",
            "ACTIVATE_PROFILE",
            "CLEANUP_TEST_STATE",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
