from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from .n3w_relay_authorization_admin import (
    RelayAuthorizationAdmin,
    RelayAuthorizationAdminError,
    ReplayPathLeaseInvalidator,
)
from ..runtime.n3w_relay_authorization import (
    RelayAuthorizationStoreUnavailable,
    SqliteRelayAuthorizationProvider,
)
from ..runtime.registration import RegistrationConflict, RegistrationRecord, RegistrationRegistry
from ..runtime.replay_registry import ReplayRegistry, ReplayRegistryUnavailable

DEFAULT_DB_PATH = "/var/lib/greenhouse-manager/registration.sqlite3"
_ADMIN_COMMANDS = {
    "n3w-relay-authz-init",
    "n3w-relay-authz-admin-audit",
    "n3w-relay-authz-grant",
    "n3w-relay-authz-revoke-grant",
    "n3w-relay-key-stage",
    "n3w-relay-key-activate",
    "n3w-relay-key-rollback",
    "n3w-relay-key-revoke",
    "n3w-relay-authz-recover",
}
_ACTIVE_NODE_COMMANDS = {
    "n3w-relay-authz-grant",
    "n3w-relay-key-stage",
    "n3w-relay-key-activate",
}


def _add_authz_paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--authz-db", required=True)
    parser.add_argument("--key-dir", required=True)


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

    relay_authz_audit = subparsers.add_parser(
        "n3w-relay-authz-audit",
        help="audit existing N3-W relay authorization metadata and private key references",
    )
    _add_authz_paths(relay_authz_audit)

    init = subparsers.add_parser(
        "n3w-relay-authz-init",
        help="initialize or migrate an isolated N3-W relay authorization store",
    )
    _add_authz_paths(init)

    admin_audit = subparsers.add_parser(
        "n3w-relay-authz-admin-audit",
        help="audit writable N3-W relay authorization lifecycle state without secrets",
    )
    _add_authz_paths(admin_audit)

    grant = subparsers.add_parser(
        "n3w-relay-authz-grant",
        help="grant one gateway access to an ACTIVE registered node",
    )
    _add_authz_paths(grant)
    grant.add_argument("--gateway-id", required=True)
    grant.add_argument("--node-id", required=True)

    revoke = subparsers.add_parser(
        "n3w-relay-authz-revoke-grant",
        help="revoke one gateway and invalidate matching Relay path state when available",
    )
    _add_authz_paths(revoke)
    revoke.add_argument("--gateway-id", required=True)
    revoke.add_argument("--node-id", required=True)
    revoke.add_argument("--replay-db")

    stage = subparsers.add_parser(
        "n3w-relay-key-stage",
        help="stage one 32-byte application key from a private local file",
    )
    _add_authz_paths(stage)
    stage.add_argument("--node-id", required=True)
    stage.add_argument("--key-input", required=True)

    activate = subparsers.add_parser(
        "n3w-relay-key-activate",
        help="activate a staged epoch and place the prior ACTIVE epoch in GRACE",
    )
    _add_authz_paths(activate)
    activate.add_argument("--node-id", required=True)
    activate.add_argument("--key-epoch", required=True, type=int)

    rollback = subparsers.add_parser(
        "n3w-relay-key-rollback",
        help="rollback an unfinished rotation to the prior GRACE epoch",
    )
    _add_authz_paths(rollback)
    rollback.add_argument("--node-id", required=True)
    rollback.add_argument("--key-epoch", required=True, type=int)

    revoke_key = subparsers.add_parser(
        "n3w-relay-key-revoke",
        help="revoke one application-key epoch and remove obsolete local material",
    )
    _add_authz_paths(revoke_key)
    revoke_key.add_argument("--node-id", required=True)
    revoke_key.add_argument("--key-epoch", required=True, type=int)

    recover = subparsers.add_parser(
        "n3w-relay-authz-recover",
        help="resume secret-free relay authorization/key cleanup after an interrupted operation",
    )
    _add_authz_paths(recover)
    recover.add_argument("--replay-db")
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


