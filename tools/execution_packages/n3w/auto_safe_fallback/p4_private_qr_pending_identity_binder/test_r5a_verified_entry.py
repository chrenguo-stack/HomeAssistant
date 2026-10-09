import base64
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import field_preboot_readonly as field
import r5a_verified_entry as entry


ROOT = Path(__file__).resolve().parent
TARGET = "root@192.0.2.10"
NAMES = (entry.ENTRYPOINT_NAME, *entry.DEPENDENCY_BLOBS)


def private_document():
    return {
        "schema": field.FROZEN_SNAPSHOT_SCHEMA,
        "hardware_id_sha256": [f"{i:064x}" for i in range(1, 6)],
        "hardware_id_count": 5,
        "read_only": True,
        "manager_mutation": False,
        "manager_replay_mutation": False,
    }


def known_host():
    key = b"synthetic authorized host key material, not a real host key"
    record = "192.0.2.10 ssh-ed25519 " + base64.b64encode(key).decode() + "\n"
    fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(key).digest()).decode().rstrip("=")
    return record.encode(), fingerprint


class ExternalAuthorityTests(unittest.TestCase):
    def cloned_package(self, target):
        for name in NAMES:
            shutil.copyfile(ROOT / name, target / name)

    def test_launcher_loads_real_frozen_field_before_import(self):
        module = entry.load_verified_field_module(ROOT)
        self.assertIsNot(module, field)
        self.assertEqual(module.SOURCE_BLOBS, entry.DEPENDENCY_BLOBS)
        self.assertIs(module.FIELD_H2_LIVE_EXECUTION_ENABLED, False)
        self.assertEqual(module._git_blob((ROOT / entry.ENTRYPOINT_NAME).read_bytes()), entry.FIELD_MODULE_BLOB)

    def test_launcher_is_not_self_referential(self):
        self.assertNotIn("APPROVED_R5A_SOURCE_GIT_BLOB", (ROOT / entry.ENTRYPOINT_NAME).read_text())
        self.assertNotIn("FIELD_MODULE_BLOB", (ROOT / entry.ENTRYPOINT_NAME).read_text())
        self.assertNotIn("APPROVED_R5A_SOURCE_GIT_BLOB", (ROOT / "field_preboot_readonly.py").read_text())

    def test_launcher_declares_external_trust_requirement(self):
        self.assertTrue(entry.PINNED_REVIEW_BASE)
        with self.assertRaisesRegex(ValueError, "R5A_ENTRY_ROOT_INVALID"):
            entry.load_verified_field_module("bad-path")

    def test_mutated_field_code_never_executes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.cloned_package(root)
            poison = root / entry.ENTRYPOINT_NAME
            poison.write_text("raise RuntimeError('MALICIOUS_CODE_EXECUTED')\n")
            with self.assertRaisesRegex(ValueError, "R5A_ENTRY_SOURCE_BLOB_DRIFT"):
                entry.load_verified_field_module(root)

    def test_dependency_blob_drift_rejected(self):
        for name in entry.DEPENDENCY_BLOBS:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                self.cloned_package(root)
                with (root / name).open("ab") as fp:
                    fp.write(b"\n")
                with self.assertRaisesRegex(ValueError, "R5A_ENTRY_SOURCE_BLOB_DRIFT"):
                    entry.load_verified_field_module(root)

    def test_symlinked_field_and_dependency_rejected(self):
        for name in (entry.ENTRYPOINT_NAME, "validator.py"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                self.cloned_package(root)
                target = root / name
                saved = root / (name + ".old")
                target.rename(saved)
                target.symlink_to(saved)
                with self.assertRaisesRegex(ValueError, "R5A_ENTRY_PATH_NOT_TRUSTED"):
                    entry.load_verified_field_module(root)

    def test_missing_dependency_fail_closed_before_load(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.cloned_package(root)
            (root / "validator.py").unlink()
            with self.assertRaisesRegex(ValueError, "R5A_ENTRY_SOURCE_UNAVAILABLE"):
                entry.load_verified_field_module(root)

    def test_field_still_blocks_h2_without_separate_authorization(self):
        module = entry.load_verified_field_module(ROOT)
        with patch.object(subprocess, "run") as runner:
            with self.assertRaisesRegex(ValueError, "H2_LIVE_EXECUTION_DISABLED"):
                module.preboot_host_once(TARGET, Path("/dev/null"))
            runner.assert_not_called()

    def test_full_mac_h1_source_positive_with_synthetic_private_authority(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            private = root / "private.json"
            private.write_text(json.dumps(private_document()))
            private.chmod(0o600)
            host_file = root / "known_hosts"
            host_raw, fingerprint = known_host()
            host_file.write_bytes(host_raw)
            host_file.chmod(0o600)
            load_real = entry.load_verified_field_module

            def load_with_synthetic_private_facts(path):
                module = load_real(path)
                module.PRIVATE_BASELINE = private
                module.FROZEN_SNAPSHOT_SHA256 = hashlib.sha256(private.read_bytes()).hexdigest()
                module.APPROVED_KNOWN_HOSTS_SHA256 = hashlib.sha256(host_raw).hexdigest()
                module.APPROVED_T1_HOST_KEY_FINGERPRINT = fingerprint
                module._trusted_target = lambda target, probe: "192.0.2.10"
                return module

            def simulated_local_key_lookup(args, **kwargs):
                self.assertEqual(args[0], "ssh-keygen")
                self.assertEqual(args[-2], "-f")
                self.assertTrue(args[-1].startswith("/dev/fd/"))
                self.assertEqual(len(kwargs["pass_fds"]), 1)
                return SimpleNamespace(returncode=0, stdout=host_raw, stderr=b"")

            with (
                patch.object(entry, "load_verified_field_module", side_effect=load_with_synthetic_private_facts),
                patch.object(subprocess, "run", side_effect=simulated_local_key_lookup) as runner,
            ):
                result = entry.verify_mac_h1_only(ROOT, TARGET, host_file)
            self.assertEqual(result["source_pin"], "PASS")
            self.assertEqual(result["private_snapshot"], "PASS")
            self.assertEqual(result["host_key"], "PASS")
            self.assertEqual(result["preboot_remote_program"], "COMPILED_NOT_EXECUTED")
            self.assertEqual(result["live_ssh"], False)
            self.assertEqual(result["h2_authorized"], False)
            self.assertEqual(result["stop"], True)
            runner.assert_called_once()
            self.assertNotIn("setup_secret", str(result).lower())
            self.assertNotIn("preboot_hashes", result)

    def test_private_snapshot_drift_fails_full_chain_before_key_lookup(self):
        with tempfile.TemporaryDirectory() as td:
            private = Path(td) / "private.json"
            private.write_text("{}")
            private.chmod(0o600)
            m = entry.load_verified_field_module(ROOT)
            m.PRIVATE_BASELINE = private
            with patch.object(entry, "load_verified_field_module", return_value=m):
                with patch.object(subprocess, "run") as runner:
                    with self.assertRaisesRegex(ValueError, "PRIVATE_SNAPSHOT_DRIFT"):
                        entry.verify_mac_h1_only(ROOT, TARGET, Path(td) / "known_hosts")
                    runner.assert_not_called()

    def test_missing_host_key_authority_fails_before_ssh(self):
        m = entry.load_verified_field_module(ROOT)
        with patch.object(m, "_private_snapshot", return_value=frozenset(f"{i:064x}" for i in range(1, 6))):
            with patch.object(m, "_trusted_target", return_value="192.0.2.10"):
                with patch.object(entry, "load_verified_field_module", return_value=m):
                    with patch.object(subprocess, "run") as runner:
                        with self.assertRaisesRegex(ValueError, "HOST_KEY_AUTHORITY_NOT_FROZEN"):
                            entry.verify_mac_h1_only(ROOT, TARGET, Path("/dev/null"))
                        runner.assert_not_called()

    def test_known_hosts_swap_does_not_change_pinned_fd_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "known_hosts"
            initial, fingerprint = known_host()
            path.write_bytes(initial)
            path.chmod(0o600)
            with (
                patch.object(field, "APPROVED_KNOWN_HOSTS_SHA256", hashlib.sha256(initial).hexdigest()),
                patch.object(field, "APPROVED_T1_HOST_KEY_FINGERPRINT", fingerprint),
                patch.object(subprocess, "run", return_value=SimpleNamespace(
                    returncode=0, stdout=initial, stderr=b"",
                )) as runner,
            ):
                with field._verified_known_hosts("192.0.2.10", path) as (fd_path, fd):
                    self.assertIn(fd_path, runner.call_args.args[0])
                    self.assertEqual(runner.call_args.kwargs["pass_fds"], (fd,))
                    moved = Path(td) / "old"
                    path.rename(moved)
                    path.write_text("192.0.2.10 ssh-ed25519 WRONG\n")
                    path.chmod(0o600)
                    os.lseek(fd, 0, os.SEEK_SET)
                    self.assertEqual(os.read(fd, len(initial)), initial)
                with self.assertRaisesRegex(ValueError, "SOURCE_OR_AUTHORITY_DRIFT"):
                    field._host_key_check("192.0.2.10", path)

    def test_host_key_snapshot_closes_on_check_failure(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "known_hosts"
            initial, fingerprint = known_host()
            path.write_bytes(initial)
            path.chmod(0o600)
            with (
                patch.object(field, "APPROVED_KNOWN_HOSTS_SHA256", hashlib.sha256(initial).hexdigest()),
                patch.object(field, "APPROVED_T1_HOST_KEY_FINGERPRINT", fingerprint),
                patch.object(subprocess, "run", return_value=SimpleNamespace(
                    returncode=255, stdout=b"", stderr=b"local lookup failed",
                )) as runner,
            ):
                with self.assertRaisesRegex(ValueError, "HOST_KEY_LOOKUP_FAILED"):
                    field._host_key_check("192.0.2.10", path)
                runner.assert_called_once()

    def test_ssh_invocation_cannot_use_original_known_hosts_path(self):
        import contextlib

        module = entry.load_verified_field_module(ROOT)
        baseline = frozenset(f"{i:064x}" for i in range(1, 6))
        proof = {
            "schema": module.SCHEMA,
            "preboot_count": 5,
            "preboot_hashes": sorted(baseline),
            "new_count": 0,
            "pending_count": 0,
            "container_continuity_pass": True,
            "manager_socket_pass": True,
            "tls_live_reprobe_pass": True,
            "read_at": datetime.now(UTC).isoformat(),
        }

        @contextlib.contextmanager
        def trusted_fd(*_):
            yield "/dev/fd/123", 123

        with (
            patch.object(module, "FIELD_H2_LIVE_EXECUTION_ENABLED", True),
            patch.object(module, "mac_static_preflight", return_value=("synthetic-remote", baseline, "192.0.2.10")),
            patch.object(module, "_verified_known_hosts", trusted_fd),
            patch.object(subprocess, "run", return_value=SimpleNamespace(
                returncode=0, stdout=json.dumps(proof).encode(), stderr=b"",
            )) as runner,
        ):
            module.preboot_host_once(TARGET, Path("/untrusted/mutable/known_hosts"))
            args = runner.call_args.args[0]
            self.assertIn("UserKnownHostsFile=/dev/fd/123", args)
            self.assertNotIn("UserKnownHostsFile=/untrusted/mutable/known_hosts", args)
            self.assertEqual(runner.call_args.kwargs["pass_fds"], (123,))
            self.assertEqual(runner.call_count, 1)

    def test_missing_field_path_has_no_import_side_effect(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "R5A_ENTRY_SOURCE_UNAVAILABLE"):
                entry.load_verified_field_module(Path(td))

    def test_live_h2_not_exposed_by_launcher(self):
        self.assertFalse(hasattr(entry, "preboot_host_once"))
        self.assertFalse(hasattr(entry, "import_setup_secret"))
        self.assertFalse(hasattr(entry, "import_payload"))
        self.assertEqual(entry.ENTRYPOINT_NAME, "field_preboot_readonly.py")


if __name__ == "__main__":
    unittest.main(verbosity=2)
