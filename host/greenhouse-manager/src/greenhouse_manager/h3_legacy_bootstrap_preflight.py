from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .t1_manager_identity_migration_postrollback_audit import (
    ManagerPostrollbackAuditError,
    validate_manager_postrollback_static_artifacts,
)

REPORT_SCHEMA = "gh.project-state.h3-legacy-bootstrap-preflight/1"
MAX_SCANNED_DIRECTORIES = 4096
MAX_CANDIDATE_DIRECTORIES = 32


class H3LegacyBootstrapPreflightError(ValueError):
    """Raised when legacy static evidence cannot be inventoried safely."""


@dataclass(frozen=True, slots=True)
class LegacyStaticPairSnapshot:
    pair_fingerprint: str
    transaction_journal_sha256: str
    rollback_manifest_sha256: str
    rollback_archive_sha256: str


@dataclass(frozen=True, slots=True)
class LegacyStaticEvidenceInventory:
    transaction_candidate_count: int
    execution_candidate_count: int
    valid_pairs: tuple[LegacyStaticPairSnapshot, ...]
    rejected_pair_count: int
    scanned_directory_count: int


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise H3LegacyBootstrapPreflightError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _pair_snapshot(transaction: Path, execution: Path) -> LegacyStaticPairSnapshot:
    artifacts = validate_manager_postrollback_static_artifacts(transaction, execution)
    journal_sha = _sha256(artifacts.workspace / "journal.json")
    manifest_sha = _sha256(artifacts.execution / "fresh-rollback-manifest.json")
    archive_sha = _sha256(artifacts.archive)
    fingerprint = hashlib.sha256(f"{journal_sha}\0{manifest_sha}\0{archive_sha}".encode("ascii")).hexdigest()[
        :16
    ]
    return LegacyStaticPairSnapshot(
        pair_fingerprint=fingerprint,
        transaction_journal_sha256=journal_sha,
        rollback_manifest_sha256=manifest_sha,
        rollback_archive_sha256=archive_sha,
    )


def inspect_legacy_static_evidence(
    search_root: str | Path,
) -> LegacyStaticEvidenceInventory:
    root_input = Path(search_root).expanduser()
    _require(
        not root_input.is_symlink(),
        "private evidence search root is missing or unsafe",
    )
    root = root_input.resolve()
    _require(
        root.is_dir() and not root.is_symlink(),
        "private evidence search root is missing or unsafe",
    )

    transactions: list[Path] = []
    executions: list[Path] = []
    scanned = 0
    for current, raw_directories, raw_files in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        scanned += 1
        _require(
            scanned <= MAX_SCANNED_DIRECTORIES,
            "private evidence directory inventory is too large",
        )
        current_path = Path(current)
        raw_directories[:] = [
            name for name in sorted(raw_directories) if not (current_path / name).is_symlink()
        ]
        files = set(raw_files)
        if "journal.json" in files:
            transactions.append(current_path)
        if {
            "fresh-rollback-manifest.json",
            "fresh-manager-rollback.tar.gz",
        }.issubset(files):
            executions.append(current_path)
        _require(
            len(transactions) <= MAX_CANDIDATE_DIRECTORIES and len(executions) <= MAX_CANDIDATE_DIRECTORIES,
            "private evidence candidate inventory is too large",
        )

    valid: list[LegacyStaticPairSnapshot] = []
    rejected = 0
    for transaction in transactions:
        for execution in executions:
            try:
                snapshot = _pair_snapshot(transaction, execution)
            except (ManagerPostrollbackAuditError, OSError, UnicodeError, ValueError):
                rejected += 1
                continue
            valid.append(snapshot)
    ordered = tuple(sorted(valid, key=lambda item: item.pair_fingerprint))
    return LegacyStaticEvidenceInventory(
        transaction_candidate_count=len(transactions),
        execution_candidate_count=len(executions),
        valid_pairs=ordered,
        rejected_pair_count=rejected,
        scanned_directory_count=scanned,
    )


def build_h3_legacy_bootstrap_preflight_report(
    readiness_report: Mapping[str, Any],
    inventory: LegacyStaticEvidenceInventory,
) -> dict[str, Any]:
    _require(
        readiness_report.get("status") == "gh_h3_readiness_succeeded"
        and readiness_report.get("implementation_ready") is True
        and readiness_report.get("ready_for_field_acceptance_preflight") is True
        and readiness_report.get("ready_for_live_apply") is False
        and readiness_report.get("live_action_authorized") is False,
        "public H3 readiness gate is not ready for legacy bootstrap preflight",
    )
    pair_count = len(inventory.valid_pairs)
    if pair_count == 1:
        next_action = "REVIEW_READ_ONLY_LEGACY_ROLLBACK_AUDIT_SCOPE"
    elif pair_count == 0:
        next_action = "LOCATE_LEGACY_ROLLBACK_STATIC_EVIDENCE"
    else:
        next_action = "RESOLVE_LEGACY_ROLLBACK_STATIC_EVIDENCE_AMBIGUITY"
    return {
        "schema": REPORT_SCHEMA,
        "status": "gh_h3_legacy_bootstrap_preflight_succeeded",
        "gate_id": readiness_report["gate_id"],
        "gate_status": "BLOCKED_PENDING_FIELD_ACCEPTANCE",
        "repository": dict(readiness_report["repository"]),
        "implementation_ready": True,
        "h3_field_accepted": False,
        "transaction_candidate_count": inventory.transaction_candidate_count,
        "execution_candidate_count": inventory.execution_candidate_count,
        "scanned_directory_count": inventory.scanned_directory_count,
        "valid_static_pair_count": pair_count,
        "rejected_pair_count": inventory.rejected_pair_count,
        "static_pairs": [asdict(item) for item in inventory.valid_pairs],
        "selected_static_pair": (asdict(inventory.valid_pairs[0]) if pair_count == 1 else None),
        "ready_for_read_only_legacy_rollback_audit_scope_review": pair_count == 1,
        "ready_for_live_runtime_gate": False,
        "ready_for_live_apply": False,
        "live_action_authorized": False,
        "next_action": next_action,
        "read_only": True,
        "private_evidence_files_modified": False,
        "live_services_inspected": False,
        "broker_operation_performed": False,
        "production_probe_invoked": False,
        "production_execution_invoked": False,
        "authorization_generated": False,
        "authorization_claimed": False,
        "operator_decision_recorded": False,
        "credential_material_read": False,
        "current_services_modified": False,
        "node_credentials_delivered": False,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "source_paths_included": False,
    }
