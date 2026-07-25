#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

REPOSITORY = Path(__file__).resolve().parents[2]
EXPORTER = (
    REPOSITORY
    / "tools"
    / "h3_n2_stage2d9r_successor_public_descriptor_exporter_20260725_v1.py"
)
SPEC = importlib.util.spec_from_file_location("stage2d9r_public_descriptor_exporter", EXPORTER)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def descriptor() -> dict[str, object]:
    value: dict[str, object] = {
        "schema": MODULE.PUBLIC_SCHEMA,
        "stage": MODULE.STAGE,
        "state": "SUCCESSOR_EXECUTION_MATERIAL_FROZEN",
        "source_sha": MODULE.AUTHORIZED_SOURCE_SHA,
        "run_suffix": MODULE.RUN_SUFFIX,
        "broker_host": "stage2d9r.local",
        "broker_port": 8883,
        "broker_tls_server_name": "stage2d9r.local",
        "mqtt_username": "stage2d9r-test",
        "mqtt_password_sha256": "1" * 64,
        "unlock_digest_sha256": MODULE.UNLOCK_DIGEST_SHA256,
        "persistence_key_file_sha256": "2" * 64,
        "ca_pem_sha256": MODULE.CA_PEM_SHA256,
        "broker_certificate_der_sha256": MODULE.BROKER_CERTIFICATE_DER_SHA256,
        "broker_spki_sha256": MODULE.BROKER_SPKI_SHA256,
        "candidate_digest_sha256": MODULE.CANDIDATE_DIGEST_SHA256,
        "prepare_command_sha256": "3" * 64,
        "verify_command_sha256": "4" * 64,
        "private_package_sha256": MODULE.PRIVATE_PACKAGE_SHA256,
    }
    for key in (
        "private_values_included",
        "private_paths_included",
        "secret_values_included",
        "execution_authorized",
        "board_operation_authorized",
        "serial_operation_authorized",
        "flash_operation_authorized",
        "physical_nvs_operation_authorized",
        "network_operation_authorized",
        "broker_start_authorized",
        "prepare_authorized",
        "verify_authorized",
        "activate_authorized",
        "cleanup_authorized",
        "production_operation_authorized",
    ):
        value[key] = False
    return value


def descriptor_bytes(value: dict[str, object] | None = None) -> bytes:
    return json.dumps(value or descriptor(), indent=2, sort_keys=True).encode() + b"\n"


def forbidden_file_names() -> tuple[str, ...]:
    return (
        "mqtt-" + "password.hex",
        "persistence-" + "key.hex",
        "unlock-" + "token.hex",
        "prepare-" + "command.txt",
        "verify-" + "command.txt",
        "root-ca." + "key.pem",
        "broker." + "key.pem",
        "mosquitto." + "password",
    )