def _run_relay_authz_command(
    args: argparse.Namespace,
    *,
    output: TextIO,
    error_output: TextIO,
) -> int:
    try:
        with SqliteRelayAuthorizationProvider(
            Path(args.authz_db),
            Path(args.key_dir),
        ) as provider:
            _write(output, provider.audit())
            return 0
    except RelayAuthorizationStoreUnavailable as exc:
        print(f"N3-W relay authorization audit failed: {exc}", file=error_output)
        return 3


def _read_private_key_input(path_value: str) -> bytes:
    path = Path(path_value).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise RelayAuthorizationAdminError("key_input_permissions_invalid")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise RelayAuthorizationAdminError("key_input_unavailable") from exc
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_IMODE(info.st_mode) & 0o077
            or (hasattr(os, "getuid") and info.st_uid != os.getuid())
        ):
            raise RelayAuthorizationAdminError("key_input_permissions_invalid")
        material = b""
        while len(material) <= 32:
            chunk = os.read(fd, 33 - len(material))
            if not chunk:
                break
            material += chunk
    finally:
        os.close(fd)
    if len(material) != 32:
        raise RelayAuthorizationAdminError("key_material_invalid")
    return material


def _open_path_invalidator(replay_path: str | None) -> tuple[ReplayRegistry | None, object | None]:
    if replay_path is None:
        return None, None
    path = Path(replay_path)
    if not path.exists():
        raise RelayAuthorizationAdminError("replay_registry_missing")
    registry = ReplayRegistry(path)
    return registry, ReplayPathLeaseInvalidator(registry)


def _run_admin_command(
    args: argparse.Namespace,
    *,
    output: TextIO,
    error_output: TextIO,
) -> int:
    registration: RegistrationRegistry | None = None
    replay: ReplayRegistry | None = None
    try:
        if args.command in _ACTIVE_NODE_COMMANDS:
            registration_path = Path(args.db)
            if not registration_path.exists():
                print(
                    f"Registration database does not exist: {registration_path}",
                    file=error_output,
                )
                return 2
            registration = RegistrationRegistry(registration_path)
            node_state = registration.node_id_lease_state
        else:
            node_state = lambda _node_id: None

        replay_arg = getattr(args, "replay_db", None)
        replay, path_invalidator = _open_path_invalidator(replay_arg)
        with RelayAuthorizationAdmin(
            Path(args.authz_db),
            Path(args.key_dir),
            node_state=node_state,
            path_invalidator=path_invalidator,
        ) as admin:
            if args.command in {"n3w-relay-authz-init", "n3w-relay-authz-admin-audit"}:
                result = admin.audit()
            elif args.command == "n3w-relay-authz-grant":
                result = admin.grant(gateway_id=args.gateway_id, node_id=args.node_id)
            elif args.command == "n3w-relay-authz-revoke-grant":
                result = admin.revoke_grant(gateway_id=args.gateway_id, node_id=args.node_id)
            elif args.command == "n3w-relay-key-stage":
                material = _read_private_key_input(args.key_input)
                result = admin.stage_key(node_id=args.node_id, key_material=material)
                del material
            elif args.command == "n3w-relay-key-activate":
                result = admin.activate_key(node_id=args.node_id, key_epoch=args.key_epoch)
            elif args.command == "n3w-relay-key-rollback":
                result = admin.rollback_rotation(node_id=args.node_id, key_epoch=args.key_epoch)
            elif args.command == "n3w-relay-key-revoke":
                result = admin.revoke_key(node_id=args.node_id, key_epoch=args.key_epoch)
            elif args.command == "n3w-relay-authz-recover":
                result = admin.recover()
            else:  # pragma: no cover - parser guards this
                raise RelayAuthorizationAdminError("admin_command_invalid")
        _write(output, result)
        if isinstance(result, dict) and result.get("recovery_pending") is True:
            return 4
        return 0
    except (RelayAuthorizationAdminError, ReplayRegistryUnavailable, ValueError) as exc:
        print(f"N3-W relay authorization administration failed: {exc}", file=error_output)
        return 3
    finally:
        if replay is not None:
            replay.close()
        if registration is not None:
            registration.close()


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
    if args.command == "n3w-relay-authz-audit":
        return _run_relay_authz_command(args, output=output, error_output=error_output)
    if args.command in _ADMIN_COMMANDS:
        return _run_admin_command(args, output=output, error_output=error_output)

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
