from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

STATE_SCHEMA = "gh.project-state.current-baseline/1"
REPORT_SCHEMA = "gh.project-state.status/1"
DEFAULT_STATE_RELATIVE_PATH = Path("project-state/current-baseline.json")


class ProjectStateError(ValueError):
    """Raised when project state is invalid or cannot be inspected safely."""


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    head_sha: str
    baseline_is_ancestor: bool
    tracked_worktree_clean: bool


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProjectStateError(message)


def _schema() -> dict[str, Any]:
    path = files("greenhouse_manager").joinpath("schemas/project_state_v1.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "project state schema is not an object")
    return value


def validate_project_state(document: object) -> dict[str, Any]:
    _require(isinstance(document, dict), "project state must be an object")
    errors = sorted(
        Draft202012Validator(_schema(), format_checker=FormatChecker()).iter_errors(document),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    )
    if errors:
        location = ".".join(str(part) for part in errors[0].absolute_path) or "root"
        raise ProjectStateError(f"project state schema validation failed at {location}")

    stages = document["stages"]
    _require(isinstance(stages, list), "project stages must be an array")
    by_id = {item["stage_id"]: item for item in stages}
    _require(len(by_id) == len(stages), "project stage identifiers must be unique")
    _require(by_id["H3"]["status"] == "in_progress", "H3 must remain in progress")
    _require(by_id["N2"]["status"] == "in_progress", "N2 must remain in progress")
    for stage_id in ("D0", "H2", "N0", "N1"):
        _require(by_id[stage_id]["status"] == "completed", f"{stage_id} must remain completed")
    for stage_id in ("N3-W", "N3-L"):
        _require(by_id[stage_id]["status"] == "not_started", f"{stage_id} cannot start before H3/N2")

    safety = document["safety"]
    _require(isinstance(safety, dict), "project safety state must be an object")
    _require(not any(safety.values()), "all H3/N2 safety gates must remain false")
    _require(document["next_gate"] in document["blocking_gates"], "next gate must be blocking")
    return document


def load_project_state(path: Path) -> tuple[dict[str, Any], str]:
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise ProjectStateError("project state file is unavailable") from error
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ProjectStateError("project state is not valid JSON") from error
    return validate_project_state(document), hashlib.sha256(payload).hexdigest()


def _git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProjectStateError("repository inspection failed") from error


def inspect_repository(repository: Path, baseline_sha: str) -> RepositorySnapshot:
    head = _git(repository, "rev-parse", "HEAD")
    _require(head.returncode == 0, "repository HEAD inspection failed")
    head_sha = head.stdout.strip()
    _require(len(head_sha) == 40, "repository HEAD is invalid")

    ancestor = _git(repository, "merge-base", "--is-ancestor", baseline_sha, head_sha)
    _require(ancestor.returncode in {0, 1}, "repository ancestry inspection failed")

    status = _git(repository, "status", "--porcelain", "--untracked-files=no")
    _require(status.returncode == 0, "repository worktree inspection failed")
    return RepositorySnapshot(
        head_sha=head_sha,
        baseline_is_ancestor=ancestor.returncode == 0,
        tracked_worktree_clean=not status.stdout.strip(),
    )


def build_status_report(
    document: dict[str, Any],
    *,
    state_sha256: str,
    repository: RepositorySnapshot,
) -> dict[str, Any]:
    validated = validate_project_state(document)
    baseline = validated["source_baseline"]
    matrix = validated["m2_board_matrix"]
    stages = validated["stages"]
    return {
        "schema": REPORT_SCHEMA,
        "status": "gh_project_state_status_succeeded",
        "active_stage": validated["active_stage"],
        "next_gate": validated["next_gate"],
        "source_baseline_repository_sha": baseline["repository_sha"],
        "source_baseline_manager_version": baseline["manager_version"],
        "candidate_manager_version": validated["candidate_manager_version"],
        "repository": asdict(repository),
        "head_matches_source_baseline": repository.head_sha == baseline["repository_sha"],
        "state_sha256": state_sha256,
        "completed_stage_ids": [item["stage_id"] for item in stages if item["status"] == "completed"],
        "in_progress_stage_ids": [item["stage_id"] for item in stages if item["status"] == "in_progress"],
        "not_started_stage_ids": [item["stage_id"] for item in stages if item["status"] == "not_started"],
        "completed_gates": list(validated["completed_gates"]),
        "blocking_gates": list(validated["blocking_gates"]),
        "m2_board_matrix": dict(matrix),
        "safety": dict(validated["safety"]),
        "last_verified_state": validated["last_verified_state"],
        "read_only": True,
        "production_execution_invoked": False,
        "current_services_modified": False,
        "node_credentials_delivered": False,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ghctl")
    product = parser.add_subparsers(dest="product", required=True)
    m2 = product.add_parser("m2", help="H3/N2 MQTT identity migration workflow")
    command = m2.add_subparsers(dest="command", required=True)
    status = command.add_parser("status", help="validate and report the read-only project baseline")
    status.add_argument("--repository", type=Path, default=Path.cwd())
    status.add_argument("--state", type=Path)
    status.add_argument("--require-baseline-ancestor", action="store_true")
    status.add_argument("--require-clean", action="store_true")
    status.add_argument("--pretty", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repository = args.repository.resolve()
    state_path = args.state.resolve() if args.state else repository / DEFAULT_STATE_RELATIVE_PATH
    try:
        document, state_sha256 = load_project_state(state_path)
        baseline_sha = document["source_baseline"]["repository_sha"]
        snapshot = inspect_repository(repository, baseline_sha)
        report = build_status_report(
            document,
            state_sha256=state_sha256,
            repository=snapshot,
        )
        if args.require_baseline_ancestor:
            _require(
                snapshot.baseline_is_ancestor,
                "source baseline is not an ancestor of repository HEAD",
            )
        if args.require_clean:
            _require(snapshot.tracked_worktree_clean, "repository has tracked worktree changes")
    except ProjectStateError as error:
        print(f"ghctl: project-state-error: {error}", file=sys.stderr)
        return 2
    indent = 2 if args.pretty else None
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
