from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .t1_manager_identity_migration_execution_preparation_capture import (
    _create_rollback,
    _reject_overlap,
    _source_inventory,
)
from .t1_manager_identity_migration_execution_preparation_common import (
    OUTPUT_PREFIX,
    PLAN_SCHEMA,
    REQUIRED_SEQUENCE,
    SCHEMA,
    ManagerIdentityExecutionPreparationError,
    canonical,
    fsync_dir,
    private_dir,
    private_file,
    record,
    sha_path,
    validate_gate,
    validate_preparation,
    write_json,
    write_private,
)
from .t1_manager_identity_migration_execution_preparation_verify import (
    verify_manager_identity_execution_preparation,
)
from .t1_manager_identity_migration_live_runtime_gate import (
    ManagerIdentityLiveRuntimeGateError,
    build_manager_identity_live_runtime_gate,
)
from .t1_manager_identity_migration_production_driver_contract import (
    ManagerIdentityProductionDriverContractError,
)
from .t1_manager_identity_migration_production_transaction_adapter_contract import (
    ManagerIdentityProductionTransactionAdapterContractError,
)
from .t1_migration_readiness import CommandRunner, SubprocessRunner

LiveGateBuilder = Callable[..., dict[str, object]]
TokenFactory = Callable[[], str]


def _output_root(path: Path) -> Path:
    if not path.name.startswith(OUTPUT_PREFIX):
        raise ManagerIdentityExecutionPreparationError(
            "execution preparation output directory name is not allowed"
        )
    return private_dir(path, "execution preparation output directory", create=True)


