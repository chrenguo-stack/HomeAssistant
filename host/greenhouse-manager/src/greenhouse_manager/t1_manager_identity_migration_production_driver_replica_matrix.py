from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from .t1_manager_identity_migration_host_replica_adapters import (
    FAULT_PHASES as HOST_FAULT_PHASES,
)
from .t1_manager_identity_migration_host_replica_adapters import (
    ManagerHostReplicaTransactionAdapters,
    ManagerIdentityHostReplicaError,
    build_manager_host_replica_plan,
)
from .t1_manager_identity_migration_host_replica_adapters import (
    _tree_inventory as _host_tree_inventory,
)
from .t1_manager_identity_migration_production_driver_contract import (
    ManagerIdentityProductionDriverContractError,
    verify_manager_production_driver_contract,
)

PLAN_SCHEMA = "gh.m2.t1-manager-identity-production-driver-replica-plan/1"
TRANSACTION_SCHEMA = "gh.m2.t1-manager-identity-production-driver-replica-transaction/1"
MATRIX_SCHEMA = "gh.m2.t1-manager-identity-production-driver-replica-fault-matrix/1"
DRIVER_CONTRACT_SCHEMA = "gh.m2.t1-manager-identity-production-driver-contract/1"

PRE_MUTATION_FAULT_PHASES = (
    "after_authorization_claim",
    "after_runtime_revalidation",
    "after_fresh_rollback_verification",
)
POST_MUTATION_FAULT_PHASES = tuple(
    phase for phase in HOST_FAULT_PHASES if phase != "rollback_incomplete"
) + (
    "after_existing_entities",
    "after_journal_commit",
)
FAULT_PHASES = (
    *PRE_MUTATION_FAULT_PHASES,
    *POST_MUTATION_FAULT_PHASES,
    "rollback_incomplete",
)

_METHODS = (
    "claim_authorization",
    "revalidate_runtime",
    "verify_fresh_rollback",
    "install_manager_material",
    "recreate_manager",
    "verify_authenticated_identity",
    "verify_ingress_subscription",
    "verify_canonical_publication",
    "verify_discovery_publication",
    "verify_reconnect",
    "verify_existing_entities",
    "postactivation_audit",
    "rollback",
    "append_journal",
)
_REQUIRED_DRIVER_FLAGS = {
    "driver_contract_review_complete": True,
    "production_manager_driver_contract_available": True,
    "production_manager_driver_installed": False,
    "authorization_claimed": False,
    "claim_enabled": False,
    "fresh_rollback_bound": False,
    "production_executor_available": False,
    "execution_enabled": False,
    "apply_enabled": False,
    "operator_action_authorized": False,
    "ready_for_manager_migration_apply": False,
    "manager_identity_migrated": False,
    "node_credentials_delivered": False,
    "current_services_modified": False,
    "preserve_anonymous": True,
    "anonymous_closure_enabled": False,
    "secret_values_included": False,
    "path_values_redacted": True,
}

DriverContractVerifier = Callable[[dict[str, object]], dict[str, object]]
HostPlanBuilder = Callable[[str | Path, str | Path], dict[str, object]]


class ProductionReplicaManagerDriver(Protocol):
    def recreate_manager(
        self,
        *,
        environment_file: Path,
        password_file: Path,
        overlay_file: Path,
    ) -> None: ...

    def verify_authenticated_identity(self, username: str, client_id: str) -> None: ...

    def verify_ingress_subscription(self) -> None: ...

    def verify_canonical_publication(self) -> None: ...

    def verify_discovery_publication(self) -> None: ...

    def verify_reconnect(self) -> None: ...

    def verify_existing_entities(self) -> None: ...

    def postactivation_audit(self) -> dict[str, object]: ...

    def recreate_after_rollback(self) -> None: ...

    def verify_legacy_anonymous_path(self) -> None: ...


class HostAdapters(Protocol):
    plan: dict[str, object] | None
    workspace: Path | None
    baseline: Path | None
    baseline_inventory: tuple[tuple[str, int, str], ...] | None
    mutation_started: bool

    def prepare(self) -> None: ...

    def close(self) -> None: ...

    def mutation_executor(self) -> dict[str, object]: ...

    def postactivation_auditor(self) -> dict[str, object]: ...

    def rollback_executor(self) -> dict[str, object]: ...