class PublicDescriptorExporterTests(unittest.TestCase):
    def test_valid_redacted_descriptor_passes(self) -> None:
        data = descriptor_bytes()
        observed = MODULE.validate_public_descriptor_bytes(data, hashlib.sha256(data).hexdigest())
        self.assertEqual(observed["candidate_digest_sha256"], MODULE.CANDIDATE_DIGEST_SHA256)

    def test_digest_drift_is_rejected(self) -> None:
        with self.assertRaisesRegex(MODULE.ExportError, "PUBLIC_DESCRIPTOR_SHA256_MISMATCH"):
            MODULE.validate_public_descriptor_bytes(descriptor_bytes(), "0" * 64)

    def test_secret_or_authorization_fields_are_rejected(self) -> None:
        value = descriptor()
        value["mqtt_password"] = "x"
        data = descriptor_bytes(value)
        with self.assertRaisesRegex(MODULE.ExportError, "PUBLIC_DESCRIPTOR_FORBIDDEN_KEY_PRESENT"):
            MODULE.validate_public_descriptor_bytes(data, hashlib.sha256(data).hexdigest())
        value = descriptor()
        value["network_operation_authorized"] = True
        data = descriptor_bytes(value)
        with self.assertRaisesRegex(MODULE.ExportError, "NETWORK_OPERATION_AUTHORIZED_MISMATCH"):
            MODULE.validate_public_descriptor_bytes(data, hashlib.sha256(data).hexdigest())

    def test_candidate_and_certificate_drift_are_rejected(self) -> None:
        value = descriptor()
        value["candidate_digest_sha256"] = "5" * 64
        data = descriptor_bytes(value)
        with self.assertRaisesRegex(MODULE.ExportError, "CANDIDATE_DIGEST_SHA256_MISMATCH"):
            MODULE.validate_public_descriptor_bytes(data, hashlib.sha256(data).hexdigest())
        value = descriptor()
        value["broker_spki_sha256"] = "6" * 64
        data = descriptor_bytes(value)
        with self.assertRaisesRegex(MODULE.ExportError, "BROKER_SPKI_SHA256_MISMATCH"):
            MODULE.validate_public_descriptor_bytes(data, hashlib.sha256(data).hexdigest())

    def test_deterministic_zip_is_reproducible_and_mode_0600(self) -> None:
        entries = {"b.txt": b"b", "a.txt": b"a"}
        first = MODULE.deterministic_zip(entries)
        second = MODULE.deterministic_zip(entries)
        self.assertEqual(first, second)
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "x.zip"
            archive_path.write_bytes(first)
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(archive.namelist(), ["a.txt", "b.txt"])
                for info in archive.infolist():
                    self.assertEqual((info.external_attr >> 16) & 0o777, 0o600)

    def test_export_package_contains_only_public_files(self) -> None:
        data = descriptor_bytes()
        original_validator = MODULE.validate_public_descriptor_bytes
        MODULE.validate_public_descriptor_bytes = lambda observed: descriptor()
        try:
            archive, binding_sha = MODULE.build_export(
                data, "a" * 40, "U1-test", "b" * 64
            )
        finally:
            MODULE.validate_public_descriptor_bytes = original_validator
        self.assertRegex(binding_sha, r"^[0-9a-f]{64}$")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "export.zip"
            path.write_bytes(archive)
            with zipfile.ZipFile(path) as zipped:
                self.assertEqual(
                    sorted(zipped.namelist()),
                    ["SHA256SUMS", "export-binding.json", "public-descriptor.redacted.json"],
                )
                all_bytes = b"".join(zipped.read(name) for name in zipped.namelist())
                for forbidden in forbidden_file_names():
                    self.assertNotIn(forbidden.encode(), all_bytes)
                self.assertNotIn(("BEGIN " + "PRIVATE KEY").encode(), all_bytes)

    def test_authorization_interval_must_be_exactly_two_hours(self) -> None:
        issued = datetime.now(timezone.utc) - timedelta(minutes=1)
        expires = issued + timedelta(hours=1)
        record = {
            "schema": MODULE.AUTH_SCHEMA,
            "stage": MODULE.STAGE,
            "authorization_id": MODULE.AUTH_PREFIX + "TEST",
            "operation": MODULE.AUTH_OPERATION,
            "authorized": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "source_sha": "a" * 40,
            "authorized_generation_source_sha": MODULE.AUTHORIZED_SOURCE_SHA,
            "generation_marker_sha256": MODULE.GENERATION_MARKER_SHA256,
            "public_descriptor_sha256": MODULE.PUBLIC_DESCRIPTOR_SHA256,
            "exporter_sha256": "b" * 64,
            "python_executable_sha256": "c" * 64,
            "output_target_digest_sha256": "d" * 64,
            "output_target_exists": False,
            "issued_at": issued.isoformat().replace("+00:00", "Z"),
            "expires_at": expires.isoformat().replace("+00:00", "Z"),
        }
        record["record_sha256"] = MODULE.authorization_record_digest(record)
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / "Downloads").mkdir()
            with self.assertRaisesRegex(MODULE.ExportError, "AUTH_OUTPUT_TARGET_DIGEST_MISMATCH|AUTH_INTERVAL_NOT_EXACTLY_TWO_HOURS"):
                MODULE.validate_authorization(record, "a" * 40, "b" * 64, "c" * 64, home, datetime.now(timezone.utc))

    def test_source_contains_no_board_network_or_secret_file_reads(self) -> None:
        source = EXPORTER.read_text(encoding="utf-8")
        for forbidden in (
            "serial." + "Serial",
            "esp" + "tool",
            "socket." + "socket",
            "mosquitto_" + "pub",
            "mosquitto_" + "sub",
            *forbidden_file_names(),
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
