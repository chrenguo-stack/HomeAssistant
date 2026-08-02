from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from greenhouse_manager.bootstrap.identity_guard import (
    CLAIM_CONFIRMATION,
    RELEASE_CONFIRMATION,
    IdentityConflictError,
    claim_identity,
    inspect_identity,
    release_identity,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="greenhouse-system-identity-guard",
        description="Offline system identity conflict guard.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("inspect", "claim", "release"):
        child = subparsers.add_parser(command)
        child.add_argument("--registry-root", type=Path, required=True)
        child.add_argument("--system-id", required=True)
        if command != "inspect":
            child.add_argument("--host-instance-id", required=True)
            child.add_argument("--enable", action="store_true")
            child.add_argument("--confirm", required=True)
    return parser


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
        if args.command == "inspect":
            report = inspect_identity(args.registry_root, args.system_id)
        elif args.command == "claim":
            report = claim_identity(
                args.registry_root,
                system_id=args.system_id,
                host_instance_id=args.host_instance_id,
                enable=args.enable,
                confirmation=args.confirm,
            )
        else:
            report = release_identity(
                args.registry_root,
                system_id=args.system_id,
                host_instance_id=args.host_instance_id,
                enable=args.enable,
                confirmation=args.confirm,
            )
    except (IdentityConflictError, OSError, ValueError) as error:
        errors.write(
            json.dumps(
                {
                    "schema": "gh.h0h1.system-identity-guard-cli/1",
                    "status": "FAIL",
                    "error_code": type(error).__name__,
                    "claim_confirmation_required": CLAIM_CONFIRMATION,
                    "release_confirmation_required": RELEASE_CONFIRMATION,
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
            {**report.to_dict(), "status": "PASS"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
