#!/usr/bin/env python3
"""Local pre-commit guard for runtime state and private-key material.

This hook is intentionally narrow. It checks only staged paths and staged file
content, performs no network access, and never edits the index or worktree.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import PurePosixPath


SCHEMA = "gh.dev.pre-commit-local-environment-guard/1"
FORBIDDEN_BASENAMES = {
    ".env",
    "secrets.yaml",
    "credentials.json",
    "home-assistant_v2.db",
    "id_rsa",
    "id_ed25519",
}
FORBIDDEN_SUFFIXES = (
    ".key",
    ".p12",
    ".pfx",
    ".jks",
    ".sqlite",
    ".sqlite3",
)
FORBIDDEN_FRAGMENTS = (
    "/.storage/",
    "/.esphome/",
    "/evidence/",
)
PRIVATE_KEY_MARKERS = (
    b"BEGIN PRIVATE KEY",
    b"BEGIN RSA PRIVATE KEY",
    b"BEGIN OPENSSH PRIVATE KEY",
    b"BEGIN EC PRIVATE KEY",
)
MAX_SCAN_BYTES = 2 * 1024 * 1024


def git(*arguments: str, binary: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=not binary,
    )


def staged_paths() -> list[str]:
    completed = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z", binary=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace").strip())
    return [item.decode("utf-8", errors="surrogateescape") for item in completed.stdout.split(b"\x00") if item]


def forbidden_path(path: str) -> str | None:
    normalized = "/" + path.replace("\\", "/")
    basename = PurePosixPath(path).name
    if basename in FORBIDDEN_BASENAMES:
        return f"forbidden runtime or credential basename {basename!r}"
    if basename.endswith(FORBIDDEN_SUFFIXES):
        return f"forbidden sensitive suffix in {basename!r}"
    if any(fragment in normalized for fragment in FORBIDDEN_FRAGMENTS):
        return "forbidden runtime-state or evidence directory"
    return None


def staged_blob(path: str) -> bytes:
    completed = git("show", f":{path}", binary=True)
    if completed.returncode != 0:
        return b""
    return completed.stdout[: MAX_SCAN_BYTES + 1]


def main() -> int:
    print(f"LOCAL_PRE_COMMIT_GUARD schema={SCHEMA}")
    try:
        paths = staged_paths()
    except RuntimeError as exc:
        print(f"FAIL git.index: {exc}", file=sys.stderr)
        return 2

    violations: list[str] = []
    for path in paths:
        reason = forbidden_path(path)
        if reason:
            violations.append(f"{path}: {reason}")
            continue

        blob = staged_blob(path)
        if len(blob) > MAX_SCAN_BYTES:
            print(f"INFO content.scan_skipped path={path} reason=file_over_2MiB")
            continue
        if b"\x00" in blob:
            continue
        markers = [marker.decode("ascii") for marker in PRIVATE_KEY_MARKERS if marker in blob]
        if markers:
            violations.append(f"{path}: private-key marker(s) {', '.join(markers)}")

    if violations:
        for violation in violations:
            print(f"FAIL staged.secret_guard: {violation}", file=sys.stderr)
        print("Commit blocked. Remove the staged sensitive material or replace it with an explicitly safe example file.", file=sys.stderr)
        return 1

    print(f"PASS staged.secret_guard checked_paths={len(paths)}")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())
