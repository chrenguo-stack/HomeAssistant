#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Protocol

from n3w_t1_production_v2_contract import (
    V2_ACTIONS,
    canonical_sha256,
    validate_plan,
    validate_release,
    validate_result,
    validate_run_context,
)

SCHEMA = "gh.n3w-t1-production-v2-r2/1"
R2_TERMINAL_STATE = "REBOOT_PENDING"
F4_INTERNAL_ACTIONS = (
    "F4_PREPARE",
    "F4_ACTIVATE",
    "F4_ACCEPT",
    "PERSIST_CERT",
    "REBOOT_CONTROL",
)
F4_AUTH_PATTERN = re.compile(r"^N3W_T1_F4_[A-Z0-9_]{8,160}$")


class ProductionV2R2Error(RuntimeError):
    pass


class PreMutationExecutionError(ProductionV2R2Error):
    def __init__(self, stage: str, cause: Exception):
        super().__init__(f"pre_mutation_failed:{stage}:{type(cause).__name__}")
        self.stage = stage


class StartedFailureFinalizationError(ProductionV2R2Error):
    def __init__(self, stage: str, cause: Exception):
        super().__init__(f"started_failure_finalization_failed:{stage}:{type(cause).__name__}")
        self.stage = stage


class R2Adapter(Protocol):
    def verify_release(self, release: dict[str, Any]) -> dict[str, Any]: ...
    def start_ssh_epoch(self) -> dict[str, Any]: ...
    def qualify(self, release: dict[str, Any]) -> dict[str, Any]: ...
    def start_marker(self, binding: dict[str, str]) -> dict[str, Any]: ...
    def marker_sha256(self) -> str: ...
    def host_baseline(self, packages: dict[str, str]) -> dict[str, Any]: ...
    def f3_deploy(self, run_context: dict[str, str]) -> dict[str, Any]: ...
    def provision(self) -> dict[str, Any]: ...
    def f4_action(self, action: str, authorization_id: str) -> dict[str, Any]: ...
    def controlled_reboot(self, authorization_id: str) -> dict[str, Any]: ...
    def close_pre_reboot_epoch(self) -> dict[str, Any]: ...
    def freeze_failure(self, failure: dict[str, Any]) -> dict[str, Any]: ...
    def collect_failure_forensics(self) -> dict[str, Any]: ...
    def failure_session_close(self) -> dict[str, Any]: ...
    def record_reflash_disposition(self) -> dict[str, Any]: ...


def _pass(document: Any, stage: str) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("status") != "PASS":
        raise ProductionV2R2Error(f"{stage}_not_pass")
    return document


def derive_internal_action_id(run_id: str, action: str) -> str:
    if re.fullmatch(r"[0-9a-f]{64}", run_id) is None:
        raise ProductionV2R2Error("run_id_invalid")
    if action not in F4_INTERNAL_ACTIONS:
        raise ProductionV2R2Error("f4_action_invalid")
    suffix = hashlib.sha256(f"{run_id}:{action}".encode("utf-8")).hexdigest()[:24].upper()
    value = f"N3W_T1_F4_V2_{action}_{suffix}"
    if F4_AUTH_PATTERN.fullmatch(value) is None:
        raise ProductionV2R2Error("derived_authorization_invalid")
    return value


def build_plan(
    release_document: Any,
    *,
    run_id: str,
    target_binding_sha256: str,
    ssh_host_key_sha256: str,
) -> dict[str, Any]:
    release = validate_release(release_document)
    plan = {
        "schema": "gh.n3w-t1-production-v2-plan/1",
        "run_id": run_id,
        "release_id": release["release_id"],
        "release_sha256": canonical_sha256(release),
        "source_head": release["source_head"],
        "target_binding_sha256": target_binding_sha256,
        "ssh_host_key_sha256": ssh_host_key_sha256,
        "actions": list(V2_ACTIONS),
    }
    return validate_plan(plan)


