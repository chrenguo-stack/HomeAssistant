from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR_PATH = REPO_ROOT / "tools/dev/local_environment_doctor_20260722_v1.py"
HARDENING_PATH = REPO_ROOT / "tools/dev/apply_local_environment_hardening_20260722_v1.py"
HOOK_PATH = REPO_ROOT / "tools/dev/hooks/pre_commit_local_environment_guard_20260722_v1.py"
POLICY_PATH = REPO_ROOT / "tools/dev/local_environment_policy_20260722_v1.json"


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"unable to load {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


DOCTOR = load_module("local_environment_doctor_v1", DOCTOR_PATH)
HARDENING = load_module("local_environment_hardening_v1", HARDENING_PATH)
HOOK = load_module("local_environment_hook_v1", HOOK_PATH)


class LocalEnvironmentToolingTests(unittest.TestCase):
    def test_policy_schema_and_safe_defaults(self) -> None:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(policy["schema"], "gh.dev.local-environment-policy/1")
        boundaries = policy["execution_boundaries"]
        self.assertFalse(boundaries["network_checks_default"])
        self.assertFalse(boundaries["device_access_default"])
        self.assertFalse(boundaries["system_mutation_default"])
        self.assertFalse(boundaries["production_service_access_default"])

    def test_parse_version(self) -> None:
        self.assertEqual(DOCTOR.parse_version("Python 3.11.9"), (3, 11, 9))
        self.assertEqual(DOCTOR.parse_version("ruff 0.15.22"), (0, 15, 22))
        self.assertEqual(DOCTOR.parse_version("unknown"), ())

    def test_forbidden_tracked_paths_preserves_examples(self) -> None:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        tracked = [
            ".env.example",
            "certs/server.example.pem",
            "runtime/.env",
            "host/secrets.yaml",
            "host/.storage/core.config_entries",
            "evidence/result.json",
        ]
        result = DOCTOR.forbidden_tracked_paths(tracked, policy["security"])
        self.assertNotIn(".env.example", result)
        self.assertNotIn("certs/server.example.pem", result)
        self.assertIn("runtime/.env", result)
        self.assertIn("host/secrets.yaml", result)
        self.assertIn("host/.storage/core.config_entries", result)
        self.assertIn("evidence/result.json", result)

    def test_sensitive_local_paths_skip_explicit_examples(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".env.example").write_text("SAFE=example\n", encoding="utf-8")
            (root / "server.example.pem").write_text("example\n", encoding="utf-8")
            (root / ".env.local").write_text("SECRET=value\n", encoding="utf-8")
            (root / "device.key").write_text("private\n", encoding="utf-8")

            doctor_paths = {path.name for path in DOCTOR.sensitive_local_paths(root)}
            hardening_paths = {path.name for path in HARDENING.sensitive_local_paths(root)}
            self.assertEqual(doctor_paths, {".env.local", "device.key"})
            self.assertEqual(hardening_paths, {".env.local", "device.key"})

    def test_hook_path_guard(self) -> None:
        self.assertIsNotNone(HOOK.forbidden_path("host/secrets.yaml"))
        self.assertIsNotNone(HOOK.forbidden_path("host/.storage/core.config_entries"))
        self.assertIsNotNone(HOOK.forbidden_path("private/device.key"))
        self.assertIsNone(HOOK.forbidden_path("host/.env.example"))
        self.assertIsNone(HOOK.forbidden_path("certs/server.example.pem"))

    def test_hardening_dry_run_is_non_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "evidence"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(HARDENING_PATH),
                    "--repo",
                    str(root / "repo"),
                    "--venv",
                    str(root / "venv"),
                    "--evidence-dir",
                    str(evidence),
                    "--install-pre-commit-hook",
                    "--restrict-sensitive-files",
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertIn("MODE=DRY_RUN", completed.stdout)
            self.assertIn("RESULT=dry_run_complete", completed.stdout)
            self.assertFalse(evidence.exists())

    def test_hook_blocks_staged_private_key_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "config",
                    "user.email",
                    "test@example.invalid",
                ],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.name", "Test"],
                check=True,
            )
            target = repo / "notes.txt"
            marker = "-----BEGIN " + "PRIVATE KEY-----\nnot-a-real-key\n"
            target.write_text(marker, encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "notes.txt"], check=True)
            completed = subprocess.run(
                [sys.executable, str(HOOK_PATH)],
                cwd=repo,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.assertEqual(completed.returncode, 1, completed.stdout)
            self.assertIn("private-key marker", completed.stdout)

    def test_hook_accepts_safe_staged_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            target = repo / "README.md"
            target.write_text("safe text\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            completed = subprocess.run(
                [sys.executable, str(HOOK_PATH)],
                cwd=repo,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertIn("PASS staged.secret_guard", completed.stdout)


if __name__ == "__main__":
    unittest.main()
