#!/usr/bin/env python3
"""Validate and redact an H3/N2 Stage 2D-8 execution manifest.

Default invocation accepts only LOCKED. The program performs no device,
network, Broker, firmware, serial, NVS, or external-service operation. The only
optional write is the caller-selected redacted JSON output file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

SCHEMA = "gh.h3.n2.stage2d8-execution-manifest/1"
GATES = {
    "LOCKED",
    "FLASH_ONLY",
    "READ_ONLY",
    "PREPARE_CANDIDATE",
    "ACTIVATE_PROFILE",
    "CLEANUP_TEST_STATE",
}
WRITE_GATES = {
    "PREPARE_CANDIDATE",
    "ACTIVATE_PROFILE",
    "CLEANUP_TEST_STATE",
}
FORBIDDEN_FIELD_FRAGMENTS = (
    "password",
    "private_key",
    "secret",
    "token",
    "ca_pem",
    "certificate_body",
    "mqtt_username",
    "broker_host",
    "wifi_ssid",
)
FORBIDDEN_TEXT = (
    "homeassistant",
    "greenhouse-manager",
    "gh/v1/",
    "mosquitto.db",
    "m401a",
    "phicomm-t1",
)
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
TEST_IDENTIFIER = re.compile(r"^gh-test-[A-Za-z0-9_.-]{1,80}$")
STORAGE_NAME = re.compile(r"^gh2d8_[A-Za-z0-9_]{1,8}$")


class ManifestError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ManifestError(message)


def mapping(value: Any, label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    difference = set(value) ^ expected
    require(not difference, f"{label} keys mismatch: {sorted(difference)}")


def string(value: Any, label: str) -> str:
    require(isinstance(value, str), f"{label} must be a string")
    require("<" not in value and ">" not in value, f"{label} contains a placeholder")
    require("\n" not in value and "\r" not in value, f"{label} contains control data")
    return value


def hex_value(value: Any, length: int, label: str) -> str:
    text = string(value, label)
    pattern = HEX40 if length == 40 else HEX64
    require(pattern.fullmatch(text) is not None, f"{label} must be {length} lowercase hex")
    return text


def absolute_path(value: Any, label: str) -> str:
    text = string(value, label)
    require(os.path.isabs(text), f"{label} must be absolute")
    return text


def nonnegative_integer(value: Any, label: str) -> int:
    require(isinstance(value, int) and value >= 0, f"{label} must be a nonnegative integer")
    return value


def walk_forbidden(value: Any, prefix: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            require(
                not any(fragment in lowered for fragment in FORBIDDEN_FIELD_FRAGMENTS),
                f"forbidden secret-bearing field: {prefix}{key}",
            )
            walk_forbidden(child, f"{prefix}{key}.")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk_forbidden(child, f"{prefix}{index}.")
    elif isinstance(value, str):
        lowered = value.lower()
        require(
            not any(token in lowered for token in FORBIDDEN_TEXT),
            f"production or forbidden identifier present at {prefix.rstrip('.')}",
        )


def image(value: Any, label: str) -> dict[str, str]:
    result = mapping(value, label)
    exact_keys(result, {"path", "sha256"}, label)
    return {
        "path": absolute_path(result["path"], f"{label}.path"),
        "sha256": hex_value(result["sha256"], 64, f"{label}.sha256"),
    }


def validate_manifest(document: Any, allow_live_gate: bool) -> dict[str, Any]:
    manifest = mapping(document, "manifest")
    exact_keys(
        manifest,
        {
            "schema",
            "gate",
            "source_commit",
            "test_firmware",
            "rollback_firmware",
            "board",
            "partition_table",
            "wifi_profile_digest",
            "broker",
            "identifiers",
            "evidence_directory",
            "recovery_procedure_digest",
            "observed_state",
            "authorization",
        },
        "manifest",
    )
    walk_forbidden(manifest)
    require(manifest["schema"] == SCHEMA, "manifest schema mismatch")

    gate = string(manifest["gate"], "gate")
    require(gate in GATES, "unsupported execution gate")
    if not allow_live_gate:
        require(gate == "LOCKED", "live-capable gate requires --allow-live-gate")

    source_commit = hex_value(manifest["source_commit"], 40, "source_commit")
    test_firmware = image(manifest["test_firmware"], "test_firmware")
    rollback_firmware = image(manifest["rollback_firmware"], "rollback_firmware")
    require(
        test_firmware["sha256"] != rollback_firmware["sha256"],
        "test and rollback firmware digests must differ",
    )

    board = mapping(manifest["board"], "board")
    exact_keys(board, {"identifier", "serial_path"}, "board")
    board_identifier = string(board["identifier"], "board.identifier")
    require(TEST_IDENTIFIER.fullmatch(board_identifier) is not None, "invalid test board identifier")
    serial_path = absolute_path(board["serial_path"], "board.serial_path")

    partition = mapping(manifest["partition_table"], "partition_table")
    exact_keys(
        partition,
        {"path", "sha256", "test_partition_label", "test_namespace"},
        "partition_table",
    )
    partition_path = absolute_path(partition["path"], "partition_table.path")
    partition_digest = hex_value(partition["sha256"], 64, "partition_table.sha256")
    partition_label = string(
        partition["test_partition_label"], "partition_table.test_partition_label"
    )
    namespace = string(partition["test_namespace"], "partition_table.test_namespace")
    require(STORAGE_NAME.fullmatch(partition_label) is not None, "invalid test partition label")
    require(STORAGE_NAME.fullmatch(namespace) is not None, "invalid test namespace")
    require(partition_label != namespace, "partition label and namespace must differ")

    wifi_digest = hex_value(manifest["wifi_profile_digest"], 64, "wifi_profile_digest")
    broker = mapping(manifest["broker"], "broker")
    exact_keys(
        broker,
        {
            "configuration_digest",
            "ca_digest",
            "acl_digest",
            "server_certificate_digest",
        },
        "broker",
    )
    broker_digests = {
        key: hex_value(value, 64, f"broker.{key}") for key, value in broker.items()
    }
    require(len(set(broker_digests.values())) == 4, "Broker digests must be distinct")

    identifiers = mapping(manifest["identifiers"], "identifiers")
    exact_keys(
        identifiers,
        {"test_run_id", "system_id", "node_id", "client_id", "topic_root"},
        "identifiers",
    )
    for key in ("test_run_id", "system_id", "node_id", "client_id"):
        text = string(identifiers[key], f"identifiers.{key}")
        require(TEST_IDENTIFIER.fullmatch(text) is not None, f"invalid identifiers.{key}")
    run_id = identifiers["test_run_id"]
    topic_root = string(identifiers["topic_root"], "identifiers.topic_root")
    require(topic_root.startswith("gh-test/"), "topic root must begin gh-test/")
    require(run_id in topic_root, "topic root must contain exact test run id")
    require("#" not in topic_root and "+" not in topic_root, "topic root cannot contain wildcards")
    require(len(set(identifiers.values())) == 5, "test identifiers must be unique")

    evidence_directory = absolute_path(manifest["evidence_directory"], "evidence_directory")
    recovery_digest = hex_value(
        manifest["recovery_procedure_digest"], 64, "recovery_procedure_digest"
    )

    observed = mapping(manifest["observed_state"], "observed_state")
    exact_keys(
        observed,
        {
            "available",
            "persistence_status",
            "active_generation",
            "candidate_generation",
            "persistent_write_count",
        },
        "observed_state",
    )
    require(isinstance(observed["available"], bool), "observed_state.available must be boolean")
    status = string(observed["persistence_status"], "observed_state.persistence_status")
    require(
        status
        in {
            "unknown",
            "empty",
            "active",
            "no_active_prepared",
            "active_with_prepared",
            "active_with_committed_orphan",
            "storage_error",
            "conflict",
            "invalid_record",
        },
        "unsupported persistence status",
    )
    observed_active = nonnegative_integer(
        observed["active_generation"], "observed_state.active_generation"
    )
    observed_candidate = nonnegative_integer(
        observed["candidate_generation"], "observed_state.candidate_generation"
    )
    nonnegative_integer(
        observed["persistent_write_count"], "observed_state.persistent_write_count"
    )

    authorization = mapping(manifest["authorization"], "authorization")
    exact_keys(
        authorization,
        {"operation", "active_generation", "candidate_generation", "record_digest"},
        "authorization",
    )
    operation = string(authorization["operation"], "authorization.operation")
    require(operation in WRITE_GATES | {"NONE"}, "unsupported authorization operation")
    authorized_active = nonnegative_integer(
        authorization["active_generation"], "authorization.active_generation"
    )
    authorized_candidate = nonnegative_integer(
        authorization["candidate_generation"], "authorization.candidate_generation"
    )
    record_digest = authorization["record_digest"]
    require(isinstance(record_digest, str), "authorization.record_digest must be a string")

    if gate in {"LOCKED", "FLASH_ONLY", "READ_ONLY"}:
        require(operation == "NONE", "non-write gate cannot contain write authorization")
        require(
            authorized_active == 0 and authorized_candidate == 0 and record_digest == "",
            "non-write gate authorization must be empty",
        )
    else:
        require(gate == operation, "gate and authorization operation must match")
        require(observed["available"], "write gate requires observed read-only state")
        hex_value(record_digest, 64, "authorization.record_digest")

        if gate == "PREPARE_CANDIDATE":
            require(
                observed_candidate == 0
                and status in {"empty", "active"},
                "PREPARE requires an observed state without a persistent candidate",
            )
            require(
                authorized_active == observed_active,
                "PREPARE active generation must match observed state",
            )
            require(
                authorized_candidate > observed_active,
                "PREPARE candidate generation must exceed observed active generation",
            )
        else:
            require(
                authorized_active == observed_active
                and authorized_candidate == observed_candidate,
                "authorization generations must match observed state",
            )
            if gate == "ACTIVATE_PROFILE":
                require(
                    status in {"no_active_prepared", "active_with_prepared"}
                    and observed_candidate > observed_active,
                    "ACTIVATE requires an observed PREPARED candidate",
                )
            if gate == "CLEANUP_TEST_STATE":
                require(status != "unknown", "CLEANUP requires an observed persistence state")

    if gate == "LOCKED":
        require(not observed["available"], "LOCKED manifest cannot claim board observation")
        require(status == "unknown", "LOCKED persistence status must be unknown")
        require(observed["persistent_write_count"] == 0, "LOCKED write count must be zero")

    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    manifest_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "schema": "gh.h3.n2.stage2d8-execution-manifest-redacted/1",
        "manifest_digest": manifest_digest,
        "gate": gate,
        "source_commit": source_commit,
        "test_firmware_sha256": test_firmware["sha256"],
        "rollback_firmware_sha256": rollback_firmware["sha256"],
        "board_identifier": board_identifier,
        "serial_path_bound": bool(serial_path),
        "partition_table_sha256": partition_digest,
        "test_partition_label": partition_label,
        "test_namespace": namespace,
        "wifi_profile_digest": wifi_digest,
        "broker_configuration_digest": broker_digests["configuration_digest"],
        "broker_ca_digest": broker_digests["ca_digest"],
        "broker_acl_digest": broker_digests["acl_digest"],
        "broker_server_certificate_digest": broker_digests[
            "server_certificate_digest"
        ],
        "test_run_id": run_id,
        "system_id": identifiers["system_id"],
        "node_id": identifiers["node_id"],
        "client_id": identifiers["client_id"],
        "topic_root": topic_root,
        "evidence_directory_bound": bool(evidence_directory),
        "partition_table_path_bound": bool(partition_path),
        "recovery_procedure_digest": recovery_digest,
        "observed_state": observed,
        "authorization": {
            "operation": operation,
            "active_generation": authorized_active,
            "candidate_generation": authorized_candidate,
            "record_digest_bound": bool(record_digest),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--allow-live-gate",
        action="store_true",
        help="validate an explicitly reviewed gate beyond LOCKED",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        raw = args.manifest.read_text(encoding="utf-8")
        document = json.loads(raw)
        normalized = validate_manifest(document, args.allow_live_gate)
    except (OSError, json.JSONDecodeError, ManifestError) as exc:
        raise SystemExit(f"stage2d8_execution_manifest_gate=fail: {exc}") from exc

    rendered = json.dumps(normalized, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print("stage2d8_execution_manifest_gate=pass")


if __name__ == "__main__":
    main()
