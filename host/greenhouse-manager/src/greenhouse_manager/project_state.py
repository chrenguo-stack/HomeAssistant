from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

STATE_SCHEMA = "gh.project-state.current-baseline/1"
REPORT_SCHEMA = "gh.project-state.status/1"
H3_READINESS_SCHEMA = "gh.project-state.current-h3-readiness/1"
H3_READINESS_REPORT_SCHEMA = "gh.project-state.h3-readiness/1"
DEFAULT_STATE_RELATIVE_PATH = Path("project-state/current-baseline.json")
DEFAULT_H3_READINESS_RELATIVE_PATH = Path("project-state/h3-readiness.json")
MAX_PUBLIC_ARTIFACT_BYTES = 2 * 1024 * 1024
EXPECTED_H3_CAPABILITY_IDS = (
    "migration_preparation",
    "fresh_chain_preparation",
    "migration_authorization",
    "host_replica_fault_matrix",
    "production_transaction_adapter_contract",
    "production_driver_replica_fault_matrix",
    "live_runtime_gate",
    "execution_preparation",
    "execution_authorization",
    "execution_transaction_gate",
    "failure_diagnostics",
    "postrollback_audit",
    "postcommit_continuity_audit",
)


class ProjectStateError(ValueError):
    """Raised when project state is invalid or cannot be inspected safely."""


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    head_sha: str
    baseline_is_ancestor: bool
    tracked_worktree_clean: bool


@dataclass(frozen=True, slots=True)
class CapabilitySnapshot:
    capability_id: str
    readiness_level: str
    artifact_count: int
    content_sha256: str


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProjectStateError(message)


