from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from .t1_broker_identity_host_replica_adapters import (
    FAULT_PHASES,
    BrokerIdentityHostReplicaError,
    ContractVerifier,
    ReplicaBrokerDriver,
    SkeletonVerifier,
    _tree_inventory,
    build_host_replica_plan,
    run_host_replica_transaction,
)
from .t1_broker_identity_production_adapter_skeleton import (
    BrokerIdentityProductionAdapterSkeletonError,
    verify_production_adapter_skeleton,
)
from .t1_broker_identity_production_executor_contract import (
    BrokerIdentityProductionExecutorContractError,
    verify_production_executor_contract,
)

SCHEMA = "gh.m2.t1-broker-identity-host-replica-fault-matrix/1"
PlanBuilder = Callable[..., dict[str, object]]
TransactionRunner = Callable[..., dict[str, object]]
DriverFactory = Callable[[], ReplicaBrokerDriver]


class InMemoryReplicaBrokerDriver:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.request_sha256: str | None = None

    def restart_mosquitto(self) -> None:
        self.events.append("restart_mosquitto")

    def wait_for_dynamic_security_state(self) -> None:
        self.events.append("wait_for_dynamic_security_state")

    def apply_exact_request(self, request: dict[str, Any]) -> None:
        self.events.append("apply_exact_request")
        payload = json.dumps(
            request,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.request_sha256 = hashlib.sha256(payload).hexdigest()

    def verify_provisioning_identity(self) -> None:
        self.events.append("verify_provisioning_identity")

    def delete_bootstrap_admin(self) -> None:
        self.events.append("delete_bootstrap_admin")

    def postactivation_audit(self) -> dict[str, object]:
        self.events.append("postactivation_audit")
        return {
            "activation_verified": True,
            "rollback_required": False,
            "broker_identity_activated": True,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }

    def restart_after_rollback(self) -> None:
        self.events.append("restart_after_rollback")

    def verify_anonymous_retained_state(self) -> None:
        self.events.append("verify_anonymous_retained_state")


def run_host_replica_fault_matrix(
    contract_file: str | Path,
    skeleton_file: str | Path,
    handoff_directory: str | Path,
    replica_template_root: str | Path,
    *,
    contract_verifier: ContractVerifier = verify_production_executor_contract,
    skeleton_verifier: SkeletonVerifier = verify_production_adapter_skeleton,
    plan_builder: PlanBuilder = build_host_replica_plan,
    transaction_runner: TransactionRunner = run_host_replica_transaction,
    driver_factory: DriverFactory = InMemoryReplicaBrokerDriver,
) -> dict[str, object]:
    contract = Path(contract_file).expanduser().resolve()
    skeleton = Path(skeleton_file).expanduser().resolve()
    handoff = Path(handoff_directory).expanduser().resolve()
    template = Path(replica_template_root).expanduser().resolve()
    plan = plan_builder(
        contract,
        skeleton,
        handoff,
        template,
        contract_verifier=contract_verifier,
        skeleton_verifier=skeleton_verifier,
    )
    if (
        plan.get("replica_transaction_ready") is not True
        or plan.get("replica_only") is not True
        or plan.get("real_t1_target_allowed") is not False
        or plan.get("docker_commands_available") is not False
        or plan.get("current_services_modified") is not False
    ):
        raise BrokerIdentityHostReplicaError(
            "host replica fault matrix plan is unsafe or incomplete"
        )

    template_inventory = _tree_inventory(template)
    scenarios: dict[str, dict[str, object]] = {}
    for phase in FAULT_PHASES:
        scenario_parent = Path(
            tempfile.mkdtemp(prefix="gh-m2-host-replica-fault-")
        )
        scenario_parent.chmod(0o700)
        scenario = scenario_parent / "replica"
        try:
            shutil.copytree(template, scenario, copy_function=shutil.copy2)
            driver = driver_factory()
            if phase == "rollback_incomplete":
                try:
                    transaction_runner(
                        contract,
                        skeleton,
                        handoff,
                        scenario,
                        driver=driver,
                        fault_phase=phase,
                        contract_verifier=contract_verifier,
                        skeleton_verifier=skeleton_verifier,
                    )
                except BrokerIdentityHostReplicaError as error:
                    explicit = "rollback failed" in str(error)
                    scenarios[phase] = {
                        "fault_injected": True,
                        "rollback_failed_reported": explicit,
                        "scenario_isolated": True,
                    }
                    if not explicit:
                        raise BrokerIdentityHostReplicaError(
                            "rollback-incomplete fault was not explicit"
                        ) from error
                else:
                    raise BrokerIdentityHostReplicaError(
                        "rollback-incomplete fault did not fail"
                    )
                continue

            report = transaction_runner(
                contract,
                skeleton,
                handoff,
                scenario,
                driver=driver,
                fault_phase=phase,
                contract_verifier=contract_verifier,
                skeleton_verifier=skeleton_verifier,
            )
            if (
                report.get("fault_injected") is not True
                or report.get("rollback_completed") is not True
                or report.get("replica_only") is not True
                or report.get("current_services_modified") is not False
            ):
                raise BrokerIdentityHostReplicaError(
                    f"host replica fault scenario did not force rollback: {phase}"
                )
            if _tree_inventory(scenario) != template_inventory:
                raise BrokerIdentityHostReplicaError(
                    f"host replica fault scenario did not restore baseline: {phase}"
                )
            scenarios[phase] = {
                "fault_injected": True,
                "rollback_completed": True,
                "baseline_restored": True,
                "scenario_isolated": True,
            }
        finally:
            shutil.rmtree(scenario_parent, ignore_errors=True)

    if _tree_inventory(template) != template_inventory:
        raise BrokerIdentityHostReplicaError(
            "host replica template changed during fault matrix"
        )
    if set(scenarios) != set(FAULT_PHASES):
        raise BrokerIdentityHostReplicaError(
            "host replica fault matrix did not exercise every phase"
        )
    return {
        "schema": SCHEMA,
        "scenarios": scenarios,
        "all_faults_exercised": True,
        "forced_rollback_verified": True,
        "rollback_failure_explicit": True,
        "template_immutable": True,
        "scenario_isolation_verified": True,
        "replica_only": True,
        "real_t1_target_allowed": False,
        "docker_commands_available": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the complete Broker identity failure matrix on independent "
            "temporary host-replica copies using an in-memory Broker driver."
        )
    )
    parser.add_argument("contract_file")
    parser.add_argument("skeleton_file")
    parser.add_argument("handoff_directory")
    parser.add_argument("replica_template_root")
    args = parser.parse_args(argv)
    try:
        report = run_host_replica_fault_matrix(
            args.contract_file,
            args.skeleton_file,
            args.handoff_directory,
            args.replica_template_root,
        )
    except (
        BrokerIdentityHostReplicaError,
        BrokerIdentityProductionAdapterSkeletonError,
        BrokerIdentityProductionExecutorContractError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 Broker host replica fault matrix failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
