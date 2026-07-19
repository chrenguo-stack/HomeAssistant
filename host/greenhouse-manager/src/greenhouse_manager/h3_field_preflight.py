from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .t1_manager_identity_migration_legacy_review_bridge import (
    validate_manager_identity_legacy_review_bridge,
)

REPORT_SCHEMA = "gh.project-state.h3-field-preflight/1"
BRIDGE_PREFIX = "greenhouse-manager-legacy-review-bridge-"
MAX_SCANNED_DIRECTORIES = 4096
_BRIDGE_NAME = re.compile(r"^greenhouse-manager-legacy-review-bridge-[A-Za-z0-9_-]{4,96}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

BridgeValidator = Callable[[str | Path], Mapping[str, Any]]


class H3FieldPreflightError(ValueError):
    """Raised when private H3 evidence cannot be inventoried safely."""


@dataclass(frozen=True, slots=True)
class LegacyReviewBridgeSnapshot:
    bridge_name: str
    name_fingerprint: str
    manifest_sha256: str
    retained_topic_sha256: str
    retained_topic_matches_expected: bool | None


@dataclass(frozen=True, slots=True)
class LegacyReviewBridgeInventory:
    valid_candidates: tuple[LegacyReviewBridgeSnapshot, ...]
    invalid_candidate_count: int
    scanned_directory_count: int


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise H3FieldPreflightError(message)


def _topic_sha256(expected_retained_topic: str | None) -> str | None:
    if expected_retained_topic is None:
        return None
    _require(
        expected_retained_topic.startswith("gh/")
        and "+" not in expected_retained_topic
        and "#" not in expected_retained_topic
        and len(expected_retained_topic.encode("utf-8")) <= 512,
        "expected retained topic must be one exact gh topic",
    )
    return hashlib.sha256(expected_retained_topic.encode("utf-8")).hexdigest()


def _verified_snapshot(
    candidate: Path,
    *,
    expected_topic_sha256: str | None,
    validator: BridgeValidator,
) -> LegacyReviewBridgeSnapshot:
    report = validator(candidate)
    required_false = (
        "ready_for_production_execution",
        "authorization_created",
        "authorization_claimed",
        "current_services_modified",
        "manager_identity_migrated",
        "node_credentials_delivered",
        "anonymous_closure_enabled",
        "secret_values_included",
        "source_paths_included",
    )
    _require(report.get("verified") is True, "legacy review bridge is not verified")
    _require(
        report.get("ready_for_fresh_evidence_chain") is True,
        "legacy review bridge is not ready for a fresh evidence chain",
    )
    _require(
        report.get("preserve_anonymous") is True,
        "legacy review bridge does not preserve anonymous compatibility",
    )
    _require(
        all(report.get(field) is False for field in required_false),
        "legacy review bridge safety binding is invalid",
    )
    manifest_sha256 = report.get("manifest_sha256")
    retained_topic_sha256 = report.get("expected_retained_topic_sha256")
    _require(
        isinstance(manifest_sha256, str) and _SHA256.fullmatch(manifest_sha256) is not None,
        "legacy review bridge manifest fingerprint is invalid",
    )
    _require(
        isinstance(retained_topic_sha256, str)
        and _SHA256.fullmatch(retained_topic_sha256) is not None,
        "legacy review bridge retained topic binding is invalid",
    )
    name = candidate.name
    _require(_BRIDGE_NAME.fullmatch(name) is not None, "legacy review bridge name is invalid")
    return LegacyReviewBridgeSnapshot(
        bridge_name=name,
        name_fingerprint=hashlib.sha256(name.encode("utf-8")).hexdigest()[:16],
        manifest_sha256=manifest_sha256,
        retained_topic_sha256=retained_topic_sha256,
        retained_topic_matches_expected=(
            None if expected_topic_sha256 is None else retained_topic_sha256 == expected_topic_sha256
        ),
    )


def inspect_legacy_review_bridges(
    search_root: str | Path,
    *,
    expected_retained_topic: str | None = None,
    validator: BridgeValidator = validate_manager_identity_legacy_review_bridge,
) -> LegacyReviewBridgeInventory:
    root_input = Path(search_root).expanduser()
    _require(not root_input.is_symlink(), "private evidence search root is missing or unsafe")
    root = root_input.resolve()
    _require(root.is_dir() and not root.is_symlink(), "private evidence search root is missing or unsafe")
    expected_topic_sha256 = _topic_sha256(expected_retained_topic)
    valid: list[LegacyReviewBridgeSnapshot] = []
    invalid = 0
    scanned = 0
    for current, raw_directories, _files in os.walk(root, topdown=True, followlinks=False):
        scanned += 1
        _require(scanned <= MAX_SCANNED_DIRECTORIES, "private evidence directory inventory is too large")
        current_path = Path(current)
        kept: list[str] = []
        for name in sorted(raw_directories):
            candidate = current_path / name
            if candidate.is_symlink():
                continue
            if not name.startswith(BRIDGE_PREFIX):
                kept.append(name)
                continue
            try:
                valid.append(
                    _verified_snapshot(
                        candidate,
                        expected_topic_sha256=expected_topic_sha256,
                        validator=validator,
                    )
                )
            except Exception:
                invalid += 1
        raw_directories[:] = kept
    valid.sort(key=lambda item: item.bridge_name)
    return LegacyReviewBridgeInventory(
        valid_candidates=tuple(valid),
        invalid_candidate_count=invalid,
        scanned_directory_count=scanned,
    )


def build_h3_field_preflight_report(
    readiness_report: Mapping[str, Any],
    inventory: LegacyReviewBridgeInventory,
    *,
    expected_retained_topic_supplied: bool,
) -> dict[str, Any]:
    _require(
        readiness_report.get("status") == "gh_h3_readiness_succeeded"
        and readiness_report.get("implementation_ready") is True
        and readiness_report.get("ready_for_field_acceptance_preflight") is True
        and readiness_report.get("ready_for_live_apply") is False
        and readiness_report.get("live_action_authorized") is False,
        "public H3 readiness gate is not ready for private evidence preflight",
    )
    matching = [
        item
        for item in inventory.valid_candidates
        if item.retained_topic_matches_expected is True
    ]
    ready = expected_retained_topic_supplied and len(matching) == 1
    if ready:
        next_action = "RUN_FRESH_CHAIN_DISCOVER_ONLY"
    elif not expected_retained_topic_supplied:
        next_action = "SUPPLY_EXPECTED_RETAINED_TOPIC"
    else:
        next_action = "RESOLVE_LEGACY_REVIEW_BRIDGE_BINDING"
    selected = asdict(matching[0]) if ready else None
    return {
        "schema": REPORT_SCHEMA,
        "status": "gh_h3_field_preflight_succeeded",
        "gate_id": readiness_report["gate_id"],
        "gate_status": "BLOCKED_PENDING_FIELD_ACCEPTANCE",
        "repository": dict(readiness_report["repository"]),
        "implementation_ready": True,
        "h3_field_accepted": False,
        "expected_retained_topic_supplied": expected_retained_topic_supplied,
        "valid_bridge_candidate_count": len(inventory.valid_candidates),
        "invalid_bridge_candidate_count": inventory.invalid_candidate_count,
        "matching_bridge_candidate_count": len(matching),
        "bridge_candidates": [asdict(item) for item in inventory.valid_candidates],
        "selected_bridge": selected,
        "ready_for_fresh_chain_discovery": ready,
        "ready_for_live_runtime_gate": False,
        "ready_for_live_apply": False,
        "live_action_authorized": False,
        "next_action": next_action,
        "read_only": True,
        "private_evidence_files_modified": False,
        "production_probe_invoked": False,
        "production_execution_invoked": False,
        "authorization_generated": False,
        "authorization_claimed": False,
        "credential_material_read": False,
        "current_services_modified": False,
        "node_credentials_delivered": False,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "source_paths_included": False,
    }
