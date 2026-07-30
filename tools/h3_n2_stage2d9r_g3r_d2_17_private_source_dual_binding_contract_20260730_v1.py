#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

G04_PRIVATE_SOURCE_SHA = "0691b3c85cf3ee018cd07cf038138cbf4dcd1f34"
G04_ACCEPTANCE_SOURCE_SHA = "e58b934c7e00125bf7d7c5a75f6ee338dd5dbdd7"
G04_PHYSICAL_DECISION_SOURCE_SHA = "2acda017ba287c36718fda1031d55acf4101697d"

class BindingError(RuntimeError):
    pass

def require(condition: bool, code: str) -> None:
    if not condition:
        raise BindingError(code)

def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "TERMINAL_RECORD_INVALID")
    return value

def validate_source_bindings(
    terminal: dict[str, Any],
    *,
    acceptance_source_sha: str,
    physical_decision_source_sha: str,
) -> dict[str, Any]:
    require(
        terminal.get("private_source_sha") == G04_PRIVATE_SOURCE_SHA,
        "TERMINAL_PRIVATE_SOURCE_SHA_DRIFT",
    )
    require(
        acceptance_source_sha == G04_ACCEPTANCE_SOURCE_SHA,
        "ACCEPTANCE_SOURCE_SHA_DRIFT",
    )
    require(
        physical_decision_source_sha == G04_PHYSICAL_DECISION_SOURCE_SHA,
        "PHYSICAL_DECISION_SOURCE_SHA_DRIFT",
    )
    return {
        "status": "PASS",
        "private_source_sha": G04_PRIVATE_SOURCE_SHA,
        "acceptance_source_sha": G04_ACCEPTANCE_SOURCE_SHA,
        "physical_decision_source_sha": G04_PHYSICAL_DECISION_SOURCE_SHA,
        "source_fields_are_distinct": len({
            G04_PRIVATE_SOURCE_SHA,
            G04_ACCEPTANCE_SOURCE_SHA,
            G04_PHYSICAL_DECISION_SOURCE_SHA,
        }) == 3,
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal", type=Path, required=True)
    parser.add_argument("--acceptance-source-sha", required=True)
    parser.add_argument("--physical-decision-source-sha", required=True)
    args = parser.parse_args()
    try:
        result = validate_source_bindings(
            load_json(args.terminal),
            acceptance_source_sha=args.acceptance_source_sha,
            physical_decision_source_sha=args.physical_decision_source_sha,
        )
    except (OSError, ValueError, BindingError) as exc:
        print(json.dumps({"status": "FAIL", "failure_code": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
