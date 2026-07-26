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

P = Path(__file__).resolve().parents[2] / "tools" / "h3_n2_stage2d9r_successor_public_pki_export_success_probe_20260727_v1.py"
S = importlib.util.spec_from_file_location("probe", P)
M = importlib.util.module_from_spec(S)
assert S.loader is not None
S.loader.exec_module(M)


def write_marker(path: Path, **changes: object) -> None:
    now = datetime.now(timezone.utc)
    value = {
        "schema": M.MARKER_SCHEMA,
        "authorization_id": M.AUTHORIZATION_ID,
        "status": "CONSUMED",
        "record_sha256": M.AUTHORIZATION_RECORD_SHA256,
        "claimed_at": (now - timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
        "consumed_at": now.isoformat().replace("+00:00", "Z"),
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "secret_values_included": False,
        "export_zip_sha256": M.EXPORT_ZIP_SHA256,
        "failure_code": None,
    }
    value.update(changes)
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)


def make_output(path: Path, *, extra: bool = False, unsafe: bool = False) -> tuple[str, str]:
    binding = {
        "schema": M.EXPORT_SCHEMA,
        "stage": M.STAGE,
        "state": "PUBLIC_PKI_EXPORTED",
        "authorization_id": M.AUTHORIZATION_ID,
        "authorization_record_sha256": M.AUTHORIZATION_RECORD_SHA256,
        "exporter_source_sha": M.AUTHORIZED_SOURCE_SHA,
        "public_descriptor_sha256": M.PUBLIC_DESCRIPTOR_SHA256,
        "candidate_digest_sha256": M.CANDIDATE_DIGEST_SHA256,
        "ca_pem_sha256": M.CA_PEM_SHA256,
        "broker_der_sha256": M.BROKER_DER_SHA256,
        "broker_spki_sha256": M.BROKER_SPKI_SHA256,
        "certificate_chain_valid": True,
        "broker_hostname_match": True,
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
        binding[key] = False
    if unsafe:
        binding["network_operation"] = True
    binding_bytes = (json.dumps(binding, indent=2, sort_keys=True) + "\n").encode()
    entries = {
        "broker.cert.pem": b"leaf\n",
        "broker.fullchain.pem": b"leaf\nca\n",
        "public-descriptor.redacted.json": b"{}\n",
        "public-pki-export-binding.json": binding_bytes,
        "root-ca.cert.pem": b"ca\n",
    }
    sums = b"".join(
        f"{hashlib.sha256(value).hexdigest()}  {name}\n".encode()
        for name, value in sorted(entries.items())
    )
    entries["SHA256SUMS"] = sums
    if extra:
        entries["extra"] = b"x"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            info.create_system = 3
            archive.writestr(info, entries[name])
    path.chmod(0o600)
    return hashlib.sha256(path.read_bytes()).hexdigest(), hashlib.sha256(binding_bytes).hexdigest()


class T(unittest.TestCase):
    def test_marker_valid(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "marker.json"
            write_marker(path)
            result = M.validate_marker(path)
            self.assertTrue(result["authorization_consumed"])
            self.assertFalse(result["marker_modified"])

    def test_marker_status_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "marker.json"
            write_marker(path, status="CONSUMED_FAILED")
            with self.assertRaisesRegex(M.ProbeError, "MARKER_STATUS_MISMATCH"):
                M.validate_marker(path)

    def test_marker_record_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "marker.json"
            write_marker(path, record_sha256="0" * 64)
            with self.assertRaisesRegex(M.ProbeError, "AUTHORIZATION_RECORD_SHA256_MISMATCH"):
                M.validate_marker(path)

    def test_output_valid(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "output.zip"
            output_sha, binding_sha = make_output(path)
            old = (M.EXPORT_ZIP_SHA256, M.EXPORT_BINDING_SHA256)
            M.EXPORT_ZIP_SHA256, M.EXPORT_BINDING_SHA256 = output_sha, binding_sha
            try:
                result = M.validate_output(path)
                self.assertEqual(result["output_entry_count"], 6)
                self.assertTrue(result["internal_sha256sums_valid"])
            finally:
                M.EXPORT_ZIP_SHA256, M.EXPORT_BINDING_SHA256 = old

    def test_output_inventory_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "output.zip"
            output_sha, binding_sha = make_output(path, extra=True)
            old = (M.EXPORT_ZIP_SHA256, M.EXPORT_BINDING_SHA256)
            M.EXPORT_ZIP_SHA256, M.EXPORT_BINDING_SHA256 = output_sha, binding_sha
            try:
                with self.assertRaisesRegex(M.ProbeError, "OUTPUT_INVENTORY_MISMATCH"):
                    M.validate_output(path)
            finally:
                M.EXPORT_ZIP_SHA256, M.EXPORT_BINDING_SHA256 = old

    def test_output_boundary_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "output.zip"
            output_sha, binding_sha = make_output(path, unsafe=True)
            old = (M.EXPORT_ZIP_SHA256, M.EXPORT_BINDING_SHA256)
            M.EXPORT_ZIP_SHA256, M.EXPORT_BINDING_SHA256 = output_sha, binding_sha
            try:
                with self.assertRaisesRegex(M.ProbeError, "BOUNDARY_NETWORK_OPERATION_MISMATCH"):
                    M.validate_output(path)
            finally:
                M.EXPORT_ZIP_SHA256, M.EXPORT_BINDING_SHA256 = old


if __name__ == "__main__":
    unittest.main()
