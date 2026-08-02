from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from greenhouse_manager.bootstrap.persistence_migration import (
    PersistenceMigrationError,
    build_persistence_migration_plan,
    load_audited_baseline,
)


def main(
    argv: Sequence[str] | None = None,
    *,
    require_exact_audited_file: bool = True,
) -> int:
    parser = argparse.ArgumentParser(
        description="Build a host-only H0/H1 Manager persistence migration plan"
    )
    parser.add_argument("baseline", help="secret-free T1 read-only baseline JSON")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    try:
        if require_exact_audited_file:
            baseline, digest = load_audited_baseline(args.baseline)
        else:
            with open(args.baseline, encoding="utf-8") as stream:
                baseline = json.load(stream)
            digest = None
        plan = build_persistence_migration_plan(
            baseline,
            source_sha256=digest,
            require_exact_audited_file=require_exact_audited_file,
        )
    except (OSError, json.JSONDecodeError, PersistenceMigrationError) as error:
        json.dump(
            {
                "status": "FAIL",
                "error_code": type(error).__name__,
                "error": str(error),
                "production_services_modified": False,
                "network_operation": False,
            },
            sys.stdout,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        sys.stdout.write("\n")
        return 2

    json.dump(
        plan.to_dict(),
        sys.stdout,
        ensure_ascii=False,
        sort_keys=True,
        indent=2 if args.pretty else None,
        separators=None if args.pretty else (",", ":"),
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
