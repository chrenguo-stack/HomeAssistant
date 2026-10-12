from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol

SCHEMA = "gh.n3w.t1-golden-master-build/1"


class GoldenMasterInstallerError(RuntimeError):
    pass


class GoldenMasterStageError(GoldenMasterInstallerError):
    def __init__(
        self,
        failed_stage: str,
        failure_code: str,
        cleanup_result: str,
    ) -> None:
        self.failed_stage = failed_stage
        self.failure_code = failure_code
        self.cleanup_result = cleanup_result
        message = (
            "golden_master_failed_and_cleanup_not_proven"
            if cleanup_result == "NOT_PROVEN"
            else "golden_master_failed"
        )
        super().__init__(message)


class GoldenMasterRecoveryRequired(GoldenMasterStageError):
    pass


class GoldenMasterAdapters(Protocol):
    def preflight_master(self) -> Mapping[str, object]: ...
    def load_images(self) -> Mapping[str, object]: ...
    def stage_public_runtime(self, candidate_root: Path) -> Mapping[str, object]: ...
    def commit_public_candidate(self, candidate_root: Path) -> Mapping[str, object]: ...
    def master_postcheck(self) -> Mapping[str, object]: ...
    def cleanup_master_candidate(self, candidate_root: Path) -> Mapping[str, object]: ...


def _safe_failure_code(error: Exception) -> str:
    raw = str(error)
    candidate = raw if isinstance(error, GoldenMasterInstallerError) else raw.split(":", 1)[0]
    if re.fullmatch(r"[a-z0-9_:-]{1,96}", candidate):
        return candidate.replace(":", "_")
    return "adapter_failure"


def _require(report: Mapping[str, object], expected: Mapping[str, object], label: str) -> None:
    for key, value in expected.items():
        if report.get(key) != value:
            raise GoldenMasterInstallerError(f"{label}:{key}_invalid")


def run_golden_master_build(
    adapters: GoldenMasterAdapters,
    candidate_root: str | Path,
    *,
    before_mutation: Callable[[], None] | None = None,
) -> dict[str, Any]:
    candidate = Path(candidate_root).expanduser()
    if not candidate.is_absolute():
        raise GoldenMasterInstallerError("candidate_root_not_absolute")
    if candidate.exists() or candidate.is_symlink():
        raise GoldenMasterInstallerError("candidate_root_already_exists")

    steps: list[str] = []
    mutation_started = False
    current_stage = "preflight"

    try:
        preflight = adapters.preflight_master()
        _require(
            preflight,
            {
                "status": "PASS",
                "instance_material_absent": True,
                "production_service_start": False,
            },
            "preflight",
        )
        steps.append("preflight")

        if before_mutation is not None:
            before_mutation()

        mutation_started = True
        current_stage = "load_images"
        images = adapters.load_images()
        _require(
            images,
            {
                "status": "PASS",
                "image_count": 3,
                "offline": True,
                "registry_pull": False,
                "platform": "linux/arm64",
                "production_service_start": False,
            },
            "load_images",
        )
        steps.append("load_images")

        current_stage = "stage_public"
        staged = adapters.stage_public_runtime(candidate)
        _require(
            staged,
            {
                "status": "PASS",
                "public_only": True,
                "instance_material_created": False,
                "services_stopped": True,
                "production_service_start": False,
            },
            "stage_public",
        )
        steps.append("stage_public")

        current_stage = "commit_public"
        committed = adapters.commit_public_candidate(candidate)
        _require(
            committed,
            {
                "status": "PASS",
                "public_committed": True,
                "transaction_owned_only": True,
                "instance_material_created": False,
                "production_service_start": False,
            },
            "commit_public",
        )
        steps.append("commit_public")

        current_stage = "master_postcheck"
        postcheck = adapters.master_postcheck()
        _require(
            postcheck,
            {
                "status": "PASS",
                "master_ready": True,
                "instance_material_absent": True,
                "product_listener_count": 0,
                "production_service_start": False,
            },
            "master_postcheck",
        )
        steps.append("master_postcheck")

        return {
            "schema": SCHEMA,
            "status": "PASS",
            "steps": steps,
            "master_ready": True,
            "instance_material_absent": True,
            "production_service_start": False,
            "board_access": False,
        }
    except Exception as error:
        failure_code = _safe_failure_code(error)
        if mutation_started:
            try:
                cleanup = adapters.cleanup_master_candidate(candidate)
                _require(
                    cleanup,
                    {
                        "status": "PASS",
                        "public_transaction_owned_only": True,
                        "instance_material_modified": False,
                        "production_service_start": False,
                    },
                    "cleanup",
                )
            except Exception as cleanup_error:
                raise GoldenMasterRecoveryRequired(
                    current_stage,
                    failure_code,
                    "NOT_PROVEN",
                ) from cleanup_error
            raise GoldenMasterStageError(
                current_stage,
                failure_code,
                "PASS",
            ) from error
        if isinstance(error, GoldenMasterInstallerError):
            raise
        raise GoldenMasterStageError(
            current_stage,
            failure_code,
            "NOT_STARTED",
        ) from error
