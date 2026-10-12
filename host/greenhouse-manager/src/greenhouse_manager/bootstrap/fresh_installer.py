from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol

SCHEMA = "gh.n3w.t1-fresh-installer-orchestration/1"


class FreshInstallerError(RuntimeError):
    pass


class FreshInstallerStageError(FreshInstallerError):
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
            "fresh_install_failed_and_cleanup_not_proven"
            if cleanup_result == "NOT_PROVEN"
            else "fresh_install_failed"
        )
        super().__init__(message)


class FreshInstallerRecoveryRequired(FreshInstallerStageError):
    pass


class FreshInstallerAdapters(Protocol):
    def preflight(self) -> Mapping[str, object]: ...
    def load_images(self) -> Mapping[str, object]: ...
    def create_identity(self, candidate_root: Path) -> Mapping[str, object]: ...
    def create_state(
        self,
        candidate_root: Path,
        system_id_sha256: str,
    ) -> Mapping[str, object]: ...
    def create_broker(
        self,
        candidate_root: Path,
        system_id: str,
    ) -> Mapping[str, object]: ...
    def initialize_dynsec(
        self,
        candidate_root: Path,
        system_id: str,
    ) -> Mapping[str, object]: ...
    def stage_runtime(
        self,
        candidate_root: Path,
        system_id: str,
    ) -> Mapping[str, object]: ...
    def commit_candidate(
        self,
        candidate_root: Path,
        system_id: str,
    ) -> Mapping[str, object]: ...
    def stopped_postcheck(self, system_id: str) -> Mapping[str, object]: ...
    def cleanup(self, candidate_root: Path) -> Mapping[str, object]: ...


def _safe_failure_code(error: Exception) -> str:
    raw = str(error)
    if type(error).__name__ == "BootstrapError":
        raw = raw.split(":", 1)[0]
    candidate = (
        raw
        if isinstance(error, FreshInstallerError)
        else raw.split(":", 1)[0]
    )
    if re.fullmatch(r"[a-z0-9_:-]{1,96}", candidate):
        return candidate.replace(":", "_")
    return "adapter_failure"


def _require(report: Mapping[str, object], expected: Mapping[str, object], label: str) -> None:
    for key, value in expected.items():
        if report.get(key) != value:
            raise FreshInstallerError(f"{label}:{key}_invalid")


def _system_id(report: Mapping[str, object]) -> str:
    value = report.get("system_id")
    if not isinstance(value, str) or not value:
        raise FreshInstallerError("identity:system_id_invalid")
    return value


def _validate_preflight(report: Mapping[str, object]) -> None:
    _require(
        report,
        {
            "status": "PASS",
            "arch": "aarch64",
            "docker_ready": True,
            "compose_ready": True,
            "network_ready": True,
            "default_route": True,
            "time_sync": True,
            "root_capacity": True,
            "product_containers": 0,
            "product_images": 0,
            "product_volumes": 0,
            "product_networks": 0,
            "product_listeners": 0,
            "product_paths_absent": True,
            "product_units_absent": True,
            "product_dispatcher_absent": True,
            "product_firewall_absent": True,
            "production_service_start": False,
        },
        "preflight",
    )