def marker_binding(plan: dict[str, Any]) -> dict[str, str]:
    normalized = validate_plan(plan)
    return {
        "run_id": normalized["run_id"],
        "release_id": normalized["release_id"],
        "release_sha256": normalized["release_sha256"],
        "source_head": normalized["source_head"],
        "target_binding_sha256": normalized["target_binding_sha256"],
        "ssh_host_key_sha256": normalized["ssh_host_key_sha256"],
        "plan_sha256": canonical_sha256(normalized),
    }


def build_f3_run_context(
    plan: dict[str, Any],
    production_marker_sha256: str,
) -> dict[str, Any]:
    normalized = validate_plan(plan)
    context = {
        "schema": "gh.n3w-t1-production-v2-run-context/1",
        "run_id": normalized["run_id"],
        "release_id": normalized["release_id"],
        "release_sha256": normalized["release_sha256"],
        "source_head": normalized["source_head"],
        "target_binding_sha256": normalized["target_binding_sha256"],
        "production_marker_sha256": production_marker_sha256,
        "action": "F3_DEPLOY",
    }
    return validate_run_context(context)


def host_baseline_install_argv(release_document: Any) -> tuple[str, ...]:
    release = validate_release(release_document)
    packages = release["packages"]
    return (
        "python3",
        "tools/n3w_t1_fresh_host_baseline.py",
        "--phase",
        "install",
        "--docker-io-package-version",
        packages["docker.io"],
        "--docker-compose-v2-package-version",
        packages["docker-compose-v2"],
    )


def f3_apply_argv(run_context_path: str) -> tuple[str, ...]:
    if not run_context_path or run_context_path.strip() != run_context_path:
        raise ProductionV2R2Error("run_context_path_invalid")
    return (
        "python3",
        "tools/n3w_t1_fresh_product_staging_host.py",
        "--phase",
        "apply",
        "--run-context",
        run_context_path,
    )


