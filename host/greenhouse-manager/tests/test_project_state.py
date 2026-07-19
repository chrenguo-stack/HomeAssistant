from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from greenhouse_manager import project_state as module

REPOSITORY = Path(__file__).resolve().parents[3]
STATE_PATH = REPOSITORY / "project-state/current-baseline.json"
READINESS_PATH = REPOSITORY / "project-state/h3-readiness.json"


def _state() -> dict[str, object]:
    value = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _readiness() -> dict[str, object]:
    value = json.loads(READINESS_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _snapshot(**overrides: object) -> module.RepositorySnapshot:
    values: dict[str, object] = {
        "head_sha": "b440652558b02f19fb33b1cdbf4cd0ebe893a285",
        "baseline_is_ancestor": True,
        "tracked_worktree_clean": True,
    }
    values.update(overrides)
    return module.RepositorySnapshot(**values)  # type: ignore[arg-type]


def test_repository_project_state_is_valid_and_fail_closed() -> None:
    document, state_sha = module.load_project_state(STATE_PATH)

    assert len(state_sha) == 64
    assert document["active_stage"] == "H3"
    assert document["next_gate"] == "H3_MANAGER_IDENTITY_FIELD_ACCEPTANCE"
    assert document["m2_board_matrix"]["passed_case_count"] == 50
    assert document["safety"] == {
        "production_execution_enabled": False,
        "anonymous_closure_enabled": False,
        "node_production_credentials_delivered": False,
        "ready_for_live_apply": False,
        "ready_for_anonymous_closure": False,
    }


def test_status_report_exposes_one_h3_n2_baseline_without_mutation() -> None:
    report = module.build_status_report(
        _state(),
        state_sha256="a" * 64,
        repository=_snapshot(),
    )

    assert report["status"] == "gh_project_state_status_succeeded"
    assert report["completed_stage_ids"] == ["D0", "H2", "N0", "N1"]
    assert report["in_progress_stage_ids"] == ["H0", "H1", "H3", "N2", "S1"]
    assert report["not_started_stage_ids"] == ["N3-W", "N3-L"]
    assert report["head_matches_source_baseline"] is True
    assert report["read_only"] is True
    assert report["production_execution_invoked"] is False
    assert report["current_services_modified"] is False
    assert report["node_credentials_delivered"] is False
    assert report["anonymous_closure_enabled"] is False
    assert report["secret_values_included"] is False


def test_repository_h3_readiness_manifest_is_valid_and_fail_closed() -> None:
    document, readiness_sha = module.load_h3_readiness(READINESS_PATH)

    assert len(readiness_sha) == 64
    assert document["gate_id"] == "H3_MANAGER_IDENTITY_FIELD_ACCEPTANCE"
    assert document["implementation_status"] == "CODE_COMPLETE"
    assert document["field_acceptance_status"] == "PENDING"
    assert len(document["capabilities"]) == 13
    assert not any(document["safety"].values())


def test_h3_readiness_inspects_complete_tracked_capability_chain() -> None:
    snapshots = module.inspect_h3_capabilities(REPOSITORY, _readiness())

    assert tuple(item.capability_id for item in snapshots) == module.EXPECTED_H3_CAPABILITY_IDS
    assert all(item.artifact_count >= 3 for item in snapshots)
    assert all(len(item.content_sha256) == 64 for item in snapshots)
    assert {item.readiness_level for item in snapshots} == {"CODE_COMPLETE", "LAB_VERIFIED"}


def test_h3_readiness_report_separates_implementation_from_field_acceptance() -> None:
    capabilities = module.inspect_h3_capabilities(REPOSITORY, _readiness())
    report = module.build_h3_readiness_report(
        _state(),
        _readiness(),
        state_sha256="a" * 64,
        readiness_sha256="b" * 64,
        repository=_snapshot(head_sha="c" * 40),
        capabilities=capabilities,
    )

    assert report["status"] == "gh_h3_readiness_succeeded"
    assert report["gate_status"] == "BLOCKED_PENDING_FIELD_ACCEPTANCE"
    assert report["implementation_ready"] is True
    assert report["h3_field_accepted"] is False
    assert report["ready_for_field_acceptance_preflight"] is True
    assert report["n2_blocking_gate_ids"] == [
        "N2_END_TO_END_SECURE_PAIRING",
        "N2_MULTI_NODE_AND_72_HOUR_ACCEPTANCE",
    ]
    assert report["n2_unblocked_by_h3"] is False
    assert report["ready_for_live_apply"] is False
    assert report["live_action_authorized"] is False


def test_h3_readiness_does_not_offer_field_preflight_from_dirty_repository() -> None:
    capabilities = module.inspect_h3_capabilities(REPOSITORY, _readiness())
    report = module.build_h3_readiness_report(
        _state(),
        _readiness(),
        state_sha256="a" * 64,
        readiness_sha256="b" * 64,
        repository=_snapshot(tracked_worktree_clean=False),
        capabilities=capabilities,
    )

    assert report["implementation_ready"] is True
    assert report["ready_for_field_acceptance_preflight"] is False
    assert report["next_action"] == "RESTORE_VERIFIED_CLEAN_REPOSITORY"
    assert report["ready_for_live_apply"] is False
    assert report["production_probe_invoked"] is False
    assert report["production_execution_invoked"] is False
    assert report["authorization_generated"] is False
    assert report["credential_material_read"] is False
    assert report["current_services_modified"] is False
    assert report["node_credentials_delivered"] is False
    assert report["anonymous_closure_enabled"] is False
    assert report["secret_values_included"] is False


def test_h3_readiness_rejects_capability_set_drift() -> None:
    document = copy.deepcopy(_readiness())
    capabilities = document["capabilities"]
    assert isinstance(capabilities, list)
    capabilities[0], capabilities[1] = capabilities[1], capabilities[0]

    with pytest.raises(module.ProjectStateError, match="capability set or ordering"):
        module.validate_h3_readiness(document)


def test_h3_readiness_rejects_any_enabled_capability() -> None:
    document = copy.deepcopy(_readiness())
    document["safety"]["production_probe_enabled"] = True  # type: ignore[index]

    with pytest.raises(module.ProjectStateError, match="schema validation failed"):
        module.validate_h3_readiness(document)


def test_h3_readiness_rejects_unsafe_artifact_path() -> None:
    with pytest.raises(module.ProjectStateError, match="artifact path is unsafe"):
        module._public_artifact(REPOSITORY, "../outside.py")


def test_h3_readiness_rejects_missing_source_marker() -> None:
    document = copy.deepcopy(_readiness())
    capabilities = document["capabilities"]
    assert isinstance(capabilities, list)
    capabilities[0]["required_markers"] = ["marker-that-does-not-exist"]

    with pytest.raises(module.ProjectStateError, match="source marker is missing"):
        module.inspect_h3_capabilities(REPOSITORY, document)


def test_cli_h3_readiness_is_offline_and_does_not_authorize_live_work(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = module.main(
        [
            "m2",
            "readiness",
            "--repository",
            str(REPOSITORY),
            "--state",
            str(STATE_PATH),
            "--manifest",
            str(READINESS_PATH),
        ]
    )

    assert result == 0
    report = json.loads(capsys.readouterr().out)
    assert report["read_only"] is True
    assert report["implementation_ready"] is True
    assert report["h3_field_accepted"] is False
    assert report["ready_for_live_apply"] is False
    assert report["live_action_authorized"] is False


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("production_execution_enabled", "schema validation failed"),
        ("anonymous_closure_enabled", "schema validation failed"),
        ("node_production_credentials_delivered", "schema validation failed"),
        ("ready_for_live_apply", "schema validation failed"),
        ("ready_for_anonymous_closure", "schema validation failed"),
    ],
)
def test_rejects_any_enabled_safety_gate(field: str, message: str) -> None:
    document = copy.deepcopy(_state())
    document["safety"][field] = True  # type: ignore[index]

    with pytest.raises(module.ProjectStateError, match=message):
        module.validate_project_state(document)


