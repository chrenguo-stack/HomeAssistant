#!/usr/bin/env python3
"""Validate schema-declared development handoff documents.

Legacy handoffs without HANDOFF_SCHEMA_VERSION are intentionally skipped by --all.
A specific --file must be schema-compliant.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Sequence

SCHEMA_VERSION = "1.0"
TEMPLATE_ID = "N3W_FC4_DEVELOPMENT_HANDOFF_TEMPLATE"
TEMPLATE_VERSION = "1.0"

REQUIRED_HEADINGS = (
    "## 1. Document Identity / Schema",
    "## 2. North Star / Route",
    "## 3. Execution Model",
    "## 4. Repository / Branch Authority",
    "## 5. Frozen Product Source",
    "## 6. Worktree / Workspace Guard",
    "## 7. Runtime Authority",
    "## 8. Product State / Proven Facts",
    "## 9. Active Blocker / Root Cause",
    "## 10. Failure Classification / Fuse",
    "## 11. Authorization Ledger",
    "## 12. Mutation State",
    "## 13. Known Failures / Regression Guards",
    "## 14. Forbidden Actions / Non-goals",
    "## 15. Next Route Action",
    "## 16. Physical State",
    "## 17. Source Repair / Changed-file Allowlist",
    "## 18. Tests / CI / Artifact Authority",
    "## 19. Next-Session Read-Only Recovery",
    "## 20. New Conversation Startup Prompt",
    "## 21. Handoff Terminal",
)

REQUIRED_KEYS = (
    "HANDOFF_SCHEMA_VERSION",
    "HANDOFF_TEMPLATE_ID",
    "HANDOFF_TEMPLATE_VERSION",
    "HANDOFF_TEMPLATE_BLOB_SHA",
    "HANDOFF_DOCUMENT_VERSION",
    "HANDOFF_DATE",
    "HANDOFF_LINT_REQUIRED",
    "HANDOFF_LINT_RESULT",
    "PUBLIC_REPOSITORY_SAFETY_REQUIRED",
    "PUBLIC_REPOSITORY_SAFETY_RESULT",
    "NORTH_STAR",
    "CURRENT_ROUTE_NODE",
    "ACTIVE_DETOUR",
    "RETURN_TO_ROUTE",
    "NEW_BRANCH_ALLOWED",
    "EXECUTION_MODEL",
    "HIGH_LEVEL_REASONING_ROLE",
    "BOUNDED_EXECUTION_ROLE",
    "ONE_GATE_ONE_ROUTE_DECISION",
    "UNKNOWN_IS_NOT_FAIL",
    "UNOBSERVED_IS_NOT_FALSE",
    "DSL_OR_EXECUTION_CONTRACT_IS_NOT_SELF_EXECUTING",
    "REPOSITORY",
    "HANDOFF_BRANCH",
    "HANDOFF_PREDECESSOR_HEAD",
    "HANDOFF_BRANCH_HEAD_POLICY",
    "FROZEN_PRODUCT_SOURCE_HEAD",
    "FROZEN_PRODUCT_SOURCE_TREE",
    "PRIVATE_WORKTREE_PATH_EXPOSED",
    "DIRTY_WORKTREE_MUTATION_ALLOWED",
    "RUNTIME_AUTHORITY_STATE",
    "PRODUCT_STATE",
    "PRODUCT_BLOCKER_PROVEN",
    "FAIL_CLASS",
    "CURRENT_EXECUTOR_FAILURE_STREAK",
    "ROUTE_AUDIT_REQUIRED",
    "CONSUMED_AUTHORIZATION_COUNT",
    "REPLAY_OF_CONSUMED_AUTHORIZATION_ALLOWED",
    "SOURCE_MUTATION_EXECUTED",
    "PHYSICAL_MUTATION_EXECUTED",
    "RUNTIME_MUTATION_EXECUTED",
    "KNOWN_FAILURES_UPDATED",
    "KNOWN_FAILURES_STATE",
    "FORBIDDEN_ACTIONS_STATE",
    "NEXT_ROUTE_ACTION",
    "PHYSICAL_STATE",
    "SOURCE_REPAIR_STATE",
    "TEST_PLAN_STATE",
    "NEXT_SESSION_RECOVERY_STATE",
    "STARTUP_PROMPT_PRESENT",
)

EXACT_VALUES = {
    "HANDOFF_SCHEMA_VERSION": SCHEMA_VERSION,
    "HANDOFF_TEMPLATE_ID": TEMPLATE_ID,
    "HANDOFF_TEMPLATE_VERSION": TEMPLATE_VERSION,
    "EXECUTION_MODEL": "HIGH_LEVEL_REASONING_PLUS_BOUNDED_CODEX_EXECUTION",
    "HIGH_LEVEL_REASONING_ROLE": "CHATGPT",
    "BOUNDED_EXECUTION_ROLE": "CODEX",
    "ONE_GATE_ONE_ROUTE_DECISION": "true",
    "UNKNOWN_IS_NOT_FAIL": "true",
    "UNOBSERVED_IS_NOT_FALSE": "true",
    "DSL_OR_EXECUTION_CONTRACT_IS_NOT_SELF_EXECUTING": "true",
    "PRIVATE_WORKTREE_PATH_EXPOSED": "false",
    "DIRTY_WORKTREE_MUTATION_ALLOWED": "false",
    "REPLAY_OF_CONSUMED_AUTHORIZATION_ALLOWED": "false",
    "FORBIDDEN_ACTIONS_STATE": "DECLARED",
    "NEXT_SESSION_RECOVERY_STATE": "DEFINED",
    "STARTUP_PROMPT_PRESENT": "true",
    "HANDOFF_LINT_REQUIRED": "true",
    "HANDOFF_LINT_RESULT": "PASS",
    "PUBLIC_REPOSITORY_SAFETY_REQUIRED": "true",
    "PUBLIC_REPOSITORY_SAFETY_RESULT": "PASS",
    "HANDOFF_BRANCH_HEAD_POLICY": "READ_CURRENT_BRANCH_HEAD_ON_RECOVERY",
}

ALLOWED_FAIL_CLASSES = {
    "PRODUCT_BLOCKER",
    "INFRASTRUCTURE_BLOCKER",
    "SECURITY_AUTHORITY_BLOCKER",
    "PHYSICAL_HARNESS_DEFECT",
    "EXECUTOR_OR_ORACLE_DEFECT",
    "EVIDENCE_GAP",
    "TRANSIENT_INFRASTRUCTURE_FAILURE",
    "NONE",
}

PRIVATE_PATTERNS = (
    ("developer-home-path", re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+/")),
    (
        "private-network-address",
        re.compile(
            r"(?<![0-9])(?:10(?:\.[0-9]{1,3}){3}|"
            r"192\.168(?:\.[0-9]{1,3}){2}|"
            r"172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})(?![0-9])"
        ),
    ),
    (
        "mac-address",
        re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])"),
    ),
    ("raw-board-hardware-id", re.compile(r"(?i)\bghw-c6-[0-9a-f]{12}\b")),
)

ASSIGNMENT_RE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True, order=True)
class Finding:
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.rule}: {self.detail}"


def parse_assignments(text: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for raw in text.splitlines():
        match = ASSIGNMENT_RE.match(raw.strip())
        if not match:
            continue
        key, value = match.groups()
        result.setdefault(key, []).append(value.strip())
    return result


def last_value(assignments: dict[str, list[str]], key: str) -> str | None:
    values = assignments.get(key)
    return values[-1] if values else None


def authorization_blocks(text: str) -> tuple[list[dict[str, str]], list[Finding]]:
    blocks: list[dict[str, str]] = []
    findings: list[Finding] = []
    active: dict[str, str] | None = None
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line == "AUTHORIZATION_LEDGER_BEGIN":
            if active is not None:
                findings.append(Finding("authorization-nested-begin", str(line_number)))
            active = {}
            continue
        if line == "AUTHORIZATION_LEDGER_END":
            if active is None:
                findings.append(Finding("authorization-orphan-end", str(line_number)))
            else:
                blocks.append(active)
                active = None
            continue
        if active is not None:
            match = ASSIGNMENT_RE.match(line)
            if match:
                key, value = match.groups()
                active[key] = value.strip()
    if active is not None:
        findings.append(Finding("authorization-unclosed-block", "EOF"))
    return blocks, findings


def validate_text(text: str, path: str = "<memory>") -> list[Finding]:
    findings: set[Finding] = set()
    assignments = parse_assignments(text)

    positions: list[int] = []
    for heading in REQUIRED_HEADINGS:
        pos = text.find(heading)
        if pos < 0:
            findings.add(Finding("missing-heading", heading))
        positions.append(pos)
    existing = [pos for pos in positions if pos >= 0]
    if existing != sorted(existing):
        findings.add(Finding("heading-order", path))

    for key in REQUIRED_KEYS:
        if key not in assignments:
            findings.add(Finding("missing-key", key))

    for key, expected in EXACT_VALUES.items():
        actual = last_value(assignments, key)
        if actual is not None and actual != expected:
            findings.add(Finding("wrong-fixed-value", f"{key}={actual!r} expected {expected!r}"))

    blob_sha = last_value(assignments, "HANDOFF_TEMPLATE_BLOB_SHA")
    if blob_sha is not None and not HEX40_RE.fullmatch(blob_sha):
        findings.add(Finding("invalid-template-blob-sha", blob_sha))

    date_value = last_value(assignments, "HANDOFF_DATE")
    if date_value is not None and not DATE_RE.fullmatch(date_value):
        findings.add(Finding("invalid-handoff-date", date_value))

    for key in (
        "FROZEN_PRODUCT_SOURCE_HEAD",
        "FROZEN_PRODUCT_SOURCE_TREE",
        "HANDOFF_PREDECESSOR_HEAD",
    ):
        value = last_value(assignments, key)
        if value is not None and value != "NOT_APPLICABLE" and not HEX40_RE.fullmatch(value):
            findings.add(Finding("invalid-git-authority", f"{key}={value}"))

    fail_class = last_value(assignments, "FAIL_CLASS")
    if fail_class is not None and fail_class not in ALLOWED_FAIL_CLASSES:
        findings.add(Finding("invalid-fail-class", fail_class))

    streak = last_value(assignments, "CURRENT_EXECUTOR_FAILURE_STREAK")
    if streak is not None:
        try:
            if int(streak) < 0:
                raise ValueError
        except ValueError:
            findings.add(Finding("invalid-failure-streak", streak))

    consumed_count = last_value(assignments, "CONSUMED_AUTHORIZATION_COUNT")
    parsed_consumed_count: int | None = None
    if consumed_count is not None:
        try:
            parsed_consumed_count = int(consumed_count)
            if parsed_consumed_count < 0:
                raise ValueError
        except ValueError:
            findings.add(Finding("invalid-consumed-authorization-count", consumed_count))

    blocks, block_findings = authorization_blocks(text)
    findings.update(block_findings)
    consumed_blocks = 0
    for index, block in enumerate(blocks, start=1):
        for key in (
            "AUTHORIZATION_ID",
            "AUTHORIZATION_STATE",
            "REPLAY_PERMITTED",
            "AUTHORIZATION_SCOPE",
        ):
            if key not in block:
                findings.add(Finding("authorization-missing-key", f"block={index} key={key}"))
        state = block.get("AUTHORIZATION_STATE")
        replay = block.get("REPLAY_PERMITTED")
        if state == "CONSUMED":
            consumed_blocks += 1
            if replay != "false":
                findings.add(Finding("consumed-authorization-replay", f"block={index}"))
        if state == "CANDIDATE" and replay not in {"false", "NOT_APPLICABLE"}:
            findings.add(Finding("candidate-authorization-replay", f"block={index}"))

    if parsed_consumed_count is not None and parsed_consumed_count != consumed_blocks:
        findings.add(
            Finding(
                "consumed-authorization-count-mismatch",
                f"declared={parsed_consumed_count} blocks={consumed_blocks}",
            )
        )

    for rule, pattern in PRIVATE_PATTERNS:
        match = pattern.search(text)
        if match:
            line = text.count("\n", 0, match.start()) + 1
            findings.add(Finding(rule, f"{path}:{line}"))

    if re.search(
        r"(?im)^SETUP_SECRET(?:_VALUE)?\s*=\s*(?!<|REDACTED|NOT_APPLICABLE|NONE)[^\s]+",
        text,
    ):
        findings.add(Finding("setup-secret-material", path))
    if re.search(
        r"(?im)^RAW_(?:HARDWARE_ID|PAIRING_ID|NODE_ID|BOARD_C_IP)\s*=\s*"
        r"(?!<|REDACTED|NOT_APPLICABLE|NONE)[^\s]+",
        text,
    ):
        findings.add(Finding("raw-private-authority", path))

    if re.search(
        r"<(?:VALUE|VERSION|YYYY-MM-DD|BRANCH|40-HEX-SHA|TEMPLATE_GIT_BLOB_SHA|EXACT_NEXT_ACTION)",
        text,
    ):
        findings.add(Finding("unresolved-template-placeholder", path))

    return sorted(findings)


def schema_declared(text: str) -> bool:
    return bool(re.search(r"(?m)^HANDOFF_SCHEMA_VERSION=", text))


def discover_schema_handoffs(repository: Path) -> tuple[list[Path], int]:
    root = repository / "docs" / "development"
    schema_files: list[Path] = []
    legacy = 0
    if not root.is_dir():
        return [], 0
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root)
        if "templates" in relative.parts:
            continue
        name = path.name.lower()
        if "handoff" not in name and "交接" not in name:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if schema_declared(text):
            schema_files.append(path)
        else:
            legacy += 1
    return schema_files, legacy


def validate_file(path: Path) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        return [Finding("file-read-error", type(error).__name__)]
    if not schema_declared(text):
        return [Finding("schema-not-declared", str(path))]
    return validate_text(text, str(path))


def self_test() -> list[str]:
    failures: list[str] = []
    base = "\n".join(REQUIRED_HEADINGS) + "\n"
    fields = {key: "X" for key in REQUIRED_KEYS}
    fields.update(EXACT_VALUES)
    fields.update(
        {
            "HANDOFF_TEMPLATE_BLOB_SHA": "a" * 40,
            "HANDOFF_DOCUMENT_VERSION": "VTEST",
            "HANDOFF_DATE": "2026-08-30",
            "NORTH_STAR": "TEST",
            "CURRENT_ROUTE_NODE": "TEST",
            "ACTIVE_DETOUR": "NONE",
            "RETURN_TO_ROUTE": "NONE",
            "NEW_BRANCH_ALLOWED": "false",
            "REPOSITORY": "example/repo",
            "HANDOFF_BRANCH": "test",
            "HANDOFF_PREDECESSOR_HEAD": "b" * 40,
            "FROZEN_PRODUCT_SOURCE_HEAD": "c" * 40,
            "FROZEN_PRODUCT_SOURCE_TREE": "d" * 40,
            "RUNTIME_AUTHORITY_STATE": "PASS",
            "PRODUCT_STATE": "TEST",
            "PRODUCT_BLOCKER_PROVEN": "false",
            "FAIL_CLASS": "NONE",
            "CURRENT_EXECUTOR_FAILURE_STREAK": "0",
            "ROUTE_AUDIT_REQUIRED": "false",
            "CONSUMED_AUTHORIZATION_COUNT": "1",
            "SOURCE_MUTATION_EXECUTED": "false",
            "PHYSICAL_MUTATION_EXECUTED": "false",
            "RUNTIME_MUTATION_EXECUTED": "false",
            "KNOWN_FAILURES_UPDATED": "false",
            "KNOWN_FAILURES_STATE": "TEST",
            "NEXT_ROUTE_ACTION": "TEST",
            "PHYSICAL_STATE": "NOT_APPLICABLE",
            "SOURCE_REPAIR_STATE": "NOT_APPLICABLE",
            "TEST_PLAN_STATE": "DEFINED",
        }
    )
    good = base + "\n".join(f"{key}={value}" for key, value in fields.items()) + "\n" + dedent(
        """
        AUTHORIZATION_LEDGER_BEGIN
        AUTHORIZATION_ID=TEST
        AUTHORIZATION_STATE=CONSUMED
        REPLAY_PERMITTED=false
        AUTHORIZATION_SCOPE=TEST
        AUTHORIZATION_LEDGER_END
        """
    )
    if validate_text(good, "good"):
        failures.append("good-document-rejected")

    bad_replay = good.replace("REPLAY_PERMITTED=false", "REPLAY_PERMITTED=true", 1)
    if not any(
        finding.rule == "consumed-authorization-replay"
        for finding in validate_text(bad_replay, "bad-replay")
    ):
        failures.append("consumed-replay-not-detected")

    bad_home = good + "\n/Users/example/private\n"
    if not any(
        finding.rule == "developer-home-path"
        for finding in validate_text(bad_home, "bad-home")
    ):
        failures.append("developer-home-path-not-detected")

    bad_missing = good.replace(REQUIRED_HEADINGS[5], "")
    if not any(
        finding.rule == "missing-heading"
        for finding in validate_text(bad_missing, "bad-missing")
    ):
        failures.append("missing-heading-not-detected")

    return failures


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=Path)
    group.add_argument("--all", action="store_true")
    group.add_argument("--self-test", action="store_true")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        failures = self_test()
        if failures:
            print("development-handoff-self-test: failed")
            for failure in failures:
                print(failure)
            return 1
        print("development-handoff-self-test: passed")
        return 0

    repository = args.repository.resolve()
    if args.file is not None:
        path = args.file
        if not path.is_absolute():
            path = repository / path
        findings = validate_file(path)
        if findings:
            print("development-handoff-lint: failed")
            for finding in findings:
                print(finding.render())
            return 1
        print("development-handoff-lint: passed")
        return 0

    files, legacy = discover_schema_handoffs(repository)
    if not files:
        print(f"development-handoff-lint: passed schema_files=0 legacy_skipped={legacy}")
        return 0

    all_findings: list[tuple[Path, Finding]] = []
    for path in files:
        for finding in validate_file(path):
            all_findings.append((path, finding))
    if all_findings:
        print("development-handoff-lint: failed")
        for path, finding in all_findings:
            print(f"{path.relative_to(repository)}: {finding.render()}")
        return 1
    print(
        "development-handoff-lint: passed "
        f"schema_files={len(files)} legacy_skipped={legacy}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
