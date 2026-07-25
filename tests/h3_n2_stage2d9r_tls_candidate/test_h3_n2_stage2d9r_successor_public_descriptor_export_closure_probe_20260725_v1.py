#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

REPOSITORY = Path(__file__).resolve().parents[2]
PROBE = (
    REPOSITORY
    / "tools"
    / "h3_n2_stage2d9r_successor_public_descriptor_export_closure_probe_20260725_v1.py"
)
SPEC = importlib.util.spec_from_file_location("stage2d9r_public_export_closure_probe", PROBE)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def marker_payload(export_sha: str) -> dict[str, object]:
    return {
        "schema": MODULE.MARKER_SCHEMA,
        "authorization_id": MODULE.AUTHORIZATION_ID,
        "status": "CONSUMED",
        "record_sha256": MODULE.AUTHORIZATION_RECORD_SHA256,
        "claimed_at": "2026-07-25T06:00:00Z",
        "consumed_at": "2026-07-25T06:01:00Z",
        "export_zip_sha256": export_sha,
        "failure_code": None,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "secret_values_included": False,
    }


def public_descriptor() -> dict[str, object]:
    return {
        "schema": MODULE.PUBLIC_SCHEMA,
        "source_sha": MODULE.AUTHORIZED_GENERATION_SOURCE_SHA,
        "candidate_digest_sha256": MODULE.CANDIDATE_DIGEST_SHA256,
        "private_package_sha256": MODULE.PRIVATE_PACKAGE_SHA256,
    }


def export_binding() -> dict[str, object]:
    value: dict[str, object] = {
        "schema": MODULE.EXPORT_BINDING_SCHEMA,
        "stage": MODULE.STAGE,
        "state": "PUBLIC_DESCRIPTOR_EXPORTED",
        "authorization_id": MODULE.AUTHORIZATION_ID,
        "authorization_record_sha256": MODULE.AUTHORIZATION_RECORD_SHA256,
        "exporter_source_sha": MODULE.AUTHORIZED_SOURCE_SHA,
        "authorized_generation_source_sha": MODULE.AUTHORIZED_GENERATION_SOURCE_SHA,
        "generation_marker_sha256": MODULE.GENERATION_MARKER_SHA256,
        "public_descriptor_sha256": "0" * 64,
        "private_package_sha256": MODULE.PRIVATE_PACKAGE_SHA256,
        "candidate_digest_sha256": MODULE.CANDIDATE_DIGEST_SHA256,
    }
    for key in (
        "private_content_included",
        "private_paths_included",
        "secret_values_included",
        "authorization_record_included",
        "board_operation",
        "serial_operation",
        "flash_operation",
        "physical_nvs_operation",
        "network_operation",
        "broker_started",
        "prepare_executed",
        "verify_executed",
        "activate_executed",
        "cleanup_executed",
        "production_operation",
    ):
        value[key] = False
    return value


def make_export(path: Path) -> tuple[str, str, str]:
    descriptor_bytes = json.dumps(public_descriptor(), sort_keys=True).encode() + b"\n"
    descriptor_sha = hashlib.sha256(descriptor_bytes).hexdigest()
    binding = export_binding()
    binding["public_descriptor_sha256"] = descriptor_sha
    binding_bytes = json.dumps(binding, sort_keys=True).encode() + b"\n"
    binding_sha = hashlib.sha256(binding_bytes).hexdigest()
    sums = (
        f"{binding_sha}  export-binding.json\n"
        f"{descriptor_sha}  public-descriptor.redacted.json\n"
    ).encode()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(
            {
                "SHA256SUMS": sums,
                "export-binding.json": binding_bytes,
                "public-descriptor.redacted.json": descriptor_bytes,
            }.items()
        ):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            info.create_system = 3
            archive.writestr(info, data)
    os.chmod(path, 0o600)
    return hashlib.sha256(path.read_bytes()).hexdigest(), binding_sha, descriptor_sha


