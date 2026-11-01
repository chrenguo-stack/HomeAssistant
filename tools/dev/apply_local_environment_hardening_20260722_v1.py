#!/usr/bin/env python3
"""Apply bounded local-development hardening with explicit authorization.

Dry-run is the default. The tool never installs packages, changes global Git
configuration, starts services, contacts production systems, or accesses
physical devices. Every mutation is local, reversible, and printed before use.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


SCRIPT_SCHEMA = "gh.dev.local-environment-hardening/1"
POLICY_NAME = "local_environment_policy_20260722_v1.json"
DOCTOR_NAME = "local_environment_doctor_20260722_v1.py"
HOOK_TEMPLATE_NAME = "pre_commit_local_environment_guard_20260722_v1.py"
CONFIG_DIRECTORY = Path("~/.config/greenhouse-dev").expanduser()
CONFIG_PATH = CONFIG_DIRECTORY / "local-environment-v1.json"


@dataclass(frozen=True)
class PlannedAction:
    code: str
    description: str


def load_policy(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("policy root must be an object")
    return value


def resolve_default(value: str) -> Path:
    return Path(value).expanduser().resolve()


def is_explicit_safe_example(path: Path) -> bool:
    name = path.name.lower()
    return name == ".env.example" or name.endswith(".example.pem")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)


def atomic_write_private(path: Path, content: str) -> None:
    ensure_private_directory(path.parent)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, path)
    path.chmod(0o600)


def sensitive_local_paths(repo: Path) -> list[Path]:
    patterns = (
        ".env",
        ".env.*",
        "secrets.yaml",
        "credentials.json",
        "*.key",
        "*.pem",
        "*.p12",
        "*.pfx",
    )
    ignored_parts = {".git", ".esphome", "build", "dist", ".venv", "venv"}
    paths: set[Path] = set()
    for pattern in patterns:
        for path in repo.rglob(pattern):
            if not path.is_file() or any(part in ignored_parts for part in path.parts):
                continue
            if is_explicit_safe_example(path):
                continue
            paths.add(path)
    return sorted(paths)


def git_hooks_directory(repo: Path) -> Path:
    completed = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-path", "hooks"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "unable to resolve Git hooks directory")
    value = Path(completed.stdout.strip())
    if not value.is_absolute():
        value = repo / value
    return value.resolve()


def install_hook(repo: Path, template: Path) -> tuple[Path, Path | None]:
    hooks_dir = git_hooks_directory(repo)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    target = hooks_dir / "pre-commit"
    backup: Path | None = None
    template_hash = sha256_file(template)
    if target.exists():
        target_hash = sha256_file(target)
        if target_hash == template_hash:
            target.chmod(0o700)
            return target, None
        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = hooks_dir / f"pre-commit.backup.{timestamp}"
        shutil.copy2(target, backup)
        backup.chmod(0o700)
    shutil.copy2(template, target)
    target.chmod(0o700)
    return target, backup


def git_worktree_valid(repo: Path) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def run_doctor(
    python: Path,
    doctor: Path,
    policy: Path,
    repo: Path,
    venv: Path,
    evidence: Path,
    output: Path,
) -> int:
    completed = subprocess.run(
        [
            str(python),
            str(doctor),
            "--policy",
            str(policy),
            "--repo",
            str(repo),
            "--venv",
            str(venv),
            "--evidence-dir",
            str(evidence),
            "--json-output",
            str(output),
        ],
        check=False,
    )
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the printed local mutations. Without this flag the tool is dry-run only.",
    )
    parser.add_argument("--repo", type=Path, help="Repository path override.")
    parser.add_argument("--venv", type=Path, help="Virtual environment path override.")
    parser.add_argument("--evidence-dir", type=Path, help="External evidence directory override.")
    parser.add_argument(
        "--install-pre-commit-hook",
        action="store_true",
        help="Install the repository-local secret guard, backing up an existing hook first.",
    )
    parser.add_argument(
        "--restrict-sensitive-files",
        action="store_true",
        help="Set local sensitive files found in the repository to mode 0600.",
    )
    parser.add_argument(
        "--skip-post-audit",
        action="store_true",
        help="Do not run the read-only doctor after applying changes.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    script_dir = Path(__file__).resolve().parent
    policy_path = script_dir / POLICY_NAME
    doctor_path = script_dir / DOCTOR_NAME
    hook_template = script_dir / "hooks" / HOOK_TEMPLATE_NAME

    try:
        policy = load_policy(policy_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL policy.load: {exc}", file=sys.stderr)
        return 2

    defaults = policy["default_paths"]
    repo = (args.repo or resolve_default(defaults["repository"])).expanduser().resolve()
    venv = (args.venv or resolve_default(defaults["virtual_environment"])).expanduser().resolve()
    evidence = (args.evidence_dir or resolve_default(defaults["evidence_directory"])).expanduser().resolve()

    actions = [
        PlannedAction("evidence.ensure", f"Create or restrict {evidence} to mode 0700."),
        PlannedAction("config.ensure", f"Create or restrict {CONFIG_DIRECTORY} to mode 0700."),
        PlannedAction(
            "config.write",
            f"Write non-secret local path configuration to {CONFIG_PATH} with mode 0600.",
        ),
    ]
    if args.install_pre_commit_hook:
        actions.append(
            PlannedAction(
                "hook.install",
                "Install the versioned local guard as the repository pre-commit hook; "
                "back up a different existing hook.",
            )
        )
    sensitive_paths = sensitive_local_paths(repo) if repo.exists() else []
    if args.restrict_sensitive_files:
        actions.append(
            PlannedAction(
                "permissions.restrict",
                f"Restrict {len(sensitive_paths)} discovered local sensitive files to mode 0600.",
            )
        )

    print(f"LOCAL_ENVIRONMENT_HARDENING schema={SCRIPT_SCHEMA}")
    print(f"MODE={'APPLY' if args.apply else 'DRY_RUN'}")
    print(f"REPOSITORY={repo}")
    print(f"VIRTUAL_ENVIRONMENT={venv}")
    print(f"EVIDENCE_DIRECTORY={evidence}")
    for action in actions:
        print(f"PLAN {action.code}: {action.description}")

    if not args.apply:
        print("RESULT=dry_run_complete")
        print("No filesystem or Git hook changes were made.")
        return 0

    if not repo.is_dir():
        print(f"FAIL repository.missing: {repo}", file=sys.stderr)
        return 2
    if not git_worktree_valid(repo):
        print("FAIL repository.git: configured repository is not a Git worktree", file=sys.stderr)
        return 2
    if not (venv / "bin" / "python").is_file():
        print(f"FAIL virtual_environment.python: {venv / 'bin/python'}", file=sys.stderr)
        return 2
    if not doctor_path.is_file() or not policy_path.is_file():
        print("FAIL tooling.incomplete: doctor or policy file is missing", file=sys.stderr)
        return 2

    ensure_private_directory(evidence)
    ensure_private_directory(CONFIG_DIRECTORY)
    configuration = {
        "schema": "gh.dev.local-environment-config/1",
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "repository": str(repo),
        "virtual_environment": str(venv),
        "evidence_directory": str(evidence),
        "policy_path": str(policy_path),
        "policy_sha256": sha256_file(policy_path),
        "secret_values_included": False,
    }
    atomic_write_private(
        CONFIG_PATH,
        json.dumps(configuration, ensure_ascii=False, indent=2) + "\n",
    )

    if args.restrict_sensitive_files:
        for path in sensitive_paths:
            path.chmod(0o600)
            print(f"APPLIED permissions.restrict path={path} mode=0o600")

    if args.install_pre_commit_hook:
        if not hook_template.is_file():
            print(f"FAIL hook.template_missing: {hook_template}", file=sys.stderr)
            return 2
        target, backup = install_hook(repo, hook_template)
        print(f"APPLIED hook.install target={target}")
        if backup:
            print(f"BACKUP={backup}")

    print(
        f"APPLIED evidence.ensure path={evidence} "
        f"mode={oct(stat.S_IMODE(evidence.stat().st_mode))}"
    )
    print(
        f"APPLIED config.write path={CONFIG_PATH} "
        f"mode={oct(stat.S_IMODE(CONFIG_PATH.stat().st_mode))}"
    )

    if args.skip_post_audit:
        print("RESULT=hardening_applied_post_audit_skipped")
        return 0

    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_directory = evidence / "local-environment" / timestamp
    ensure_private_directory(report_directory)
    report_path = report_directory / "local-environment-audit.json"
    return_code = run_doctor(
        venv / "bin" / "python",
        doctor_path,
        policy_path,
        repo,
        venv,
        evidence,
        report_path,
    )
    print(f"POST_AUDIT_REPORT={report_path}")
    print(f"POST_AUDIT_RC={return_code}")
    print("RESULT=hardening_applied")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
