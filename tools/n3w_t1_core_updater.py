#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from n3w_t1_core_updater_common import STATUS_SCHEMA, Target, UpdaterError
from n3w_t1_core_updater_core import CoreUpdater
from n3w_t1_core_updater_host import LocalHost
from n3w_t1_core_updater_state import StateStore


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="t1-core-updater")
    sub = command.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    plan = sub.add_parser("plan")
    plan.add_argument("--target-manifest", type=Path, required=True)
    plan.add_argument("--manager-tar", type=Path)
    apply = sub.add_parser("apply")
    apply.add_argument("--target-manifest", type=Path, required=True)
    apply.add_argument("--manager-tar", type=Path, required=True)
    apply.add_argument("--authorization-id", required=True)
    apply.add_argument("--confirmation", required=True)
    rollback = sub.add_parser("rollback")
    rollback.add_argument("--confirmation", required=True)
    sub.add_parser("status")
    return command


def safe_reason(error: Exception) -> str:
    value = str(error)
    if (
        not value
        or len(value) > 200
        or any(character in value for character in ("/", "\\", "@"))
    ):
        return type(error).__name__
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    updater = CoreUpdater(LocalHost(), StateStore())
    try:
        if args.command == "inspect":
            result = updater.inspect()
        elif args.command == "plan":
            result = updater.plan(
                Target.load(args.target_manifest),
                args.manager_tar,
            )
        elif args.command == "apply":
            result = updater.apply(
                Target.load(args.target_manifest),
                args.manager_tar,
                authorization_id=args.authorization_id,
                confirmation=args.confirmation,
            )
        elif args.command == "rollback":
            result = updater.rollback(confirmation=args.confirmation)
        elif args.command == "status":
            result = updater.status()
        else:
            raise UpdaterError("command_unknown")
    except Exception as error:
        print(
            json.dumps(
                {
                    "schema": STATUS_SCHEMA,
                    "status": "STOP",
                    "operation": args.command,
                    "reason": safe_reason(error),
                    "t1_mutation": (
                        "UNKNOWN"
                        if args.command in {"apply", "rollback"}
                        else False
                    ),
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