class R2Orchestrator:
    def __init__(self, adapter: R2Adapter):
        self.adapter = adapter

    def _finalize_started_failure(
        self,
        *,
        stage: str,
        error: Exception,
    ) -> dict[str, Any]:
        failure = {
            "status": "FAIL",
            "failed_stage": stage,
            "error_type": type(error).__name__,
            "error_class": "MUTATION_FAIL_REFLASH_REQUIRED",
            "automatic_retry": False,
        }
        _pass(self.adapter.freeze_failure(failure), "failure_freeze")
        forensic = _pass(
            self.adapter.collect_failure_forensics(),
            "failure_forensics",
        )
        if forensic.get("evidence_complete") is not True:
            raise ProductionV2R2Error("failure_forensics_incomplete")
        session = _pass(
            self.adapter.failure_session_close(),
            "failure_session_close",
        )
        if session.get("session_closed") is not True:
            raise ProductionV2R2Error("failure_session_not_closed")
        disposition = _pass(
            self.adapter.record_reflash_disposition(),
            "reflash_disposition",
        )
        if disposition.get("reflash_required") is not True:
            raise ProductionV2R2Error("reflash_disposition_invalid")
        return {
            "schema": SCHEMA,
            "status": "FAIL",
            "state": "REFLASH_REQUIRED",
            "failed_stage": stage,
            "error_class": "MUTATION_FAIL_REFLASH_REQUIRED",
            "evidence_complete": True,
            "operator_session_closed": True,
            "reflash_required": True,
            "automatic_retry": False,
            "post_reboot_acceptance_complete": False,
            "board_access": False,
        }

    def execute(
        self,
        release_document: Any,
        *,
        run_id: str,
        target_binding_sha256: str,
        approved: bool,
    ) -> dict[str, Any]:
        release = validate_release(deepcopy(release_document))
        epoch_started = False
        marker_started = False
        stage = "VERIFY_RELEASE"
        try:
            _pass(self.adapter.verify_release(release), "release")
            stage = "SSH_EPOCH"
            epoch = _pass(self.adapter.start_ssh_epoch(), "ssh_epoch")
            epoch_started = True
            host_key = epoch.get("host_key_sha256")
            if not isinstance(host_key, str):
                raise ProductionV2R2Error("ssh_host_key_missing")
            stage = "QUALIFICATION"
            _pass(self.adapter.qualify(release), "qualification")
            plan = build_plan(
                release,
                run_id=run_id,
                target_binding_sha256=target_binding_sha256,
                ssh_host_key_sha256=host_key,
            )
            if approved is not True:
                raise ProductionV2R2Error("production_approval_required")
            stage = "MARKER_START"
            binding = marker_binding(plan)
            marker = self.adapter.start_marker(binding)
            if not isinstance(marker, dict) or marker.get("state") != "STARTED":
                raise ProductionV2R2Error("marker_start_not_confirmed")
            marker_started = True
            marker_sha = self.adapter.marker_sha256()
            context = build_f3_run_context(plan, marker_sha)

            stage = "HOST_BASELINE"
            _pass(
                self.adapter.host_baseline(dict(release["packages"])),
                "host_baseline",
            )
            stage = "F3_DEPLOY"
            _pass(self.adapter.f3_deploy(context), "f3")
            stage = "PROVISION"
            _pass(self.adapter.provision(), "provision")

            action_ids = {
                action: derive_internal_action_id(run_id, action)
                for action in F4_INTERNAL_ACTIONS
            }
            for action in F4_INTERNAL_ACTIONS[:-1]:
                stage = action
                _pass(
                    self.adapter.f4_action(action, action_ids[action]),
                    action.casefold(),
                )

            stage = "REBOOT_CONTROL"
            _pass(
                self.adapter.controlled_reboot(action_ids["REBOOT_CONTROL"]),
                "reboot_control",
            )
            stage = "SSH_EPOCH_CLOSE"
            close = _pass(
                self.adapter.close_pre_reboot_epoch(),
                "ssh_epoch_close",
            )
            if close.get("session_closed") is not True:
                raise ProductionV2R2Error("ssh_epoch_not_closed")
            epoch_started = False
            return {
                "schema": SCHEMA,
                "status": "PASS",
                "state": R2_TERMINAL_STATE,
                "plan_sha256": canonical_sha256(plan),
                "run_context": context,
                "marker_binding": binding,
                "internal_action_ids": action_ids,
                "automatic_retry": False,
                "post_reboot_acceptance_complete": False,
                "production_service_start": True,
                "board_access": False,
            }
        except Exception as error:
            if marker_started:
                try:
                    return self._finalize_started_failure(
                        stage=stage,
                        error=error,
                    )
                except Exception as finalization_error:
                    raise StartedFailureFinalizationError(
                        stage,
                        finalization_error,
                    ) from finalization_error
            if epoch_started:
                close = _pass(
                    self.adapter.close_pre_reboot_epoch(),
                    "pre_mutation_session_close",
                )
                if close.get("session_closed") is not True:
                    raise ProductionV2R2Error(
                        "pre_mutation_session_not_closed"
                    ) from error
            raise PreMutationExecutionError(stage, error) from error


def self_check() -> dict[str, object]:
    source = __import__("pathlib").Path(__file__).read_text(encoding="utf-8")
    before_self = source.split("def self_check(", 1)[0]
    r3_normal = source.split('R3_SCHEMA =', 1)[1] if 'R3_SCHEMA =' in source else ""
    normal = before_self + r3_normal
    forbidden = ("repair-", "resume-if-needed", "force", "override")
    found = [token for token in forbidden if token in normal]
    return {
        "schema": SCHEMA,
        "status": "PASS" if not found else "STOP",
        "forbidden_normal_path_tokens": found,
        "r2_terminal_state": R2_TERMINAL_STATE,
        "automatic_retry": False,
        "board_access": False,
    }




R3_SCHEMA = "gh.n3w-t1-production-v2-r3/1"


class R3Adapter(R2Adapter, Protocol):
    def wait_for_ssh(self) -> dict[str, Any]: ...
    def start_post_reboot_epoch(self) -> dict[str, Any]: ...
    def post_reboot_acceptance(
        self,
        release: dict[str, Any],
        binding: dict[str, str],
    ) -> dict[str, Any]: ...
    def accept_marker(
        self,
        binding: dict[str, str],
        acceptance_sha256: str,
    ) -> dict[str, Any]: ...
    def close_post_reboot_epoch(self) -> dict[str, Any]: ...


