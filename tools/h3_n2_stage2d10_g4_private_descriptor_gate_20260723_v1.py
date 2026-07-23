#!/usr/bin/env python3
"""Fail-closed validator for Stage 2D-10 G4 private execution descriptors."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re

SCHEMA = "gh.h3.n2.stage2d10-g4-private-execution-descriptor/1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PLACEHOLDER = re.compile(r"<[^>]+>")


class DescriptorError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DescriptorError(message)


def nested(data: dict[str, object], key: str) -> dict[str, object]:
    value = data.get(key)
    require(isinstance(value, dict), f"{key} must be an object")
    return value


def is_absolute_private_path(value: object) -> bool:
    text = str(value)
    return PurePosixPath(text).is_absolute() and PLACEHOLDER.search(text) is None


def has_placeholder(value: object) -> bool:
    if isinstance(value, dict):
        return any(has_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(has_placeholder(item) for item in value)
    return PLACEHOLDER.search(str(value)) is not None


def validate(data: dict[str, object], require_authorized: bool) -> str:
    require(data.get("schema") == SCHEMA, "schema mismatch")

    partition = nested(data, "test_partition")
    require(partition.get("label") == "gh2d8_p2d9", "partition mismatch")
    require(partition.get("namespace") == "gh2d8_s2d9", "namespace mismatch")

    authorization = nested(data, "activation_authorization")
    require(
        authorization.get("operation") == "ACTIVATE_PROFILE",
        "operation mismatch",
    )
    require(authorization.get("active_generation") == 0, "active mismatch")
    require(
        authorization.get("candidate_generation") == 1,
        "candidate mismatch",
    )
    require(authorization.get("one_shot") is True, "one_shot required")
    require(
        authorization.get("replay_permitted") is False,
        "replay must be false",
    )

    counts = nested(data, "allowed_counts")
    expected_counts = {
        "firmware_flash": 1,
        "activate_command": 1,
        "verify_command": 1,
        "locked_recovery": 1,
        "cleanup_command": 0,
    }
    require(counts == expected_counts, "allowed counts mismatch")

    identifiers = nested(data, "identifiers")
    topic_root = str(identifiers.get("topic_root", ""))
    require(topic_root.startswith("gh-test/"), "topic root must be test-only")
    require("homeassistant" not in topic_root.lower(), "Discovery topic forbidden")
    require("gh/v1/" not in topic_root, "production topic forbidden")

    commands = nested(data, "commands")
    require("cleanup" not in str(commands).lower(), "cleanup command forbidden")

    authorized = data.get("execution_authorized") is True
    if require_authorized:
        require(authorized, "descriptor is not execution-authorized")

    if not authorized:
        require(has_placeholder(data), "locked template must retain placeholders")
        return "LOCKED"

    require(not has_placeholder(data), "authorized descriptor has placeholders")
    require(HEX40.fullmatch(str(data.get("source_sha"))) is not None, "source sha")
    for key in (
        "artifact_sha256",
        "candidate_digest_sha256",
        "board_binding_sha256",
        "python_environment_digest",
    ):
        require(HEX64.fullmatch(str(data.get(key))) is not None, f"{key} invalid")

    for key in (
        "pre_activation_partition_sha256",
    ):
        require(HEX64.fullmatch(str(partition.get(key))) is not None, f"{key} invalid")

    broker = nested(data, "broker")
    for key in (
        "configuration_sha256",
        "acl_sha256",
        "password_file_sha256",
        "ca_sha256",
        "server_certificate_sha256",
        "server_key_sha256",
    ):
        require(HEX64.fullmatch(str(broker.get(key))) is not None, f"{key} invalid")

    require(
        str(broker.get("client_id", "")).startswith("gh-test-client-"),
        "client id must be test-only",
    )
    require(
        is_absolute_private_path(data.get("serial_path")),
        "serial path must be absolute",
    )
    evidence = nested(data, "evidence")
    require(
        is_absolute_private_path(evidence.get("private_directory")),
        "evidence path must be absolute",
    )
    require(
        HEX64.fullmatch(str(evidence.get("recovery_procedure_sha256")))
        is not None,
        "recovery digest invalid",
    )

    authorization_id = str(data.get("authorization_id", ""))
    require(authorization_id.startswith("D2-"), "authorization id invalid")
    require(
        HEX64.fullmatch(str(authorization.get("authorization_record_digest")))
        is not None,
        "authorization digest invalid",
    )
    for key in ("activate_command_sha256", "verify_command_sha256"):
        require(HEX64.fullmatch(str(commands.get(key))) is not None, f"{key} invalid")

    return "ACTIVATE_PROFILE"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--descriptor", type=Path, required=True)
    parser.add_argument("--require-authorized", action="store_true")
    args = parser.parse_args()

    try:
        data = json.loads(args.descriptor.read_text(encoding="utf-8"))
        gate = validate(data, args.require_authorized)
    except Exception as exc:
        print("STAGE2D10_G4_PRIVATE_DESCRIPTOR_GATE=FAIL")
        print(f"FAILURE_CLASS={type(exc).__name__}")
        print(f"FAILURE_MESSAGE={exc}")
        return 2

    print("STAGE2D10_G4_PRIVATE_DESCRIPTOR_GATE=PASS")
    print(f"GATE={gate}")
    print(
        "EXECUTION_AUTHORIZED="
        + str(bool(data.get("execution_authorized"))).lower()
    )
    print("PRIVATE_VALUES_INCLUDED_IN_OUTPUT=false")
    print("CLEANUP_TEST_STATE_AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