def test_rejects_wireless_stage_started_before_h3_n2_close() -> None:
    document = copy.deepcopy(_state())
    stages = document["stages"]
    assert isinstance(stages, list)
    wireless = next(item for item in stages if item["stage_id"] == "N3-W")
    wireless["status"] = "in_progress"
    wireless["acceptance"] = "CODE_COMPLETE"

    with pytest.raises(module.ProjectStateError, match="N3-W cannot start"):
        module.validate_project_state(document)


def test_cli_status_reports_head_drift_without_authorizing_work(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        module,
        "inspect_repository",
        lambda repository, baseline_sha: _snapshot(
            head_sha="c" * 40,
            baseline_is_ancestor=True,
            tracked_worktree_clean=False,
        ),
    )

    result = module.main(["m2", "status", "--repository", str(REPOSITORY)])

    assert result == 0
    report = json.loads(capsys.readouterr().out)
    assert report["head_matches_source_baseline"] is False
    assert report["repository"]["tracked_worktree_clean"] is False
    assert report["safety"]["production_execution_enabled"] is False


def test_cli_require_baseline_ancestor_fails_closed_on_unrelated_head(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        module,
        "inspect_repository",
        lambda repository, baseline_sha: _snapshot(
            head_sha="c" * 40,
            baseline_is_ancestor=False,
        ),
    )

    result = module.main(
        [
            "m2",
            "status",
            "--repository",
            str(REPOSITORY),
            "--require-baseline-ancestor",
        ]
    )

    assert result == 2
    assert "not an ancestor" in capsys.readouterr().err
