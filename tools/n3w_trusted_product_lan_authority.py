#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence, TextIO

import n3w_broker_ingress_guard as broker_guard

SCHEMA = "gh.trusted-product-lan/1"
INTERFACE = broker_guard.INTERFACE
DEFAULT_RUNTIME_DIR = Path("/run/n3wfc4-trusted-lan")
DEFAULT_STATE_FILE = DEFAULT_RUNTIME_DIR / "state.json"


class AuthorityPublishError(RuntimeError):
    pass


def build_state_document(
    decision: broker_guard.NetworkDecision,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    base: dict[str, object] = {
        "schema": SCHEMA,
        "interface": INTERFACE,
        "available": decision.trusted_subnet is not None,
        "reason": decision.reason,
        "published_at": observed.isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    generation_input = "|".join(
        (
            INTERFACE,
            str(decision.trusted_subnet or ""),
            decision.reason,
            str(decision.candidate_network_count),
            str(base["published_at"]),
        )
    )
    base["generation"] = hashlib.sha256(generation_input.encode("utf-8")).hexdigest()
    if decision.trusted_subnet is not None:
        base["subnet"] = str(decision.trusted_subnet)
    return base


def atomic_publish(
    document: dict[str, object],
    *,
    runtime_dir: Path = DEFAULT_RUNTIME_DIR,
    state_file: Path = DEFAULT_STATE_FILE,
) -> None:
    if not runtime_dir.is_absolute() or not state_file.is_absolute():
        raise AuthorityPublishError("trusted_lan_runtime_path_invalid")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    try:
        fd, temporary = tempfile.mkstemp(prefix=".state.", dir=runtime_dir)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, state_file)
        directory_fd = os.open(runtime_dir, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as error:
        raise AuthorityPublishError("trusted_lan_publish_failed") from error
    finally:
        if "temporary" in locals() and os.path.exists(temporary):
            os.unlink(temporary)


def _public_result(document: dict[str, object], *, applied: bool) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": "PASS" if document["available"] else "FAIL_CLOSED",
        "applied": applied,
        "interface": INTERFACE,
        "reason": document["reason"],
        "generation": document["generation"],
        "raw_customer_subnet_in_public_output": False,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    output = stdout or sys.stdout
    error = stderr or sys.stderr
    decision = broker_guard.read_network_decision()
    document = build_state_document(decision)
    try:
        if args.apply:
            atomic_publish(document)
    except AuthorityPublishError as exc:
        error.write(json.dumps({
                "schema": SCHEMA,
                "status": "ERROR",
                "reason": str(exc),
                "raw_customer_subnet_in_public_output": False,
            }, sort_keys=True) + "\n")
        return 3
    if output is not None:
        output.write(json.dumps(_public_result(document, applied=args.apply), sort_keys=True) + "\n")
    return 0 if decision.trusted_subnet is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
