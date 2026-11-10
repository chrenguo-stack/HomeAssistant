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
from n3w_t1_core_updater_v2 import MultiComponentCoreUpdater
from n3w_t1_core_updater_v2_common import (
    COMPONENTS,
    STATUS_SCHEMA_V2,
    TARGET_SCHEMA_V2,
    ComponentTarget,
    ProductAcceptance,
    UpgradeBaseline,
    UpdaterV2Error,
)
from n3w_t1_core_updater_v2_state import V2StateStore


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="t1-core-updater")
    sub = command.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--component", choices=COMPONENTS)
    sub.add_parser("baseline")
    plan = sub.add_parser("plan")
    plan.add_argument("--target-manifest", type=Path, required=True)
    plan.add_argument("--baseline-manifest", type=Path)
    plan.add_argument("--manager-tar", type=Path)
    plan.add_argument("--image-tar", type=Path)
    apply = sub.add_parser("apply")
    apply.add_argument("--target-manifest", type=Path, required=True)
    apply.add_argument("--baseline-manifest", type=Path)
    apply.add_argument("--manager-tar", type=Path)
    apply.add_argument("--image-tar", type=Path)
    apply.add_argument("--authorization-id", required=True)
    apply.add_argument("--confirmation", required=True)
    rollback = sub.add_parser("rollback")
    rollback.add_argument("--confirmation", required=True)
    finalize = sub.add_parser("finalize")
    finalize.add_argument("--acceptance-authority", type=Path, required=True)
    finalize.add_argument("--confirmation", required=True)
    sub.add_parser("status")
    sub.add_parser("runtime-state")
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


def _target_schema(path: Path) -> str | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value.get("schema") if isinstance(value, dict) else None


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    host = LocalHost()
    legacy = CoreUpdater(host, StateStore())
    v2_store = V2StateStore()
    v2 = MultiComponentCoreUpdater(host, v2_store)
    v2_operation = False
    try:
        if args.command == "inspect":
            v2_operation = args.component is not None
            result = (
                v2.inspect(args.component)
                if v2_operation
                else legacy.inspect()
            )
        elif args.command == "baseline":
            v2_operation = True
            result = v2.baseline()
        elif args.command == "plan":
            if _target_schema(args.target_manifest) == TARGET_SCHEMA_V2:
                v2_operation = True
                if args.baseline_manifest is None:
                    raise UpdaterV2Error("baseline_manifest_required")
                archive = args.image_tar or args.manager_tar
                result = v2.plan(
                    ComponentTarget.load(args.target_manifest),
                    UpgradeBaseline.load(args.baseline_manifest),
                    archive,
                )
            else:
                result = legacy.plan(
                    Target.load(args.target_manifest),
                    args.manager_tar,
                )
        elif args.command == "apply":
            if _target_schema(args.target_manifest) == TARGET_SCHEMA_V2:
                v2_operation = True
                archive = args.image_tar or args.manager_tar
                if archive is None:
                    raise UpdaterV2Error("target_archive_required")
                if args.baseline_manifest is None:
                    raise UpdaterV2Error("baseline_manifest_required")
                result = v2.apply(
                    ComponentTarget.load(args.target_manifest),
                    UpgradeBaseline.load(args.baseline_manifest),
                    archive,
                    authorization_id=args.authorization_id,
                    confirmation=args.confirmation,
                )
            else:
                if args.manager_tar is None:
                    raise UpdaterError("manager_tar_required")
                result = legacy.apply(
                    Target.load(args.target_manifest),
                    args.manager_tar,
                    authorization_id=args.authorization_id,
                    confirmation=args.confirmation,
                )
        elif args.command == "rollback":
            v2_operation = v2_store.path.exists()
            result = (
                v2.rollback(confirmation=args.confirmation)
                if v2_operation
                else legacy.rollback(confirmation=args.confirmation)
            )
        elif args.command == "finalize":
            v2_operation = True
            result = v2.finalize(
                ProductAcceptance.load(args.acceptance_authority),
                confirmation=args.confirmation,
            )
        elif args.command == "status":
            v2_operation = v2_store.path.exists()
            result = v2.status() if v2_operation else legacy.status()
        elif args.command == "runtime-state":
            v2_operation = True
            result = v2.runtime_state()
        else:
            raise UpdaterError("command_unknown")
    except Exception as error:
        print(
            json.dumps(
                {
                    "schema": (
                        STATUS_SCHEMA_V2 if v2_operation else STATUS_SCHEMA
                    ),
                    "status": "STOP",
                    "operation": args.command,
                    "reason": safe_reason(error),
                    "t1_mutation": (
                        "UNKNOWN"
                        if args.command in {"apply", "rollback", "finalize"}
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