AdaptersFactory = Callable[..., HostAdapters]
DriverFactory = Callable[[Path], ProductionReplicaManagerDriver]


class ManagerProductionDriverReplicaError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise ManagerProductionDriverReplicaError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManagerProductionDriverReplicaError(f"{label} is invalid") from error
    if not isinstance(document, dict):
        raise ManagerProductionDriverReplicaError(f"{label} must be a JSON object")
    return document


def _validated_driver_contract(
    driver_contract_file: str | Path,
    *,
    verifier: DriverContractVerifier,
) -> tuple[Path, dict[str, Any], str]:
    path = Path(driver_contract_file).expanduser().resolve()
    contract = _read_private_json(path, "manager production driver contract")
    result = verifier(contract)
    if result.get("verified") is not True:
        raise ManagerProductionDriverReplicaError(
            "manager production driver contract verification is incomplete"
        )
    digest = result.get("driver_contract_sha256")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or contract.get("driver_contract_sha256") != digest
    ):
        raise ManagerProductionDriverReplicaError(
            "manager production driver contract binding is invalid"
        )
    if contract.get("schema") != DRIVER_CONTRACT_SCHEMA:
        raise ManagerProductionDriverReplicaError(
            "manager production driver contract schema is invalid"
        )
    for field, expected in _REQUIRED_DRIVER_FLAGS.items():
        if contract.get(field) is not expected:
            raise ManagerProductionDriverReplicaError(
                f"manager production driver safety flag failed: {field}"
            )
    return path, contract, digest


