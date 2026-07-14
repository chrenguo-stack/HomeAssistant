from __future__ import annotations

import json
import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from manager_execution_preparation_fixtures import build_preparation, preclaim_report

from greenhouse_manager.t1_manager_identity_migration_execution_preparation import (
    ManagerIdentityExecutionPreparationError,
    prepare_manager_identity_execution,
    verify_manager_identity_execution_preparation,
)

NOW = datetime(2026, 7, 13, 4, 30, tzinfo=UTC)


class FakeRunner:
    pass


def _prepare(
    tmp_path: Path,
    *,
    include_environment: bool,
    gate_builder=None,
) -> tuple[dict[str, object], Path, Path, Path]:
    preparation, driver, output, gate = build_preparation(
        tmp_path,
        include_environment=include_environment,
    )

    def stable_gate(*_args: object, **_kwargs: object) -> dict[str, object]:
        return gate

    report = prepare_manager_identity_execution(
        driver,
        preparation,
        output,
        freshness_seconds=900,
        runner=FakeRunner(),
        now=NOW,
        token_factory=lambda: "testing",
        live_gate_builder=gate_builder or stable_gate,
        preclaim_probe=preclaim_report,
    )
    package = output / str(report["execution_preparation_name"])
    return report, package, preparation, driver


@pytest.mark.parametrize("include_environment", [False, True])
def test_prepares_private_verified_fresh_rollback(
    tmp_path: Path,
    include_environment: bool,
) -> None:
    report, package, _preparation, _driver = _prepare(
        tmp_path,
        include_environment=include_environment,
    )

    assert report["prepared"] is True
    assert report["fresh_rollback_captured"] is True
    assert report["fresh_rollback_verified"] is True
    assert report["execution_preparation_ready"] is True
    assert report["preclaim_candidate_probe_passed"] is True
    assert report["authorization_created"] is False
    assert report["execution_enabled"] is False
    assert report["apply_enabled"] is False
    assert report["manager_identity_migrated"] is False
    assert report["node_credentials_delivered"] is False
    assert report["preserve_anonymous"] is True
    assert report["anonymous_closure_enabled"] is False
    assert report["secret_values_included"] is False
    assert report["source_paths_included"] is False
    assert package.stat().st_mode & 0o077 == 0
    assert all(
        path.stat().st_mode & 0o777 == 0o600
        for path in package.iterdir()
        if path.is_file()
    )

    verified = verify_manager_identity_execution_preparation(
        package,
        now=NOW,
        require_fresh=True,
    )
    assert verified["verified"] is True
    assert verified["fresh_now"] is True

    with tarfile.open(package / "fresh-manager-rollback.tar.gz", "r:gz") as archive:
        names = set(archive.getnames())
    assert "rollback-manifest.json" in names
    assert "compose/config/000.yaml" in names
    assert ("compose/environment/.env" in names) is include_environment

    preclaim = json.loads(
        (package / "preclaim-candidate-probe.json").read_text(encoding="utf-8")
    )
    assert preclaim["network_none"] is True
    assert preclaim["password_owned_by_runtime_user"] is True
    rollback = json.loads(
        (package / "fresh-rollback-manifest.json").read_text(encoding="utf-8")
    )
    assert rollback["manager_only"] is True
    assert rollback["preserve_anonymous"] is True
    assert rollback["anonymous_closure_enabled"] is False
    assert rollback["manager_runtime_uid"] == 999
    assert rollback["manager_runtime_gid"] == 999
    directory_targets = [
        Path(value) for value in rollback["created_directory_targets"]
    ]
    secret_root = Path(rollback["manager_secret_root"])
    assert directory_targets
    assert all(
        target == secret_root or target.is_relative_to(secret_root)
        for target in directory_targets
    )
    assert Path(rollback["compose_working_directory"]) not in directory_targets
    assert rollback["preclaim_authentication_environment_baseline"] == {
        "GH_MQTT_USERNAME": {"present": False, "nonempty": False},
        "GH_MQTT_PASSWORD": {"present": False, "nonempty": False},
        "GH_MQTT_PASSWORD_FILE": {"present": False, "nonempty": False},
    }
    assert rollback["preclaim_candidate_probe_sha256"]

    serialized = json.dumps(report)
    assert str(tmp_path) not in serialized


def test_rejects_live_gate_drift_during_capture(tmp_path: Path) -> None:
    preparation, driver, output, first_gate = build_preparation(
        tmp_path,
        include_environment=False,
    )
    second_gate = dict(first_gate)
    second_gate["live_binding_sha256"] = "5" * 64
    calls = 0

    def drifting_gate(*_args: object, **_kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return first_gate if calls == 1 else second_gate

    with pytest.raises(
        ManagerIdentityExecutionPreparationError,
        match="live runtime gate drifted",
    ):
        prepare_manager_identity_execution(
            driver,
            preparation,
            output,
            runner=FakeRunner(),
            now=NOW,
            token_factory=lambda: "testing",
            live_gate_builder=drifting_gate,
            preclaim_probe=preclaim_report,
        )


def test_rejects_compose_drift_after_preparation(tmp_path: Path) -> None:
    preparation, driver, output, gate = build_preparation(
        tmp_path,
        include_environment=False,
    )
    runtime = json.loads(
        (preparation / "manager-runtime-binding.json").read_text(encoding="utf-8")
    )
    compose_path = Path(runtime["compose"]["config_files"][0]["path"])
    compose_path.write_text("changed\n", encoding="utf-8")

    with pytest.raises(
        ManagerIdentityExecutionPreparationError,
        match="Compose file metadata drifted",
    ):
        prepare_manager_identity_execution(
            driver,
            preparation,
            output,
            runner=FakeRunner(),
            now=NOW,
            token_factory=lambda: "testing",
            live_gate_builder=lambda *_args, **_kwargs: gate,
            preclaim_probe=preclaim_report,
        )


def test_rejects_output_inside_compose_directory(tmp_path: Path) -> None:
    preparation, driver, _output, gate = build_preparation(
        tmp_path,
        include_environment=False,
    )
    runtime = json.loads(
        (preparation / "manager-runtime-binding.json").read_text(encoding="utf-8")
    )
    compose_root = Path(runtime["compose"]["working_dir"])
    overlapping = compose_root / "greenhouse-m2-manager-execution-preparations.test"

    with pytest.raises(
        ManagerIdentityExecutionPreparationError,
        match="overlaps a protected path",
    ):
        prepare_manager_identity_execution(
            driver,
            preparation,
            overlapping,
            runner=FakeRunner(),
            now=NOW,
            token_factory=lambda: "testing",
            live_gate_builder=lambda *_args, **_kwargs: gate,
            preclaim_probe=preclaim_report,
        )


def test_rejects_expired_execution_preparation(tmp_path: Path) -> None:
    _report, package, _preparation, _driver = _prepare(
        tmp_path,
        include_environment=False,
    )

    with pytest.raises(
        ManagerIdentityExecutionPreparationError,
        match="has expired",
    ):
        verify_manager_identity_execution_preparation(
            package,
            now=NOW + timedelta(seconds=901),
            require_fresh=True,
        )

    stale = verify_manager_identity_execution_preparation(
        package,
        now=NOW + timedelta(seconds=901),
        require_fresh=False,
    )
    assert stale["verified"] is True
    assert stale["fresh_now"] is False
