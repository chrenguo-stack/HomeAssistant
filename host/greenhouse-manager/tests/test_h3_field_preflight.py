from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from greenhouse_manager import h3_field_preflight as module

TOPIC = "gh/v1/greenhouse-01/state/gh-n1-a9f2f8/telemetry"


def _report(topic: str = TOPIC) -> dict[str, object]:
    return {
        "verified": True,
        "manifest_sha256": "a" * 64,
        "expected_retained_topic_sha256": hashlib.sha256(topic.encode()).hexdigest(),
        "ready_for_fresh_evidence_chain": True,
        "ready_for_production_execution": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "read_only_live_services": True,
        "current_services_modified": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "source_paths_included": False,
    }


def _bridge(root: Path, suffix: str) -> Path:
    bridge = root / f"greenhouse-manager-legacy-review-bridge-{suffix}"
    bridge.mkdir()
    return bridge


def _readiness(*, preflight_ready: bool = True) -> dict[str, object]:
    return {
        "status": "gh_h3_readiness_succeeded",
        "gate_id": "H3_MANAGER_IDENTITY_FIELD_ACCEPTANCE",
        "implementation_ready": True,
        "ready_for_field_acceptance_preflight": preflight_ready,
        "ready_for_live_apply": False,
        "live_action_authorized": False,
        "repository": {
            "head_sha": "b" * 40,
            "baseline_is_ancestor": True,
            "tracked_worktree_clean": True,
        },
    }


def test_inventory_verifies_and_redacts_one_bridge(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path, "20260719T120000Z-safe1")

    inventory = module.inspect_legacy_review_bridges(
        tmp_path,
        validator=lambda candidate: _report() if candidate == bridge else {},
    )

    assert inventory.invalid_candidate_count == 0
    assert len(inventory.valid_candidates) == 1
    candidate = inventory.valid_candidates[0]
    assert candidate.bridge_name == bridge.name
    assert len(candidate.name_fingerprint) == 16
    assert candidate.retained_topic_matches_expected is None


def test_expected_topic_selects_exactly_one_bridge(tmp_path: Path) -> None:
    _bridge(tmp_path, "20260719T120000Z-safe1")

    inventory = module.inspect_legacy_review_bridges(
        tmp_path,
        expected_retained_topic=TOPIC,
        validator=lambda _candidate: _report(),
    )
    report = module.build_h3_field_preflight_report(
        _readiness(),
        inventory,
        expected_retained_topic_supplied=True,
    )

    assert report["ready_for_fresh_chain_discovery"] is True
    assert report["matching_bridge_candidate_count"] == 1
    assert report["next_action"] == "RUN_FRESH_CHAIN_DISCOVER_ONLY"
    assert report["selected_bridge"]["manifest_sha256"] == "a" * 64
    serialized = json.dumps(report)
    assert TOPIC not in serialized
    assert str(tmp_path) not in serialized
    assert report["ready_for_live_runtime_gate"] is False
    assert report["ready_for_live_apply"] is False
    assert report["live_action_authorized"] is False
    assert report["production_probe_invoked"] is False
    assert report["production_execution_invoked"] is False
    assert report["authorization_generated"] is False
    assert report["authorization_claimed"] is False
    assert report["credential_material_read"] is False
    assert report["current_services_modified"] is False
    assert report["node_credentials_delivered"] is False
    assert report["anonymous_closure_enabled"] is False
    assert report["secret_values_included"] is False
    assert report["source_paths_included"] is False


def test_missing_topic_stays_at_input_collection_gate(tmp_path: Path) -> None:
    _bridge(tmp_path, "20260719T120000Z-safe1")
    inventory = module.inspect_legacy_review_bridges(
        tmp_path,
        validator=lambda _candidate: _report(),
    )

    report = module.build_h3_field_preflight_report(
        _readiness(),
        inventory,
        expected_retained_topic_supplied=False,
    )

    assert report["ready_for_fresh_chain_discovery"] is False
    assert report["next_action"] == "SUPPLY_EXPECTED_RETAINED_TOPIC"


def test_duplicate_matching_bridges_fail_closed(tmp_path: Path) -> None:
    _bridge(tmp_path, "20260719T120000Z-safe1")
    _bridge(tmp_path, "20260719T120100Z-safe2")
    inventory = module.inspect_legacy_review_bridges(
        tmp_path,
        expected_retained_topic=TOPIC,
        validator=lambda _candidate: _report(),
    )

    report = module.build_h3_field_preflight_report(
        _readiness(),
        inventory,
        expected_retained_topic_supplied=True,
    )

    assert report["matching_bridge_candidate_count"] == 2
    assert report["ready_for_fresh_chain_discovery"] is False
    assert report["selected_bridge"] is None
    assert report["next_action"] == "RESOLVE_LEGACY_REVIEW_BRIDGE_BINDING"


def test_invalid_bridge_is_counted_without_leaking_exception(tmp_path: Path) -> None:
    _bridge(tmp_path, "20260719T120000Z-bad1")

    def reject(_candidate: Path) -> dict[str, object]:
        raise RuntimeError("private path and secret-shaped diagnostic")

    inventory = module.inspect_legacy_review_bridges(tmp_path, validator=reject)

    assert inventory.valid_candidates == ()
    assert inventory.invalid_candidate_count == 1


def test_search_root_symlink_is_rejected(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)

    with pytest.raises(module.H3FieldPreflightError, match="missing or unsafe"):
        module.inspect_legacy_review_bridges(alias, validator=lambda _candidate: _report())


@pytest.mark.parametrize("topic", ["not-gh/topic", "gh/+/telemetry", "gh/#"])
def test_expected_topic_must_be_exact(topic: str, tmp_path: Path) -> None:
    with pytest.raises(module.H3FieldPreflightError, match="exact gh topic"):
        module.inspect_legacy_review_bridges(
            tmp_path,
            expected_retained_topic=topic,
            validator=lambda _candidate: _report(),
        )


def test_public_readiness_must_be_clean_and_ready(tmp_path: Path) -> None:
    inventory = module.inspect_legacy_review_bridges(
        tmp_path,
        validator=lambda _candidate: _report(),
    )

    with pytest.raises(module.H3FieldPreflightError, match="public H3 readiness"):
        module.build_h3_field_preflight_report(
            _readiness(preflight_ready=False),
            inventory,
            expected_retained_topic_supplied=False,
        )