class PublicExportClosureProbeTests(unittest.TestCase):
    def test_valid_marker_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "marker.json"
            marker.write_text(json.dumps(marker_payload(MODULE.EXPORT_ZIP_SHA256)) + "\n")
            before = marker.read_bytes()
            observed = MODULE.validate_marker(marker)
            self.assertEqual(observed, hashlib.sha256(before).hexdigest())
            self.assertEqual(marker.read_bytes(), before)

    def test_marker_failure_or_replay_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "marker.json"
            value = marker_payload(MODULE.EXPORT_ZIP_SHA256)
            value["failure_code"] = "X"
            marker.write_text(json.dumps(value) + "\n")
            with self.assertRaisesRegex(MODULE.ProbeError, "MARKER_FAILURE_CODE_PRESENT"):
                MODULE.validate_marker(marker)
            value = marker_payload(MODULE.EXPORT_ZIP_SHA256)
            value["replay_permitted"] = True
            marker.write_text(json.dumps(value) + "\n")
            with self.assertRaisesRegex(MODULE.ProbeError, "REPLAY_BOUNDARY_MISMATCH"):
                MODULE.validate_marker(marker)

    def test_valid_public_export_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "export.zip"
            export_sha, binding_sha, descriptor_sha = make_export(path)
            original = (
                MODULE.EXPORT_ZIP_SHA256,
                MODULE.EXPORT_BINDING_SHA256,
                MODULE.PUBLIC_DESCRIPTOR_SHA256,
            )
            MODULE.EXPORT_ZIP_SHA256 = export_sha
            MODULE.EXPORT_BINDING_SHA256 = binding_sha
            MODULE.PUBLIC_DESCRIPTOR_SHA256 = descriptor_sha
            try:
                before = path.read_bytes()
                observed = MODULE.validate_export(path)
            finally:
                (
                    MODULE.EXPORT_ZIP_SHA256,
                    MODULE.EXPORT_BINDING_SHA256,
                    MODULE.PUBLIC_DESCRIPTOR_SHA256,
                ) = original
            self.assertEqual(observed, (export_sha, binding_sha, descriptor_sha))
            self.assertEqual(path.read_bytes(), before)

    def test_export_digest_and_inventory_drift_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "export.zip"
            export_sha, binding_sha, descriptor_sha = make_export(path)
            original = MODULE.EXPORT_ZIP_SHA256
            MODULE.EXPORT_ZIP_SHA256 = "0" * 64
            try:
                with self.assertRaisesRegex(MODULE.ProbeError, "EXPORT_ZIP_SHA256_MISMATCH"):
                    MODULE.validate_export(path)
            finally:
                MODULE.EXPORT_ZIP_SHA256 = original

    def test_forbidden_public_descriptor_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "export.zip"
            descriptor = public_descriptor()
            descriptor["mqtt_password"] = "secret"
            descriptor_bytes = json.dumps(descriptor, sort_keys=True).encode() + b"\n"
            descriptor_sha = hashlib.sha256(descriptor_bytes).hexdigest()
            binding = export_binding()
            binding["public_descriptor_sha256"] = descriptor_sha
            binding_bytes = json.dumps(binding, sort_keys=True).encode() + b"\n"
            binding_sha = hashlib.sha256(binding_bytes).hexdigest()
            sums = f"{binding_sha}  export-binding.json\n{descriptor_sha}  public-descriptor.redacted.json\n".encode()
            with zipfile.ZipFile(path, "w") as archive:
                for name, data in sorted({"SHA256SUMS": sums, "export-binding.json": binding_bytes, "public-descriptor.redacted.json": descriptor_bytes}.items()):
                    info = zipfile.ZipInfo(name)
                    info.external_attr = 0o600 << 16
                    info.create_system = 3
                    archive.writestr(info, data)
            os.chmod(path, 0o600)
            original = (MODULE.EXPORT_ZIP_SHA256, MODULE.EXPORT_BINDING_SHA256, MODULE.PUBLIC_DESCRIPTOR_SHA256)
            MODULE.EXPORT_ZIP_SHA256 = hashlib.sha256(path.read_bytes()).hexdigest()
            MODULE.EXPORT_BINDING_SHA256 = binding_sha
            MODULE.PUBLIC_DESCRIPTOR_SHA256 = descriptor_sha
            try:
                with self.assertRaisesRegex(MODULE.ProbeError, "PUBLIC_DESCRIPTOR_FORBIDDEN_KEY_PRESENT"):
                    MODULE.validate_export(path)
            finally:
                MODULE.EXPORT_ZIP_SHA256, MODULE.EXPORT_BINDING_SHA256, MODULE.PUBLIC_DESCRIPTOR_SHA256 = original

    def test_source_contains_no_private_material_reads_or_execution_apis(self) -> None:
        source = PROBE.read_text(encoding="utf-8")
        for forbidden in (
            "serial.Serial",
            "esptool",
            "socket.socket",
            "subprocess",
            "mosquitto_pub",
            "mosquitto_sub",
            "mqtt-password.hex",
            "persistence-key.hex",
            "unlock-token.hex",
            "root-ca.key.pem",
            "broker.key.pem",
            "mosquitto.password",
            "prepare-command.txt",
            "verify-command.txt",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