def prepare_manager_identity_execution(
    driver_contract_file: str | Path,
    preparation_directory: str | Path,
    output_directory: str | Path,
    *,
    freshness_seconds: int = 900,
    runner: CommandRunner | None = None,
    now: datetime | None = None,
    token_factory: TokenFactory | None = None,
    live_gate_builder: LiveGateBuilder = build_manager_identity_live_runtime_gate,
) -> dict[str, object]:
    if freshness_seconds < 60 or freshness_seconds > 1800:
        raise ValueError("freshness seconds must be between 60 and 1800")
    driver = private_file(Path(driver_contract_file).expanduser().resolve(), "driver contract")
    preparation_root = Path(preparation_directory).expanduser().resolve()
    preparation = validate_preparation(preparation_root)
    output = _output_root(Path(output_directory).expanduser().resolve())
    command_runner = runner or SubprocessRunner()
    first_gate = live_gate_builder(driver, preparation_root, runner=command_runner)
    validate_gate(first_gate)
    runtime = preparation["runtime"]
    inventory, protected = _source_inventory(runtime)
    _reject_overlap(output, (preparation_root, driver, *protected))
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    expires = observed + timedelta(seconds=freshness_seconds)
    token = token_factory() if token_factory else secrets.token_hex(4)
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{4,32}", token):
        raise ManagerIdentityExecutionPreparationError(
            "execution preparation token is invalid"
        )
    name = f"greenhouse-manager-execution-preparation-{observed:%Y%m%dT%H%M%SZ}-{token}"
    destination = output / name
    if destination.exists():
        raise ManagerIdentityExecutionPreparationError(
            "execution preparation destination already exists"
        )
    with tempfile.TemporaryDirectory(prefix=".gh-manager-execution-", dir=output) as temporary:
        root = Path(temporary) / name
        root.mkdir(mode=0o700)
        created_at = observed.isoformat(timespec="seconds").replace("+00:00", "Z")
        expires_at = expires.isoformat(timespec="seconds").replace("+00:00", "Z")
        rollback_path = root / "fresh-manager-rollback.tar.gz"
        rollback_manifest_path = root / "fresh-rollback-manifest.json"
        _create_rollback(
            rollback_path,
            rollback_manifest_path,
            inventory,
            runtime,
            first_gate,
            preparation,
            created_at,
        )
        second_gate = live_gate_builder(driver, preparation_root, runner=command_runner)
        validate_gate(second_gate)
        if canonical(first_gate) != canonical(second_gate):
            raise ManagerIdentityExecutionPreparationError(
                "live runtime gate drifted during rollback capture"
            )
        gate_path = root / "live-runtime-gate.json"
        write_json(gate_path, second_gate)
        plan = {
            "schema": PLAN_SCHEMA,
            "created_at": created_at,
            "expires_at": expires_at,
            "required_sequence": REQUIRED_SEQUENCE,
            "restart_scope": ["greenhouse-manager"],
            "forbidden_service_changes": ["mosquitto", "homeassistant", "node"],
            "fresh_rollback_required": True,
            "fresh_rollback_captured": True,
            "fresh_rollback_verified": True,
            "execution_preparation_ready": True,
            "authorization_created": False,
            "authorization_claimed": False,
            "production_manager_driver_installed": False,
            "production_executor_available": False,
            "execution_enabled": False,
            "apply_enabled": False,
            "operator_action_authorized": False,
            "ready_for_manager_migration_authorization": True,
            "ready_for_manager_migration_apply": False,
            "manager_identity_migrated": False,
            "node_credentials_delivered": False,
            "current_services_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }
        plan_path = root / "execution-plan.json"
        write_json(plan_path, plan)
        runbook_path = root / "operator-runbook.txt"
        write_private(
            runbook_path,
            (
                b"Manager identity execution preparation only.\n"
                b"The fresh rollback archive expires with this package.\n"
                b"No authorization, credential installation, Compose edit, container recreate, "
                b"manager migration, node credential delivery, or anonymous closure is authorized.\n"
            ),
        )
        records = [
            record(rollback_path, root, contains_secret=True),
            record(rollback_manifest_path, root, contains_secret=True),
            record(gate_path, root, contains_secret=False),
            record(plan_path, root, contains_secret=False),
            record(runbook_path, root, contains_secret=False),
        ]
        manifest = {
            "schema": SCHEMA,
            "created_at": created_at,
            "expires_at": expires_at,
            "classification": "secret-local-manager-execution-preparation",
            "prepared": True,
            "fresh_rollback_captured": True,
            "fresh_rollback_verified": True,
            "execution_preparation_ready": True,
            "read_only_live_services": True,
            "current_services_modified": False,
            "authorization_created": False,
            "authorization_claimed": False,
            "production_manager_driver_installed": False,
            "production_executor_available": False,
            "execution_enabled": False,
            "apply_enabled": False,
            "operator_action_authorized": False,
            "broker_identity_activated": True,
            "homeassistant_authenticated": True,
            "manager_identity_migrated": False,
            "node_credentials_delivered": False,
            "ready_for_manager_migration_authorization": True,
            "ready_for_manager_migration_apply": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "bindings": {
                "fresh_rollback_archive_sha256": sha_path(rollback_path),
                "fresh_rollback_manifest_sha256": sha_path(rollback_manifest_path),
                "runtime_binding_sha256": second_gate["runtime_binding_sha256"],
                "driver_contract_sha256": second_gate["driver_contract_sha256"],
                "adapter_contract_sha256": second_gate["adapter_contract_sha256"],
                "live_binding_sha256": second_gate["live_binding_sha256"],
                "preparation_manifest_sha256": preparation["manifest_sha256"],
                "preparation_record_set_sha256": preparation["record_set_sha256"],
            },
            "records": records,
            "secret_values_included": True,
            "normal_report_contains_secrets": False,
            "normal_report_contains_source_paths": False,
        }
        manifest_path = root / "manifest.json"
        write_json(manifest_path, manifest)
        manifest_sha = sha_path(manifest_path)
        os.replace(root, destination)
        fsync_dir(output)
    verified = verify_manager_identity_execution_preparation(
        destination,
        now=observed,
        require_fresh=True,
    )
    if verified.get("verified") is not True:
        raise ManagerIdentityExecutionPreparationError(
            "execution preparation package verification failed"
        )
    report = {
        "schema": SCHEMA,
        "prepared": True,
        "execution_preparation_name": name,
        "manifest_sha256": manifest_sha,
        "expires_at": expires_at,
        "fresh_rollback_captured": True,
        "fresh_rollback_verified": True,
        "execution_preparation_ready": True,
        "read_only_live_services": True,
        "current_services_modified": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "production_manager_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "broker_identity_activated": True,
        "homeassistant_authenticated": True,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "ready_for_manager_migration_authorization": True,
        "ready_for_manager_migration_apply": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "source_paths_included": False,
    }
    serialized = canonical(report)
    if any(str(path) in serialized for path in (driver, preparation_root, output, *protected)):
        raise ManagerIdentityExecutionPreparationError(
            "sanitized execution preparation report contains a protected path"
        )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Capture a fresh manager-only rollback and build a non-executable "
            "real-T1 manager migration execution preparation package."
        )
    )
    parser.add_argument("driver_contract_file")
    parser.add_argument("preparation_directory")
    parser.add_argument("--output", required=True)
    parser.add_argument("--freshness-seconds", type=int, default=900)
    args = parser.parse_args(argv)
    try:
        report = prepare_manager_identity_execution(
            args.driver_contract_file,
            args.preparation_directory,
            args.output,
            freshness_seconds=args.freshness_seconds,
        )
    except (
        ManagerIdentityExecutionPreparationError,
        ManagerIdentityLiveRuntimeGateError,
        ManagerIdentityProductionDriverContractError,
        ManagerIdentityProductionTransactionAdapterContractError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 manager execution preparation failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
