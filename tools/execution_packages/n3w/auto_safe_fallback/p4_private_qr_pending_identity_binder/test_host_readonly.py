import hashlib
import json
import pathlib
import subprocess
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import host_readonly as h
import remote_projection as rp

ROOT = pathlib.Path(__file__).parent
BASE = frozenset(f"{i:064x}" for i in range(1, 6))
TARGET = "root@192.168.50.23"


def valid_response():
    now = datetime.now(UTC)
    return {
        "schema": "n3w.p4.pending-identity-projection/1",
        "hardware_sha256": "a" * 64,
        "pairing_sha256": "b" * 64,
        "expires_at": (now + timedelta(seconds=100)).isoformat(),
        "preboot_count": 5,
        "preboot_hashes": sorted(BASE),
        "new_count": 1,
        "read_at": (now - timedelta(seconds=1)).isoformat(),
        "container_continuity_pass": True,
        "manager_socket_pass": True,
        "tls_live_reprobe_pass": True,
    }


class HostTests(unittest.TestCase):
    def script(self):
        with patch.object(h, "private_preboot_baseline", return_value=BASE):
            return h.build_remote_program(
                (ROOT / "bridge_handoff.py").read_text(),
                (ROOT / "remote_projection.py").read_text(),
            )

    def invoke(self, response=None, *, target=TARGET, result_code=0, stderr=b""):
        if response is None:
            response = valid_response()
        with (
            patch.object(h, "private_preboot_baseline", return_value=BASE),
            patch.object(
                h, "_trusted_target_digest",
                return_value=hashlib.sha256(TARGET.split("@")[1].encode()).hexdigest(),
            ),
            patch.object(h.subprocess, "run") as runner,
        ):
            runner.return_value = SimpleNamespace(
                returncode=result_code,
                stdout=json.dumps(response).encode(),
                stderr=stderr,
            )
            try:
                result = h.remote_snapshot_once(target)
            except ValueError:
                self.assertLessEqual(runner.call_count, 1)
                raise
            self.assertEqual(runner.call_count, 1)
            return result, runner

    def test_combined_script_syntax(self):
        import ast
        script = self.script()
        ast.parse(script)
        self.assertIn("BASELINE_HASHES", script)
        self.assertNotIn("GHN3W2:ghw-c6-", script)

    def test_wrong_baseline(self):
        with self.assertRaises(ValueError):
            h.private_preboot_baseline(ROOT / "not-the-frozen-private-snapshot.json")

    def test_missing_readonly_functions_rejected(self):
        with patch.object(h, "private_preboot_baseline", return_value=BASE):
            with patch.object(h, "EXPECTED_BRIDGE_GIT_BLOB", h._git_blob("print(1)")):
                with self.assertRaisesRegex(ValueError, "READONLY_CORE_MISSING"):
                    h.build_remote_program(
                        "print(1)", (ROOT / "remote_projection.py").read_text()
                    )

    def test_remote_code_excludes_importer_even_if_bridge_contains_it(self):
        script = self.script()
        for text in (
            "OneShotImporter", "ssh_manager_stdin_transport",
            "import-payload", "capture_private_qr", "setup_secret",
        ):
            self.assertNotIn(text, script)

    def test_mutating_sql_in_readonly_extract_stops(self):
        bridge = (ROOT / "bridge_handoff.py").read_text()
        changed = bridge.replace("PRAGMA query_only=ON", "DELETE FROM registrations")
        with patch.object(h, "private_preboot_baseline", return_value=BASE):
            with patch.object(h, "EXPECTED_BRIDGE_GIT_BLOB", h._git_blob(changed)):
                with self.assertRaisesRegex(ValueError, "REMOTE_SQL_MUTATION"):
                    h.build_remote_program(
                        changed, (ROOT / "remote_projection.py").read_text()
                    )

    def test_source_sha_drift_rejected_before_private_read(self):
        changed = (ROOT / "bridge_handoff.py").read_text() + "\n"
        with patch.object(h, "private_preboot_baseline") as get_baseline:
            with self.assertRaisesRegex(ValueError, "READONLY_SOURCE_BLOB_DRIFT"):
                h.build_remote_program(
                    changed, (ROOT / "remote_projection.py").read_text()
                )
            get_baseline.assert_not_called()

    def test_r4_bound_dispatch_positive(self):
        response = valid_response()
        result, runner = self.invoke(response)
        self.assertEqual(result, response)
        args, options = runner.call_args
        self.assertEqual(args[0][-4:], ["--", TARGET, "python3", "-"])
        self.assertIn("StrictHostKeyChecking=yes", args[0])
        self.assertIn("BatchMode=yes", args[0])
        self.assertEqual(args[0][args[0].index("-F") + 1], "/dev/null")
        self.assertEqual(options["input"], self.script().encode())
        self.assertEqual(options["timeout"], 15)
        self.assertNotIn("GHN3W2:", str(runner.call_args))
        self.assertNotIn("shell", options)

    def test_r4_arbitrary_program_argument_refused(self):
        with patch.object(h.subprocess, "run") as runner:
            with self.assertRaises(TypeError):
                h.remote_snapshot_once(TARGET, program="print(1)")
            runner.assert_not_called()

    def test_r4_old_expected_target_hash_argument_refused(self):
        with patch.object(h.subprocess, "run") as runner:
            with self.assertRaises(TypeError):
                h.remote_snapshot_once(
                    TARGET, expected_target_sha=hashlib.sha256(TARGET.encode()).hexdigest()
                )
            runner.assert_not_called()

    def test_r4_source_modified_no_ssh(self):
        with (
            patch.object(h, "EXPECTED_BRIDGE_GIT_BLOB", "0" * 40),
            patch.object(h, "private_preboot_baseline") as baseline,
            patch.object(h.subprocess, "run") as runner,
        ):
            with self.assertRaisesRegex(ValueError, "READONLY_SOURCE_BLOB_DRIFT"):
                h.remote_snapshot_once(TARGET)
            baseline.assert_not_called()
            runner.assert_not_called()

    def test_r4_snapshot_failure_no_ssh(self):
        with (
            patch.object(h, "private_preboot_baseline", side_effect=ValueError("PRIVATE_SNAPSHOT_DRIFT")),
            patch.object(h.subprocess, "run") as runner,
        ):
            with self.assertRaisesRegex(ValueError, "PRIVATE_SNAPSHOT_DRIFT"):
                h.remote_snapshot_once(TARGET)
            runner.assert_not_called()

    def test_r4_alternate_snapshot_path_no_ssh(self):
        with patch.object(h.subprocess, "run") as runner:
            with self.assertRaisesRegex(ValueError, "PRIVATE_SNAPSHOT_PATH_DRIFT"):
                h.remote_snapshot_once(TARGET, snapshot_path=ROOT / "fake-private.json")
            runner.assert_not_called()

    def test_r4_wrong_target_no_ssh(self):
        with (
            patch.object(h, "private_preboot_baseline", return_value=BASE),
            patch.object(h, "_trusted_target_digest", return_value=hashlib.sha256(b"192.168.50.23").hexdigest()),
            patch.object(h.subprocess, "run") as runner,
        ):
            with self.assertRaisesRegex(ValueError, "TARGET_BINDING_INVALID"):
                h.remote_snapshot_once("root@192.168.50.24")
            runner.assert_not_called()

    def test_r4_public_target_no_ssh(self):
        with (
            patch.object(h, "private_preboot_baseline", return_value=BASE),
            patch.object(h.subprocess, "run") as runner,
        ):
            with self.assertRaisesRegex(ValueError, "TARGET_BINDING_INVALID"):
                h.remote_snapshot_once("root@8.8.8.8")
            runner.assert_not_called()

    def test_r4_probe_target_pin_from_pinned_file(self):
        value = h._trusted_target_digest((ROOT / "remote_projection.py").read_text())
        self.assertEqual(len(value), 64)
        with self.assertRaisesRegex(ValueError, "TARGET_AUTHORITY_MISSING"):
            h._trusted_target_digest('EXPECTED_T1_IP_SHA = "wrong"')

    def test_r4_forged_all_true_wrong_old_hashes_stops(self):
        bad = valid_response()
        bad["preboot_hashes"] = sorted(f"{i:064x}" for i in range(6, 11))
        with self.assertRaisesRegex(ValueError, "REMOTE_RESPONSE_INVALID"):
            self.invoke(bad)

    def test_r4_prior_hardware_cannot_be_new(self):
        bad = valid_response()
        bad["hardware_sha256"] = sorted(BASE)[0]
        with self.assertRaisesRegex(ValueError, "REMOTE_RESPONSE_INVALID"):
            self.invoke(bad)

    def test_r4_wrong_types_and_fields_stop(self):
        for change in (
            {"new_count": True},
            {"preboot_count": "5"},
            {"container_continuity_pass": 1},
            {"preboot_hashes": list(reversed(sorted(BASE)))},
            {"pairing_sha256": "bad"},
            {"unknown": "extra"},
        ):
            bad = valid_response()
            bad.update(change)
            with self.subTest(change=change):
                with self.assertRaisesRegex(ValueError, "REMOTE_RESPONSE_INVALID"):
                    self.invoke(bad)

    def test_r4_expired_and_near_expiry_stop(self):
        for seconds in (-1, 5, 59):
            bad = valid_response()
            bad["expires_at"] = (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat()
            with self.subTest(seconds=seconds):
                with self.assertRaisesRegex(ValueError, "REMOTE_PENDING_STALE_OR_SHORT"):
                    self.invoke(bad)

    def test_r4_stale_and_future_read_at_stop(self):
        for offset in (-20, 20):
            bad = valid_response()
            bad["read_at"] = (datetime.now(UTC) + timedelta(seconds=offset)).isoformat()
            with self.subTest(offset=offset):
                with self.assertRaisesRegex(ValueError, "REMOTE_PENDING_STALE_OR_SHORT"):
                    self.invoke(bad)

    def test_r4_invalid_response_exit_and_oversized_stderr_stop(self):
        with self.assertRaisesRegex(ValueError, "REMOTE_READONLY_STOP"):
            self.invoke(result_code=2)
        with self.assertRaisesRegex(ValueError, "REMOTE_READONLY_STOP"):
            self.invoke(stderr=b"x" * 8193)

    def test_r4_ssh_timeout_one_attempt_only(self):
        with (
            patch.object(h, "private_preboot_baseline", return_value=BASE),
            patch.object(h, "_trusted_target_digest", return_value=hashlib.sha256(b"192.168.50.23").hexdigest()),
            patch.object(h.subprocess, "run", side_effect=subprocess.TimeoutExpired("ssh", 15)) as runner,
        ):
            with self.assertRaisesRegex(ValueError, "REMOTE_READONLY_STOP"):
                h.remote_snapshot_once(TARGET)
            runner.assert_called_once()

    def test_r4_missing_ssh_host_key_is_a_stop(self):
        with (
            patch.object(h, "private_preboot_baseline", return_value=BASE),
            patch.object(h, "_trusted_target_digest", return_value=hashlib.sha256(b"192.168.50.23").hexdigest()),
            patch.object(h.subprocess, "run") as runner,
        ):
            runner.return_value = SimpleNamespace(
                returncode=255, stdout=b"", stderr=b"host key verification failed"
            )
            with self.assertRaisesRegex(ValueError, "REMOTE_READONLY_STOP"):
                h.remote_snapshot_once(TARGET)
            runner.assert_called_once()

    def test_tls_reprobe_missing_fails_closed(self):
        bad = valid_response()
        bad["tls_live_reprobe_pass"] = False
        with self.assertRaisesRegex(ValueError, "REMOTE_RESPONSE_INVALID"):
            self.invoke(bad)

    def test_container_continuity_false_fails(self):
        bad = valid_response()
        bad["container_continuity_pass"] = False
        with self.assertRaisesRegex(ValueError, "REMOTE_RESPONSE_INVALID"):
            self.invoke(bad)

    def test_t1_remote_entry_with_simulated_source(self):
        with (
            patch.object(rp, "_assert_runtime") as attest,
            patch.object(rp, "project_readonly", create=True) as project,
        ):
            attest.return_value = (
                pathlib.Path("/synth/reg.db"),
                pathlib.Path("/synth/cred.db"),
            )
            project.return_value = valid_response()
            result = rp.main_remote(sorted(BASE))
            self.assertTrue(result["tls_live_reprobe_pass"])
            self.assertNotIn("setup_secret", result)

    def test_bad_preboot_blocked_before_probe(self):
        with patch.object(rp, "_assert_runtime") as attest:
            with self.assertRaises(Exception):
                rp.main_remote(["a" * 64])
            attest.assert_not_called()

    def test_runtime_contract_has_broker_ca_and_leaf(self):
        txt = (ROOT / "remote_projection.py").read_text()
        self.assertIn("EXPECTED_TLS_CA", txt)
        self.assertIn("EXPECTED_TLS_LEAF", txt)
        self.assertIn("ssl.create_default_context", txt)
        self.assertIn("tls.getpeercert", txt)
        self.assertNotIn("shell=True", txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
