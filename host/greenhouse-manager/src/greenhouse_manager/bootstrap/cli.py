from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from greenhouse_manager.bootstrap.system_init import (
    INITIALIZATION_CONFIRMATION,
    InitializationError,
    initialize_system,
    verify_initialization,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="greenhouse-init",
        description="Default-disabled greenhouse system identity initializer.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    initialize = subparsers.add_parser("initialize")
    initialize.add_argument("--root", type=Path, required=True)
    initialize.add_argument("--enable-initialization", action="store_true")
    initialize.add_argument("--confirm", required=True)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--root", type=Path, required=True)
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
        if args.command == "initialize":
            report = initialize_system(
                args.root,
                enable=args.enable_initialization,
                confirmation=args.confirm,
            )
        else:
            report = verify_initialization(args.root)
    except (InitializationError, OSError, ValueError) as error:
        errors.write(
            json.dumps(
                {
                    "schema": "gh.h0h1.system-initialization-cli/1",
                    "status": "FAIL",
                    "error_code": type(error).__name__,
                    "initialization_confirmation_required": INITIALIZATION_CONFIRMATION,
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
            {
                **report.to_dict(),
                "status": "PASS",
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
