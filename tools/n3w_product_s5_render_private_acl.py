#!/usr/bin/env python3
"""Bind only the three approved S5 peer-authorization ACL entries."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path


IDENTITY = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
SUFFIXES = (
    ("write", "relay-peer-auth/time-request"),
    ("write", "relay-peer-auth/request"),
    ("read", "relay-peer-auth/+"),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--relay-credentials", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    relay = json.loads(args.relay_credentials.read_text(encoding="utf-8"))
    system = relay.get("system_id")
    node = relay.get("node_id")
    if not isinstance(system, str) or IDENTITY.fullmatch(system) is None:
        raise ValueError("invalid_system_id")
    if not isinstance(node, str) or IDENTITY.fullmatch(node) is None:
        raise ValueError("invalid_relay_node_id")

    original = args.output.read_text(encoding="utf-8")
    updated = original
    for permission, suffix in SUFFIXES:
        pattern = re.compile(
            rf"^ topic {permission} gh/v1/{re.escape(system)}/"
            rf"(?:ingress|out)/node/[A-Za-z0-9_-]+/{re.escape(suffix)}$",
            re.MULTILINE,
        )
        matches = pattern.findall(updated)
        if len(matches) != 1:
            raise ValueError("approved_acl_entry_count_mismatch")
        direction = "ingress" if permission == "write" else "out"
        replacement = (
            f" topic {permission} gh/v1/{system}/{direction}/node/{node}/{suffix}"
        )
        updated = pattern.sub(replacement, updated, count=1)

    before_without_approved = original
    after_without_approved = updated
    for permission, suffix in SUFFIXES:
        scrub = re.compile(
            rf"^ topic {permission} gh/v1/{re.escape(system)}/"
            rf"(?:ingress|out)/node/[A-Za-z0-9_-]+/{re.escape(suffix)}$",
            re.MULTILINE,
        )
        before_without_approved = scrub.sub("[APPROVED_ENTRY]", before_without_approved)
        after_without_approved = scrub.sub("[APPROVED_ENTRY]", after_without_approved)
    if before_without_approved != after_without_approved:
        raise ValueError("acl_scope_expanded")

    mode = args.output.stat().st_mode & 0o777
    fd, temporary = tempfile.mkstemp(prefix=".acl-", dir=args.output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, args.output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("PRIVATE_ACL_APPROVED_ENTRIES_BIND=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
