#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from greenhouse_manager.bootstrap.fresh_product_state import (
    BUSINESS_TABLES,
    EXPECTED_MANAGER_TABLES,
    MANAGER_DATABASE_NAME,
    RELAY_AUTH_NAME,
    RELAY_KEY_DIR_NAME,
    REPLAY_NAME,
    SCHEMA,
    FreshProductStateError,
    audit_fresh_state,
    create_fresh_state,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("create", "audit"), required=True)
    parser.add_argument("--manager-root", type=Path, required=True)
    parser.add_argument("--n3w-root", type=Path, required=True)
    parser.add_argument("--expected-system-id-sha256", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.phase == "create":
            report = create_fresh_state(
                args.manager_root,
                args.n3w_root,
                expected_system_id_sha256=args.expected_system_id_sha256,
            )
        else:
            report = audit_fresh_state(
                args.manager_root,
                args.n3w_root,
                expected_system_id_sha256=args.expected_system_id_sha256,
            )
    except (
        FreshProductStateError,
        OSError,
        sqlite3.Error,
        ValueError,
    ) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "phase": args.phase,
                    "status": "STOP",
                    "reason": str(error),
                    "production_service_start": False,
                    "network_operation": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2

    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
