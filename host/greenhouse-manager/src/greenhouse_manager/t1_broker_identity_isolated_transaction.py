from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .dynsec_api import DynsecError
from .t1_backup import BackupError, _extract_verified
from .t1_broker_identity_activation_checks import (
    BrokerIdentityActivationCheckError,
    Runner,
    Verifier,
)
from .t1_broker_identity_activation_handoff import (
    BrokerIdentityActivationHandoffError,
    verify_broker_identity_activation_handoff,
)
from .t1_broker_identity_isolated_adapters import (
    FAULT_PHASES,
    BackupExtractor,
    IsolatedBrokerIdentitySnapshotAdapters,
    NameFactory,
    StageVerifier,
    WaitForFile,
)
from .t1_broker_identity_isolated_helpers import (
    BrokerIdentityIsolatedTransactionError,
)
from .t1_migration_stage import MigrationStageError, verify_migration_stage
from .t1_shadow import ShadowError, SubprocessRunner, _wait_for_file

SCHEMA = "gh.m2.t1-broker-identity-isolated-transaction/1"
FAULT_MATRIX_SCHEMA = "gh.m2.t1-broker-identity-isolated-fault-matrix/1"


def run_isolated_snapshot_transaction(
    handoff_directory: str | Path,
    stage_directory: str | Path,
    *,
    expected_retained_topic: str,
    fault_phase: str | None = None,
    runner: Runner | None = None,
    name_factory: NameFactory | None = None,
    handoff_verifier: Verifier = verify_broker_identity_activation_handoff,
    stage_verifier: StageVerifier = verify_migration_stage,
    backup_extractor: BackupExtractor = _extract_verified,
    wait_for_file: WaitForFile = _wait_for_file,
) -> dict[str, object]:
    command_runner = runner or SubprocessRunner()
    adapters = IsolatedBrokerIdentitySnapshotAdapters(
        handoff_directory,
        stage_directory,
        expected_retained_topic=expected_retained_topic,
        runner=command_runner,
        fault_phase=fault_phase,
        name_factory=name_factory,
        handoff_verifier=handoff_verifier,
        stage_verifier=stage_verifier,
        backup_extractor=backup_extractor,
        wait_for_file=wait_for_file,
    )
    mutation: dict[str, object] | None = None
    postactivation: dict[str, object] | None = None
    rollback: dict[str, object] | None = None
    fault_error: Exception | None = None
    rollback_error: Exception | None = None
    with adapters:
        try:
            mutation = adapters.mutation_executor(
                adapters.handoff,
                command_runner,
            )
            postactivation = adapters.postactivation_auditor(
                adapters.handoff,
                command_runner,
            )
            if postactivation.get("activation_verified") is not True:
                raise BrokerIdentityIsolatedTransactionError(
                    "isolated postactivation audit failed"
                )
            if fault_phase is not None:
                raise BrokerIdentityIsolatedTransactionError(
                    "isolated fault injection did not trigger"
                )
        except Exception as error:
            fault_error = error
            if adapters.snapshot_mutation_started:
                try:
                    rollback = adapters.rollback_executor(
                        adapters.handoff,
                        command_runner,
                    )
                except Exception as error_after_rollback:
                    rollback_error = error_after_rollback
        source_immutable = adapters.sources_unchanged()

    if rollback_error is not None:
        raise BrokerIdentityIsolatedTransactionError(
            "isolated transaction failed and rollback failed"
        ) from rollback_error
    if not source_immutable:
        raise BrokerIdentityIsolatedTransactionError(
            "isolated transaction changed handoff or stage sources"
        )
    if fault_error is not None and not adapters.snapshot_mutation_started:
        raise fault_error
    if fault_error is not None and rollback is None:
        raise BrokerIdentityIsolatedTransactionError(
            "isolated transaction failed without verified rollback"
        ) from fault_error

    fault_injected = fault_phase is not None
    return {
        "schema": SCHEMA,
        "fault_phase": fault_phase,
        "fault_injected": fault_injected,
        "mutation_completed": mutation is not None,
        "postactivation_verified": (
            postactivation is not None
            and postactivation.get("activation_verified") is True
        ),
        "rollback_completed": (
            rollback is not None
            and rollback.get("rollback_completed") is True
        ),
        "candidate_cleanup_verified": True,
        "handoff_immutable": True,
        "stage_immutable": True,
        "network": "none",
        "isolated_snapshot": True,
        "production_executor_available": False,
        "live_activation_enabled": False,
        "apply_enabled": False,
        "active_paths_modified": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def run_isolated_fault_matrix(
    handoff_directory: str | Path,
    stage_directory: str | Path,
    *,
    expected_retained_topic: str,
    runner: Runner | None = None,
    name_factory: NameFactory | None = None,
    handoff_verifier: Verifier = verify_broker_identity_activation_handoff,
    stage_verifier: StageVerifier = verify_migration_stage,
    backup_extractor: BackupExtractor = _extract_verified,
    wait_for_file: WaitForFile = _wait_for_file,
) -> dict[str, object]:
    command_runner = runner or SubprocessRunner()
    scenarios: dict[str, dict[str, object]] = {}
    for phase in FAULT_PHASES:
        if phase == "rollback_incomplete":
            try:
                run_isolated_snapshot_transaction(
                    handoff_directory,
                    stage_directory,
                    expected_retained_topic=expected_retained_topic,
                    fault_phase=phase,
                    runner=command_runner,
                    name_factory=name_factory,
                    handoff_verifier=handoff_verifier,
                    stage_verifier=stage_verifier,
                    backup_extractor=backup_extractor,
                    wait_for_file=wait_for_file,
                )
            except BrokerIdentityIsolatedTransactionError as error:
                scenarios[phase] = {
                    "fault_injected": True,
                    "rollback_failed_reported": "rollback failed" in str(error),
                }
            else:
                raise BrokerIdentityIsolatedTransactionError(
                    "rollback-incomplete fault was not reported"
                )
            continue
        report = run_isolated_snapshot_transaction(
            handoff_directory,
            stage_directory,
            expected_retained_topic=expected_retained_topic,
            fault_phase=phase,
            runner=command_runner,
            name_factory=name_factory,
            handoff_verifier=handoff_verifier,
            stage_verifier=stage_verifier,
            backup_extractor=backup_extractor,
            wait_for_file=wait_for_file,
        )
        scenarios[phase] = {
            "fault_injected": report["fault_injected"],
            "rollback_completed": report["rollback_completed"],
            "candidate_cleanup_verified": report[
                "candidate_cleanup_verified"
            ],
        }
    if any(
        item.get("fault_injected") is not True
        or (
            item.get("rollback_completed") is not True
            and item.get("rollback_failed_reported") is not True
        )
        for item in scenarios.values()
    ):
        raise BrokerIdentityIsolatedTransactionError(
            "isolated fault matrix is incomplete"
        )
    return {
        "schema": FAULT_MATRIX_SCHEMA,
        "scenarios": scenarios,
        "all_faults_exercised": True,
        "forced_rollback_verified": True,
        "rollback_failure_explicit": True,
        "candidate_cleanup_verified": True,
        "handoff_immutable": True,
        "stage_immutable": True,
        "network": "none",
        "isolated_snapshot": True,
        "production_executor_available": False,
        "live_activation_enabled": False,
        "apply_enabled": False,
        "active_paths_modified": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Runner | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Exercise Broker identity mutation, postactivation and rollback "
            "adapters only on a temporary --network none snapshot."
        )
    )
    parser.add_argument("handoff_directory")
    parser.add_argument("stage_directory")
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument("--fault-phase", choices=FAULT_PHASES)
    parser.add_argument("--fault-matrix", action="store_true")
    args = parser.parse_args(argv)
    if args.fault_matrix and args.fault_phase:
        parser.error("--fault-matrix and --fault-phase are mutually exclusive")
    try:
        if args.fault_matrix:
            report = run_isolated_fault_matrix(
                args.handoff_directory,
                args.stage_directory,
                expected_retained_topic=args.expected_retained_topic,
                runner=runner,
            )
        else:
            report = run_isolated_snapshot_transaction(
                args.handoff_directory,
                args.stage_directory,
                expected_retained_topic=args.expected_retained_topic,
                fault_phase=args.fault_phase,
                runner=runner,
            )
    except (
        BackupError,
        BrokerIdentityActivationCheckError,
        BrokerIdentityActivationHandoffError,
        BrokerIdentityIsolatedTransactionError,
        DynsecError,
        MigrationStageError,
        ShadowError,
        OSError,
        ValueError,
    ) as error:
        print(
            f"T1 Broker isolated transaction failed: {error}",
            file=sys.stderr,
        )
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
