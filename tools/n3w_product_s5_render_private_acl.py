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
    ("write", "telemetry"),
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
    block_pattern = re.compile(
        r"^user p5relay\n(?P<body>(?:^ [^\n]*(?:\n|$))*)",
        re.MULTILINE,
    )
    block_match = block_pattern.search(original)
    if block_match is None:
        raise ValueError("p5relay_acl_block_missing")
    original_block = block_match.group(0)
    updated_block = original_block
    telemetry_pattern = re.compile(
        rf"^ topic write gh/v1/{re.escape(system)}/ingress/node/"
        rf"[A-Za-z0-9_-]+/telemetry$",
        re.MULTILINE,
    )
    telemetry_count = len(telemetry_pattern.findall(updated_block))
    telemetry_added = telemetry_count == 0
    if telemetry_count > 1:
        raise ValueError("approved_acl_entry_count_mismatch")
    if telemetry_added:
        gateway_pattern = re.compile(
            rf"^( topic write gh/v1/{re.escape(system)}/ingress/gateway/"
            rf"[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/frame)$",
            re.MULTILINE,
        )
        if len(gateway_pattern.findall(updated_block)) != 1:
            raise ValueError("p5relay_gateway_anchor_count_mismatch")
        updated_block = gateway_pattern.sub(
            rf"\1\n topic write gh/v1/{system}/ingress/node/{node}/telemetry",
            updated_block,
            count=1,
        )
    for permission, suffix in SUFFIXES:
        pattern = re.compile(
            rf"^ topic {permission} gh/v1/{re.escape(system)}/"
            rf"(?:ingress|out)/node/[A-Za-z0-9_-]+/{re.escape(suffix)}$",
            re.MULTILINE,
        )
        matches = pattern.findall(updated_block)
        if len(matches) != 1:
            raise ValueError("approved_acl_entry_count_mismatch")
        direction = "ingress" if permission == "write" else "out"
        replacement = (
            f" topic {permission} gh/v1/{system}/{direction}/node/{node}/{suffix}"
        )
        updated_block = pattern.sub(replacement, updated_block, count=1)

    updated = original.replace(original_block, updated_block, 1)

    before_without_approved = original_block
    after_without_approved = updated_block
    for permission, suffix in SUFFIXES:
        scrub = re.compile(
            rf"^ topic {permission} gh/v1/{re.escape(system)}/"
            rf"(?:ingress|out)/node/[A-Za-z0-9_-]+/{re.escape(suffix)}$",
            re.MULTILINE,
        )
        marker = f"[APPROVED_ENTRY:{permission}:{suffix}]"
        before_without_approved = scrub.sub(marker, before_without_approved)
        after_without_approved = scrub.sub(marker, after_without_approved)
    if telemetry_added:
        after_without_approved = after_without_approved.replace(
            "[APPROVED_ENTRY:write:telemetry]\n", "", 1
        )
    if before_without_approved != after_without_approved:
        raise ValueError("acl_scope_expanded")
    if original.replace(original_block, "[P5RELAY_BLOCK]", 1) != updated.replace(
        updated_block, "[P5RELAY_BLOCK]", 1
    ):
        raise ValueError("acl_outside_p5relay_changed")

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