def _schema() -> dict[str, Any]:
    path = files("greenhouse_manager").joinpath("schemas/project_state_v1.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "project state schema is not an object")
    return value


def _h3_readiness_schema() -> dict[str, Any]:
    path = files("greenhouse_manager").joinpath("schemas/h3_readiness_v1.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "H3 readiness schema is not an object")
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


def validate_h3_readiness(document: object) -> dict[str, Any]:
    _require(isinstance(document, dict), "H3 readiness manifest must be an object")
    errors = sorted(
        Draft202012Validator(
            _h3_readiness_schema(),
            format_checker=FormatChecker(),
        ).iter_errors(document),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    )
    if errors:
        location = ".".join(str(part) for part in errors[0].absolute_path) or "root"
        raise ProjectStateError(f"H3 readiness schema validation failed at {location}")

    capabilities = document["capabilities"]
    _require(isinstance(capabilities, list), "H3 readiness capabilities must be an array")
    capability_ids = tuple(item["capability_id"] for item in capabilities)
    _require(
        capability_ids == EXPECTED_H3_CAPABILITY_IDS,
        "H3 readiness capability set or ordering is invalid",
    )
    artifact_paths: list[str] = []
    for capability in capabilities:
        artifact_paths.extend(
            [capability["source"], *capability["tests"], *capability["protocols"]]
        )
    _require(
        len(artifact_paths) == len(set(artifact_paths)),
        "H3 readiness artifacts must be uniquely owned",
    )
    safety = document["safety"]
    _require(isinstance(safety, dict), "H3 readiness safety state must be an object")
    _require(not any(safety.values()), "all H3 readiness safety capabilities must remain false")
    return document


def load_h3_readiness(path: Path) -> tuple[dict[str, Any], str]:
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise ProjectStateError("H3 readiness manifest is unavailable") from error
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ProjectStateError("H3 readiness manifest is not valid JSON") from error
    return validate_h3_readiness(document), hashlib.sha256(payload).hexdigest()


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


def _public_artifact(repository: Path, relative_path: str) -> tuple[str, bytes]:
    pure = PurePosixPath(relative_path)
    _require(
        not pure.is_absolute() and ".." not in pure.parts and "." not in pure.parts,
        "H3 readiness artifact path is unsafe",
    )
    resolved_repository = repository.resolve()
    resolved = (resolved_repository / Path(*pure.parts)).resolve()
    _require(
        resolved.is_relative_to(resolved_repository),
        "H3 readiness artifact escapes repository",
    )
    _require(
        resolved.is_file() and not resolved.is_symlink(),
        f"H3 readiness artifact is missing or unsafe: {relative_path}",
    )
    tracked = _git(repository, "ls-files", "--error-unmatch", "--", relative_path)
    _require(
        tracked.returncode == 0,
        f"H3 readiness artifact is not tracked: {relative_path}",
    )
    try:
        payload = resolved.read_bytes()
    except OSError as error:
        raise ProjectStateError(f"H3 readiness artifact is unreadable: {relative_path}") from error
    _require(
        len(payload) <= MAX_PUBLIC_ARTIFACT_BYTES,
        f"H3 readiness artifact is too large: {relative_path}",
    )
    return relative_path, payload


def inspect_h3_capabilities(
    repository: Path,
    readiness: dict[str, Any],
) -> tuple[CapabilitySnapshot, ...]:
    validated = validate_h3_readiness(readiness)
    snapshots: list[CapabilitySnapshot] = []
    for capability in validated["capabilities"]:
        paths = [capability["source"], *capability["tests"], *capability["protocols"]]
        artifacts = [_public_artifact(repository, path) for path in paths]
        source = artifacts[0][1].decode("utf-8")
        for marker in capability["required_markers"]:
            _require(
                marker in source,
                f"H3 readiness source marker is missing: {capability['capability_id']}",
            )
        digest = hashlib.sha256()
        for relative_path, payload in artifacts:
            digest.update(relative_path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(payload)
            digest.update(b"\0")
        snapshots.append(
            CapabilitySnapshot(
                capability_id=capability["capability_id"],
                readiness_level=capability["readiness_level"],
                artifact_count=len(artifacts),
                content_sha256=digest.hexdigest(),
            )
        )
    return tuple(snapshots)


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


def build_h3_readiness_report(
    project_state: dict[str, Any],
    readiness: dict[str, Any],
    *,
    state_sha256: str,
    readiness_sha256: str,
    repository: RepositorySnapshot,
    capabilities: Sequence[CapabilitySnapshot],
) -> dict[str, Any]:
    state = validate_project_state(project_state)
    manifest = validate_h3_readiness(readiness)
    _require(
        manifest["gate_id"] == state["next_gate"],
        "H3 readiness gate does not match current project gate",
    )
    _require(
        tuple(item.capability_id for item in capabilities) == EXPECTED_H3_CAPABILITY_IDS,
        "H3 readiness capability inspection is incomplete",
    )
    stage = next(item for item in state["stages"] if item["stage_id"] == "H3")
    _require(
        stage["status"] == "in_progress" and stage["acceptance"] == "LAB_VERIFIED",
        "H3 project stage is not at the expected pre-field state",
    )
    preflight_ready = repository.baseline_is_ancestor and repository.tracked_worktree_clean
    return {
        "schema": H3_READINESS_REPORT_SCHEMA,
        "status": "gh_h3_readiness_succeeded",
        "gate_id": manifest["gate_id"],
        "gate_status": "BLOCKED_PENDING_FIELD_ACCEPTANCE",
        "implementation_status": manifest["implementation_status"],
        "implementation_ready": True,
        "field_acceptance_status": manifest["field_acceptance_status"],
        "h3_field_accepted": False,
        "capability_count": len(capabilities),
        "capabilities": [asdict(item) for item in capabilities],
        "repository": asdict(repository),
        "state_sha256": state_sha256,
        "readiness_sha256": readiness_sha256,
        "next_action": (
            "H3_PRIVATE_FIELD_ACCEPTANCE_PREFLIGHT"
            if preflight_ready
            else "RESTORE_VERIFIED_CLEAN_REPOSITORY"
        ),
        "ready_for_field_acceptance_preflight": preflight_ready,
        "n2_blocking_gate_ids": list(state["blocking_gates"][1:]),
        "n2_unblocked_by_h3": False,
        "ready_for_live_apply": False,
        "live_action_authorized": False,
        "read_only": True,
        "production_probe_invoked": False,
        "production_execution_invoked": False,
        "authorization_generated": False,
        "credential_material_read": False,
        "current_services_modified": False,
        "node_credentials_delivered": False,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "safety": dict(manifest["safety"]),
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
    readiness = command.add_parser(
        "readiness",
        help="audit the offline H3 implementation chain without live access",
    )
    readiness.add_argument("--repository", type=Path, default=Path.cwd())
    readiness.add_argument("--state", type=Path)
    readiness.add_argument("--manifest", type=Path)
    readiness.add_argument("--require-baseline-ancestor", action="store_true")
    readiness.add_argument("--require-clean", action="store_true")
    readiness.add_argument("--pretty", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repository = args.repository.resolve()
    state_path = args.state.resolve() if args.state else repository / DEFAULT_STATE_RELATIVE_PATH
    try:
        document, state_sha256 = load_project_state(state_path)
        baseline_sha = document["source_baseline"]["repository_sha"]
        snapshot = inspect_repository(repository, baseline_sha)
        if args.command == "status":
            report = build_status_report(
                document,
                state_sha256=state_sha256,
                repository=snapshot,
            )
        else:
            readiness_path = (
                args.manifest.resolve()
                if args.manifest
                else repository / DEFAULT_H3_READINESS_RELATIVE_PATH
            )
            readiness, readiness_sha256 = load_h3_readiness(readiness_path)
            capabilities = inspect_h3_capabilities(repository, readiness)
            report = build_h3_readiness_report(
                document,
                readiness,
                state_sha256=state_sha256,
                readiness_sha256=readiness_sha256,
                repository=snapshot,
                capabilities=capabilities,
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
