from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

import greenhouse_manager.t1_migration_stage_rehearsal as stage_rehearsal
from greenhouse_manager.t1_migration_stage import MigrationStageError
from greenhouse_manager.t1_shadow import ShadowError


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: str, mode: int = 0o600) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    path.chmod(mode)
    return path


class InspectRunner:
    def __init__(self, *, residue: bool = False) -> None:
        self.residue = residue
        self.calls: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.calls.append(command)
        if command[:2] == ("docker", "inspect"):
            return (0, "present") if self.residue else (1, "missing")
        return (1, "unexpected")


def _stage_fixture(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    stage = tmp_path / "greenhouse-t1-auth-stage-test"
    stage.mkdir(mode=0o700)
    rollback = _write(tmp_path / "sources/rollback.tar.gz", "rollback")
    source_package = _write(tmp_path / "sources/migration.tar.gz", "package")
    staged_package = _write(stage / "source/migration.tar.gz", "package")
    live_compose = _write(
        tmp_path / "live/docker-compose.yml",
        "services: {}\n",
        0o644,
    )
    _write(
        stage / "activation-plan.json",
        json.dumps(
            {
                "activation_enabled": False,
                "current_services_modified": False,
                "active_paths_modified": False,
                "preserve_anonymous": True,
                "anonymous_closure_enabled": False,
            }
        ),
    )
    manifest = {
        "schema": "gh.m2.t1-auth-migration-stage/1",
        "activation_enabled": False,
        "current_services_modified": False,
        "active_paths_modified": False,
        "source_rollback": {
            "path": str(rollback),
            "archive": rollback.name,
            "sha256": _sha256(rollback),
        },
        "source_migration_package": {
            "path": str(source_package),
            "package": source_package.name,
            "sha256": _sha256(source_package),
            "staged_copy": str(staged_package.relative_to(stage)),
        },
        "files": [
            {
                "path": "baseline/deployments/01/config.yml",
                "source_path": str(live_compose),
                "sha256": _sha256(live_compose),
            }
        ],
    }
    _write(
        stage / "stage-manifest.json",
        json.dumps(manifest, sort_keys=True),
    )
    return stage, manifest


def _success_result() -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-auth-migration-rehearsal/1",
        "archive": "rollback.tar.gz",
        "package": "migration.tar.gz",
        "package_sha256": "redacted",
        "network": "none",
        "source_binding": True,
        "exact_package_request_applied": True,
        "exact_package_identity_matrix": True,
        "client_id_binding": True,
        "provisioning_control_only": True,
        "bootstrap_admin_removed": True,
        "provisioning_after_admin_removal": True,
        "legacy_anonymous_after_admin_removal": True,
        "anonymous_control_denied": True,
        "retained_state_recovered": True,
        "current_services_modified": False,
    }


def _install_fakes(
    monkeypatch: pytest.MonkeyPatch,
    manifest: dict[str, Any],
    calls: list[dict[str, object]],
) -> None:
    monkeypatch.setattr(
        stage_rehearsal,
        "verify_migration_stage",
        lambda _path: manifest,
    )
    monkeypatch.setattr(
        stage_rehearsal,
        "verify_migration_package",
        lambda _path: {"schema": "gh.m2.t1-auth-migration/1"},
    )

    def fake_rehearsal(
        _rollback: Path,
        _package: Path,
        *,
        expected_retained_topic: str,
        runner: InspectRunner,
        name_factory,
        verification_executor=None,
    ) -> dict[str, object]:
        candidate = name_factory()
        calls.append(
            {
                "candidate": candidate,
                "topic": expected_retained_topic,
                "fault": verification_executor is not None,
            }
        )
        if verification_executor is not None:
            verification_executor(
                runner,
                candidate,
                Path("/tmp/staging"),
                None,
                None,
                expected_retained_topic,
            )
        return _success_result()

    monkeypatch.setattr(
        stage_rehearsal,
        "run_migration_package_rehearsal",
        fake_rehearsal,
    )


def test_rehearses_stage_with_fault_cleanup_and_immutability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage, manifest = _stage_fixture(tmp_path)
    calls: list[dict[str, object]] = []
    _install_fakes(monkeypatch, manifest, calls)
    runner = InspectRunner()

    result = stage_rehearsal.run_migration_stage_rehearsal(
        stage,
        expected_retained_topic=(
            "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
        ),
        runner=runner,
    )

    assert result["schema"] == "gh.m2.t1-auth-migration-stage-rehearsal/1"
    assert result["network"] == "none"
    assert result["fault_after_exact_request_injected"] is True
    assert result["fault_candidate_cleanup"] is True
    assert result["success_candidate_cleanup"] is True
    assert result["stage_immutable"] is True
    assert result["live_sources_unchanged"] is True
    assert result["exact_package_identity_matrix"] is True
    assert result["current_services_modified"] is False
    assert [item["fault"] for item in calls] == [True, False]
    assert len(
        [call for call in runner.calls if call[:2] == ("docker", "inspect")]
    ) == 2


def test_rejects_candidate_residue_after_fault(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage, manifest = _stage_fixture(tmp_path)
    calls: list[dict[str, object]] = []
    _install_fakes(monkeypatch, manifest, calls)

    with pytest.raises(ShadowError, match="remained"):
        stage_rehearsal.run_migration_stage_rehearsal(
            stage,
            expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
            runner=InspectRunner(residue=True),
        )

    assert len(calls) == 1
    assert calls[0]["fault"] is True


def test_rejects_unsafe_activation_plan_before_rehearsal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage, manifest = _stage_fixture(tmp_path)
    activation = stage / "activation-plan.json"
    document = json.loads(activation.read_text(encoding="utf-8"))
    document["activation_enabled"] = True
    activation.write_text(json.dumps(document), encoding="utf-8")
    activation.chmod(0o600)
    monkeypatch.setattr(
        stage_rehearsal,
        "verify_migration_stage",
        lambda _path: manifest,
    )

    with pytest.raises(MigrationStageError, match="safety flags"):
        stage_rehearsal.run_migration_stage_rehearsal(
            stage,
            expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
            runner=InspectRunner(),
        )


def test_rejects_live_source_drift_before_candidate_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage, manifest = _stage_fixture(tmp_path)
    live_source = Path(manifest["files"][0]["source_path"])
    live_source.write_text("changed\n", encoding="utf-8")
    live_source.chmod(0o644)
    monkeypatch.setattr(
        stage_rehearsal,
        "verify_migration_stage",
        lambda _path: manifest,
    )

    with pytest.raises(MigrationStageError, match="checksum changed"):
        stage_rehearsal.run_migration_stage_rehearsal(
            stage,
            expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
            runner=InspectRunner(),
        )


def test_stage_rehearsal_module_imports_without_paho() -> None:
    project = Path(__file__).resolve().parents[1]
    script = textwrap.dedent(
        """
        import importlib.abc
        import sys

        class BlockPaho(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "paho" or fullname.startswith("paho."):
                    raise ModuleNotFoundError(
                        "blocked for no-install host test",
                        name=fullname,
                    )
                return None

        sys.meta_path.insert(0, BlockPaho())

        from greenhouse_manager.t1_migration_stage_rehearsal import (
            STAGE_REHEARSAL_SCHEMA,
        )

        assert STAGE_REHEARSAL_SCHEMA.endswith("/1")
        """
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project / "src")
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_no_install_stage_rehearsal_launcher_help() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_migration_stage_rehearsal.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "expected-retained-topic" in completed.stdout
