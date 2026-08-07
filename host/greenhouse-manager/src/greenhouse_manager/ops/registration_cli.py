from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from ..runtime.registration import RegistrationConflict, RegistrationRecord, RegistrationRegistry
from ..runtime.replay_registry import ReplayRegistry, ReplayRegistryUnavailable

DEFAULT_DB_PATH = "/var/lib/greenhouse-manager/registration.sqlite3"


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

    approve = subparsers.add_parser("approve", help="record operator approval only")
    approve.add_argument("hardware_id")
    approve.add_argument("pairing_id")
    approve.add_argument("--node-id", required=True)
    approve.add_argument(
        "--logical-location-id",
        required=True,
        help="stable logical monitoring location bound to this node_id",
    )
    reject = subparsers.add_parser("reject", help="reject a pending registration")
    reject.add_argument("hardware_id")
    reject.add_argument("pairing_id")
    reject.add_argument("--reason", default="user_rejected")

    repair = subparsers.add_parser("authorize-repair", help="open one explicit re-pair window")
    repair.add_argument("hardware_id")

    subparsers.add_parser("expire", help="expire overdue pending registrations")

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
                record = registry.approve(
                    args.hardware_id,
                    args.pairing_id,
                    node_id=args.node_id,
                    logical_location_id=args.logical_location_id,
                )
                _write(
                    output,
                    {
                        "result": "operator_approved",
                        "credential_issued": False,
                        "registration": _record_document(record),
                    },
                )
            elif args.command == "reject":
                record = registry.reject(args.hardware_id, args.pairing_id, reason=args.reason)
                _write(output, {"result": "rejected", "registration": _record_document(record)})
            elif args.command == "authorize-repair":
                record = registry.authorize_repair(args.hardware_id)
                _write(
                    output,
                    {
                        "result": "repair_authorized",
                        "one_time": True,
                        "registration": _record_document(record),
                    },
                )
            elif args.command == "expire":
                _write(output, {"expired": registry.expire_pending()})
    except (KeyError, RegistrationConflict, ValueError) as exc:
        print(f"Registration command failed: {exc}", file=error_output)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
