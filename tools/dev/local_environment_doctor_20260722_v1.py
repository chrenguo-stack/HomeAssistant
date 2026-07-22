#!/usr/bin/env python3
"""Read-only local development environment audit for the greenhouse project.

The script uses only the Python standard library. It does not install packages,
start services, contact production systems, access serial devices, or mutate the
repository. Optional network-facing checks are disabled unless explicitly
requested.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import importlib.metadata
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence


SCRIPT_SCHEMA = "gh.dev.local-environment-doctor/1"
DEFAULT_POLICY_NAME = "local_environment_policy_20260722_v1.json"
STATUS_ORDER = {"PASS": 0, "INFO": 1, "WARN": 2, "FAIL": 3}


@dataclasses.dataclass(frozen=True)
class CheckResult:
    status: str
    code: str
    message: str
    details: dict[str, Any] = dataclasses.field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def run_command(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: int = 12,
) -> tuple[int, str]:
    """Run a bounded command and return merged, trimmed output."""

    try:
        completed = subprocess.run(
            list(command),
            cwd=str(cwd) if cwd else None,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    output = completed.stdout.replace("\x00", "").strip()
    return completed.returncode, output[:12000]


def parse_version(value: str) -> tuple[int, ...]:
    match = re.search(r"(\d+(?:\.\d+)+)", value)
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def path_mode(path: Path) -> str:
    try:
        return oct(stat.S_IMODE(path.stat().st_mode))
    except OSError:
        return "unknown"


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError):
        return False


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("policy root must be an object")
    return data


def locate_policy(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()
    return Path(__file__).resolve().with_name(DEFAULT_POLICY_NAME)


def configured_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def add(
    results: list[CheckResult],
    status: str,
    code: str,
    message: str,
    **details: Any,
) -> None:
    results.append(CheckResult(status, code, message, details))


def check_host(policy: dict[str, Any], results: list[CheckResult], repo: Path) -> None:
    host_policy = policy["host"]
    system = platform.system()
    machine = platform.machine()
    supported_systems = set(host_policy["supported_systems"])
    supported_architectures = set(host_policy["supported_architectures"])

    add(
        results,
        "PASS" if system in supported_systems else "FAIL",
        "host.system",
        f"Host system is {system}.",
        supported=sorted(supported_systems),
    )
    add(
        results,
        "PASS" if machine in supported_architectures else "FAIL",
        "host.architecture",
        f"Host architecture is {machine}.",
        supported=sorted(supported_architectures),
    )

    disk_target = repo if repo.exists() else Path.home()
    usage = shutil.disk_usage(disk_target)
    free_gib = round(usage.free / (1024**3), 2)
    minimum = float(host_policy["minimum_free_disk_gib"])
    recommended = float(host_policy["recommended_free_disk_gib"])
    if free_gib < minimum:
        status = "FAIL"
    elif free_gib < recommended:
        status = "WARN"
    else:
        status = "PASS"
    add(
        results,
        status,
        "host.disk",
        f"Free disk space is {free_gib} GiB.",
        minimum_gib=minimum,
        recommended_gib=recommended,
    )


def check_commands(policy: dict[str, Any], results: list[CheckResult]) -> None:
    tooling = policy["tooling"]
    for command in tooling["required_commands"]:
        resolved = shutil.which(command)
        add(
            results,
            "PASS" if resolved else "FAIL",
            f"command.required.{command}",
            f"Required command {command!r} is {'available' if resolved else 'missing'}.",
            path=resolved,
        )
    for command in tooling["optional_commands"]:
        resolved = shutil.which(command)
        add(
            results,
            "PASS" if resolved else "WARN",
            f"command.optional.{command}",
            f"Optional command {command!r} is {'available' if resolved else 'missing'}.",
            path=resolved,
        )


def package_version(python: Path, package: str) -> tuple[int, str]:
    code = (
        "import importlib.metadata as m; "
        f"print(m.version({package!r}))"
    )
    return run_command([str(python), "-c", code])


def check_python(
    policy: dict[str, Any],
    results: list[CheckResult],
    venv: Path,
) -> None:
    python_policy = policy["tooling"]["python"]
    minimum = parse_version(python_policy["minimum"])
    maximum = parse_version(python_policy["maximum_exclusive"])
    current = sys.version_info[:3]
    current_ok = current >= minimum and current < maximum
    add(
        results,
        "PASS" if current_ok else "WARN",
        "python.current",
        f"Audit interpreter is Python {platform.python_version()}.",
        executable=sys.executable,
        expected_range=f">={python_policy['minimum']}, <{python_policy['maximum_exclusive']}",
    )

    venv_python = venv / "bin" / "python"
    if not venv_python.exists():
        add(
            results,
            "FAIL",
            "python.venv",
            "Configured virtual environment Python is missing.",
            path=str(venv_python),
        )
        return

    rc, version_output = run_command([str(venv_python), "--version"])
    version = parse_version(version_output)
    venv_ok = rc == 0 and version >= minimum and version < maximum
    add(
        results,
        "PASS" if venv_ok else "FAIL",
        "python.venv",
        f"Configured virtual environment reports {version_output or 'no version'}.",
        path=str(venv_python),
        expected_range=f">={python_policy['minimum']}, <{python_policy['maximum_exclusive']}",
    )

    expected = policy["tooling"]["expected_versions"]
    for package in ("esphome", "pytest", "ruff"):
        rc, output = package_version(venv_python, package)
        if rc != 0:
            add(
                results,
                "FAIL",
                f"python.package.{package}",
                f"Python package {package!r} is not available in the configured virtual environment.",
            )
            continue

        if package == "esphome":
            ok = output == str(expected["esphome"])
            expected_text = str(expected["esphome"])
        elif package == "ruff":
            ok = output == str(expected["ruff"])
            expected_text = str(expected["ruff"])
        else:
            parsed = parse_version(output)
            ok = bool(parsed) and parsed[0] == int(expected["pytest_major"])
            expected_text = f"major {expected['pytest_major']}"
        add(
            results,
            "PASS" if ok else "WARN",
            f"python.package.{package}",
            f"{package} version is {output}.",
            expected=expected_text,
        )


def git_output(repo: Path, *arguments: str) -> tuple[int, str]:
    return run_command(["git", "-C", str(repo), *arguments])


def forbidden_tracked_paths(
    tracked: Iterable[str],
    security: dict[str, Any],
) -> list[str]:
    names = set(security["forbidden_tracked_path_names"])
    suffixes = tuple(security["forbidden_tracked_suffixes"])
    fragments = tuple(security["forbidden_tracked_path_fragments"])
    forbidden: list[str] = []
    for raw in tracked:
        normalized = "/" + raw.strip().replace("\\", "/")
        basename = Path(raw).name
        if basename in names or basename.endswith(suffixes):
            forbidden.append(raw)
        elif any(fragment in normalized for fragment in fragments):
            forbidden.append(raw)
    return sorted(set(forbidden))


def check_git(policy: dict[str, Any], results: list[CheckResult], repo: Path) -> None:
    if not repo.exists():
        add(results, "FAIL", "git.repo.exists", "Configured repository path is missing.", path=str(repo))
        return

    rc, inside = git_output(repo, "rev-parse", "--is-inside-work-tree")
    if rc != 0 or inside != "true":
        add(results, "FAIL", "git.repo.valid", "Configured path is not a Git worktree.", path=str(repo))
        return
    add(results, "PASS", "git.repo.valid", "Configured path is a Git worktree.", path=str(repo))

    rc, root = git_output(repo, "rev-parse", "--show-toplevel")
    canonical_repo = Path(root).resolve() if rc == 0 and root else repo.resolve()
    add(
        results,
        "PASS" if canonical_repo == repo.resolve() else "WARN",
        "git.repo.root",
        "Repository path matches the Git top-level directory."
        if canonical_repo == repo.resolve()
        else "Configured repository path is not the Git top-level directory.",
        git_root=str(canonical_repo),
    )

    _, branch = git_output(repo, "branch", "--show-current")
    _, head = git_output(repo, "rev-parse", "HEAD")
    add(results, "INFO", "git.identity", "Current Git identity captured.", branch=branch or "DETACHED", head=head)

    _, status_output = git_output(repo, "status", "--porcelain=v1", "--untracked-files=all")
    dirty_lines = [line for line in status_output.splitlines() if line.strip()]
    add(
        results,
        "PASS" if not dirty_lines else "WARN",
        "git.worktree.clean",
        "Git worktree is clean." if not dirty_lines else f"Git worktree has {len(dirty_lines)} changed or untracked paths.",
        changed_path_count=len(dirty_lines),
    )

    protected = set(policy["git"]["protected_branches"])
    add(
        results,
        "WARN" if branch in protected else "PASS",
        "git.branch.protection",
        f"Current branch {branch!r} is protected; create or switch to a stage branch before development."
        if branch in protected
        else f"Current branch {branch or 'DETACHED'!r} is not a protected development target.",
    )

    rc, origin = git_output(repo, "remote", "get-url", "origin")
    allowed = set(policy["git"]["allowed_origin_urls"])
    origin_ok = rc == 0 and origin in allowed
    add(
        results,
        "PASS" if origin_ok else "FAIL",
        "git.origin",
        f"Origin remote is {origin or 'missing'}.",
        allowed=sorted(allowed),
    )

    rc, tracked_output = git_output(repo, "ls-files", "-z")
    tracked = tracked_output.split("\x00") if rc == 0 else []
    forbidden = forbidden_tracked_paths(tracked, policy["security"])
    add(
        results,
        "PASS" if not forbidden else "FAIL",
        "git.tracked_sensitive_paths",
        "No forbidden sensitive runtime paths are tracked."
        if not forbidden
        else f"Found {len(forbidden)} forbidden tracked sensitive paths.",
        paths=forbidden[:50],
    )

    rc, staged = git_output(repo, "diff", "--cached", "--no-ext-diff", "--unified=0", "--", ".")
    markers = policy["security"]["private_key_markers"]
    found_markers = [marker for marker in markers if marker in staged] if rc == 0 else []
    add(
        results,
        "PASS" if not found_markers else "FAIL",
        "git.staged_private_key_markers",
        "No private-key markers are present in staged text."
        if not found_markers
        else "Private-key markers are present in staged text.",
        markers=found_markers,
    )


def sensitive_local_paths(repo: Path) -> list[Path]:
    candidates: list[Path] = []
    patterns = (".env", ".env.*", "secrets.yaml", "credentials.json", "*.key", "*.pem", "*.p12", "*.pfx")
    for pattern in patterns:
        candidates.extend(repo.rglob(pattern))
    ignored_parts = {".git", ".esphome", "build", "dist", ".venv", "venv"}
    return sorted(
        {
            path
            for path in candidates
            if path.is_file() and not any(part in ignored_parts for part in path.parts)
        }
    )


def check_local_permissions(results: list[CheckResult], repo: Path) -> None:
    if not repo.exists():
        return
    insecure: list[dict[str, str]] = []
    for path in sensitive_local_paths(repo):
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
        except OSError:
            continue
        if mode & 0o077:
            insecure.append({"path": str(path), "mode": oct(mode)})
    add(
        results,
        "PASS" if not insecure else "WARN",
        "security.local_file_permissions",
        "Sensitive local files are not group/world accessible."
        if not insecure
        else f"Found {len(insecure)} sensitive local files with broad permissions.",
        files=insecure[:30],
    )


def check_environment(policy: dict[str, Any], results: list[CheckResult]) -> None:
    fragments = tuple(policy["security"]["sensitive_environment_name_fragments"])
    names = sorted(
        name
        for name, value in os.environ.items()
        if value and any(fragment in name.upper() for fragment in fragments)
    )
    add(
        results,
        "WARN" if names else "PASS",
        "security.sensitive_environment_names",
        f"Detected {len(names)} populated sensitive-looking environment variable names. Values were not read or reported."
        if names
        else "No populated sensitive-looking environment variable names were detected.",
        names=names,
    )


def check_evidence_directory(results: list[CheckResult], repo: Path, evidence: Path) -> None:
    if not evidence.exists():
        add(
            results,
            "WARN",
            "evidence.directory",
            "External evidence directory does not exist yet.",
            path=str(evidence),
        )
        return
    if not evidence.is_dir():
        add(results, "FAIL", "evidence.directory", "Evidence path exists but is not a directory.", path=str(evidence))
        return

    mode = stat.S_IMODE(evidence.stat().st_mode)
    outside = not is_within(evidence, repo)
    secure_mode = (mode & 0o077) == 0
    status = "PASS" if outside and secure_mode else "FAIL"
    add(
        results,
        status,
        "evidence.directory",
        "Evidence directory is outside the repository and private."
        if status == "PASS"
        else "Evidence directory must be outside the repository and have no group/world permissions.",
        path=str(evidence),
        mode=oct(mode),
        outside_repository=outside,
    )


def check_optional_runtime(results: list[CheckResult], network_checks: bool) -> None:
    if shutil.which("docker"):
        rc, output = run_command(["docker", "version", "--format", "{{.Client.Version}}"], timeout=8)
        add(
            results,
            "PASS" if rc == 0 else "WARN",
            "optional.docker_client",
            f"Docker client version is {output}." if rc == 0 else "Docker client exists but version query failed.",
        )
    if shutil.which("gh"):
        rc, output = run_command(["gh", "--version"], timeout=8)
        first_line = output.splitlines()[0] if output else "unknown"
        add(
            results,
            "PASS" if rc == 0 else "WARN",
            "optional.github_cli",
            f"GitHub CLI reports {first_line}.",
        )
        if network_checks:
            auth_rc, _ = run_command(["gh", "auth", "status"], timeout=12)
            add(
                results,
                "PASS" if auth_rc == 0 else "WARN",
                "optional.github_cli_auth",
                "GitHub CLI authentication check passed."
                if auth_rc == 0
                else "GitHub CLI authentication check did not pass.",
            )
    else:
        add(results, "INFO", "optional.network_checks", "Network-facing checks were not attempted because gh is unavailable.")


def summarize(results: list[CheckResult]) -> dict[str, int]:
    return {status: sum(item.status == status for item in results) for status in STATUS_ORDER}


def write_report(path: Path, report: dict[str, Any]) -> None:
    if not path.parent.exists():
        raise FileNotFoundError(f"report parent does not exist: {path.parent}")
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, help="Policy JSON path.")
    parser.add_argument("--repo", type=Path, help="Repository path override.")
    parser.add_argument("--venv", type=Path, help="Virtual environment path override.")
    parser.add_argument("--evidence-dir", type=Path, help="External evidence directory override.")
    parser.add_argument("--json-output", type=Path, help="Write a redacted JSON report; parent must already exist.")
    parser.add_argument("--network-checks", action="store_true", help="Also check GitHub CLI authentication. Disabled by default.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when warnings exist.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    policy_path = locate_policy(args.policy)
    try:
        policy = read_json(policy_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL policy.load: {exc}", file=sys.stderr)
        return 2

    defaults = policy["default_paths"]
    repo = (args.repo or configured_path(defaults["repository"])).expanduser().resolve()
    venv = (args.venv or configured_path(defaults["virtual_environment"])).expanduser().resolve()
    evidence = (args.evidence_dir or configured_path(defaults["evidence_directory"])).expanduser().resolve()

    results: list[CheckResult] = []
    check_host(policy, results, repo)
    check_commands(policy, results)
    check_python(policy, results, venv)
    check_git(policy, results, repo)
    check_local_permissions(results, repo)
    check_environment(policy, results)
    check_evidence_directory(results, repo, evidence)
    check_optional_runtime(results, args.network_checks)

    ordered = sorted(results, key=lambda item: (STATUS_ORDER[item.status], item.code))
    summary = summarize(ordered)
    report = {
        "schema": SCRIPT_SCHEMA,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "policy": {
            "path": str(policy_path),
            "schema": policy.get("schema"),
            "version": policy.get("policy_version"),
        },
        "inputs": {
            "repository": str(repo),
            "virtual_environment": str(venv),
            "evidence_directory": str(evidence),
            "network_checks": bool(args.network_checks),
        },
        "summary": summary,
        "results": [item.as_dict() for item in ordered],
        "secret_values_included": False,
        "system_mutation_performed": False,
        "production_access_performed": False,
    }

    print(f"LOCAL_ENVIRONMENT_AUDIT schema={SCRIPT_SCHEMA}")
    for item in ordered:
        print(f"{item.status:4} {item.code}: {item.message}")
    print(
        "SUMMARY "
        + " ".join(f"{status}={summary[status]}" for status in ("PASS", "INFO", "WARN", "FAIL"))
    )

    if args.json_output:
        try:
            write_report(args.json_output.expanduser().resolve(), report)
        except OSError as exc:
            print(f"FAIL report.write: {exc}", file=sys.stderr)
            return 2
        print(f"REPORT={args.json_output.expanduser().resolve()}")

    if summary["FAIL"]:
        return 2
    if args.strict and summary["WARN"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
