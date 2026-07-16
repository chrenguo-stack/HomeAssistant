from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .t1_manager_identity_postcommit_continuity_audit import (
    _PROTECTED_SERVICES,
    _TARGET,
    SCHEMA,
    CommandRunner,
    ManagerPostcommitContinuityAuditError,
    SubprocessRunner,
    _inspect,
    _parse_time,
    _private_directory,
    _private_json,
    _retained,
    _snapshot,
    _stable_socket,
    _validate_logs,
    _validate_manager_identity,
    _validate_retained,
    _validate_transaction,
    _workspace_digest,
)

_EXECUTION_SCHEMA_PREFIXES = (
    "gh.m2.t1-manager-identity-production-execution-packet/",
    "gh.m2.t1-manager-target-production-execution/",
)


def _file_fingerprint(path: Path) -> tuple[int, int, int, int, str]:
    if path.is_symlink() or not path.is_file():
        raise ManagerPostcommitContinuityAuditError(
            "manager production execution result is missing or unsafe"
        )
    metadata = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return (
        metadata.st_mode & 0o777,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_size,
        digest.hexdigest(),
    )


def _execution_result(
    path: Path,
    journal: Mapping[str, Any],
) -> dict[str, Any]:
    document = _private_json(path, "manager production execution result")
    schema = document.get("schema")
    if not isinstance(schema, str) or not schema.startswith(
        _EXECUTION_SCHEMA_PREFIXES
    ):
        raise ManagerPostcommitContinuityAuditError(
            "manager production execution result schema is invalid"
        )
    required = {
        "transaction_id": journal.get("transaction_id"),
        "authorization_id": journal.get("authorization_id"),
        "authorization_claimed": True,
        "authorization_consumed": True,
        "production_execution_completed": True,
        "postactivation_verified": True,
        "manager_identity_migrated": True,
        "greenhouse_manager_recreated": True,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    if any(
        document.get(field) != expected for field, expected in required.items()
    ):
        raise ManagerPostcommitContinuityAuditError(
            "manager production execution result binding is invalid"
        )
    return document


def build_manager_identity_postcommit_continuity_audit(
    transaction_workspace: str | Path,
    execution_result_file: str | Path,
    *,
    system_id: str,
    node_id: str,
    discovery_topic: str,
    mqtt_port: int = 1883,
    timeout_s: float = 8.0,
    poll_interval_s: float = 1.0,
    proc_root: str | Path = "/proc",
    runner: CommandRunner | None = None,
) -> dict[str, object]:
    if (
        not system_id
        or not node_id
        or not discovery_topic.startswith("homeassistant/")
        or "+" in discovery_topic
        or "#" in discovery_topic
        or not 1 <= mqtt_port <= 65535
        or timeout_s <= 0
        or poll_interval_s <= 0
    ):
        raise ValueError("postcommit continuity audit inputs are invalid")

    workspace = _private_directory(
        Path(transaction_workspace),
        "manager production transaction workspace",
    )
    execution_path = Path(execution_result_file).expanduser()
    if not execution_path.is_absolute() or execution_path.is_symlink():
        raise ManagerPostcommitContinuityAuditError(
            "manager production execution result path is unsafe"
        )
    execution_path = execution_path.resolve()

    before_workspace_digest = _workspace_digest(workspace)
    before_execution_fingerprint = _file_fingerprint(execution_path)
    journal = _private_json(
        workspace / "journal.json",
        "manager transaction journal",
    )
    execution = _execution_result(execution_path, journal)
    created_at, committed_at = _validate_transaction(journal, execution)

    command_runner = runner or SubprocessRunner()
    before_runtime = _snapshot(command_runner)
    manager = _inspect(command_runner, _TARGET)
    state = manager["State"]
    assert isinstance(state, dict)
    manager_started = _parse_time(state.get("StartedAt"), "manager started_at")
    if manager_started < created_at or manager_started > committed_at:
        raise ManagerPostcommitContinuityAuditError(
            "greenhouse-manager was not preserved from the committed transaction"
        )
    for name in _PROTECTED_SERVICES:
        started = _parse_time(before_runtime[name][2], f"{name} started_at")
        if started > created_at:
            raise ManagerPostcommitContinuityAuditError(
                "a protected service changed after the manager transaction began"
            )

    proc_path = Path(proc_root)
    pid = _validate_manager_identity(manager, proc_root=proc_path)
    if not _stable_socket(
        proc_path,
        pid,
        mqtt_port,
        timeout_s=timeout_s,
        poll_interval_s=poll_interval_s,
    ):
        raise ManagerPostcommitContinuityAuditError(
            "greenhouse-manager MQTT socket is not stable"
        )

    canonical_topic = f"gh/v1/{system_id}/state/{node_id}/telemetry"
    availability_topic = f"gh/v1/{system_id}/state/{node_id}/availability"
    canonical = _retained(command_runner, canonical_topic, timeout_s=timeout_s)
    availability = _retained(
        command_runner,
        availability_topic,
        timeout_s=timeout_s,
    )
    discovery = _retained(command_runner, discovery_topic, timeout_s=timeout_s)
    _validate_retained(
        canonical,
        availability,
        discovery,
        system_id=system_id,
        node_id=node_id,
    )
    _validate_logs(
        command_runner,
        started_at=str(state["StartedAt"]),
        system_id=system_id,
        node_id=node_id,
        discovery_topic=discovery_topic,
    )

    after_runtime = _snapshot(command_runner)
    after_workspace_digest = _workspace_digest(workspace)
    after_execution_fingerprint = _file_fingerprint(execution_path)
    if after_runtime != before_runtime:
        raise ManagerPostcommitContinuityAuditError(
            "a protected service changed during the read-only audit"
        )
    if after_workspace_digest != before_workspace_digest:
        raise ManagerPostcommitContinuityAuditError(
            "transaction files changed during the read-only audit"
        )
    if after_execution_fingerprint != before_execution_fingerprint:
        raise ManagerPostcommitContinuityAuditError(
            "execution result changed during the read-only audit"
        )

    checks = {
        "transaction_committed": True,
        "external_execution_result_bound": True,
        "execution_result_unchanged_during_audit": True,
        "manager_running_zero_restart": True,
        "manager_container_preserved_since_commit": True,
        "manager_authenticated_environment_present": True,
        "manager_password_mount_read_only": True,
        "manager_password_source_private": True,
        "manager_password_ownership_bound": True,
        "manager_mqtt_socket_stable": True,
        "ingress_subscription_continuous": True,
        "canonical_retained_continuous": True,
        "availability_retained_continuous": True,
        "discovery_retained_continuous": True,
        "existing_entity_identity_continuous": True,
        "anonymous_retained_compatibility_present": True,
        "mosquitto_unchanged": True,
        "homeassistant_unchanged": True,
        "protected_services_stable_during_audit": True,
        "transaction_files_unchanged_during_audit": True,
    }
    return {
        "schema": SCHEMA,
        "status": "manager_identity_postcommit_continuity_audit_succeeded",
        "read_only": True,
        "continuity_audit_passed": all(checks.values()),
        "checks": checks,
        "transaction_phase": "committed",
        "transaction_terminal": True,
        "execution_committed": True,
        "production_execution_completed": True,
        "postactivation_verified": True,
        "manager_identity_migrated": True,
        "greenhouse_manager_recreated": True,
        "runtime_manager_image_preserved": True,
        "runtime_manager_upgrade_performed": False,
        "rollback_completed": False,
        "rollback_failed": False,
        "mosquitto_modified": False,
        "homeassistant_modified": False,
        "nodes_modified": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "current_services_modified": False,
        "transaction_files_modified": False,
        "execution_result_file_modified": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "authorization_reused": False,
        "production_execution_invoked": False,
        "manual_recovery_required": False,
        "ready_for_broker_preactivation_fresh_evidence": True,
        "secret_values_included": False,
        "path_values_redacted": True,
        "container_ids_included": False,
        "image_ids_included": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a read-only continuity audit for a committed greenhouse-manager "
            "MQTT identity migration."
        )
    )
    parser.add_argument("transaction_workspace")
    parser.add_argument("execution_result_file")
    parser.add_argument("--system-id", required=True)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--discovery-topic", required=True)
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = build_manager_identity_postcommit_continuity_audit(
            args.transaction_workspace,
            args.execution_result_file,
            system_id=args.system_id,
            node_id=args.node_id,
            discovery_topic=args.discovery_topic,
            mqtt_port=args.mqtt_port,
            timeout_s=args.timeout_seconds,
            poll_interval_s=args.poll_interval_seconds,
        )
    except (
        ManagerPostcommitContinuityAuditError,
        OSError,
        UnicodeError,
        ValueError,
    ):
        print(
            "T1 manager postcommit continuity audit failed safely",
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            report,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0 if report["continuity_audit_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
