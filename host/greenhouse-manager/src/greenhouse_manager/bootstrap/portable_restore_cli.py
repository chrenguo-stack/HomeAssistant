from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from greenhouse_manager.bootstrap.portable_restore import (
    CREATE_CONFIRMATION,
    RESTORE_CONFIRMATION,
    PortableRestoreError,
    create_portable_backup,
    restore_portable_backup,
    verify_portable_backup,
)


def _private_text(path: Path, *, label: str) -> str:
    resolved = path.expanduser().resolve()
    if resolved.is_symlink() or not resolved.is_file():
        raise PortableRestoreError(f"{label} must be a regular file")
    if resolved.stat().st_mode & 0o077:
        raise PortableRestoreError(f"{label} permissions are not private")
    value = resolved.read_text(encoding="utf-8").rstrip("\r\n")
    if not value:
        raise PortableRestoreError(f"{label} must not be empty")
    return value


def _inventory(path: Path) -> dict[str, str]:
    value = _private_text(path, label="inventory file")
    try:
        document = json.loads(value)
    except json.JSONDecodeError as error:
        raise PortableRestoreError("inventory file is invalid") from error
    if not isinstance(document, dict) or not all(
        isinstance(key, str) and isinstance(item, str)
        for key, item in document.items()
    ):
        raise PortableRestoreError("inventory file must contain a string mapping")
    return dict(document)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="greenhouse-portable-restore",
        description="Encrypted, host-only greenhouse system backup and restore contract.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    create.add_argument("--source-root", type=Path, required=True)
    create.add_argument("--inventory-file", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--passphrase-file", type=Path, required=True)
    create.add_argument("--enable-create", action="store_true")
    create.add_argument("--confirm", required=True)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--archive", type=Path, required=True)
    verify.add_argument("--passphrase-file", type=Path, required=True)

    restore = subparsers.add_parser("restore")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--target-root", type=Path, required=True)
    restore.add_argument("--passphrase-file", type=Path, required=True)
    restore.add_argument("--expected-system-id")
    restore.add_argument("--enable-restore", action="store_true")
    restore.add_argument("--confirm", required=True)
    return parser


def _success(report: Any) -> dict[str, Any]:
    return {**report.to_dict(), "status": "PASS"}


def main(
    argv: Sequence[str] | None = None,
    *,
    output: TextIO | None = None,
    error_output: TextIO | None = None,
) -> int:
    destination = output or sys.stdout
    errors = error_output or sys.stderr
    args = _parser().parse_args(argv)
    try:
        passphrase = _private_text(args.passphrase_file, label="passphrase file")
        if args.command == "create":
            report = create_portable_backup(
                args.source_root,
                _inventory(args.inventory_file),
                args.output,
                passphrase=passphrase,
                enable=args.enable_create,
                confirmation=args.confirm,
            )
        elif args.command == "verify":
            report = verify_portable_backup(
                args.archive,
                passphrase=passphrase,
            )
        else:
            report = restore_portable_backup(
                args.archive,
                args.target_root,
                passphrase=passphrase,
                expected_system_id=args.expected_system_id,
                enable=args.enable_restore,
                confirmation=args.confirm,
            )
    except (PortableRestoreError, OSError, ValueError) as error:
        errors.write(
            json.dumps(
                {
                    "schema": "gh.h0h1.portable-restore-cli/1",
                    "status": "FAIL",
                    "error_code": type(error).__name__,
                    "create_confirmation_required": CREATE_CONFIRMATION,
                    "restore_confirmation_required": RESTORE_CONFIRMATION,
                    "production_services_modified": False,
                    "network_operation": False,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        return 2
    destination.write(
        json.dumps(
            _success(report),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
