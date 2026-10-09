import base64
from contextlib import contextmanager
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import field_preboot_readonly as f


ROOT = Path(__file__).resolve().parent
BASE = frozenset(f"{i:064x}" for i in range(1, 6))
TARGET = "root@192.0.2.10"


def response():
    return {
        "schema": f.SCHEMA,
        "preboot_count": 5,
        "preboot_hashes": sorted(BASE),
        "new_count": 0,
        "pending_count": 0,
        "container_continuity_pass": True,
        "manager_socket_pass": True,
        "tls_live_reprobe_pass": True,
        "read_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
    }


class FieldPrebootTests(unittest.TestCase):
    def test_frozen_source_manifest_matches_r4(self):
        sources = f._source_bytes()
        self.assertEqual(set(sources), set(f.SOURCE_BLOBS))
        for name, raw in sources.items():
            self.assertEqual(f._git_blob(raw), f.SOURCE_BLOBS[name])

    def test_generated_remote_is_readonly_and_compiles(self):
        import ast
        script = f.build_preboot_program(f._source_bytes(), BASE)
        ast.parse(script)
        self.assertIn("PREBOOT_PENDING_PRESENT", script)
        self.assertIn("BASELINE_HASHES", script)
        self.assertNotIn("import-payload", script)
        self.assertNotIn("OneShotImporter", script)
        self.assertNotIn("main_remote(", script)
        self.assertNotIn("GHN3W2", script)

    def test_generated_source_bytes_are_pinned(self):
        src = f._source_bytes()
        src["bridge_handoff.py"] += b"\n"
        with self.assertRaisesRegex(ValueError, "READONLY_SOURCE_DRIFT"):
            f.build_preboot_program(src, BASE)

    def test_wrong_preboot_hashes_rejected(self):
        with self.assertRaisesRegex(ValueError, "PREBOOT_BASELINE_INVALID"):
            f.build_preboot_program(f._source_bytes(), frozenset(["a" * 64]))

    def test_private_snapshot_owner_only_synthetic(self):
        with tempfile.TemporaryDirectory() as home:
            path = Path(home) / "snapshot.json"
            doc = {
                "schema": f.FROZEN_SNAPSHOT_SCHEMA,
                "hardware_id_sha256": sorted(BASE),
                "hardware_id_count": 5,
                "read_only": True,
                "manager_mutation": False,
                "manager_replay_mutation": False,
            }
            raw = json.dumps(doc).encode()
            path.write_bytes(raw)
            path.chmod(0o600)
            with patch.object(f, "PRIVATE_BASELINE", path), patch.object(
                f, "FROZEN_SNAPSHOT_SHA256", hashlib.sha256(raw).hexdigest()
            ):
                self.assertEqual(f._private_snapshot(), BASE)
                path.chmod(0o644)
                with self.assertRaisesRegex(ValueError, "PRIVATE_SNAPSHOT_AUTHORITY_INVALID"):
                    f._private_snapshot()
                path.chmod(0o600)
                path.write_bytes(raw + b" ")
                with self.assertRaisesRegex(ValueError, "PRIVATE_SNAPSHOT_DRIFT"):
                    f._private_snapshot()

    def test_snapshot_symbolic_link_rejected(self):
        with tempfile.TemporaryDirectory() as home:
            path = Path(home) / "snap.json"
            path.write_text("{}")
            path.chmod(0o600)
            link = Path(home) / "link.json"
            link.symlink_to(path)
            with patch.object(f, "PRIVATE_BASELINE", link):
                with self.assertRaisesRegex(ValueError, "PRIVATE_SNAPSHOT_SYMLINK"):
                    f._private_snapshot()

    def test_wrong_phase_posthello_response_stops(self):
        bad = response()
        bad.update(new_count=1, pending_count=1)
        with self.assertRaisesRegex(ValueError, "PREBOOT_RESPONSE_INVALID"):
            f._validate_preboot_response(bad, BASE)

    def test_forged_old_identities_stops(self):
        bad = response()
        bad["preboot_hashes"] = ["a" * 64] * 5
        with self.assertRaisesRegex(ValueError, "PREBOOT_RESPONSE_INVALID"):
            f._validate_preboot_response(bad, BASE)

    def test_not_exactly_five_stops(self):
        for value in (4, 6, True, "5"):
            bad = response()
            bad["preboot_count"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "PREBOOT_RESPONSE_INVALID"):
                f._validate_preboot_response(bad, BASE)

    def test_stale_and_future_clock_stops(self):
        for seconds in (-30, 30):
            bad = response()
            bad["read_at"] = (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat()
            with self.subTest(seconds=seconds), self.assertRaisesRegex(ValueError, "PREBOOT_READBACK_STALE"):
                f._validate_preboot_response(bad, BASE)

    def test_pass_report_contains_no_private_hashes(self):
        out = f._validate_preboot_response(response(), BASE)
        self.assertEqual(out["status"], "PASS_READONLY_NO_PAIRING")
        self.assertEqual(out["new_count"], 0)
        self.assertNotIn("preboot_hashes", out)
        self.assertNotIn("setup_secret", out)

    def test_target_must_match_pinned_probe(self):
        ip = TARGET.split("@")[1]
        probe = ('EXPECTED_T1_IP_SHA = "' + hashlib.sha256(ip.encode()).hexdigest() + '"').encode()
        self.assertEqual(f._trusted_target(TARGET, probe), ip)
        for invalid in ("root@192.0.2.11", "alice@192.0.2.10", "root@127.0.0.1"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                f._trusted_target(invalid, probe)

    def test_default_h2_disabled_before_any_ssh(self):
        with patch.object(f.subprocess, "run") as runner:
            with self.assertRaisesRegex(ValueError, "H2_LIVE_EXECUTION_DISABLED"):
                f.preboot_host_once(TARGET, Path("/dev/null"))
            runner.assert_not_called()

    def test_h1_checks_source_before_private_authority_and_ssh(self):
        with patch.object(f, "_source_bytes", side_effect=ValueError("SOURCE_OR_AUTHORITY_DRIFT")):
            with patch.object(f, "_private_snapshot") as snap:
                with patch.object(f.subprocess, "run") as runner:
                    with self.assertRaisesRegex(ValueError, "SOURCE_OR_AUTHORITY_DRIFT"):
                        f.mac_static_preflight(TARGET, Path("/dev/null"))
                    snap.assert_not_called()
                    runner.assert_not_called()

    def test_source_path_mismatch_stops(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "source.py"
            p.write_text("print('synthetic')")
            expected = f._git_blob(p.read_bytes())
            p.write_text("print('different')")
            with self.assertRaisesRegex(ValueError, "SOURCE_OR_AUTHORITY_DRIFT"):
                f._regular_pinned(p, expected, git=True)

    def test_host_key_requires_independent_pins(self):
        with patch.object(f.subprocess, "run") as runner:
            with self.assertRaisesRegex(ValueError, "HOST_KEY_AUTHORITY_NOT_FROZEN"):
                f._host_key_check("192.0.2.10", Path("/dev/null"))
            runner.assert_not_called()

    def test_host_key_good_fingerprint_and_wrong_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "known_hosts"
            key = b"synthetic ed25519 public key bytes"
            b64 = base64.b64encode(key).decode("ascii")
            path.write_text("192.0.2.10 ssh-ed25519 " + b64 + "\n")
            path.chmod(0o600)
            fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(key).digest()).decode().rstrip("=")
            with (
                patch.object(f, "APPROVED_KNOWN_HOSTS_SHA256", hashlib.sha256(path.read_bytes()).hexdigest()),
                patch.object(f, "APPROVED_T1_HOST_KEY_FINGERPRINT", fingerprint),
                patch.object(f.subprocess, "run") as runner,
            ):
                runner.return_value = SimpleNamespace(returncode=0, stdout=path.read_bytes(), stderr=b"")
                f._host_key_check("192.0.2.10", path)
                runner.assert_called_once()
                self.assertEqual(runner.call_args[0][0][0], "ssh-keygen")
                with patch.object(f, "APPROVED_T1_HOST_KEY_FINGERPRINT", "SHA256:wrong"):
                    with self.assertRaisesRegex(ValueError, "HOST_KEY_MISMATCH"):
                        f._host_key_check("192.0.2.10", path)

    def test_untrusted_known_hosts_permissions_stop_before_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "known_hosts"
            path.write_text("synthetic")
            path.chmod(0o666)
            with (
                patch.object(f, "APPROVED_KNOWN_HOSTS_SHA256", hashlib.sha256(path.read_bytes()).hexdigest()),
                patch.object(f, "APPROVED_T1_HOST_KEY_FINGERPRINT", "SHA256:test"),
                patch.object(f.subprocess, "run") as runner,
            ):
                with self.assertRaisesRegex(ValueError, "HOST_KEY_FILE_INVALID"):
                    f._host_key_check("192.0.2.10", path)
                runner.assert_not_called()

    def test_preboot_runner_does_not_accept_arbitrary_program(self):
        with patch.object(f.subprocess, "run") as runner:
            with self.assertRaises(TypeError):
                f.preboot_host_once(TARGET, Path("/dev/null"), program="print(1)")
            runner.assert_not_called()

    @staticmethod
    @contextmanager
    def synthetic_pinned_host_key(ip, path):
        yield "/dev/fd/99", 99

    def test_preboot_runner_uses_exact_generated_stdin_only(self):
        program = f.build_preboot_program(f._source_bytes(), BASE)
        with (
            patch.object(f, "FIELD_H2_LIVE_EXECUTION_ENABLED", True),
            patch.object(f, "mac_static_preflight", return_value=(program, BASE, "192.0.2.10")),
            patch.object(f, "_verified_known_hosts", self.synthetic_pinned_host_key),
            patch.object(f.subprocess, "run") as runner,
        ):
            runner.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(response()).encode(), stderr=b"")
            out = f.preboot_host_once(TARGET, Path("/dev/null"))
            self.assertEqual(out["status"], "PASS_READONLY_NO_PAIRING")
            argv = runner.call_args[0][0]
            self.assertEqual(argv[-4:], ["--", TARGET, "python3", "-"])
            self.assertIn("StrictHostKeyChecking=yes", argv)
            self.assertIn("UpdateHostKeys=no", argv)
            self.assertIn("UserKnownHostsFile=/dev/fd/99", argv)
            self.assertEqual(runner.call_args.kwargs["input"], program.encode())
            self.assertEqual(runner.call_args.kwargs["timeout"], 15)
            self.assertEqual(runner.call_args.kwargs["pass_fds"], (99,))

    def test_ssh_timeout_consumes_one_attempt(self):
        with (
            patch.object(f, "FIELD_H2_LIVE_EXECUTION_ENABLED", True),
            patch.object(f, "mac_static_preflight", return_value=("print(1)", BASE, "192.0.2.10")),
            patch.object(f, "_verified_known_hosts", self.synthetic_pinned_host_key),
            patch.object(f.subprocess, "run", side_effect=subprocess.TimeoutExpired("ssh", 15)) as runner,
        ):
            with self.assertRaisesRegex(ValueError, "PREBOOT_SSH_UNKNOWN_STOP"):
                f.preboot_host_once(TARGET, Path("/dev/null"))
            runner.assert_called_once()

    def test_remote_bad_json_and_bad_rc_stop(self):
        with (
            patch.object(f, "FIELD_H2_LIVE_EXECUTION_ENABLED", True),
            patch.object(f, "mac_static_preflight", return_value=("print(1)", BASE, "192.0.2.10")),
            patch.object(f, "_verified_known_hosts", self.synthetic_pinned_host_key),
            patch.object(f.subprocess, "run") as runner,
        ):
            runner.return_value = SimpleNamespace(returncode=0, stdout=b"{", stderr=b"")
            with self.assertRaisesRegex(ValueError, "PREBOOT_RESPONSE_INVALID"):
                f.preboot_host_once(TARGET, Path("/dev/null"))
            runner.return_value = SimpleNamespace(returncode=255, stdout=b"", stderr=b"host key verification failed")
            with self.assertRaisesRegex(ValueError, "PREBOOT_REMOTE_STOP"):
                f.preboot_host_once(TARGET, Path("/dev/null"))

    def test_generated_preboot_sqlite_has_exact_five_baseline(self):
        src = f.build_preboot_program(f._source_bytes(), BASE)
        namespace = {"__name__": "n3w_r5a_synthetic"}
        exec(compile(src, "r5a_fixed_readonly", "exec"), namespace)
        with tempfile.TemporaryDirectory() as tmp:
            reg = Path(tmp) / "registration.sqlite3"
            cred = Path(tmp) / "credential.sqlite3"
            with sqlite3.connect(reg) as db:
                for table in ("registrations", "pairing_sessions", "registration_events", "registration_node_history", "node_id_leases", "retirement_outbox"):
                    fields = sorted(namespace["REQUIRED_COLUMNS"][table])
                    db.execute("CREATE TABLE " + table + " (" + ", ".join(col + " TEXT" for col in fields) + ")")
                for i in range(5):
                    db.execute("INSERT INTO registrations (hardware_id) VALUES (?)", ("synthetic-node-" + str(i),))
            with sqlite3.connect(cred) as db:
                fields = sorted(namespace["REQUIRED_COLUMNS"]["credential_assignments"])
                db.execute("CREATE TABLE credential_assignments (" + ", ".join(col + " TEXT" for col in fields) + ")")
            expected = frozenset(hashlib.sha256(("synthetic-node-" + str(i)).encode()).hexdigest() for i in range(5))
            self.assertEqual(namespace["_five_identity_snapshot"](reg, cred, expected), expected)
            with sqlite3.connect(reg) as db:
                db.execute("INSERT INTO pairing_sessions (hardware_id, state) VALUES (?, ?)", ("synthetic-node-5", "pending"))
            with self.assertRaisesRegex(Exception, "PREBOOT_PENDING_PRESENT"):
                namespace["_five_identity_snapshot"](reg, cred, expected)
            with sqlite3.connect(reg) as db:
                db.execute("DELETE FROM pairing_sessions")
                db.execute("INSERT INTO registrations (hardware_id) VALUES (?)", ("synthetic-node-5",))
            with self.assertRaisesRegex(Exception, "PREBOOT_IDENTITY_CHANGED"):
                namespace["_five_identity_snapshot"](reg, cred, expected)
            missing = Path(tmp) / "missing.sqlite3"
            with sqlite3.connect(missing) as db:
                db.execute("CREATE TABLE registrations (hardware_id TEXT)")
            with self.assertRaisesRegex(Exception, "PREBOOT_SCHEMA_INVALID"):
                namespace["_five_identity_snapshot"](missing, cred, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
