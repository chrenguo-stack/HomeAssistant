from __future__ import annotations

from pathlib import Path

import pytest

from greenhouse_manager.bootstrap.golden_master_installer import (
    GoldenMasterStageError,
    run_golden_master_build,
)


class FakeAdapters:
    def __init__(self, *, fail_stage: str | None = None) -> None:
        self.fail_stage = fail_stage
        self.calls: list[str] = []

    def _call(self, name: str) -> None:
        self.calls.append(name)
        if self.fail_stage == name:
            raise RuntimeError("adapter_failure")

    def preflight_master(self):
        self._call("preflight")
        return {
            "status": "PASS",
            "instance_material_absent": True,
            "production_service_start": False,
        }

    def load_images(self):
        self._call("load_images")
        return {
            "status": "PASS",
            "image_count": 3,
            "offline": True,
            "registry_pull": False,
            "platform": "linux/arm64",
            "production_service_start": False,
        }

    def stage_public_runtime(self, _candidate_root: Path):
        self._call("stage_public")
        return {
            "status": "PASS",
            "public_only": True,
            "instance_material_created": False,
            "services_stopped": True,
            "production_service_start": False,
        }

    def commit_public_candidate(self, _candidate_root: Path):
        self._call("commit_public")
        return {
            "status": "PASS",
            "public_committed": True,
            "transaction_owned_only": True,
            "instance_material_created": False,
            "production_service_start": False,
        }

    def master_postcheck(self):
        self._call("master_postcheck")
        return {
            "status": "PASS",
            "master_ready": True,
            "instance_material_absent": True,
            "product_listener_count": 0,
            "production_service_start": False,
        }

    def cleanup_master_candidate(self, _candidate_root: Path):
        self._call("cleanup")
        return {
            "status": "PASS",
            "public_transaction_owned_only": True,
            "instance_material_modified": False,
            "production_service_start": False,
        }


def test_master_orchestration_contains_only_public_stages(tmp_path: Path) -> None:
    adapters = FakeAdapters()
    report = run_golden_master_build(adapters, tmp_path / "candidate")

    assert report["status"] == "PASS"
    assert report["instance_material_absent"] is True
    assert adapters.calls == [
        "preflight",
        "load_images",
        "stage_public",
        "commit_public",
        "master_postcheck",
    ]


def test_master_failure_cleans_only_master_transaction(tmp_path: Path) -> None:
    adapters = FakeAdapters(fail_stage="stage_public")

    with pytest.raises(GoldenMasterStageError) as captured:
        run_golden_master_build(adapters, tmp_path / "candidate")

    assert captured.value.failed_stage == "stage_public"
    assert captured.value.cleanup_result == "PASS"
    assert adapters.calls[-1] == "cleanup"
