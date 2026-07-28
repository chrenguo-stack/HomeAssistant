#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import h3_n2_stage2d9r_g3r_repaired_u1_host_preauth_probe_20260728_v1 as probe
import h3_n2_stage2d9r_g3r_repaired_u1_host_preauth_review_packager_20260728_v1 as packager

PROBE = TOOLS / "h3_n2_stage2d9r_g3r_repaired_u1_host_preauth_probe_20260728_v1.py"


def write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o700)


class RepairedU1HostPreauthTests(unittest.TestCase):
    def test_default_cli_is_inert(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(PROBE)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=15,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        value = json.loads(completed.stdout)
        self.assertEqual(value["status"], "SOURCE_ONLY_REQUIRES_EXPLICIT_HOST_PROBE")
        self.assertFalse(value["host_probe_executed"])
        self.assertFalse(value["authorized"])
        self.assertFalse(value["secret_generation"])

    def test_package_is_deterministic_and_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            out_a = root / "a"
            out_b = root / "b"
            result_a = packager.build_package(ROOT, out_a, "a" * 40)
            result_b = packager.build_package(ROOT, out_b, "a" * 40)
            archive_a = out_a / result_a["archive_name"]
            archive_b = out_b / result_b["archive_name"]
            self.assertEqual(archive_a.read_bytes(), archive_b.read_bytes())
            self.assertEqual(result_a["archive_sha256"], result_b["archive_sha256"])
            binding, request, archive_sha = probe.validate_package(out_a)
            self.assertEqual(binding["host_preflight_source_sha"], "a" * 40)
            self.assertEqual(binding["upstream_source_sha"], probe.UPSTREAM_SOURCE_SHA)
            self.assertEqual(request["state"], "AWAITING_HOST_TOOLCHAIN_PROBE")
            self.assertFalse(request["authorized"])
            self.assertEqual(archive_sha, result_a["archive_sha256"])

    def test_host_probe_returns_unauthorized_bound_request(self) -> None:
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temp:
            root = Path(temp)
            package_root = root / "package"
            home = root / "home"
            home.mkdir(mode=0o700)
            packager.build_package(ROOT, package_root, "b" * 40)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            openssl = fake_bin / "openssl"
            mosquitto = fake_bin / "mosquitto_passwd"
            write_executable(
                openssl,
                "#!/bin/sh\nif [ \"$1\" = version ]; then echo 'OpenSSL test-host'; exit 0; fi\nexit 1\n",
            )
            write_executable(
                mosquitto,
                "#!/bin/sh\necho 'mosquitto_passwd test-host'\nexit 1\n",
            )
            result = probe.run_host_probe(package_root, home, openssl, mosquitto)
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["ready_for_exact_u1_decision"])
            request = result["request"]
            self.assertEqual(request["state"], probe.RESULT_STATE)
            self.assertEqual(request["source_sha"], probe.UPSTREAM_SOURCE_SHA)
            self.assertEqual(request["host_preflight_source_sha"], "b" * 40)
            self.assertRegex(request["request_binding_sha256"], r"^[0-9a-f]{64}$")
            self.assertIsNone(request["authorization_id"])
            self.assertIsNone(request["issued_at"])
            self.assertIsNone(request["expires_at"])
            self.assertFalse(request["authorized"])
            self.assertFalse(request["custody_root_exists"])
            self.assertFalse(request["private_paths_included"])
            self.assertNotIn(str(home), json.dumps(result))

    def test_existing_custody_root_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temp:
            root = Path(temp)
            package_root = root / "package"
            home = root / "home"
            home.mkdir(mode=0o700)
            packager.build_package(ROOT, package_root, "c" * 40)
            custody = home / Path(".local/state/greenhouse-stage2d9r/repaired-successor-private-execution-material-tlsvalid03")
            custody.mkdir(parents=True)
            custody.parent.chmod(0o700)
            with self.assertRaisesRegex(Exception, "CUSTODY_ROOT_ALREADY_EXISTS"):
                probe.custody_metadata(home, package_root)

    def test_tampered_upstream_source_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package_root = Path(temp) / "package"
            packager.build_package(ROOT, package_root, "d" * 40)
            target = package_root / next(iter(probe.UPSTREAM_SOURCE_DIGESTS))
            target.write_bytes(target.read_bytes() + b"\n")
            with self.assertRaisesRegex(probe.ProbeError, "PACKAGE_MEMBER_DIGEST_MISMATCH"):
                probe.validate_package(package_root)

    def test_packager_rejects_upstream_source_as_layer_head(self) -> None:
        inventory = {
            relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            for relative in packager.SOURCE_FILES
        }
        with self.assertRaisesRegex(packager.PackageError, "MUST_EXTEND_UPSTREAM"):
            packager.build_binding(probe.UPSTREAM_SOURCE_SHA, inventory)

    def test_source_imports_exclude_execution_transports(self) -> None:
        for path in (
            PROBE,
            TOOLS / "h3_n2_stage2d9r_g3r_repaired_u1_host_preauth_review_packager_20260728_v1.py",
        ):
            spec = importlib.util.spec_from_file_location("checked", path)
            self.assertIsNotNone(spec)
            text = path.read_text(encoding="utf-8")
            for forbidden in (
                "import socket", "import serial", "import esptool", "import requests",
                "import paho", "subprocess.Popen", "write_flash", "erase_flash",
                "GH2D9R_PREPARE_V1 ", "GH2D9R_VERIFY_V1 ",
            ):
                self.assertNotIn(forbidden, text)

    def test_scope_record_keeps_all_execution_false(self) -> None:
        value = json.loads(
            (ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-repaired-u1-host-preauth-scope-20260728-v1.json").read_text()
        )
        self.assertEqual(value["status"], "ACCEPTED_SOURCE_AND_HOST_READONLY_DESIGN_ONLY")
        self.assertEqual(value["layering"]["base_head_sha"], probe.UPSTREAM_SOURCE_SHA)
        self.assertEqual(value["retired_execution"]["terminal_status"], "CONSUMED_FAILED")
        self.assertEqual(value["retired_execution"]["terminal_state"], "LOCKED_RECOVERY_COMPLETED")
        for key in (
            "authorization_created", "authorization_claimed", "authorization_consumed",
            "secret_generation", "private_material_created", "board_operation",
            "usb_enumeration", "serial_operation", "flash_operation",
            "physical_nvs_operation", "network_operation", "broker_started",
            "prepare_executed", "verify_executed", "private_values_included",
            "private_paths_included", "secret_values_included",
        ):
            self.assertIs(value[key], False, key)


if __name__ == "__main__":
    unittest.main()
