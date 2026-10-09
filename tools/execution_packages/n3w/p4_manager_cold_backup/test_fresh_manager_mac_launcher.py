from __future__ import annotations

import io
import subprocess
import tarfile
import unittest
from unittest.mock import patch

import fresh_manager_mac_launcher as launcher


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.stream = io.BytesIO(body)

    def read(self, size=-1):
        return self.stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stream.close()


class LauncherTests(unittest.TestCase):
    def test_remote_program_is_syntactically_valid(self):
        source = launcher.REMOTE_CODE.replace("__EXPECTED__", repr(launcher.EXPECTED))
        compile(source, "remote_t1_stager", "exec")
        self.assertIn("STAGE_ALREADY_EXISTS_NO_RETRY", source)
        self.assertIn("R5_PRIVATE_AUTHORITY_NOT_UNIQUE", source)
        self.assertIn("PREBOOT_BASELINE=0_0_0_AND_EMPTY_RELAY_KEYS", source)
        self.assertIn("--permit-live-manager-replacement", source)

    def test_git_blob_framing_and_exact_tar_members(self):
        blob = b"synthetic-source"
        expected = {"first.py": launcher.git_sha(blob)}
        with patch.object(launcher, "EXPECTED", expected):
            archive = launcher.pack_files({"first.py": blob})
        with tarfile.open(fileobj=io.BytesIO(archive)) as files:
            members = files.getmembers()
            self.assertEqual([x.name for x in members], ["first.py"])
            self.assertEqual(members[0].mode, 0o600)
            self.assertEqual(files.extractfile(members[0]).read(), blob)

    def test_mac_download_verifies_each_exact_git_blob(self):
        expected_data = b"synthetic-mac-source"
        with patch.object(launcher, "EXPECTED", {"one.py": launcher.git_sha(expected_data)}):
            with patch.object(launcher.urllib.request, "urlopen", return_value=FakeResponse(expected_data)):
                fetched = launcher.fetch_scripts()
                self.assertEqual(fetched, {"one.py": expected_data})

    def test_bad_download_is_refused_before_ssh(self):
        with patch.object(launcher, "EXPECTED", {"one.py": "0" * 40}):
            with patch.object(launcher.urllib.request, "urlopen", return_value=FakeResponse(b"wrong")):
                with self.assertRaisesRegex(RuntimeError, "SOURCE_BLOB_MISMATCH"):
                    launcher.fetch_scripts()

    def test_extra_unbound_file_is_rejected(self):
        with patch.object(launcher, "EXPECTED", {"one.py": launcher.git_sha(b"ok")}):
            with self.assertRaisesRegex(RuntimeError, "SOURCE_SET_MISMATCH"):
                launcher.pack_files({"one.py": b"ok", "other.py": b"untrusted"})

    def test_ssh_target_rejects_shell_metacharacters(self):
        for target in ("-oProxyCommand=bad", "user@host;id", "user@host && id", "user@host\nid", "user@"):
            with self.subTest(target=target):
                with self.assertRaisesRegex(RuntimeError, "SSH_TARGET_INVALID"):
                    launcher.validate_target(target)
        self.assertEqual(launcher.validate_target("user@t1.local"), "user@t1.local")

    def test_transport_only_returns_verified_pass(self):
        mock = subprocess.CompletedProcess(args=[], returncode=0,
                                           stdout=b"T1_FRESH_MANAGER=PASS\n", stderr=b"")
        with patch.object(launcher.subprocess, "run", return_value=mock) as execute:
            self.assertEqual(launcher.execute("user@t1.local", b"archive"), "T1_FRESH_MANAGER=PASS")
            argv = execute.call_args.args[0]
            self.assertEqual(argv[0], "ssh")
            self.assertEqual(argv[-2], "user@t1.local")
            self.assertIn("sudo -n python3 -c", argv[-1])
            self.assertEqual(execute.call_args.kwargs["input"], b"archive")

    def test_unknown_ssh_failure_never_claims_pass(self):
        result = subprocess.CompletedProcess(args=[], returncode=255, stdout=b"",
                                             stderr=b"private-debug-not-to-print")
        with patch.object(launcher.subprocess, "run", return_value=result):
            self.assertEqual(launcher.execute("t1", b"archive"),
                             "T1_FRESH_MANAGER=STOP:SSH_OR_SUDO_FAILED_NO_RETRY")

    def test_remote_stop_keeps_safe_reason(self):
        result = subprocess.CompletedProcess(args=[], returncode=1,
                                             stdout=b"T1_FRESH_MANAGER=STOP:R5_PRIVATE_AUTHORITY_NOT_UNIQUE\n",
                                             stderr=b"")
        with patch.object(launcher.subprocess, "run", return_value=result):
            self.assertEqual(launcher.execute("t1", b"archive"),
                             "T1_FRESH_MANAGER=STOP:R5_PRIVATE_AUTHORITY_NOT_UNIQUE")


if __name__ == "__main__":
    unittest.main()
