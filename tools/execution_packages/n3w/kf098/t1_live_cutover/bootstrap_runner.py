#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

REPOSITORY = "chrenguo-stack/HomeAssistant"
ARTIFACT_RUN_ID = 36329597775
ARTIFACT_ID = 10935052471
ARTIFACT_NAME = "n3w-kf098-manager-exact-source-575ce642"
IMAGE_TAR_SHA256 = "6392b8c9bb87d95404346583d6f44967bd4e20fcc092be393c45f75a4ca7a5b2"
PACKAGE_FILES = (
    "executor.py",
    "remote_cutover.py",
    "manifest.json",
    "TASK.md",
)
PACKAGE_REMOTE_ROOT = "tools/execution_packages/n3w/kf098/t1_live_cutover"
DEFAULT_WORK_ROOT = Path.home() / ".local/share/n3w-kf098-20260928"
REF_RE = re.compile(r"^[0-9a-f]{40}$")


class StopExecution(RuntimeError):
    pass


def run(
    args: list[str],
    *,
    timeout: int = 180,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        args,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def require_ok(
    completed: subprocess.CompletedProcess[bytes],
    message: str,
) -> bytes:
    if completed.returncode:
        stderr = completed.stderr.decode("utf-8", errors="backslashreplace")
        stdout = completed.stdout.decode("utf-8", errors="backslashreplace")
        detail = stderr.strip() or stdout.strip()
        raise StopExecution(f"{message}: {detail[:800]}")
    return completed.stdout


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise StopExecution(f"missing file: {path}")
    return sha256_bytes(path.read_bytes())


def write_private(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    os.chmod(path, 0o600)


def write_private_json(path: Path, value: Any) -> None:
    write_private(
        path,
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode(),
    )


def ensure_private_root(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise StopExecution("work root is not a directory")
        if path.stat().st_mode & 0o777 != 0o700:
            raise StopExecution("work root mode must be 0700")
    else:
        path.mkdir(parents=True, mode=0o700)
    if path.stat().st_mode & 0o777 != 0o700:
        raise StopExecution("work root mode must be 0700")


def validate_ref(value: str) -> None:
    if not REF_RE.fullmatch(value):
        raise StopExecution("package ref must be an exact 40-character lowercase SHA")


def gh_json(endpoint: str) -> dict[str, Any]:
    raw = require_ok(
        run(
            [
                "gh",
                "api",
                "--method",
                "GET",
                "-H",
                "Accept: application/vnd.github+json",
                endpoint,
            ],
            timeout=60,
        ),
        f"GitHub API request failed: {endpoint}",
    )
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise StopExecution("GitHub API returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise StopExecution("GitHub API response is not an object")
    return value


def verify_commit(package_ref: str) -> None:
    value = gh_json(
        f"repos/{REPOSITORY}/commits/{package_ref}"
    )
    if value.get("sha") != package_ref:
        raise StopExecution("GitHub commit binding mismatch")


def fetch_repository_file(
    package_ref: str,
    repository_path: str,
) -> bytes:
    value = gh_json(
        f"repos/{REPOSITORY}/contents/{repository_path}?ref={package_ref}"
    )
    if value.get("type") != "file":
        raise StopExecution(f"repository path is not a file: {repository_path}")
    encoded = value.get("content")
    encoding = value.get("encoding")
    if not isinstance(encoded, str) or encoding != "base64":
        raise StopExecution(f"repository file payload invalid: {repository_path}")
    try:
        return base64.b64decode(encoded, validate=False)
    except Exception as exc:
        raise StopExecution(
            f"repository file base64 invalid: {repository_path}"
        ) from exc


def verify_cached_package(
    package_dir: Path,
    package_ref: str,
) -> dict[str, str]:
    authority_path = package_dir / "package-authority.json"
    if not authority_path.is_file():
        raise StopExecution("cached package authority is missing")
    try:
        authority = json.loads(authority_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise StopExecution("cached package authority is invalid") from exc
    if authority.get("repository") != REPOSITORY:
        raise StopExecution("cached package repository mismatch")
    if authority.get("package_ref") != package_ref:
        raise StopExecution("cached package ref mismatch")
    expected = authority.get("files")
    if not isinstance(expected, dict):
        raise StopExecution("cached package hash map is invalid")
    actual: dict[str, str] = {}
    for name in PACKAGE_FILES:
        path = package_dir / name
        digest = sha256_file(path)
        if expected.get(name) != digest:
            raise StopExecution(f"cached package file drift: {name}")
        actual[name] = digest
    return actual


def prepare_package(
    work_root: Path,
    package_ref: str,
) -> tuple[Path, dict[str, str]]:
    package_dir = work_root / f"package-{package_ref[:12]}"
    if package_dir.exists():
        if package_dir.stat().st_mode & 0o777 != 0o700:
            raise StopExecution("cached package directory mode must be 0700")
        return package_dir, verify_cached_package(
            package_dir,
            package_ref,
        )

    verify_commit(package_ref)
    temp_dir = Path(
        tempfile.mkdtemp(
            prefix=".package-incoming-",
            dir=work_root,
        )
    )
    os.chmod(temp_dir, 0o700)
    try:
        hashes: dict[str, str] = {}
        for name in PACKAGE_FILES:
            payload = fetch_repository_file(
                package_ref,
                f"{PACKAGE_REMOTE_ROOT}/{name}",
            )
            write_private(temp_dir / name, payload)
            hashes[name] = sha256_bytes(payload)
        write_private_json(
            temp_dir / "package-authority.json",
            {
                "repository": REPOSITORY,
                "package_ref": package_ref,
                "files": hashes,
            },
        )
        os.replace(temp_dir, package_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return package_dir, verify_cached_package(
        package_dir,
        package_ref,
    )


def verify_artifact_dir(path: Path) -> None:
    image = path / "greenhouse-manager-arm64.tar"
    manifest = path / "manifest.json"
    manifest_sha = path / "manifest.sha256"
    if not image.is_file() or not manifest.is_file() or not manifest_sha.is_file():
        raise StopExecution("artifact directory is incomplete")
    if sha256_file(image) != IMAGE_TAR_SHA256:
        raise StopExecution("artifact image tar SHA256 mismatch")
    expected_manifest = (
        f"{sha256_file(manifest)}  manifest.json"
    )
    if manifest_sha.read_text(encoding="utf-8").strip() != expected_manifest:
        raise StopExecution("artifact portable manifest checksum mismatch")


def prepare_artifact(work_root: Path) -> Path:
    artifact_dir = work_root / f"artifact-{ARTIFACT_ID}"
    if artifact_dir.exists():
        if artifact_dir.stat().st_mode & 0o777 != 0o700:
            raise StopExecution("artifact directory mode must be 0700")
        verify_artifact_dir(artifact_dir)
        return artifact_dir

    temp_dir = Path(
        tempfile.mkdtemp(
            prefix=".artifact-incoming-",
            dir=work_root,
        )
    )
    os.chmod(temp_dir, 0o700)
    try:
        require_ok(
            run(
                [
                    "gh",
                    "run",
                    "download",
                    str(ARTIFACT_RUN_ID),
                    "--repo",
                    REPOSITORY,
                    "--name",
                    ARTIFACT_NAME,
                    "--dir",
                    str(temp_dir),
                ],
                timeout=300,
            ),
            "exact artifact download failed",
        )
        for path in temp_dir.iterdir():
            if path.is_file():
                os.chmod(path, 0o600)
        verify_artifact_dir(temp_dir)
        os.replace(temp_dir, artifact_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return artifact_dir


def evidence_root(
    work_root: Path,
    phase: str,
    attempt: int,
) -> Path:
    if attempt < 1 or attempt > 99:
        raise StopExecution("attempt must be between 1 and 99")
    path = work_root / f"evidence-{phase}-{attempt:02d}"
    if path.exists():
        raise StopExecution(f"evidence root already exists: {path}")
    path.mkdir(mode=0o700)
    return path


def prompt_target() -> str:
    try:
        value = input("T1 SSH target: ").strip()
    except EOFError as exc:
        raise StopExecution("T1 SSH target is required") from exc
    if not value:
        raise StopExecution("T1 SSH target is empty")
    return value


def run_phase(
    package_dir: Path,
    artifact_dir: Path,
    work_root: Path,
    phase: str,
    attempt: int,
    target: str | None,
) -> int:
    evidence = evidence_root(
        work_root,
        phase,
        attempt,
    )
    args = [
        "python3",
        str(package_dir / "executor.py"),
        "--phase",
        phase,
        "--artifact-dir",
        str(artifact_dir),
        "--evidence-root",
        str(evidence),
    ]
    if phase != "local-preflight":
        selected_target = target or prompt_target()
        args.extend(
            [
                "--t1-ssh-target",
                selected_target,
            ]
        )
    completed = subprocess.run(
        args,
        check=False,
    )
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--package-ref",
        required=True,
    )
    parser.add_argument(
        "--phase",
        required=True,
        choices=(
            "local-preflight",
            "stage",
            "remote-preflight",
            "apply",
            "rollback",
        ),
    )
    parser.add_argument(
        "--attempt",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--t1-ssh-target",
    )
    parser.add_argument(
        "--work-root",
        type=Path,
        default=DEFAULT_WORK_ROOT,
    )
    args = parser.parse_args()

    try:
        validate_ref(args.package_ref)
        ensure_private_root(args.work_root)
        package_dir, package_hashes = prepare_package(
            args.work_root,
            args.package_ref,
        )
        artifact_dir = prepare_artifact(
            args.work_root,
        )
        print(
            json.dumps(
                {
                    "bootstrap": "PASS",
                    "repository": REPOSITORY,
                    "package_ref": args.package_ref,
                    "package_dir": str(package_dir),
                    "artifact_id": ARTIFACT_ID,
                    "artifact_dir": str(artifact_dir),
                    "package_hashes": package_hashes,
                    "phase": args.phase,
                },
                sort_keys=True,
            )
        )
        return run_phase(
            package_dir,
            artifact_dir,
            args.work_root,
            args.phase,
            args.attempt,
            args.t1_ssh_target,
        )
    except (StopExecution, subprocess.TimeoutExpired) as exc:
        print(
            json.dumps(
                {
                    "bootstrap": "STOP",
                    "reason": f"{type(exc).__name__}:{exc}"[:1600],
                    "phase": args.phase,
                },
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