def _run_id_sha256(run_id: str) -> str:
    return hashlib.sha256(run_id.encode("ascii")).hexdigest()


def _private_result_sha256(value: dict[str, Any]) -> str:
    return canonical_sha256(value)


def _final_result(
    release: dict[str, Any],
    *,
    run_id: str,
    target_binding_sha256: str,
    status: str,
    marker_state: str,
    error_class: str,
    device_acceptance: str,
    production_ready: bool,
    operator_session_closed: bool,
    evidence_complete: bool,
    reflash_required: bool,
    terminal_stage: str,
    evidence_seed: dict[str, Any],
) -> dict[str, Any]:
    document = {
        "schema": "gh.n3w-t1-production-v2-result/1",
        "status": status,
        "release_id": release["release_id"],
        "release_sha256": canonical_sha256(release),
        "source_head": release["source_head"],
        "run_id_sha256": _run_id_sha256(run_id),
        "target_binding_sha256": target_binding_sha256,
        "marker_state": marker_state,
        "error_class": error_class,
        "device_acceptance": device_acceptance,
        "T1_PRODUCTION_READY": production_ready,
        "operator_session_closed": operator_session_closed,
        "evidence_complete": evidence_complete,
        "reflash_required": reflash_required,
        "terminal_stage": terminal_stage,
        "private_result_sha256": _private_result_sha256(evidence_seed),
    }
    return validate_result(document)


