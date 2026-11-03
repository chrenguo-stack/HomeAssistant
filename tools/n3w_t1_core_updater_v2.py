from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from n3w_t1_core_updater_a1_policy import A1Policy, LocalA1Policy
from n3w_t1_core_updater_components import adapter_for
from n3w_t1_core_updater_v2_common import (
    APPLY_CONFIRMATION_V2,
    AUTHORIZATION_ID,
    INSPECT_SCHEMA_V2,
    PLAN_SCHEMA_V2,
    ROLLBACK_CONFIRMATION_V2,
    STATUS_SCHEMA_V2,
    TX_SCHEMA_V2,
    ComponentTarget,
    UpgradeBaseline,
    UpdaterV2Error,
    V2Host,
    sha256_file,
    sha256_bytes,
    canonical,
    validate_component_candidate,
)
from n3w_t1_core_updater_v2_state import V2StateStore


class MultiComponentCoreUpdater:
    def __init__(
        self,
        host: V2Host,
        store: V2StateStore,
        policy: A1Policy | None = None,
    ) -> None:
        self.host = host
        self.store = store
        self.policy = policy or LocalA1Policy()

    @staticmethod
    def _public_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
        runtime = snapshot["runtime"]
        return {
            "image_bindings": snapshot["image_bindings"],
            "image_binding_modes": snapshot["image_binding_modes"],
            "compose_env_sha256": snapshot["compose_env_sha256"],
            "compose_render_sha256": snapshot["compose_render_sha256"],
            "services_unit": snapshot["services_unit"],
            "runtime": {
                name: {
                    "image_ref": runtime[name]["image_ref"],
                    "image_id": runtime[name]["image_id"],
                    "network_mode": runtime[name]["network_mode"],
                    "runtime_contract_sha256": runtime[name][
                        "runtime_contract_sha256"
                    ],
                }
                for name in ("broker", "manager", "homeassistant")
            },
            "listeners": snapshot["listeners"],
            "mqtt_authenticated": snapshot.get("mqtt_authenticated"),
            "homeassistant_http_status": snapshot.get(
                "homeassistant_http_status"
            ),
        }

    def baseline(self) -> dict[str, Any]:
        snapshot = self.host.inspect_v2()
        self.host.assert_mutation_safe("broker")
        policy = self.policy.capture()
        self.policy.validate_pre("manager", policy)
        baseline = UpgradeBaseline(
            stack_images=dict(snapshot["image_bindings"]),
            image_binding_modes=dict(snapshot["image_binding_modes"]),
            runtime_contract_sha256={
                component: snapshot["runtime"][component][
                    "runtime_contract_sha256"
                ]
                for component in ("manager", "homeassistant", "broker")
            },
            a1_hard_authority=self.policy.hard_authority(policy),
            a1_classification_sha256=(
                "e664ced300ea2bb743b116550b7a3e22237e7f556f54400a060eef30671d30e7"
            ),
        )
        return baseline.public()

    def _validate_baseline(
        self,
        component: str,
        baseline: UpgradeBaseline,
        snapshot: dict[str, Any],
        policy: dict[str, Any],
    ) -> None:
        if baseline.stack_images != snapshot["image_bindings"]:
            raise UpdaterV2Error("baseline_stack_image_drift")
        if baseline.image_binding_modes != snapshot["image_binding_modes"]:
            raise UpdaterV2Error("baseline_image_binding_mode_drift")
        for name, expected in baseline.runtime_contract_sha256.items():
            current = snapshot["runtime"][name].get(
                "runtime_contract_sha256"
            )
            if current != expected:
                raise UpdaterV2Error(
                    f"baseline_runtime_contract_drift:{name}"
                )
        self.policy.validate_baseline(
            component,
            policy,
            baseline.a1_hard_authority,
        )

    def inspect(self, component: str | None = None) -> dict[str, Any]:
        snapshot = self.host.inspect_v2()
        policy = self.policy.capture()
        if component is not None:
            adapter_for(component)
            self.policy.validate_pre(component, policy)
        return {
            "schema": INSPECT_SCHEMA_V2,
            "status": "PASS",
            "operation": "inspect",
            "component": component or "all",
            "mutation": False,
            "snapshot": self._public_snapshot(snapshot),
            "a1_policy_sha256": sha256_bytes(canonical(policy)),
        }

    def plan(
        self,
        target: ComponentTarget,
        baseline: UpgradeBaseline,
        tar_path: Path | None = None,
    ) -> dict[str, Any]:
        adapter = adapter_for(target.component)
        pre = self.host.inspect_v2()
        self.host.assert_mutation_safe(target.component)
        self.host.assert_component_upgradeable(target.component)
        policy = self.policy.capture()
        self.policy.validate_pre(target.component, policy)
        self._validate_baseline(
            target.component,
            baseline,
            pre,
            policy,
        )

        current = adapter.current_binding(pre)
        if current != target.expected_predecessor_image_ref:
            raise UpdaterV2Error("target_predecessor_mismatch")
        if current == target.target_image_ref:
            raise UpdaterV2Error("target_already_active")

        predecessor_id = self.host.image_id(current)
        runtime = pre["runtime"][target.component]
        if predecessor_id != runtime["image_id"]:
            raise UpdaterV2Error("predecessor_image_authority_drift")

        target_prestate = self.host.image_id(target.target_image_ref)
        archive_verified = False
        if tar_path is not None:
            if sha256_file(tar_path) != target.target_archive_sha256:
                raise UpdaterV2Error("target_archive_sha256_mismatch")
            archive_verified = True
            if target_prestate is not None:
                self.host.verify_image_archive(
                    target.target_image_ref,
                    tar_path,
                    target.target_archive_sha256,
                )
        elif target_prestate is not None:
            raise UpdaterV2Error("target_image_portable_identity_requires_archive")

        return {
            "schema": PLAN_SCHEMA_V2,
            "status": "PASS",
            "operation": "plan",
            "component": target.component,
            "mutation": False,
            "current": {
                "image": current,
                "image_id": predecessor_id,
            },
            "target": target.public(),
            "baseline_sha256": sha256_bytes(canonical(baseline.public())),
            "target_image_prestate": (
                "ABSENT" if target_prestate is None else "PRESENT_AND_EXACT"
            ),
            "target_archive_verified": archive_verified,
            "actions": [
                "verify_or_load_exact_target_image",
                f"quiesce_{target.component}_production_owner",
                f"replace_only_{target.component}_image_binding",
                "validate_effective_compose_delta_target_only",
                f"activate_{target.component}_production_owner",
                "verify_target_and_peer_hard_contracts",
                "verify_a1_soft_runtime_health",
            ],
            "rollback_available": True,
        }

    def apply(
        self,
        target: ComponentTarget,
        baseline: UpgradeBaseline,
        tar_path: Path,
        *,
        authorization_id: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if os.geteuid() != 0:
            raise UpdaterV2Error("root_required")
        if confirmation != APPLY_CONFIRMATION_V2:
            raise UpdaterV2Error("apply_confirmation_missing")
        if AUTHORIZATION_ID.fullmatch(authorization_id) is None:
            raise UpdaterV2Error("authorization_id_invalid")
        with self.store.lock():
            try:
                return self._apply_locked(
                    target,
                    baseline,
                    tar_path,
                    authorization_id=authorization_id,
                )
            finally:
                self.host.release_component_guard()

    def _apply_locked(
        self,
        target: ComponentTarget,
        baseline: UpgradeBaseline,
        tar_path: Path,
        *,
        authorization_id: str,
    ) -> dict[str, Any]:
        if sha256_file(tar_path) != target.target_archive_sha256:
            raise UpdaterV2Error("target_archive_sha256_mismatch")

        adapter = adapter_for(target.component)
        pre = self.host.inspect_v2()
        self.host.assert_mutation_safe(target.component)
        self.host.assert_component_upgradeable(target.component)
        pre_policy = self.policy.capture()
        self.policy.validate_pre(target.component, pre_policy)
        self._validate_baseline(
            target.component,
            baseline,
            pre,
            pre_policy,
        )

        predecessor = adapter.current_binding(pre)
        if predecessor != target.expected_predecessor_image_ref:
            raise UpdaterV2Error("target_predecessor_mismatch")
        predecessor_id = self.host.image_id(predecessor)
        if predecessor_id != pre["runtime"][target.component]["image_id"]:
            raise UpdaterV2Error("predecessor_image_authority_drift")

        target_prestate = self.host.image_id(target.target_image_ref)
        self.store.prepare_new()
        tx = {
            "schema": TX_SCHEMA_V2,
            "status": "APPLYING",
            "phase": "AUTHORIZED",
            "component": target.component,
            "authorization_id_sha256": sha256_bytes(
                authorization_id.encode("utf-8")
            ),
            "authorization_consumed": True,
            "predecessor_image": predecessor,
            "predecessor_image_id": predecessor_id,
            "predecessor_network_mode": pre["runtime"][target.component][
                "network_mode"
            ],
            "predecessor_runtime_contract_sha256": pre["runtime"][
                target.component
            ]["runtime_contract_sha256"],
            "pre_peer_runtime": adapter.peer_runtime_authority(pre),
            "pre_a1_policy": pre_policy,
            "baseline_sha256": sha256_bytes(canonical(baseline.public())),
            "target": target.public(),
            "started_at_unix": int(time.time()),
            "candidate_image_preexisting": target_prestate is not None,
        }
        self.store.write(tx)

        try:
            if target_prestate is None:
                self.host.load_image(tar_path)
            target_runtime_id = self.host.verify_image_archive(
                target.target_image_ref,
                tar_path,
                target.target_archive_sha256,
            )
            tx.update(
                phase="TARGET_IMAGE_READY",
                target_runtime_image_id=target_runtime_id,
            )
            self.store.write(tx)

            before_render = pre["compose_render"]
            tx.update(phase="QUIESCING")
            self.store.write(tx)
            adapter.quiesce(self.host)
            tx.update(phase="QUIESCED")
            self.store.write(tx)

            self.host.rewrite_component_image(
                target.component,
                predecessor,
                target.target_image_ref,
            )
            after_render = self.host.render_compose()
            validate_component_candidate(
                before_render,
                after_render,
                target.component,
                predecessor,
                target.target_image_ref,
            )
            tx.update(phase="TARGET_BINDING_PUBLISHED")
            self.store.write(tx)

            tx.update(phase="ACTIVATING")
            self.store.write(tx)
            adapter.activate(self.host)
            tx.update(phase="TARGET_RUNTIME_STARTED")
            self.store.write(tx)

            post = self.host.inspect_v2()
            adapter.verify_target_runtime(
                post,
                target,
                target_runtime_id,
                tx["predecessor_network_mode"],
            )
            if post["runtime"][target.component][
                "runtime_contract_sha256"
            ] != baseline.runtime_contract_sha256[target.component]:
                raise UpdaterV2Error("post_target_runtime_contract_drift")
            adapter.verify_peer_runtime(post, tx["pre_peer_runtime"])
            post_policy = self.policy.capture()
            self.policy.validate_post(
                target.component,
                pre_policy,
                post_policy,
            )
            tx.update(phase="VERIFYING")
            self.store.write(tx)

            tx.update(
                status="COMMITTED",
                phase="COMMITTED",
                committed_at_unix=int(time.time()),
                post_a1_policy_sha256=sha256_bytes(canonical(post_policy)),
            )
            self.store.write(tx)
            return {
                "schema": STATUS_SCHEMA_V2,
                "status": "PASS",
                "operation": "apply",
                "component": target.component,
                "transaction_status": "COMMITTED",
                "authorization_consumed": True,
                "runtime": self._public_snapshot(post),
                "t1_mutation": True,
            }
        except Exception as error:
            self._rollback_after_failure(
                target,
                tx,
                reason=type(error).__name__,
            )
            raise

    def _rollback_after_failure(
        self,
        target: ComponentTarget,
        tx: dict[str, Any],
        *,
        reason: str,
    ) -> None:
        adapter = adapter_for(target.component)
        try:
            if tx.get("phase") in {"AUTHORIZED", "TARGET_IMAGE_READY"}:
                current = self.host.inspect_v2()
                if (
                    adapter.current_binding(current) != tx["predecessor_image"]
                    or current["runtime"][target.component]["image_id"]
                    != tx["predecessor_image_id"]
                    or current["runtime"][target.component][
                        "runtime_contract_sha256"
                    ]
                    != tx["predecessor_runtime_contract_sha256"]
                ):
                    raise UpdaterV2Error("prestop_runtime_drift")
                adapter.verify_peer_runtime(current, tx["pre_peer_runtime"])
                self.policy.validate_post(
                    target.component,
                    tx["pre_a1_policy"],
                    self.policy.capture(),
                )
                tx.update(
                    status="ROLLED_BACK",
                    phase="ROLLED_BACK",
                    failure_reason=reason,
                    rolled_back_at_unix=int(time.time()),
                    t1_mutation=False,
                )
                self.store.write(tx)
                return

            adapter.quiesce(self.host)
            binding = self.host.component_binding_v2(target.component)
            if binding == target.target_image_ref:
                self.host.rewrite_component_image(
                    target.component,
                    target.target_image_ref,
                    tx["predecessor_image"],
                )
            elif binding != tx["predecessor_image"]:
                raise UpdaterV2Error("rollback_binding_unknown")
            adapter.activate(self.host)
            post = self.host.inspect_v2()
            if (
                adapter.current_binding(post) != tx["predecessor_image"]
                or post["runtime"][target.component]["image_id"]
                != tx["predecessor_image_id"]
                or post["runtime"][target.component][
                    "runtime_contract_sha256"
                ]
                != tx["predecessor_runtime_contract_sha256"]
            ):
                raise UpdaterV2Error("rollback_predecessor_runtime_invalid")
            adapter.verify_peer_runtime(post, tx["pre_peer_runtime"])
            self.policy.validate_post(
                target.component,
                tx["pre_a1_policy"],
                self.policy.capture(),
            )
            tx.update(
                status="ROLLED_BACK",
                phase="ROLLED_BACK",
                failure_reason=reason,
                rolled_back_at_unix=int(time.time()),
                t1_mutation=True,
            )
            self.store.write(tx)
        except Exception as rollback_error:
            tx.update(
                status="FAILED_EMERGENCY",
                phase="FAILED_EMERGENCY",
                failure_reason=reason,
                rollback_error=type(rollback_error).__name__,
            )
            self.store.write(tx)
            raise UpdaterV2Error("automatic_rollback_failed") from rollback_error

    def rollback(self, *, confirmation: str) -> dict[str, Any]:
        if os.geteuid() != 0:
            raise UpdaterV2Error("root_required")
        if confirmation != ROLLBACK_CONFIRMATION_V2:
            raise UpdaterV2Error("rollback_confirmation_missing")
        with self.store.lock():
            tx = self.store.read()
            if tx is None or tx.get("status") not in {
                "COMMITTED",
                "APPLYING",
                "ROLLING_BACK",
                "FAILED_EMERGENCY",
            }:
                raise UpdaterV2Error("recoverable_transaction_required")
            target_doc = tx.get("target")
            if not isinstance(target_doc, dict):
                raise UpdaterV2Error("rollback_transaction_authority_invalid")
            target = ComponentTarget(
                component=str(target_doc["component"]),
                mutation_profile=str(target_doc["mutation_profile"]),
                target_image_ref=str(target_doc["target_image_ref"]),
                target_platform=str(target_doc["target_platform"]),
                target_archive_sha256=str(target_doc["target_archive_sha256"]),
                artifact_identity=dict(target_doc["artifact_identity"]),
                expected_predecessor_image_ref=str(
                    target_doc["expected_predecessor_image_ref"]
                ),
                rollback_compatible=bool(target_doc["rollback_compatible"]),
                compatibility_evidence=dict(
                    target_doc["compatibility_evidence"]
                ),
                a1_classification_sha256=str(
                    target_doc["a1_classification_sha256"]
                ),
            )
            adapter = adapter_for(target.component)

            binding = self.host.component_binding_v2(target.component)
            if binding == tx["predecessor_image"]:
                try:
                    current = self.host.inspect_v2()
                except Exception:
                    current = None
                if current is not None and (
                    current["runtime"][target.component]["image_id"]
                    == tx["predecessor_image_id"]
                    and current["runtime"][target.component][
                        "runtime_contract_sha256"
                    ]
                    == tx["predecessor_runtime_contract_sha256"]
                ):
                    adapter.verify_peer_runtime(
                        current,
                        tx["pre_peer_runtime"],
                    )
                    self.policy.validate_post(
                        target.component,
                        tx["pre_a1_policy"],
                        self.policy.capture(),
                    )
                    tx.update(
                        status="ROLLED_BACK",
                        phase="ROLLED_BACK",
                        rolled_back_at_unix=int(time.time()),
                        t1_mutation=False,
                    )
                    self.store.write(tx)
                    return {
                        "schema": STATUS_SCHEMA_V2,
                        "status": "PASS",
                        "operation": "rollback",
                        "component": target.component,
                        "transaction_status": "ROLLED_BACK",
                        "t1_mutation": False,
                    }

            if binding not in {
                tx["predecessor_image"],
                target.target_image_ref,
            }:
                raise UpdaterV2Error("rollback_binding_unknown")

            if self.host.image_id(tx["predecessor_image"]) != tx[
                "predecessor_image_id"
            ]:
                raise UpdaterV2Error("rollback_predecessor_image_missing")

            tx.update(
                status="ROLLING_BACK",
                phase="ROLLBACK_AUTHORIZED",
            )
            self.store.write(tx)

            try:
                adapter.quiesce(self.host)
                if self.host.component_binding_v2(
                    target.component
                ) == target.target_image_ref:
                    before_render = self.host.render_compose()
                    self.host.rewrite_component_image(
                        target.component,
                        target.target_image_ref,
                        tx["predecessor_image"],
                    )
                    after_render = self.host.render_compose()
                    validate_component_candidate(
                        before_render,
                        after_render,
                        target.component,
                        target.target_image_ref,
                        tx["predecessor_image"],
                    )
                adapter.activate(self.host)
                post = self.host.inspect_v2()
                if (
                    adapter.current_binding(post) != tx["predecessor_image"]
                    or post["runtime"][target.component]["image_id"]
                    != tx["predecessor_image_id"]
                    or post["runtime"][target.component][
                        "runtime_contract_sha256"
                    ]
                    != tx["predecessor_runtime_contract_sha256"]
                ):
                    raise UpdaterV2Error(
                        "rollback_predecessor_runtime_invalid"
                    )
                adapter.verify_peer_runtime(post, tx["pre_peer_runtime"])
                self.policy.validate_post(
                    target.component,
                    tx["pre_a1_policy"],
                    self.policy.capture(),
                )
                tx.update(
                    status="ROLLED_BACK",
                    phase="ROLLED_BACK",
                    rolled_back_at_unix=int(time.time()),
                    t1_mutation=True,
                )
                self.store.write(tx)
                return {
                    "schema": STATUS_SCHEMA_V2,
                    "status": "PASS",
                    "operation": "rollback",
                    "component": target.component,
                    "transaction_status": "ROLLED_BACK",
                    "runtime": self._public_snapshot(post),
                    "t1_mutation": True,
                }
            except Exception as error:
                tx.update(
                    status="FAILED_EMERGENCY",
                    phase="FAILED_EMERGENCY",
                    rollback_error=type(error).__name__,
                )
                self.store.write(tx)
                raise
            finally:
                self.host.release_component_guard()

    def status(self) -> dict[str, Any]:
        transaction = self.store.read()
        legacy = self.store.read_legacy()
        return {
            "schema": STATUS_SCHEMA_V2,
            "status": "PASS",
            "operation": "status",
            "component": (
                transaction.get("component")
                if isinstance(transaction, dict)
                else None
            ),
            "mutation": False,
            "recovery_required": (
                transaction is not None
                and transaction.get("status") not in {
                    "COMMITTED",
                    "ROLLED_BACK",
                }
            )
            or (
                legacy is not None
                and legacy.get("status") not in {
                    "COMMITTED",
                    "ROLLED_BACK",
                }
            ),
            "transaction": transaction,
            "legacy_manager_transaction": legacy,
        }
