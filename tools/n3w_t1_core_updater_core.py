from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from n3w_t1_core_updater_common import (
    APPLY_CONFIRMATION,
    AUTHORIZATION_ID,
    INSPECT_SCHEMA,
    PLAN_SCHEMA,
    ROLLBACK_CONFIRMATION,
    STATUS_SCHEMA,
    TX_SCHEMA,
    Host,
    Target,
    UpdaterError,
    sha256_file,
    sha256_text,
    validate_candidate,
)
from n3w_t1_core_updater_state import StateStore


class CoreUpdater:
    def __init__(self, host: Host, store: StateStore) -> None:
        self.host = host
        self.store = store

    @staticmethod
    def _public_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
        runtime = snapshot["runtime"]
        return {
            "manager_image": snapshot["manager_image"],
            "compose_env_sha256": snapshot["compose_env_sha256"],
            "compose_render_sha256": snapshot["compose_render_sha256"],
            "services_unit": snapshot["services_unit"],
            "runtime": {
                name: {
                    "image_ref": runtime[name]["image_ref"],
                    "image_id": runtime[name]["image_id"],
                    "restart_count": runtime[name]["restart_count"],
                    "network_mode": runtime[name]["network_mode"],
                    "started_at": runtime[name]["started_at"],
                    "container_id_sha256": sha256_text(
                        runtime[name]["container_id"]
                    ),
                }
                for name in ("broker", "manager", "homeassistant")
            },
            "listeners": snapshot["listeners"],
        }

    @staticmethod
    def _stable_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
        broker = runtime["broker"]
        homeassistant = runtime["homeassistant"]
        return {
            "broker": {
                "image_ref": broker["image_ref"],
                "image_id": broker["image_id"],
            },
            "homeassistant": {
                "image_ref": homeassistant["image_ref"],
                "image_id": homeassistant["image_id"],
                "network_mode": homeassistant["network_mode"],
            },
        }

    @staticmethod
    def _verify_ha_stable(
        current: dict[str, Any],
        baseline: dict[str, Any],
    ) -> None:
        for key in ("image_ref", "image_id", "network_mode"):
            if current.get(key) != baseline.get(key):
                raise UpdaterError("rollback_homeassistant_identity_drift")

    def inspect(self) -> dict[str, Any]:
        snapshot = self.host.inspect()
        return {
            "schema": INSPECT_SCHEMA,
            "status": "PASS",
            "operation": "inspect",
            "component": "manager",
            "mutation": False,
            "snapshot": self._public_snapshot(snapshot),
        }

    def plan(
        self,
        target: Target,
        tar_path: Path | None = None,
    ) -> dict[str, Any]:
        pre = self.host.inspect()
        current = pre["manager_image"]
        if (
            target.expected_predecessor_image is not None
            and current != target.expected_predecessor_image
        ):
            raise UpdaterError("target_predecessor_mismatch")
        if current == target.image:
            raise UpdaterError("target_already_active")
        predecessor_id = self.host.image_id(current)
        if predecessor_id != pre["runtime"]["manager"]["image_id"]:
            raise UpdaterError("predecessor_image_authority_drift")
        target_prestate = self.host.image_id(target.image)
        if target_prestate not in {None, target.image_id}:
            raise UpdaterError("target_image_tag_conflict")
        tar_verified = False
        if tar_path is not None:
            if sha256_file(tar_path) != target.tar_sha256:
                raise UpdaterError("target_tar_sha256_mismatch")
            tar_verified = True
        return {
            "schema": PLAN_SCHEMA,
            "status": "PASS",
            "operation": "plan",
            "component": "manager",
            "mutation": False,
            "current": {
                "image": current,
                "image_id": predecessor_id,
            },
            "target": target.public(),
            "target_image_prestate": (
                "ABSENT" if target_prestate is None else "PRESENT_AND_EXACT"
            ),
            "manager_tar_verified": tar_verified,
            "actions": [
                "load_exact_target_image_if_absent",
                "stop_manager_and_homeassistant_via_services_owner",
                "atomically_replace_only_GH_MANAGER_IMAGE",
                "validate_compose_delta_is_manager_image_only",
                "start_manager_and_homeassistant_via_services_owner",
                "verify_manager_exact_target_and_non_manager_continuity",
            ],
            "broker_mutation": False,
            "homeassistant_image_mutation": False,
            "host_platform_mutation": False,
            "rollback_available": target.rollback_compatible,
        }

    def _verify_post(
        self,
        pre: dict[str, Any],
        target: Target,
    ) -> dict[str, Any]:
        post = self.host.inspect()
        if post["manager_image"] != target.image:
            raise UpdaterError("post_manager_image_ref_invalid")
        manager = post["runtime"]["manager"]
        if (
            manager["image_id"] != target.image_id
            or manager["network_mode"] != "host"
        ):
            raise UpdaterError("post_manager_runtime_invalid")
        before = pre["runtime"]["homeassistant"]
        after = post["runtime"]["homeassistant"]
        for key in ("image_ref", "image_id", "network_mode"):
            if before[key] != after[key]:
                raise UpdaterError("post_homeassistant_identity_drift")
        self.host.broker_continuity(pre["runtime"]["broker"])
        return post

    def _rollback_immediate(
        self,
        pre: dict[str, Any],
        target: Target,
        tx: dict[str, Any],
        reason: str,
    ) -> None:
        try:
            if tx.get("phase") in {"AUTHORIZED", "TARGET_IMAGE_LOADED"}:
                post = self.host.inspect()
                if (
                    post["manager_image"] != pre["manager_image"]
                    or post["runtime"]["manager"]["image_id"]
                    != pre["runtime"]["manager"]["image_id"]
                ):
                    raise UpdaterError("prestop_rollback_runtime_drift")
                self.host.broker_continuity(pre["runtime"]["broker"])
                tx.update(
                    status="ROLLED_BACK",
                    phase="ROLLBACK_COMPLETE_PRESTOP",
                    failure_reason=reason,
                )
                self.store.write(tx)
                return
            try:
                self.host.stop_services()
            except Exception:
                pass
            try:
                self.host.rewrite_manager_image(
                    target.image,
                    pre["manager_image"],
                )
            except UpdaterError as error:
                if "predecessor_drift" not in str(error):
                    raise
            self.host.start_services()
            post = self.host.inspect()
            if post["manager_image"] != pre["manager_image"]:
                raise UpdaterError("rollback_predecessor_ref_invalid")
            manager = post["runtime"]["manager"]
            if manager["image_id"] != pre["runtime"]["manager"]["image_id"]:
                raise UpdaterError("rollback_predecessor_image_invalid")
            before = pre["runtime"]["homeassistant"]
            after = post["runtime"]["homeassistant"]
            for key in ("image_ref", "image_id", "network_mode"):
                if before[key] != after[key]:
                    raise UpdaterError("rollback_homeassistant_identity_drift")
            self.host.broker_continuity(pre["runtime"]["broker"])
            tx.update(
                status="ROLLED_BACK",
                phase="ROLLBACK_COMPLETE",
                failure_reason=reason,
            )
            self.store.write(tx)
        except Exception as rollback_error:
            tx.update(
                status="FAILED_EMERGENCY",
                phase="ROLLBACK_FAILED",
                failure_reason=reason,
                rollback_error=type(rollback_error).__name__,
            )
            self.store.write(tx)
            raise UpdaterError("automatic_rollback_failed") from rollback_error

    def apply(
        self,
        target: Target,
        tar_path: Path,
        *,
        authorization_id: str,
        confirmation: str,
    ) -> dict[str, Any]:
        with self.store.lock():
            return self._apply_locked(
                target,
                tar_path,
                authorization_id=authorization_id,
                confirmation=confirmation,
            )

    def _apply_locked(
        self,
        target: Target,
        tar_path: Path,
        *,
        authorization_id: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if os.geteuid() != 0:
            raise UpdaterError("root_required")
        if confirmation != APPLY_CONFIRMATION:
            raise UpdaterError("apply_confirmation_missing")
        if AUTHORIZATION_ID.fullmatch(authorization_id) is None:
            raise UpdaterError("authorization_id_invalid")
        if sha256_file(tar_path) != target.tar_sha256:
            raise UpdaterError("target_tar_sha256_mismatch")
        pre = self.host.inspect()
        current = pre["manager_image"]
        if (
            target.expected_predecessor_image is not None
            and current != target.expected_predecessor_image
        ):
            raise UpdaterError("target_predecessor_mismatch")
        if current == target.image:
            raise UpdaterError("target_already_active")
        predecessor_id = self.host.image_id(current)
        if predecessor_id != pre["runtime"]["manager"]["image_id"]:
            raise UpdaterError("predecessor_image_authority_drift")
        target_prestate = self.host.image_id(target.image)
        if target_prestate not in {None, target.image_id}:
            raise UpdaterError("target_image_tag_conflict")
        self.store.prepare_new()
        tx = {
            "schema": TX_SCHEMA,
            "status": "APPLYING",
            "phase": "AUTHORIZED",
            "component": "manager",
            "authorization_id_sha256": sha256_text(authorization_id),
            "authorization_consumed": True,
            "predecessor_image": current,
            "predecessor_image_id": predecessor_id,
            "target": target.public(),
            "pre_compose_env_sha256": pre["compose_env_sha256"],
            "pre_stable_runtime": self._stable_runtime(pre["runtime"]),
            "started_at_unix": int(time.time()),
            "candidate_image_preexisting": target_prestate is not None,
        }
        self.store.write(tx)
        try:
            if target_prestate is None:
                self.host.load_image(tar_path)
                tx.update(phase="TARGET_IMAGE_LOADED")
                self.store.write(tx)
            if self.host.image_id(target.image) != target.image_id:
                raise UpdaterError("target_image_binding_invalid")
            before_render = pre["compose_render"]
            tx.update(phase="STOPPING_APPLICATION_SERVICES")
            self.store.write(tx)
            self.host.stop_services()
            tx.update(phase="APPLICATION_SERVICES_STOPPED")
            self.store.write(tx)
            self.host.broker_continuity(pre["runtime"]["broker"])
            candidate_env_sha = self.host.rewrite_manager_image(
                current,
                target.image,
            )
            tx.update(
                phase="MANAGER_BINDING_PUBLISHED",
                candidate_compose_env_sha256=candidate_env_sha,
            )
            self.store.write(tx)
            after_render = self.host.render_compose()
            validate_candidate(
                before_render,
                after_render,
                current,
                target.image,
            )
            self.host.start_services()
            tx.update(phase="TARGET_RUNTIME_STARTED")
            self.store.write(tx)
            post = self._verify_post(pre, target)
            tx.update(
                status="COMMITTED",
                phase="COMMITTED",
                committed_at_unix=int(time.time()),
                post_compose_env_sha256=post["compose_env_sha256"],
            )
            self.store.write(tx)
            return {
                "schema": STATUS_SCHEMA,
                "status": "PASS",
                "operation": "apply",
                "component": "manager",
                "transaction_status": "COMMITTED",
                "authorization_consumed": True,
                "target": target.public(),
                "runtime": self._public_snapshot(post),
                "broker_mutation": False,
                "homeassistant_image_mutation": False,
                "t1_mutation": True,
            }
        except Exception as error:
            self._rollback_immediate(
                pre,
                target,
                tx,
                type(error).__name__,
            )
            raise

    def rollback(self, *, confirmation: str) -> dict[str, Any]:
        with self.store.lock():
            return self._rollback_locked(confirmation=confirmation)

    def _rollback_locked(self, *, confirmation: str) -> dict[str, Any]:
        if os.geteuid() != 0:
            raise UpdaterError("root_required")
        if confirmation != ROLLBACK_CONFIRMATION:
            raise UpdaterError("rollback_confirmation_missing")
        tx = self.store.read()
        if tx is None or tx.get("status") not in {"COMMITTED", "APPLYING"}:
            raise UpdaterError("recoverable_transaction_required")
        target_doc = tx.get("target")
        stable = tx.get("pre_stable_runtime")
        if (
            not isinstance(target_doc, dict)
            or target_doc.get("rollback_compatible") is not True
            or not isinstance(stable, dict)
            or not isinstance(stable.get("broker"), dict)
            or not isinstance(stable.get("homeassistant"), dict)
        ):
            raise UpdaterError("rollback_transaction_authority_invalid")

        target_image = target_doc.get("image")
        target_id = target_doc.get("image_id")
        predecessor = tx.get("predecessor_image")
        predecessor_id = tx.get("predecessor_image_id")
        if not all(
            isinstance(value, str)
            for value in (
                target_image,
                target_id,
                predecessor,
                predecessor_id,
            )
        ):
            raise UpdaterError("transaction_image_binding_invalid")
        if self.host.image_id(predecessor) != predecessor_id:
            raise UpdaterError("rollback_predecessor_image_missing")

        original_status = tx["status"]
        original_phase = tx.get("phase")

        if (
            original_status == "APPLYING"
            and original_phase in {"AUTHORIZED", "TARGET_IMAGE_LOADED"}
        ):
            current = self.host.inspect()
            if (
                current["manager_image"] != predecessor
                or current["runtime"]["manager"]["image_id"] != predecessor_id
            ):
                raise UpdaterError("prestop_recovery_predecessor_drift")
            self._verify_ha_stable(
                current["runtime"]["homeassistant"],
                stable["homeassistant"],
            )
            self.host.broker_continuity(stable["broker"])
            tx.update(
                status="ROLLED_BACK",
                phase="RECOVERY_COMPLETE_PRESTOP",
                rolled_back_at_unix=int(time.time()),
            )
            self.store.write(tx)
            return {
                "schema": STATUS_SCHEMA,
                "status": "PASS",
                "operation": "rollback",
                "component": "manager",
                "transaction_status": "ROLLED_BACK",
                "recovered_from_status": original_status,
                "recovered_from_phase": original_phase,
                "runtime": self._public_snapshot(current),
                "t1_mutation": False,
            }

        supported_apply_phases = {
            "STOPPING_APPLICATION_SERVICES",
            "APPLICATION_SERVICES_STOPPED",
            "MANAGER_BINDING_PUBLISHED",
            "TARGET_RUNTIME_STARTED",
        }
        if (
            original_status == "APPLYING"
            and original_phase not in supported_apply_phases
        ):
            raise UpdaterError("rollback_apply_phase_unsupported")

        if original_status == "COMMITTED":
            current = self.host.inspect()
            if (
                current["manager_image"] != target_image
                or current["runtime"]["manager"]["image_id"] != target_id
            ):
                raise UpdaterError("rollback_target_not_active")
            rollback_broker = current["runtime"]["broker"]
            rollback_ha = current["runtime"]["homeassistant"]
        else:
            rollback_broker = stable["broker"]
            rollback_ha = stable["homeassistant"]

        tx.update(
            status="ROLLING_BACK",
            phase=(
                "ROLLBACK_AUTHORIZED"
                if original_status == "COMMITTED"
                else "RECOVERY_ROLLBACK_AUTHORIZED"
            ),
        )
        self.store.write(tx)

        try:
            self.host.stop_services()
            self.host.broker_continuity(rollback_broker)

            binding = self.host.manager_binding()
            if binding == target_image:
                before_render = self.host.render_compose()
                self.host.rewrite_manager_image(
                    target_image,
                    predecessor,
                )
                after_render = self.host.render_compose()
                validate_candidate(
                    before_render,
                    after_render,
                    target_image,
                    predecessor,
                )
            elif binding != predecessor:
                raise UpdaterError("rollback_manager_binding_unknown")

            self.host.start_services()
            post = self.host.inspect()
            if (
                post["manager_image"] != predecessor
                or post["runtime"]["manager"]["image_id"] != predecessor_id
            ):
                raise UpdaterError("rollback_predecessor_runtime_invalid")
            self._verify_ha_stable(
                post["runtime"]["homeassistant"],
                rollback_ha,
            )
            self.host.broker_continuity(rollback_broker)
            tx.update(
                status="ROLLED_BACK",
                phase=(
                    "ROLLBACK_COMPLETE"
                    if original_status == "COMMITTED"
                    else "RECOVERY_ROLLBACK_COMPLETE"
                ),
                rolled_back_at_unix=int(time.time()),
            )
            self.store.write(tx)
            return {
                "schema": STATUS_SCHEMA,
                "status": "PASS",
                "operation": "rollback",
                "component": "manager",
                "transaction_status": "ROLLED_BACK",
                "recovered_from_status": original_status,
                "recovered_from_phase": original_phase,
                "runtime": self._public_snapshot(post),
                "t1_mutation": True,
            }
        except Exception as error:
            tx.update(
                status="FAILED_EMERGENCY",
                phase="ROLLBACK_FAILED",
                rollback_error=type(error).__name__,
            )
            self.store.write(tx)
            raise

    def status(self) -> dict[str, Any]:
        transaction = self.store.read()
        return {
            "schema": STATUS_SCHEMA,
            "status": "PASS",
            "operation": "status",
            "component": "manager",
            "mutation": False,
            "recovery_required": (
                transaction is not None
                and transaction.get("status") not in {"COMMITTED", "ROLLED_BACK"}
            ),
            "transaction": transaction,
        }