class R3Orchestrator:
    def __init__(self, adapter: R3Adapter):
        self.adapter = adapter

    def _finalize_post_reboot_failure(
        self,
        release: dict[str, Any],
        *,
        run_id: str,
        target_binding_sha256: str,
        stage: str,
        error: Exception,
    ) -> dict[str, Any]:
        failure = {
            "status": "FAIL",
            "failed_stage": stage,
            "error_type": type(error).__name__,
            "error_class": "POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED",
            "automatic_retry": False,
        }
        _pass(self.adapter.freeze_failure(failure), "failure_freeze")
        forensic = _pass(
            self.adapter.collect_failure_forensics(),
            "failure_forensics",
        )
        if forensic.get("evidence_complete") is not True:
            raise ProductionV2R2Error("failure_forensics_incomplete")
        session = _pass(
            self.adapter.failure_session_close(),
            "failure_session_close",
        )
        if session.get("session_closed") is not True:
            raise ProductionV2R2Error("failure_session_not_closed")
        disposition = _pass(
            self.adapter.record_reflash_disposition(),
            "reflash_disposition",
        )
        if disposition.get("reflash_required") is not True:
            raise ProductionV2R2Error("reflash_disposition_invalid")
        return _final_result(
            release,
            run_id=run_id,
            target_binding_sha256=target_binding_sha256,
            status="FAIL",
            marker_state="STARTED",
            error_class="POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED",
            device_acceptance="FAIL",
            production_ready=False,
            operator_session_closed=True,
            evidence_complete=True,
            reflash_required=True,
            terminal_stage=stage,
            evidence_seed={
                "failure": failure,
                "forensic": forensic,
                "session": session,
                "disposition": disposition,
            },
        )

    def execute(
        self,
        release_document: Any,
        *,
        run_id: str,
        target_binding_sha256: str,
        approved: bool,
    ) -> dict[str, Any]:
        release = validate_release(deepcopy(release_document))
        try:
            pre = R2Orchestrator(self.adapter).execute(
                release,
                run_id=run_id,
                target_binding_sha256=target_binding_sha256,
                approved=approved,
            )
        except PreMutationExecutionError as error:
            return _final_result(
                release,
                run_id=run_id,
                target_binding_sha256=target_binding_sha256,
                status="FAIL",
                marker_state="ABSENT",
                error_class="PRE_MUTATION_FAIL",
                device_acceptance="NOT_REACHED",
                production_ready=False,
                operator_session_closed=True,
                evidence_complete=True,
                reflash_required=False,
                terminal_stage=error.stage,
                evidence_seed={
                    "error_type": type(error).__name__,
                    "error": str(error)[:200],
                },
            )

        if pre.get("status") != "PASS":
            return _final_result(
                release,
                run_id=run_id,
                target_binding_sha256=target_binding_sha256,
                status="FAIL",
                marker_state="STARTED",
                error_class="MUTATION_FAIL_REFLASH_REQUIRED",
                device_acceptance="NOT_REACHED",
                production_ready=False,
                operator_session_closed=pre.get("operator_session_closed") is True,
                evidence_complete=pre.get("evidence_complete") is True,
                reflash_required=pre.get("reflash_required") is True,
                terminal_stage=str(pre.get("failed_stage", "PRE_REBOOT")),
                evidence_seed={"r2_failure": pre},
            )

        binding = pre.get("marker_binding")
        if not isinstance(binding, dict):
            raise ProductionV2R2Error("r2_marker_binding_missing")
        stage = "WAIT_FOR_SSH"
        accepted = False
        acceptance: dict[str, Any] | None = None
        try:
            _pass(self.adapter.wait_for_ssh(), "wait_for_ssh")
            stage = "SSH_EPOCH_2"
            epoch = _pass(
                self.adapter.start_post_reboot_epoch(),
                "post_reboot_ssh_epoch",
            )
            if epoch.get("host_key_sha256") != binding["ssh_host_key_sha256"]:
                raise ProductionV2R2Error("post_reboot_ssh_host_key_mismatch")

            stage = "POST_REBOOT_ACCEPTANCE"
            acceptance = _pass(
                self.adapter.post_reboot_acceptance(release, binding),
                "post_reboot_acceptance",
            )
            acceptance_sha = acceptance.get("acceptance_sha256")
            if (
                not isinstance(acceptance_sha, str)
                or re.fullmatch(r"[0-9a-f]{64}", acceptance_sha) is None
            ):
                raise ProductionV2R2Error("acceptance_sha256_invalid")

            stage = "MARKER_ACCEPTED"
            marker = self.adapter.accept_marker(binding, acceptance_sha)
            if (
                not isinstance(marker, dict)
                or marker.get("state") != "ACCEPTED"
                or marker.get("acceptance_sha256") != acceptance_sha
                or marker.get("T1_PRODUCTION_READY") is not True
            ):
                raise ProductionV2R2Error("marker_accept_not_confirmed")
            accepted = True

            stage = "SSH_EPOCH_2_CLOSE"
            close = _pass(
                self.adapter.close_post_reboot_epoch(),
                "post_reboot_ssh_epoch_close",
            )
            if close.get("session_closed") is not True:
                raise ProductionV2R2Error("post_reboot_ssh_epoch_not_closed")

            return _final_result(
                release,
                run_id=run_id,
                target_binding_sha256=target_binding_sha256,
                status="PASS",
                marker_state="ACCEPTED",
                error_class="NONE",
                device_acceptance="PASS",
                production_ready=True,
                operator_session_closed=True,
                evidence_complete=True,
                reflash_required=False,
                terminal_stage="COMPLETE",
                evidence_seed={
                    "acceptance_sha256": acceptance_sha,
                    "plan_sha256": binding["plan_sha256"],
                    "session_closed": True,
                },
            )
        except Exception as error:
            if accepted:
                return _final_result(
                    release,
                    run_id=run_id,
                    target_binding_sha256=target_binding_sha256,
                    status="FAIL",
                    marker_state="ACCEPTED",
                    error_class="PROCESS_CLEANUP_FAIL",
                    device_acceptance="PASS",
                    production_ready=True,
                    operator_session_closed=False,
                    evidence_complete=False,
                    reflash_required=False,
                    terminal_stage="PROCESS_CLEANUP_FAIL",
                    evidence_seed={
                        "acceptance_sha256": (
                            acceptance.get("acceptance_sha256")
                            if isinstance(acceptance, dict)
                            else None
                        ),
                        "error_type": type(error).__name__,
                    },
                )
            return self._finalize_post_reboot_failure(
                release,
                run_id=run_id,
                target_binding_sha256=target_binding_sha256,
                stage=stage,
                error=error,
            )


if __name__ == "__main__":
    print(json.dumps(self_check(), sort_keys=True, separators=(",", ":")))
