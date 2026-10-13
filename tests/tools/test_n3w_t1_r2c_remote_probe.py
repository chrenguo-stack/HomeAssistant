from __future__ import annotations

import time

import n3w_t1_r2c_remote_probe as probe
import pytest
from n3w_t1_r2c_evidence_schema import REQUIREMENT_FIELDS, validate_report
from n3w_t1_r2c_readonly_commands import ReadonlyCommandError


def complete_requirement(requirement_id: str) -> dict:
    return {
        "status": "OBSERVED",
        "complete": True,
        "reason_code": None,
        "method_ids": [],
        "provenance": [],
        "fields": {
            name: {"value": None, "status": "OBSERVED"}
            for name in REQUIREMENT_FIELDS[requirement_id]
        },
    }


def bind_complete_collectors(monkeypatch: pytest.MonkeyPatch) -> None:
    stable_analysis = {
        "status": "OBSERVED",
        "main_sha256": "a" * 64,
        "files": [{"role": "main", "sha256": "a" * 64, "depth": 0}],
        "helper_dependencies": [],
        "config_source_lines": [{"file_role": "main", "line": 1}],
        "referenced_config_keys": ["SET_HOSTNAME"],
        "unresolved": [],
    }
    monkeypatch.setattr(
        probe,
        "analyze_firstrun_tree",
        lambda _root: stable_analysis,
    )
    monkeypatch.setattr(
        probe,
        "_config_fingerprint",
        lambda _root: ("OBSERVED", "b" * 64),
    )
    for index in range(1, 10):
        requirement_id = f"E{index}"

        def collector(_root, requirement_id=requirement_id, **_kwargs):
            return complete_requirement(requirement_id)

        monkeypatch.setattr(probe, f"collect_e{index}", collector)


def report(monkeypatch: pytest.MonkeyPatch) -> dict:
    bind_complete_collectors(monkeypatch)
    monkeypatch.setattr(
        probe,
        "_read_boot_id",
        lambda _root: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    )
    return probe.collect_report(
        root="/",
        execution_id="r2c-test-1",
        source_head="a" * 40,
        probe_sha256="b" * 64,
        contract_sha256="c" * 64,
        grant_id="grant-test-1",
        target_binding_token_sha256="d" * 64,
    )


def test_complete_collection_builds_valid_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = report(monkeypatch)

    validate_report(document)
    assert document["capture_status"] == "COMPLETE"
    assert document["static_review_status"] == "NOT_EXECUTED"
    assert document["stop_reasons"] == []
    assert document["target_binding"]["same_boot"] is True
    assert document["boundaries"]["t1_access"] is True
    assert document["boundaries"]["intentional_target_write"] is False
    assert document["os_identity_semantics_proven"] is False
    assert document["controlled_clone_boot_required"] is True
    assert document["disk_capture_ready"] is False


def test_target_drift_stops_later_collectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        probe,
        "_read_boot_id",
        lambda _root: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    )
    drift = complete_requirement("E1")
    drift["status"] = "ERROR"
    drift["complete"] = False
    drift["reason_code"] = "STOP_TARGET_DRIFT"
    monkeypatch.setattr(probe, "collect_e1", lambda _root, runner=None: drift)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("later collector must not run after target drift")

    monkeypatch.setattr(probe, "collect_e2", forbidden)
    document = probe.collect_report(
        root="/",
        execution_id="r2c-test-2",
        source_head="a" * 40,
        probe_sha256="b" * 64,
        contract_sha256="c" * 64,
        grant_id="grant-test-2",
        target_binding_token_sha256="d" * 64,
    )

    assert document["capture_status"] == "FAILED"
    assert "STOP_TARGET_DRIFT" in document["stop_reasons"]
    assert document["requirements"]["E2"]["status"] == "NOT_EXECUTED"
    assert document["requirements"]["E2"]["reason_code"] == "STOP_TARGET_DRIFT"


def test_boot_change_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bind_complete_collectors(monkeypatch)
    boot_ids = iter(
        (
            "cccccccc-cccc-cccc-cccc-cccccccccccc",
            "dddddddd-dddd-dddd-dddd-dddddddddddd",
        )
    )
    monkeypatch.setattr(probe, "_read_boot_id", lambda _root: next(boot_ids))

    document = probe.collect_report(
        root="/",
        execution_id="r2c-test-3",
        source_head="a" * 40,
        probe_sha256="b" * 64,
        contract_sha256="c" * 64,
        grant_id="grant-test-3",
        target_binding_token_sha256="d" * 64,
    )

    assert document["capture_status"] == "INCOMPLETE"
    assert document["target_binding"]["same_boot"] is False
    assert "STOP_TARGET_CHANGED" in document["stop_reasons"]


def test_budget_runner_refuses_command_after_deadline() -> None:
    runner = probe.BudgetRunner(time.monotonic() - 1)

    with pytest.raises(ReadonlyCommandError, match="remote_total_budget_exhausted"):
        runner("C1_ARCH")

    assert runner.exhausted is True


def test_probe_rejects_invalid_binding_inputs() -> None:
    with pytest.raises(probe.ProbeError, match="execution_id_invalid"):
        probe.collect_report(
            root="/",
            execution_id="bad value",
            source_head="a" * 40,
            probe_sha256="b" * 64,
            contract_sha256="c" * 64,
            grant_id="grant-test-4",
            target_binding_token_sha256="d" * 64,
        )


def test_firstrun_source_change_marks_e2_e3_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bind_complete_collectors(monkeypatch)
    analyses = iter(
        (
            {
                "status": "OBSERVED",
                "main_sha256": "1" * 64,
                "files": [{"role": "main", "sha256": "1" * 64, "depth": 0}],
                "helper_dependencies": [],
                "config_source_lines": [{"file_role": "main", "line": 1}],
                "referenced_config_keys": ["SET_HOSTNAME"],
                "unresolved": [],
            },
            {
                "status": "OBSERVED",
                "main_sha256": "2" * 64,
                "files": [{"role": "main", "sha256": "2" * 64, "depth": 0}],
                "helper_dependencies": [],
                "config_source_lines": [{"file_role": "main", "line": 1}],
                "referenced_config_keys": ["SET_HOSTNAME"],
                "unresolved": [],
            },
        )
    )
    monkeypatch.setattr(probe, "analyze_firstrun_tree", lambda _root: next(analyses))
    monkeypatch.setattr(
        probe,
        "_config_fingerprint",
        lambda _root: ("OBSERVED", "b" * 64),
    )
    monkeypatch.setattr(
        probe,
        "_read_boot_id",
        lambda _root: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
    )

    document = probe.collect_report(
        root="/",
        execution_id="r2c-test-continuity",
        source_head="a" * 40,
        probe_sha256="b" * 64,
        contract_sha256="c" * 64,
        grant_id="grant-test-continuity",
        target_binding_token_sha256="d" * 64,
    )

    assert document["requirements"]["E2"]["status"] == "ERROR"
    assert document["requirements"]["E3"]["status"] == "ERROR"
    assert document["requirements"]["E2"]["reason_code"] == "STOP_TARGET_CHANGED"
    assert "STOP_TARGET_CHANGED" in document["stop_reasons"]


def test_firstrun_continuity_is_recorded_privately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = report(monkeypatch)

    for requirement_id in ("E2", "E3"):
        provenance = document["requirements"][requirement_id]["provenance"]
        assert provenance[-1]["continuity"] == "PASS"
        assert len(provenance[-1]["source_set_sha256"]) == 64
