from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, TextIO

from ..runtime.credential_lifecycle import (
    CredentialLifecycleConflict,
    CredentialLifecycleStore,
)
from ..runtime.n3w_auto_node_id import AutomaticNodeIdApprover
from ..runtime.registration import RegistrationConflict, RegistrationRecord, RegistrationRegistry
from ..runtime.replay_registry import ReplayRegistry, ReplayRegistryUnavailable

DEFAULT_DB_PATH = "/var/lib/greenhouse-manager/registration.sqlite3"
DEFAULT_CREDENTIAL_DB_PATH = "/var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3"
ContainerInspector = Callable[[str], object]


def _docker_inspect_container(container_name: str) -> object:
    try:
        completed = subprocess.run(
            ("docker", "inspect", "--type", "container", container_name),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise RegistrationConflict("manager container inspection unavailable") from exc
    if completed.returncode != 0:
        raise RegistrationConflict("manager container inspection failed")
    try:
        documents = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RegistrationConflict("manager container inspection invalid") from exc
    if not isinstance(documents, list) or len(documents) != 1:
        raise RegistrationConflict("manager container inspection ambiguous")
    return documents[0]


def _container_path_binding_matches(
    mounts: object,
    *,
    host_path: Path,
    container_path: str,
) -> bool:
    if not isinstance(mounts, list):
        return False
    requested = PurePosixPath(container_path)
    if not requested.is_absolute():
        return False
    try:
        resolved_host = host_path.resolve(strict=True)
    except OSError:
        return False

    matches = 0
    for mount in mounts:
        if not isinstance(mount, Mapping) or mount.get("Type") != "bind":
            continue
        source = mount.get("Source")
        destination = mount.get("Destination")
        if not isinstance(source, str) or not isinstance(destination, str):
            continue
        destination_path = PurePosixPath(destination)
        try:
            relative = requested.relative_to(destination_path)
        except ValueError:
            continue
        try:
            bound_host = (Path(source) / Path(*relative.parts)).resolve(strict=True)
        except OSError:
            continue
        if bound_host == resolved_host:
            matches += 1
    return matches == 1


def _verify_stopped_manager_and_database_bindings(
    document: object,
    *,
    container_name: str,
    registration_db: Path,
    registration_container_path: str,
    credential_db: Path,
    credential_container_path: str,
) -> None:
    if not isinstance(document, Mapping):
        raise RegistrationConflict("manager container inspection invalid")
    name = document.get("Name")
    if not isinstance(name, str) or name.removeprefix("/") != container_name:
        raise RegistrationConflict("manager container identity mismatch")
    state = document.get("State")
    if not isinstance(state, Mapping) or not (
        state.get("Status") == "exited"
        and state.get("Running") is False
        and state.get("Restarting") is False
        and state.get("Paused") is False
        and state.get("Pid") == 0
    ):
        raise RegistrationConflict("manager container process is not proven stopped")

    mounts = document.get("Mounts")
    if not _container_path_binding_matches(
        mounts,
        host_path=registration_db,
        container_path=registration_container_path,
    ):
        raise RegistrationConflict("registration database binding mismatch")
    if not _container_path_binding_matches(
        mounts,
        host_path=credential_db,
        container_path=credential_container_path,
    ):
        raise RegistrationConflict("credential database binding mismatch")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage M2 pending registrations")
    parser.add_argument(
        "--db",
        default=os.getenv("GH_PAIRING_DB_PATH", DEFAULT_DB_PATH),
        help="registration SQLite path",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="list current registration records")

    events = subparsers.add_parser("events", help="list secret-free audit events")
    events.add_argument("--hardware-id")
    events.add_argument("--limit", type=int, default=100)

    approve = subparsers.add_parser(
        "approve",
        help="record operator approval with Manager-assigned NODE_ID",
    )
    approve.add_argument("hardware_id")
    approve.add_argument("pairing_id")
    approve.add_argument(
        "--logical-location-id",
        required=True,
        help="stable logical monitoring location bound to the Manager-assigned node_id",
    )
    reject = subparsers.add_parser("reject", help="reject a pending registration")
    reject.add_argument("hardware_id")
    reject.add_argument("pairing_id")
    reject.add_argument("--reason", default="user_rejected")

    subparsers.add_parser("expire", help="expire overdue pending registrations")

    abandon = subparsers.add_parser(
        "abandon-expired-first",
        help=("release an expired, never-approved first registration while preserving its replay tombstone"),
    )
    abandon.add_argument("hardware_id")
    abandon.add_argument("pairing_id")
    abandon.add_argument(
        "--credential-db",
        required=True,
        help="existing credential lifecycle SQLite path used for the no-history gate",
    )
    abandon.add_argument(
        "--manager-container",
        required=True,
        help="exact stopped Manager container whose database mounts must be verified",
    )
    abandon.add_argument(
        "--registration-container-path",
        default=DEFAULT_DB_PATH,
        help="registration database path inside the Manager container",
    )
    abandon.add_argument(
        "--credential-container-path",
        default=DEFAULT_CREDENTIAL_DB_PATH,
        help="credential lifecycle database path inside the Manager container",
    )
    abandon.add_argument(
        "--reason",
        default="expired_first_pairing_recovery",
    )
    abandon.add_argument(
        "--confirm-manager-stopped",
        action="store_true",
        help="confirm that no Manager runtime can write either database",
    )

    replay_audit = subparsers.add_parser(
        "n3w-replay-audit",
        help="audit an existing Manager-owned N3-W replay registry without mutation",
    )
    replay_audit.add_argument("--replay-db", required=True)

    replay_inspect = subparsers.add_parser(
        "n3w-replay-inspect",
        help="inspect one tuple in an existing N3-W replay registry without mutation",
    )
    replay_inspect.add_argument("--replay-db", required=True)
    replay_inspect.add_argument("--node-id", required=True)
    replay_inspect.add_argument("--boot-id", required=True)
    replay_inspect.add_argument("--seq", required=True, type=int)
    return parser


def _time(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _record_document(record: RegistrationRecord) -> dict[str, Any]:
    return {
        "hardware_id": record.hardware_id,
        "pairing_id": record.pairing_id,
        "pairing_epoch": record.pairing_epoch,
        "model": record.model,
        "fw_version": record.fw_version,
        "state": record.state,
        "first_seen_at": _time(record.first_seen_at),
        "last_seen_at": _time(record.last_seen_at),
        "expires_at": _time(record.expires_at),
        "node_id": record.node_id,
        "logical_location_id": record.logical_location_id,
        "retired_at": _time(record.retired_at) if record.retired_at else None,
        "reason": record.reason,
    }


def _write(output: TextIO, document: Any) -> None:
    json.dump(document, output, ensure_ascii=False, separators=(",", ":"), default=str)
    output.write("\n")


def _run_replay_command(
    args: argparse.Namespace,
    *,
    output: TextIO,
    error_output: TextIO,
) -> int:
    database = Path(args.replay_db)
    try:
        with ReplayRegistry(database, read_only=True) as registry:
            if args.command == "n3w-replay-audit":
                _write(output, registry.audit())
                return 0
            inspection = registry.inspect(
                node_id=args.node_id,
                boot_id=args.boot_id,
                seq=args.seq,
            )
            _write(
                output,
                {
                    "schema": "gh.n3w-replay-registry-inspection/1",
                    "status": inspection.status,
                    "node_id": inspection.key.node_id,
                    "boot_id": inspection.key.boot_id,
                    "seq": inspection.key.seq,
                    "highest_session_hex": (
                        f"{inspection.highest_session:016x}"
                        if inspection.highest_session is not None
                        else None
                    ),
                    "mutated": False,
                },
            )
            return 0
    except (ReplayRegistryUnavailable, ValueError) as exc:
        print(f"N3-W replay command failed: {exc}", file=error_output)
        return 3


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    container_inspector: ContainerInspector | None = None,
) -> int:
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    args = _parser().parse_args(argv)

    if args.command in {"n3w-replay-audit", "n3w-replay-inspect"}:
        return _run_replay_command(args, output=output, error_output=error_output)

    database = Path(args.db)
    if not database.exists():
        print(f"Registration database does not exist: {database}", file=error_output)
        return 2

    credential_database: Path | None = None
    if args.command == "abandon-expired-first":
        credential_database = Path(args.credential_db)
        if not credential_database.is_file():
            print(
                f"Credential lifecycle database does not exist: {credential_database}",
                file=error_output,
            )
            return 2
        if not args.confirm_manager_stopped:
            print(
                "Registration command failed: --confirm-manager-stopped is required",
                file=error_output,
            )
            return 3
        try:
            _verify_stopped_manager_and_database_bindings(
                (container_inspector or _docker_inspect_container)(args.manager_container),
                container_name=args.manager_container,
                registration_db=database,
                registration_container_path=args.registration_container_path,
                credential_db=credential_database,
                credential_container_path=args.credential_container_path,
            )
        except RegistrationConflict as exc:
            print(f"Registration command failed: {exc}", file=error_output)
            return 3

    try:
        with RegistrationRegistry(database) as registry:
            if args.command == "list":
                _write(output, [_record_document(record) for record in registry.list_current()])
            elif args.command == "events":
                events = registry.list_events(hardware_id=args.hardware_id, limit=args.limit)
                documents = []
                for event in events:
                    document = asdict(event)
                    document["occurred_at"] = _time(event.occurred_at)
                    documents.append(document)
                _write(output, documents)
            elif args.command == "approve":
                record = AutomaticNodeIdApprover(registry).approve(
                    args.hardware_id,
                    args.pairing_id,
                    logical_location_id=args.logical_location_id,
                )
                _write(
                    output,
                    {
                        "result": "operator_approved",
                        "credential_issued": False,
                        "node_id_assignment": "manager_automatic",
                        "registration": _record_document(record),
                    },
                )
            elif args.command == "reject":
                record = registry.reject(args.hardware_id, args.pairing_id, reason=args.reason)
                _write(
                    output,
                    {"result": "rejected", "registration": _record_document(record)},
                )
            elif args.command == "expire":
                _write(output, {"expired": registry.expire_pending()})
            elif args.command == "abandon-expired-first":
                assert credential_database is not None
                with CredentialLifecycleStore(
                    credential_database,
                    read_only=True,
                ) as credential_history:
                    _verify_stopped_manager_and_database_bindings(
                        (container_inspector or _docker_inspect_container)(args.manager_container),
                        container_name=args.manager_container,
                        registration_db=database,
                        registration_container_path=args.registration_container_path,
                        credential_db=credential_database,
                        credential_container_path=args.credential_container_path,
                    )
                    record = registry.abandon_expired_first_registration(
                        args.hardware_id,
                        args.pairing_id,
                        credential_history=credential_history,
                        reason=args.reason,
                    )
                _write(
                    output,
                    {
                        "result": "expired_first_registration_abandoned",
                        "registration": _record_document(record),
                        "current_registration_released": True,
                        "replay_tombstone_preserved": True,
                        "credential_history_absent": True,
                        "manager_container_stopped": True,
                        "registration_db_binding_verified": True,
                        "credential_db_binding_verified": True,
                        "device_reset_performed": False,
                    },
                )
    except (
        CredentialLifecycleConflict,
        KeyError,
        RegistrationConflict,
        ValueError,
    ) as exc:
        print(f"Registration command failed: {exc}", file=error_output)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