def _bind_host_plan(
    contract: Mapping[str, Any],
    host_plan: Mapping[str, Any],
) -> None:
    bindings = {
        "preparation_manifest_sha256": "preparation_manifest_sha256",
        "manager_runtime_binding_sha256": "runtime_binding_sha256",
        "manager_username_fingerprint": "manager_username_fingerprint",
        "manager_client_id_fingerprint": "manager_client_id_fingerprint",
    }
    for contract_field, plan_field in bindings.items():
        if contract.get(contract_field) != host_plan.get(plan_field):
            raise ManagerProductionDriverReplicaError(
                f"manager production driver host-plan binding failed: {contract_field}"
            )
    required = {
        "replica_transaction_ready": True,
        "replica_only": True,
        "real_t1_target_allowed": False,
        "docker_commands_available": False,
        "authorization_claimed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_manager_migration_apply": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required.items():
        if host_plan.get(field) is not expected:
            raise ManagerProductionDriverReplicaError(
                f"manager host replica plan safety flag failed: {field}"
            )
    plan_sha = host_plan.get("plan_sha256")
    if not isinstance(plan_sha, str) or len(plan_sha) != 64:
        raise ManagerProductionDriverReplicaError(
            "manager host replica plan SHA-256 is invalid"
        )


def build_manager_production_driver_replica_plan(
    driver_contract_file: str | Path,
    preparation_directory: str | Path,
    replica_root: str | Path,
    *,
    driver_verifier: DriverContractVerifier = verify_manager_production_driver_contract,
    host_plan_builder: HostPlanBuilder = build_manager_host_replica_plan,
) -> dict[str, object]:
    _path, contract, driver_sha = _validated_driver_contract(
        driver_contract_file,
        verifier=driver_verifier,
    )
    try:
        host_plan = host_plan_builder(preparation_directory, replica_root)
    except ManagerIdentityHostReplicaError as error:
        raise ManagerProductionDriverReplicaError(
            "manager host replica plan could not be built"
        ) from error
    _bind_host_plan(contract, host_plan)
    plan: dict[str, object] = {
        "schema": PLAN_SCHEMA,
        "driver_contract_sha256": driver_sha,
        "adapter_contract_sha256": contract["adapter_contract_sha256"],
        "preparation_manifest_sha256": contract["preparation_manifest_sha256"],
        "manager_runtime_binding_sha256": contract[
            "manager_runtime_binding_sha256"
        ],
        "host_replica_plan_sha256": host_plan["plan_sha256"],
        "fault_phases": list(FAULT_PHASES),
        "method_inventory": list(_METHODS),
        "production_replica_fault_matrix_ready": True,
        "ready_for_live_runtime_gate": False,
        "replica_only": True,
        "real_t1_target_allowed": False,
        "docker_commands_available": False,
        "authorization_claimed": False,
        "production_manager_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_manager_migration_apply": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    plan["plan_sha256"] = _sha_bytes(_canonical_json(plan).encode("utf-8"))
    return plan


def _default_adapters_factory(*args: Any, **kwargs: Any) -> HostAdapters:
    return ManagerHostReplicaTransactionAdapters(*args, **kwargs)


class ManagerProductionDriverReplicaTransaction:
    def __init__(
        self,
        driver_contract_file: str | Path,
        preparation_directory: str | Path,
        replica_root: str | Path,
        *,
        driver: ProductionReplicaManagerDriver,
        fault_phase: str | None = None,
        driver_verifier: DriverContractVerifier = verify_manager_production_driver_contract,
        host_plan_builder: HostPlanBuilder = build_manager_host_replica_plan,
        adapters_factory: AdaptersFactory = _default_adapters_factory,
    ) -> None:
        if fault_phase is not None and fault_phase not in FAULT_PHASES:
            raise ValueError("unsupported manager production replica fault phase")
        self.driver_contract_file = Path(driver_contract_file).expanduser().resolve()
        self.preparation = Path(preparation_directory).expanduser().resolve()
        self.replica_root = Path(replica_root).expanduser().resolve()
        self.driver = driver
        self.fault_phase = fault_phase
        self.driver_verifier = driver_verifier
        self.host_plan_builder = host_plan_builder
        self.adapters_factory = adapters_factory
        self.contract: dict[str, Any] | None = None
        self.driver_contract_sha256: str | None = None
        self.plan: dict[str, object] | None = None
        self.adapters: HostAdapters | None = None
        self.journal_path: Path | None = None
        self.claim_path: Path | None = None
        self.method_coverage = {name: False for name in _METHODS}

    def __enter__(self) -> ManagerProductionDriverReplicaTransaction:
        self.prepare()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _phase(self, phase: str) -> None:
        if self.fault_phase == phase:
            raise ManagerProductionDriverReplicaError(
                f"injected manager production replica fault: {phase}"
            )

    def prepare(self) -> None:
        if self.adapters is not None:
            return
        _path, contract, driver_sha = _validated_driver_contract(
            self.driver_contract_file,
            verifier=self.driver_verifier,
        )
        self.contract = contract
        self.driver_contract_sha256 = driver_sha
        self.plan = build_manager_production_driver_replica_plan(
            self.driver_contract_file,
            self.preparation,
            self.replica_root,
            driver_verifier=self.driver_verifier,
            host_plan_builder=self.host_plan_builder,
        )
        base_fault = self.fault_phase if self.fault_phase in HOST_FAULT_PHASES else None
        try:
            adapters = self.adapters_factory(
                self.preparation,
                self.replica_root,
                driver=self.driver,
                fault_phase=base_fault,
            )
            adapters.prepare()
        except ManagerIdentityHostReplicaError as error:
            raise ManagerProductionDriverReplicaError(
                "manager production replica adapters could not be prepared"
            ) from error
        self.adapters = adapters
        if adapters.plan is None:
            raise ManagerProductionDriverReplicaError(
                "manager production replica host plan is unavailable"
            )
        _bind_host_plan(contract, adapters.plan)

    def close(self) -> None:
        if self.adapters is not None:
            self.adapters.close()
            self.adapters = None

    def _workspace(self) -> Path:
        self.prepare()
        if self.adapters is None or self.adapters.workspace is None:
            raise ManagerProductionDriverReplicaError(
                "manager production replica workspace is unavailable"
            )
        return self.adapters.workspace

    def _append_journal(self, phase: str, status: str) -> None:
        workspace = self._workspace()
        journal_root = workspace / "production-driver-journal"
        journal_root.mkdir(mode=0o700, exist_ok=True)
        journal_root.chmod(0o700)
        path = journal_root / "transaction.jsonl"
        record = {
            "schema": "gh.m2.t1-manager-production-driver-replica-journal/1",
            "driver_contract_sha256": self.driver_contract_sha256,
            "phase": phase,
            "status": status,
            "replica_only": True,
        }
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
                stream.write(_canonical_json(record) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            path.chmod(0o600)
        directory = os.open(journal_root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        self.journal_path = path
        self.method_coverage["append_journal"] = True

    def claim_authorization(self) -> None:
        workspace = self._workspace()
        source_root = workspace / "synthetic-authorization"
        claim_root = workspace / "claimed-authorization"
        source_root.mkdir(mode=0o700, exist_ok=True)
        claim_root.mkdir(mode=0o700, exist_ok=True)
        source_root.chmod(0o700)
        claim_root.chmod(0o700)
        source = source_root / "authorization.json"
        claim = claim_root / "authorization.claimed.json"
        payload = {
            "schema": "gh.m2.t1-manager-production-driver-replica-authorization/1",
            "driver_contract_sha256": self.driver_contract_sha256,
            "single_use": True,
            "consumed": False,
            "replica_only": True,
        }
        with source.open("x", encoding="utf-8") as stream:
            stream.write(_canonical_json(payload) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        source.chmod(0o600)
        source_inode = source.stat().st_ino
        os.link(source, claim)
        claim.chmod(0o600)
        claim_directory = os.open(claim_root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(claim_directory)
        finally:
            os.close(claim_directory)
        source.unlink()
        source_directory = os.open(source_root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(source_directory)
        finally:
            os.close(source_directory)
        if (
            source.exists()
            or not claim.is_file()
            or claim.is_symlink()
            or claim.stat().st_mode & 0o777 != 0o600
            or claim.stat().st_ino != source_inode
        ):
            raise ManagerProductionDriverReplicaError(
                "synthetic manager authorization claim verification failed"
            )
        self.claim_path = claim
        self.method_coverage["claim_authorization"] = True
        self._append_journal("authorization_claim", "verified")
        self._phase("after_authorization_claim")

    def revalidate_runtime(self) -> None:
        if self.contract is None or self.plan is None:
            self.prepare()
        assert self.contract is not None
        refreshed = self.host_plan_builder(self.preparation, self.replica_root)
        _bind_host_plan(self.contract, refreshed)
        if refreshed.get("plan_sha256") != self.plan.get("host_replica_plan_sha256"):
            raise ManagerProductionDriverReplicaError(
                "manager production replica runtime plan drifted"
            )
        self.method_coverage["revalidate_runtime"] = True
        self._append_journal("runtime_revalidation", "verified")
        self._phase("after_runtime_revalidation")

    def verify_fresh_rollback(self) -> None:
        self.prepare()
        assert self.adapters is not None
        if (
            self.adapters.baseline is None
            or self.adapters.baseline_inventory is None
            or not self.adapters.baseline_inventory
        ):
            raise ManagerProductionDriverReplicaError(
                "manager production replica rollback snapshot is unavailable"
            )
        baseline_manager = self.adapters.baseline / "manager"
        current_manager = self.replica_root / "manager"
        if (
            _host_tree_inventory(baseline_manager)
            != self.adapters.baseline_inventory
            or _host_tree_inventory(current_manager)
            != self.adapters.baseline_inventory
        ):
            raise ManagerProductionDriverReplicaError(
                "manager production replica rollback snapshot verification failed"
            )
        self.method_coverage["verify_fresh_rollback"] = True
        self._append_journal("fresh_rollback_verification", "verified")
        self._phase("after_fresh_rollback_verification")

    def execute(self) -> dict[str, object]:
        self.claim_authorization()
        self.revalidate_runtime()
        self.verify_fresh_rollback()
        assert self.adapters is not None
        mutation = self.adapters.mutation_executor()
        for method in (
            "install_manager_material",
            "recreate_manager",
            "verify_authenticated_identity",
            "verify_ingress_subscription",
            "verify_canonical_publication",
            "verify_discovery_publication",
            "verify_reconnect",
        ):
            self.method_coverage[method] = True
        self._append_journal("manager_mutation_and_core_verification", "verified")
        postactivation = self.adapters.postactivation_auditor()
        self.method_coverage["postactivation_audit"] = True
        self._append_journal("postactivation_audit", "verified")
        self.driver.verify_existing_entities()
        self.method_coverage["verify_existing_entities"] = True
        self._append_journal("existing_entities", "verified")
        self._phase("after_existing_entities")
        self._append_journal("journal_commit", "committed")
        self._phase("after_journal_commit")
        return {
            "mutation": mutation,
            "postactivation": postactivation,
            "authorization_claimed_in_replica": True,
            "runtime_revalidated_in_replica": True,
            "fresh_rollback_verified_in_replica": True,
            "existing_entities_verified_in_replica": True,
            "journal_committed_in_replica": True,
        }

    def rollback(self) -> dict[str, object]:
        self.prepare()
        assert self.adapters is not None
        report = self.adapters.rollback_executor()
        self.method_coverage["rollback"] = True
        self._append_journal("rollback", "verified")
        return report


def run_manager_production_driver_replica_transaction(
    driver_contract_file: str | Path,
    preparation_directory: str | Path,
    replica_root: str | Path,
    *,
    driver: ProductionReplicaManagerDriver,
    fault_phase: str | None = None,
    driver_verifier: DriverContractVerifier = verify_manager_production_driver_contract,
    host_plan_builder: HostPlanBuilder = build_manager_host_replica_plan,
    adapters_factory: AdaptersFactory = _default_adapters_factory,
) -> dict[str, object]:
    success: dict[str, object] | None = None
    rollback: dict[str, object] | None = None
    transaction_error: Exception | None = None
    rollback_error: Exception | None = None
    transaction = ManagerProductionDriverReplicaTransaction(
        driver_contract_file,
        preparation_directory,
        replica_root,
        driver=driver,
        fault_phase=fault_phase,
        driver_verifier=driver_verifier,
        host_plan_builder=host_plan_builder,
        adapters_factory=adapters_factory,
    )
    try:
        transaction.prepare()
        try:
            success = transaction.execute()
            if fault_phase is not None:
                raise ManagerProductionDriverReplicaError(
                    "manager production replica fault injection did not trigger"
                )
        except Exception as error:
            transaction_error = error
            if transaction.adapters is not None and transaction.adapters.mutation_started:
                try:
                    rollback = transaction.rollback()
                except Exception as after_rollback:
                    rollback_error = after_rollback
    finally:
        coverage = dict(transaction.method_coverage)
        mutation_started = bool(
            transaction.adapters is not None and transaction.adapters.mutation_started
        )
        transaction.close()
    if rollback_error is not None:
        raise ManagerProductionDriverReplicaError(
            "manager production replica transaction failed and rollback failed"
        ) from rollback_error
    pre_failure = transaction_error is not None and not mutation_started
    if transaction_error is not None and not pre_failure and rollback is None:
        raise ManagerProductionDriverReplicaError(
            "manager production replica transaction failed without verified rollback"
        ) from transaction_error
    return {
        "schema": TRANSACTION_SCHEMA,
        "fault_phase": fault_phase,
        "fault_injected": fault_phase is not None,
        "success_completed": success is not None,
        "pre_mutation_failure_contained": pre_failure,
        "mutation_started": mutation_started,
        "postactivation_verified": (
            success is not None
            and isinstance(success.get("postactivation"), dict)
            and success["postactivation"].get("manager_identity_verified") is True
        ),
        "existing_entities_verified": (
            success is not None
            and success.get("existing_entities_verified_in_replica") is True
        ),
        "rollback_completed": (
            rollback is not None and rollback.get("rollback_completed") is True
        ),
        "method_coverage": coverage,
        "manager_identity_migrated_in_replica": success is not None,
        "replica_only": True,
        "real_t1_target_allowed": False,
        "docker_commands_available": False,
        "production_manager_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_manager_migration_apply": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def run_manager_production_driver_replica_fault_matrix(
    driver_contract_file: str | Path,
    preparation_directory: str | Path,
    replica_template: str | Path,
    *,
    driver_factory: DriverFactory,
    driver_verifier: DriverContractVerifier = verify_manager_production_driver_contract,
    host_plan_builder: HostPlanBuilder = build_manager_host_replica_plan,
    adapters_factory: AdaptersFactory = _default_adapters_factory,
) -> dict[str, object]:
    template = Path(replica_template).expanduser().resolve()
    template_inventory = _host_tree_inventory(template)
    results: dict[str, object] = {}
    coverage = {name: False for name in _METHODS}
    with tempfile.TemporaryDirectory(
        prefix="gh-m2-manager-production-driver-matrix-"
    ) as temporary:
        matrix_root = Path(temporary)
        success_root = matrix_root / "success"
        shutil.copytree(template, success_root, copy_function=shutil.copy2)
        success = run_manager_production_driver_replica_transaction(
            driver_contract_file,
            preparation_directory,
            success_root,
            driver=driver_factory(success_root),
            driver_verifier=driver_verifier,
            host_plan_builder=host_plan_builder,
            adapters_factory=adapters_factory,
        )
        if (
            success.get("postactivation_verified") is not True
            or success.get("existing_entities_verified") is not True
            or success.get("rollback_completed") is not False
        ):
            raise ManagerProductionDriverReplicaError(
                "manager production driver replica success rehearsal did not complete"
            )
        for method, exercised in success["method_coverage"].items():
            coverage[method] = coverage[method] or exercised
        results["success"] = True

        for phase in FAULT_PHASES:
            candidate = matrix_root / phase
            shutil.copytree(template, candidate, copy_function=shutil.copy2)
            if phase == "rollback_incomplete":
                try:
                    run_manager_production_driver_replica_transaction(
                        driver_contract_file,
                        preparation_directory,
                        candidate,
                        driver=driver_factory(candidate),
                        fault_phase=phase,
                        driver_verifier=driver_verifier,
                        host_plan_builder=host_plan_builder,
                        adapters_factory=adapters_factory,
                    )
                except ManagerProductionDriverReplicaError as error:
                    results[phase] = "rollback failed" in str(error)
                    coverage["rollback"] = True
                else:
                    raise ManagerProductionDriverReplicaError(
                        "manager production replica incomplete rollback was not reported"
                    )
                continue
            report = run_manager_production_driver_replica_transaction(
                driver_contract_file,
                preparation_directory,
                candidate,
                driver=driver_factory(candidate),
                fault_phase=phase,
                driver_verifier=driver_verifier,
                host_plan_builder=host_plan_builder,
                adapters_factory=adapters_factory,
            )
            for method, exercised in report["method_coverage"].items():
                coverage[method] = coverage[method] or exercised
            if phase in PRE_MUTATION_FAULT_PHASES:
                if (
                    report.get("pre_mutation_failure_contained") is not True
                    or report.get("rollback_completed") is not False
                ):
                    raise ManagerProductionDriverReplicaError(
                        f"manager production pre-mutation fault was not contained: {phase}"
                    )
            elif report.get("rollback_completed") is not True:
                raise ManagerProductionDriverReplicaError(
                    f"manager production post-mutation fault did not roll back: {phase}"
                )
            if _host_tree_inventory(candidate) != template_inventory:
                raise ManagerProductionDriverReplicaError(
                    f"manager production replica fault changed baseline: {phase}"
                )
            results[phase] = True
    if _host_tree_inventory(template) != template_inventory:
        raise ManagerProductionDriverReplicaError(
            "manager production driver replica template changed during matrix"
        )
    return {
        "schema": MATRIX_SCHEMA,
        "success_rehearsal_passed": results.get("success") is True,
        "fault_results": results,
        "fault_phase_count": len(FAULT_PHASES),
        "all_faults_exercised": all(results.get(phase) is True for phase in FAULT_PHASES),
        "rollback_failure_reported_explicitly": (
            results.get("rollback_incomplete") is True
        ),
        "method_coverage": coverage,
        "all_driver_methods_exercised": all(coverage.values()),
        "template_immutable": True,
        "production_replica_fault_matrix_passed": True,
        "ready_for_live_runtime_gate": True,
        "replica_only": True,
        "real_t1_target_allowed": False,
        "docker_commands_available": False,
        "production_manager_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_manager_migration_apply": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a disabled production-driver replica fault-matrix plan for a "
            "marked temporary greenhouse-manager host replica."
        )
    )
    parser.add_argument("driver_contract_file")
    parser.add_argument("preparation_directory")
    parser.add_argument("replica_root")
    args = parser.parse_args(argv)
    try:
        report = build_manager_production_driver_replica_plan(
            args.driver_contract_file,
            args.preparation_directory,
            args.replica_root,
        )
    except (
        ManagerIdentityHostReplicaError,
        ManagerIdentityProductionDriverContractError,
        ManagerProductionDriverReplicaError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 manager production driver replica plan failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
