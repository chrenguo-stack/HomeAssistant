#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/h3_n2_stage2d9r_private_content_binding_probe_20260724_v1.py"
SPEC = importlib.util.spec_from_file_location("private_content_binding_probe", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class PrivateContentBindingProbeContractTest(unittest.TestCase):
    def test_authorization_digest_excludes_record_field(self) -> None:
        record = {"a": 1, "record_sha256": "0" * 64}
        self.assertEqual(
            probe.authorization_digest(record),
            probe.canonical_json_sha256({"a": 1}),
        )

    def test_private_write_is_exclusive_and_mode_0600(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "auth" / "marker.json"
            probe.private_write(path, {"status": "CLAIMED"})
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                probe.private_write(path, {"status": "CLAIMED"})

    def _marker(self, root: Path) -> tuple[Path, str]:
        value = {
            "authorization_id": "U1-TEST-01",
            "status": "CONSUMED",
            "record_sha256": "a" * 64,
            "one_shot": True,
            "replay_permitted": False,
            "secret_values_included": False,
        }
        raw = json.dumps(value, indent=2, sort_keys=True).encode() + b"\n"
        path = root / "marker.json"
        path.write_bytes(raw)
        os.chmod(path, 0o600)
        return path, hashlib.sha256(raw).hexdigest()

    def test_exact_marker_binds_full_file_and_safe_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path, digest = self._marker(Path(td))
            value = probe.exact_marker(path, digest, "U1-TEST-01", "CONSUMED")
            self.assertEqual(value["record_sha256"], "a" * 64)

    def test_exact_marker_rejects_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path, _ = self._marker(Path(td))
            with self.assertRaisesRegex(probe.BindingError, "DESCRIPTOR_DIGEST_MISMATCH"):
                probe.exact_marker(path, "0" * 64, "U1-TEST-01", "CONSUMED")

    def test_material_set_digest_is_order_independent(self) -> None:
        a = {
            "z": {"relative_path": "z", "mode": "0600", "sha256": "1" * 64},
            "a": {"relative_path": "a", "mode": "0600", "sha256": "2" * 64},
        }
        b = {"a": a["a"], "z": a["z"]}
        self.assertEqual(probe.material_set_digest(a), probe.material_set_digest(b))

    def test_private_root_requires_exact_digest_and_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            relative = Path("custody")
            root = home / relative
            root.mkdir()
            os.chmod(root, 0o700)
            digest = probe.sha256_bytes(str(root.resolve(strict=False)).encode())
            self.assertEqual(probe.private_root(home, relative, digest), root)
            os.chmod(root, 0o755)
            with self.assertRaisesRegex(probe.BindingError, "CUSTODY_ROOT_MODE_MISMATCH"):
                probe.private_root(home, relative, digest)

    def test_parse_utc_requires_zulu(self) -> None:
        parsed = probe.parse_utc("2026-07-24T00:00:00Z", "issued_at")
        self.assertEqual(parsed.tzinfo, timezone.utc)
        with self.assertRaisesRegex(probe.BindingError, "ISSUED_AT_INVALID"):
            probe.parse_utc("2026-07-24T00:00:00", "issued_at")

    @unittest.skipUnless(shutil.which("openssl"), "openssl unavailable")
    def test_offline_private_key_matches_certificate(self) -> None:
        openssl = Path(shutil.which("openssl") or "").resolve(strict=True)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            key = root / "key.pem"
            cert = root / "cert.pem"
            subprocess.run(
                [
                    str(openssl), "req", "-x509", "-newkey", "rsa:2048",
                    "-nodes", "-subj", "/CN=test.local", "-days", "1",
                    "-keyout", str(key), "-out", str(cert),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            self.assertEqual(
                probe.sha256_bytes(probe.key_public_der(openssl, key)),
                probe.sha256_bytes(probe.cert_public_der(openssl, cert)),
            )

    def test_source_has_no_network_or_board_libraries(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "import socket",
            "import serial",
            "esptool",
            "mosquitto_sub",
            "mosquitto_pub",
            "PREPARE_CANDIDATE",
            "ACTIVATE_PROFILE",
            "CLEANUP_TEST_STATE",
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
