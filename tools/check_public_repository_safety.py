#!/usr/bin/env python3
"""Fail closed when tracked files contain high-confidence public-repo leaks.

The checker deliberately reports only a rule name, repository path, and line
number. It never echoes the matched value, so CI logs cannot amplify a leak.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence


MAX_SCANNED_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True, order=True)
class Finding:
    rule: str
    path: str
    line: int | None = None

    def render(self) -> str:
        location = self.path if self.line is None else f"{self.path}:{self.line}"
        return f"{self.rule}: {location}"


CONTENT_RULES: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    (
        "private-key-material",
        re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
    (
        "github-access-token",
        re.compile(
            rb"(?<![A-Za-z0-9])(?:gh[pousr]_[A-Za-z0-9]{36,}|"
            rb"github_pat_[A-Za-z0-9_]{50,})"
        ),
    ),
    (
        "aws-access-key",
        re.compile(rb"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])"),
    ),
    ("google-api-key", re.compile(rb"AIza[0-9A-Za-z_-]{35}")),
    ("slack-token", re.compile(rb"xox[baprs]-[0-9A-Za-z-]{20,}")),
    (
        "jwt-like-token",
        re.compile(
            rb"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,}\."
            rb"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
        ),
    ),
    (
        "url-embedded-credentials",
        re.compile(
            rb"(?i)\b(?:mqtt|mqtts|http|https)://[^\s/:@]{2,}:"
            rb"[^\s/@]{6,}@"
        ),
    ),
    (
        "private-network-address",
        re.compile(
            rb"(?<![0-9])(?:10(?:\.[0-9]{1,3}){3}|"
            rb"192\.168(?:\.[0-9]{1,3}){2}|"
            rb"172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})(?![0-9])"
        ),
    ),
    (
        "mac-address",
        re.compile(rb"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])"),
    ),
    (
        "developer-home-path",
        re.compile(rb"/(?:Users|home)/[A-Za-z0-9._-]+/"),
    ),
)


BLOCKED_EXACT_NAMES = {
    ".env",
    "credentials.json",
    "home-assistant_v2.db",
    "id_ed25519",
    "id_rsa",
    "secrets.yaml",
}
BLOCKED_SUFFIXES = (
    ".gz",
    ".jks",
    ".key",
    ".p12",
    ".pem",
    ".pfx",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".tgz",
    ".zip",
)
BLOCKED_COMPONENTS = {".esphome", ".storage", "evidence"}
SENSITIVE_ENV_MARKERS = (
    "API_KEY",
    "PASSWORD",
    "PASSWD",
    "PRIVATE_KEY",
    "PSK",
    "SECRET",
    "TOKEN",
)
SENSITIVE_YAML_KEYS = {
    "api_key",
    "password",
    "passwd",
    "private_key",
    "psk",
    "secret",
    "token",
}
SAFE_CONFIG_PREFIXES = (b"${", b"<", b"!secret")
SAFE_CONFIG_WORDS = {b"change_me", b"dummy", b"example", b"null", b"test", b"~"}


def _is_example(path: PurePosixPath) -> bool:
    name = path.name.lower()
    return name == ".env.example" or ".example." in name or name.endswith(".example")


def blocked_path_reason(raw_path: str) -> str | None:
    path = PurePosixPath(raw_path)
    lowered = path.name.lower()
    if any(part.lower() in BLOCKED_COMPONENTS for part in path.parts):
        return "runtime-state-path"
    if _is_example(path):
        return None
    if lowered in BLOCKED_EXACT_NAMES or lowered.startswith(".env."):
        return "credential-file-path"
    if lowered.endswith(BLOCKED_SUFFIXES):
        return "private-material-path"
    return None


def _config_value_is_safe(value: bytes) -> bool:
    normalized = value.strip().strip(b"\"'").lower()
    return (
        not normalized
        or normalized.startswith(b"#")
        or normalized.startswith(SAFE_CONFIG_PREFIXES)
        or normalized in SAFE_CONFIG_WORDS
    )


def _scan_dotenv(path: str, data: bytes) -> set[Finding]:
    findings: set[Finding] = set()
    for line_number, line in enumerate(data.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(b"#") or b"=" not in stripped:
            continue
        key_raw, value = stripped.split(b"=", 1)
        key = key_raw.removeprefix(b"export ").decode("ascii", "ignore").upper()
        if not key or key.endswith(("_FILE", "_PATH")):
            continue
        if any(
            marker in key for marker in SENSITIVE_ENV_MARKERS
        ) and not _config_value_is_safe(value):
            findings.add(Finding("nonempty-sensitive-env-value", path, line_number))
    return findings


def _scan_yaml(path: str, data: bytes) -> set[Finding]:
    findings: set[Finding] = set()
    for line_number, line in enumerate(data.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(b"#") or b":" not in stripped:
            continue
        key_raw, value = stripped.split(b":", 1)
        key = key_raw.strip().strip(b"\"'").decode("ascii", "ignore").lower()
        if key in SENSITIVE_YAML_KEYS and not _config_value_is_safe(value):
            findings.add(Finding("nonempty-sensitive-yaml-value", path, line_number))
    return findings


def scan_blob(path: str, data: bytes) -> list[Finding]:
    findings: set[Finding] = set()
    if len(data) > MAX_SCANNED_BYTES:
        return [Finding("oversized-tracked-file", path)]
    if b"\0" in data[:8192]:
        return []
    for rule, pattern in CONTENT_RULES:
        for match in pattern.finditer(data):
            line = data.count(b"\n", 0, match.start()) + 1
            findings.add(Finding(rule, path, line))
    pure_path = PurePosixPath(path)
    lowered_name = pure_path.name.lower()
    if (
        lowered_name.startswith(".env")
        or ".env." in lowered_name
        or lowered_name.endswith(".env")
    ):
        findings.update(_scan_dotenv(path, data))
    if pure_path.suffix.lower() in {".yaml", ".yml"}:
        findings.update(_scan_yaml(path, data))
    return sorted(findings)


def tracked_paths(repository: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repository,
        check=True,
        stdout=subprocess.PIPE,
    )
    return [
        item.decode("utf-8", "surrogateescape")
        for item in result.stdout.split(b"\0")
        if item
    ]


def scan_repository(
    repository: Path, paths: Iterable[str] | None = None
) -> list[Finding]:
    findings: set[Finding] = set()
    selected = tracked_paths(repository) if paths is None else list(paths)
    for raw_path in selected:
        reason = blocked_path_reason(raw_path)
        if reason is not None:
            findings.add(Finding(reason, raw_path))
            continue
        path = repository / raw_path
        try:
            data = path.read_bytes()
        except OSError:
            findings.add(Finding("tracked-file-unreadable", raw_path))
            continue
        findings.update(scan_blob(raw_path, data))
    return sorted(findings)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repository = args.repository.resolve()
    try:
        findings = scan_repository(repository)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"public-repository-safety: checker-error: {type(error).__name__}")
        return 2
    if findings:
        print("public-repository-safety: failed")
        for finding in findings:
            print(finding.render())
        print(
            "Matched values are intentionally omitted. Remove or replace the source material."
        )
        return 1
    print("public-repository-safety: passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