def run_fresh_staging(
    adapters: FreshInstallerAdapters,
    candidate_root: str | Path,
    *,
    before_mutation: Callable[[], None] | None = None,
) -> dict[str, Any]:
    candidate = Path(candidate_root).expanduser()
    if not candidate.is_absolute():
        raise FreshInstallerError("candidate_root_not_absolute")
    if candidate.exists() or candidate.is_symlink():
        raise FreshInstallerError("candidate_root_already_exists")

    steps: list[str] = []
    mutation_started = False
    system_id: str | None = None
    current_stage = "preflight"

    try:
        preflight = adapters.preflight()
        _validate_preflight(preflight)
        steps.append("preflight")

        if before_mutation is not None:
            before_mutation()

        mutation_started = True
        current_stage = "load_images"
        image_report = adapters.load_images()
        _require(
            image_report,
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

        current_stage = "identity"
        identity_report = adapters.create_identity(candidate)
        _require(
            identity_report,
            {
                "created": True,
                "production_services_modified": False,
                "network_operation": False,
            },
            "identity",
        )
        system_id = _system_id(identity_report)
        system_id_sha256 = hashlib.sha256(system_id.encode()).hexdigest()
        steps.append("identity")

        current_stage = "state"
        state_report = adapters.create_state(candidate, system_id_sha256)
        _require(
            state_report,
            {
                "status": "PASS",
                "fresh_product_state": True,
                "legacy_state_imported": False,
                "node_credential_count": 0,
                "production_service_start": False,
            },
            "state",
        )
        if state_report.get("system_id_sha256") != system_id_sha256:
            raise FreshInstallerError("state:system_identity_binding_invalid")
        steps.append("state")

        current_stage = "broker"
        broker_report = adapters.create_broker(candidate, system_id)
        _require(
            broker_report,
            {
                "service_count": 3,
                "node_credential_count": 0,
                "broker_transport_ca_separate_from_system_ca": True,
                "secret_values_included": False,
                "production_service_start": False,
                "network_operation": False,
            },
            "broker",
        )
        if broker_report.get("system_id") != system_id:
            raise FreshInstallerError("broker:system_identity_binding_invalid")
        steps.append("broker")

        current_stage = "dynsec"
        dynsec_report = adapters.initialize_dynsec(candidate, system_id)
        _require(
            dynsec_report,
            {
                "status": "PASS",
                "service_client_count": 3,
                "service_role_count": 3,
                "node_client_count": 0,
                "node_role_count": 0,
                "default_acl_exact": True,
                "admin_runtime_use_forbidden": True,
                "secret_values_included": False,
                "production_service_start": False,
            },
            "dynsec",
        )
        steps.append("dynsec")

        current_stage = "runtime"
        runtime_report = adapters.stage_runtime(candidate, system_id)
        _require(
            runtime_report,
            {
                "status": "PASS",
                "source_files_staged": True,
                "network_count": 2,
                "guard_ready": True,
                "services_stopped": True,
                "production_service_start": False,
            },
            "runtime",
        )
        steps.append("runtime")

        current_stage = "commit"
        commit_report = adapters.commit_candidate(candidate, system_id)
        _require(
            commit_report,
            {
                "status": "PASS",
                "committed": True,
                "transaction_owned_only": True,
                "production_service_start": False,
            },
            "commit",
        )
        steps.append("commit")

        current_stage = "postcheck"
        postcheck = adapters.stopped_postcheck(system_id)
        _require(
            postcheck,
            {
                "status": "PASS",
                "fresh_product_staged": True,
                "node_credential_count": 0,
                "product_listener_count": 0,
                "production_service_start": False,
            },
            "postcheck",
        )
        steps.append("postcheck")

        return {
            "schema": SCHEMA,
            "status": "PASS",
            "system_id": system_id,
            "steps": steps,
            "fresh_product_staged": True,
            "node_credential_count": 0,
            "production_service_start": False,
            "activation_authorized": False,
            "board_access": False,
        }
    except Exception as error:
        failure_code = _safe_failure_code(error)
        if mutation_started:
            try:
                cleanup = adapters.cleanup(candidate)
                _require(
                    cleanup,
                    {
                        "status": "PASS",
                        "transaction_owned_only": True,
                        "production_service_start": False,
                    },
                    "cleanup",
                )
            except Exception as cleanup_error:
                raise FreshInstallerRecoveryRequired(
                    current_stage,
                    failure_code,
                    "NOT_PROVEN",
                ) from cleanup_error
            raise FreshInstallerStageError(
                current_stage,
                failure_code,
                "PASS",
            ) from error
        raise FreshInstallerStageError(
            current_stage,
            failure_code,
            "NOT_STARTED",
        ) from error
