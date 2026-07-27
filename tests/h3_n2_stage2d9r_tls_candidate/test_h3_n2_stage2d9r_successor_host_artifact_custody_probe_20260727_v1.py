#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

PROBE = Path(__file__).resolve().parents[2] / "tools" / "h3_n2_stage2d9r_successor_host_artifact_custody_probe_20260727_v1.py"
spec = importlib.util.spec_from_file_location("probe", PROBE)
assert spec and spec.loader
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.saved = {
            "PRIVATE_PACKAGE_SHA256": probe.PRIVATE_PACKAGE_SHA256,
            "PUBLIC_DESCRIPTOR_SHA256": probe.PUBLIC_DESCRIPTOR_SHA256,
            "CONSUMED_MARKER_SHA256": probe.CONSUMED_MARKER_SHA256,
        }

    def tearDown(self) -> None:
        for key, value in self.saved.items():
            setattr(probe, key, value)
        self.temp.cleanup()

    def make_tree(
        self,
        *,
        public_authorized: bool = False,
        custody_override: str | None = None,
    ) -> tuple[Path, Path, Path]:
        root = self.home / probe.CUSTODY_RELATIVE
        root.mkdir(parents=True)
        os.chmod(root.parent, 0o700)
        os.chmod(root, 0o700)
        materials = {}
        for index, name in enumerate(probe.REQUIRED_PRIVATE_FILES):
            path = root / name
            data = (
                b"a" * 64 + b"\n"
                if name in ("mqtt-password.hex", "persistence-key.hex", "unlock-token.hex")
                else f"fixture-{index}\n".encode()
            )
            path.write_bytes(data)
            os.chmod(path, 0o600)
            materials[name] = {
                "relative_path": name,
                "mode": "0600",
                "sha256": sha(data),
            }
        materials["persistence-key.hex"]["sha256"] = probe.PERSISTENCE_KEY_FILE_SHA256
        materials["prepare-command.txt"]["sha256"] = probe.PREPARE_COMMAND_SHA256
        materials["verify-command.txt"]["sha256"] = probe.VERIFY_COMMAND_SHA256
        materials["root-ca.cert.pem"]["sha256"] = probe.CA_PEM_SHA256
        materials["broker.cert.pem"]["sha256"] = probe.BROKER_PEM_SHA256
        materials["broker.fullchain.pem"]["sha256"] = probe.BROKER_FULLCHAIN_SHA256
        package = probe.private_material_digest(materials)
        probe.PRIVATE_PACKAGE_SHA256 = package

        public = {
            "schema": "gh.h3.n2.stage2d9r-private-execution-material-successor-public/1",
            "stage": probe.STAGE,
            "state": "SUCCESSOR_EXECUTION_MATERIAL_FROZEN",
            "source_sha": probe.SOURCE_SHA,
            "run_suffix": probe.RUN_SUFFIX,
            "broker_host": "stage2d9r.local",
            "broker_port": 8883,
            "broker_tls_server_name": "stage2d9r.local",
            "mqtt_username": "stage2d9r-test",
            "mqtt_password_sha256": "1" * 64,
            "unlock_digest_sha256": probe.UNLOCK_DIGEST_SHA256,
            "persistence_key_file_sha256": probe.PERSISTENCE_KEY_FILE_SHA256,
            "ca_pem_sha256": probe.CA_PEM_SHA256,
            "broker_certificate_der_sha256": probe.BROKER_DER_SHA256,
            "broker_spki_sha256": probe.BROKER_SPKI_SHA256,
            "candidate_digest_sha256": probe.CANDIDATE_DIGEST_SHA256,
            "prepare_command_sha256": probe.PREPARE_COMMAND_SHA256,
            "verify_command_sha256": probe.VERIFY_COMMAND_SHA256,
            "private_package_sha256": package,
        }
        for key in probe.FALSE_PUBLIC_FIELDS:
            public[key] = False
        if public_authorized:
            public["execution_authorized"] = True
        public_bytes = json.dumps(public, indent=2, sort_keys=True).encode() + b"\n"
        public_path = root / probe.PUBLIC_DESCRIPTOR
        public_path.write_bytes(public_bytes)
        os.chmod(public_path, 0o600)
        probe.PUBLIC_DESCRIPTOR_SHA256 = sha(public_bytes)

        private = {
            "schema": "gh.h3.n2.stage2d9r-private-execution-material-successor-custody/1",
            "stage": probe.STAGE,
            "state": "SUCCESSOR_EXECUTION_MATERIAL_FROZEN",
            "source_sha": probe.SOURCE_SHA,
            "run_suffix": probe.RUN_SUFFIX,
            "custody_root": custody_override or str(root.resolve()),
            "custody_root_mode": "0700",
            "generator_sha256": probe.GENERATOR_SHA256,
            "contract_sha256": probe.CONTRACT_SHA256,
            "protocol_sha256": probe.PROTOCOL_SHA256,
            "python_executable_sha256": probe.PYTHON_EXECUTABLE_SHA256,
            "openssl_executable_sha256": probe.OPENSSL_SHA256,
            "mosquitto_passwd_executable_sha256": probe.MOSQUITTO_PASSWD_SHA256,
            "private_package_sha256": package,
            "public_descriptor_sha256": probe.PUBLIC_DESCRIPTOR_SHA256,
            "authorization": {
                "authorization_id": probe.AUTHORIZATION_ID,
                "record_sha256": probe.AUTH_RECORD_SHA256,
                "one_shot": True,
                "replay_permitted": False,
                "automatic_retry_permitted": False,
                "consumed": True,
            },
            "materials": materials,
            "offline_proofs": {"all": True},
            "private_values_included": False,
            "raw_private_values_in_descriptor": False,
            "board_operation_authorized": False,
            "network_operation_authorized": False,
            "broker_start_authorized": False,
            "flash_operation_authorized": False,
            "physical_nvs_operation_authorized": False,
            "prepare_authorized": False,
            "verify_authorized": False,
            "activate_authorized": False,
            "cleanup_authorized": False,
            "production_operation_authorized": False,
        }
        private_path = root / probe.PRIVATE_DESCRIPTOR
        private_path.write_text(json.dumps(private, indent=2, sort_keys=True) + "\n")
        os.chmod(private_path, 0o600)

        auth = self.home / probe.AUTH_RELATIVE
        auth.mkdir(parents=True)
        os.chmod(auth, 0o700)
        marker = {
            "schema": "gh.h3.n2.stage2d9r-private-execution-material-successor-u1-consumption/1",
            "authorization_id": probe.AUTHORIZATION_ID,
            "status": "CONSUMED",
            "record_sha256": probe.AUTH_RECORD_SHA256,
            "claimed_at": "2026-07-25T00:00:00Z",
            "consumed_at": "2026-07-25T00:01:00Z",
            "public_descriptor_sha256": probe.PUBLIC_DESCRIPTOR_SHA256,
            "failure_code": None,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "secret_values_included": False,
        }
        marker_path = auth / f"{probe.AUTHORIZATION_ID}.consumed.json"
        marker_path.write_text(json.dumps(marker, indent=2, sort_keys=True) + "\n")
        os.chmod(marker_path, 0o600)
        probe.CONSUMED_MARKER_SHA256 = sha(marker_path.read_bytes())
        return root, private_path, marker_path

    def test_happy_metadata_probe(self) -> None:
        self.make_tree()
        result = probe.validate_custody(self.home)
        self.assertEqual(result["authorization_status"], "CONSUMED")
        self.assertFalse(result["private_material_content_read"])
        self.assertEqual(result["metadata_file_count"], 15)

    def test_missing_material_fails(self) -> None:
        root, _, _ = self.make_tree()
        (root / "mqtt-password.hex").unlink()
        with self.assertRaisesRegex(probe.ProbeError, "CUSTODY_INVENTORY_MISMATCH"):
            probe.validate_custody(self.home)

    def test_wrong_root_mode_fails(self) -> None:
        root, _, _ = self.make_tree()
        os.chmod(root, 0o755)
        with self.assertRaisesRegex(probe.ProbeError, "CUSTODY_ROOT_MODE_MISMATCH"):
            probe.validate_custody(self.home)

    def test_secret_size_fails(self) -> None:
        root, _, _ = self.make_tree()
        (root / "unlock-token.hex").write_text("x\n")
        os.chmod(root / "unlock-token.hex", 0o600)
        with self.assertRaisesRegex(probe.ProbeError, "SECRET_FILE_SIZE_MISMATCH"):
            probe.validate_custody(self.home)

    def test_private_package_binding_fails(self) -> None:
        self.make_tree()
        probe.PRIVATE_PACKAGE_SHA256 = "0" * 64
        with self.assertRaisesRegex(probe.ProbeError, "PRIVATE_PACKAGE_DIGEST_MISMATCH"):
            probe.validate_custody(self.home)

    def test_descriptor_root_fails(self) -> None:
        self.make_tree(custody_override="/forbidden/private/path")
        with self.assertRaisesRegex(probe.ProbeError, "PRIVATE_DESCRIPTOR_ROOT_MISMATCH"):
            probe.validate_custody(self.home)

    def test_public_authorization_expansion_fails(self) -> None:
        self.make_tree(public_authorized=True)
        with self.assertRaisesRegex(probe.ProbeError, "PUBLIC_DESCRIPTOR_AUTHORIZATION_EXPANDED"):
            probe.validate_custody(self.home)

    def test_marker_digest_fails(self) -> None:
        self.make_tree()
        probe.CONSUMED_MARKER_SHA256 = "f" * 64
        with self.assertRaisesRegex(probe.ProbeError, "CONSUMED_MARKER_DIGEST_MISMATCH"):
            probe.validate_custody(self.home)

    def test_symlink_material_fails(self) -> None:
        root, _, _ = self.make_tree()
        target = root / "target"
        target.write_text("x")
        os.chmod(target, 0o600)
        (root / "mqtt-password.hex").unlink()
        (root / "mqtt-password.hex").symlink_to(target)
        with self.assertRaisesRegex(
            probe.ProbeError,
            "CUSTODY_INVENTORY_MISMATCH|PRIVATE_MATERIAL_METADATA_INVALID",
        ):
            probe.validate_custody(self.home)


if __name__ == "__main__":
    unittest.main()
