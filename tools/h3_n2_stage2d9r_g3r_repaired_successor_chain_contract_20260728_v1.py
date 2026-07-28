#!/usr/bin/env python3
"""Pure source contract for the Stage 2D-9R G3R repaired successor chain.

This module contains no secret generation, board, USB, serial, esptool, Flash,
physical NVS, network, Broker, PREPARE, VERIFY, ACTIVATE, or CLEANUP code.  It
freezes the public layering rules approved by
D1-H3N2-STAGE2D9R-G3R-REPAIRED-SUCCESSOR-CHAIN-20260728-01.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from typing import Mapping, Sequence

SCHEMA = "gh.h3.n2.stage2d9r-g3r-repaired-successor-chain-contract/1"
FINAL_BINDING_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-repaired-successor-final-execution-binding/1"
)
STAGE = "H3/N2 Stage 2D-9R G3R repaired successor"
DECISION_ID = "D1-H3N2-STAGE2D9R-G3R-REPAIRED-SUCCESSOR-CHAIN-20260728-01"

CURRENT_MAIN_SHA = "c16da1a2d4d8300198b0603359eea349a034e2ea"
PREVIOUS_MAIN_SHA = "43aa37b0cc343efdd2024f369517e55c5b6461f1"
BASE_PULL_REQUEST = 185
BASE_HEAD_SHA = "662bd9027595a7dcfaaaedb977691b13b3fec74b"
REPAIR_SOURCE_BINDING = "0a2c96b7615d9f222cf72fcf899b6caf3a7c875f"
REPAIR_REVIEW_ARTIFACT_ID = 8658678213
REPAIR_REVIEW_ARTIFACT_SHA256 = (
    "7d2fa7b03c0082d5bc6a26e51a7fa4bc3823dc583ba00a1f1afac6dbd0e1f0cb"
)
REPAIR_MERGED_IMAGE_SHA256 = (
    "d2e4f3402f0282d801bb1c05060b39aa3200f28d8ca03cf88026eb5c6178341a"
)

RETIRED_D2_REQUEST_ID = "D2-H3N2-STAGE2D9R-G3R-SUCCESSOR-20260727-01"
RETIRED_D2_TERMINAL_STATUS = "CONSUMED_FAILED"
RETIRED_D2_TERMINAL_STATE = "LOCKED_RECOVERY_COMPLETED"
RUN_SUFFIX = "tlsvalid03"
CUSTODY_SELECTION_RULE = (
    "HOME_LOCAL_STATE_STAGE2D9R_REPAIRED_SUCCESSOR_PRIVATE_MATERIAL_TLSVALID03"
)
CUSTODY_RELATIVE = (
    ".local/state/greenhouse-stage2d9r/"
    "repaired-successor-private-execution-material-tlsvalid03"
)
ESP_HOME_VERSION = "2026.4.3"

TEST_PARTITION_LABEL = "gh2d8_p2d9"
TEST_PARTITION_NAMESPACE = "gh2d8_s2d9"
TEST_PARTITION_ADDRESS = 0x400000
TEST_PARTITION_SIZE = 0x10000
ERASED_PARTITION_SHA256 = (
    "71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063"
)

REQUIRED_PRIVATE_FILES = (
    "mqtt-password.hex",
    "mosquitto.password",
    "persistence-key.hex",
    "unlock-token.hex",
    "prepare-command.txt",
    "verify-command.txt",
    "root-ca.key.pem",
    "root-ca.cert.pem",
    "broker.key.pem",
    "broker.cert.pem",
    "broker.fullchain.pem",
    "mosquitto.stage2d9r.conf",
    "mosquitto.stage2d9r.acl",
)

GATE_ORDER = (
    "SOURCE_AND_PUBLIC_FREEZE",
    "PRIVATE_MATERIAL_U1",
    "IMMUTABLE_AND_RECOVERY_FREEZE",
    "BASELINE_READONLY_GATE",
    "HOST_ONLY_FINAL_PREFLIGHT",
    "PHYSICAL_D2",
)

FINAL_EXECUTION_DIGEST_FIELDS = (
    "private_package_sha256",
    "public_descriptor_sha256",
    "candidate_digest_sha256",
    "ca_pem_sha256",
    "prepare_command_sha256",
    "verify_command_sha256",
    "repaired_host_controller_sha256",
    "immutable_archive_sha256",
    "immutable_payload_sha256",
    "immutable_merged_image_sha256",
    "immutable_partition_table_sha256",
    "recovery_archive_sha256",
    "recovery_payload_sha256",
    "recovery_descriptor_sha256",
    "python_environment_sha256",
    "openssl_environment_sha256",
    "esphome_environment_sha256",
)

# These values identify the retired tlsvalid02 physical-execution chain and may
# appear only as deny-list evidence.  A repaired successor binding must not use
# any of them as a current input.
RETIRED_DIGESTS = frozenset(
    {
        "7b585fc53b9201fd2c6161e544ac062d4223f509bfc86a10052d97907e4f55bb",
        "294df853b85fd86ae31ae05dc68b44fa3deac0cbffdbb8c24f62ca8175ef641f",
        "53965a7dc1ec4265cc21eee11a03a22e0bc20ff6c8e3ffa56f42b4043da8c347",
        "a0ff758217a1769c1876336c131cb85e64dcb2369758c649f36798cd8083aaf2",
        "9d98b4aa1d87604e8c37aaa50892bf4cd47b8b8a0479acdabe78d41d39b36096",
        "b8c7e937ff325d121aeff8414618e88b8a229cca00bc27e439c587f830851dc8",
        "14e882f550ca92d14cf6776e518eb083b7344683b5534487bd28e95d93b29747",
        "925ae87831a259d5a477fba9dde009b4d6a218e43735638521d4a10a38fe95bf",
        "3274a9329f46f420b65037efdf3cb9e453121ec7f74573430fb2afc8a7de882e",
        "50c4ff6569401b3c1cb20570ed149b0a5978fdc202c2aa33dff1b6ea1fe58d2e",
        "912e7e2ec4f10cb81836e5a50df1dd5745eae2ba057bd51b1929671fb5872beb",
    }
)

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ContractError(RuntimeError):
    """Fail-closed repaired-successor contract error."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_sha256(value: object) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def validate_sha40(value: object, code: str) -> str:
    require(isinstance(value, str) and HEX40.fullmatch(value) is not None, code)
    return value


def validate_sha256(value: object, code: str, *, reject_retired: bool = True) -> str:
    require(isinstance(value, str) and HEX64.fullmatch(value) is not None, code)
    if reject_retired:
        require(value not in RETIRED_DIGESTS, f"{code}_RETIRED_REUSE")
    return value


def validate_private_inventory(
    materials: Mapping[str, Mapping[str, str]],
) -> str:
    require(set(materials) == set(REQUIRED_PRIVATE_FILES), "PRIVATE_INVENTORY_MISMATCH")
    normalized: dict[str, dict[str, str]] = {}
    for name in sorted(materials):
        metadata = materials[name]
        require(metadata.get("relative_path") == name, "PRIVATE_RELATIVE_PATH_MISMATCH")
        require(metadata.get("mode") == "0600", "PRIVATE_MODE_MISMATCH")
        digest = validate_sha256(metadata.get("sha256"), "PRIVATE_DIGEST_INVALID")
        normalized[name] = {
            "relative_path": name,
            "mode": "0600",
            "sha256": digest,
        }
    return canonical_json_sha256(
        {
            "schema": "gh.h3.n2.stage2d9r-g3r-repaired-successor-private-inventory/1",
            "run_suffix": RUN_SUFFIX,
            "materials": normalized,
        }
    )


def build_final_execution_payload(
    *,
    source_sha: str,
    digest_bindings: Mapping[str, str],
    immutable_build_count: int,
    immutable_builds_byte_identical: bool,
) -> dict[str, object]:
    validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    require(source_sha != BASE_HEAD_SHA, "FINAL_SOURCE_MUST_EXTEND_REPAIR_BASE")
    require(set(digest_bindings) == set(FINAL_EXECUTION_DIGEST_FIELDS),
            "FINAL_DIGEST_FIELD_SET_MISMATCH")
    normalized: dict[str, str] = {}
    for key in FINAL_EXECUTION_DIGEST_FIELDS:
        normalized[key] = validate_sha256(
            digest_bindings[key], f"FINAL_{key.upper()}_INVALID"
        )
    require(immutable_build_count == 2, "IMMUTABLE_BUILD_COUNT_MISMATCH")
    require(immutable_builds_byte_identical is True,
            "IMMUTABLE_BUILDS_NOT_BYTE_IDENTICAL")
    require(
        normalized["immutable_merged_image_sha256"] != REPAIR_MERGED_IMAGE_SHA256,
        "REPAIR_REVIEW_IMAGE_NOT_FINAL_IMMUTABLE",
    )
    return {
        "schema": FINAL_BINDING_SCHEMA,
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "current_main_sha": CURRENT_MAIN_SHA,
        "base_pull_request": BASE_PULL_REQUEST,
        "base_head_sha": BASE_HEAD_SHA,
        "source_sha": source_sha,
        "repair_source_binding": REPAIR_SOURCE_BINDING,
        "repair_source_binding_is_final_execution_binding": False,
        "run_suffix": RUN_SUFFIX,
        "custody_selection_rule": CUSTODY_SELECTION_RULE,
        "esphome_version": ESP_HOME_VERSION,
        "immutable_build_count": immutable_build_count,
        "immutable_builds_byte_identical": immutable_builds_byte_identical,
        "test_partition": {
            "label": TEST_PARTITION_LABEL,
            "namespace": TEST_PARTITION_NAMESPACE,
            "address": TEST_PARTITION_ADDRESS,
            "size": TEST_PARTITION_SIZE,
            "erased_sha256": ERASED_PARTITION_SHA256,
        },
        "bindings": normalized,
        "board_operation_authorized": False,
        "serial_operation_authorized": False,
        "flash_operation_authorized": False,
        "physical_nvs_operation_authorized": False,
        "network_operation_authorized": False,
        "broker_operation_authorized": False,
        "prepare_authorized": False,
        "verify_authorized": False,
        "activate_authorized": False,
        "cleanup_authorized": False,
        "ready_authorized": False,
        "merge_authorized": False,
        "release_authorized": False,
        "tag_authorized": False,
        "deployment_authorized": False,
        "private_values_included": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }


def derive_final_execution_binding(payload: Mapping[str, object]) -> tuple[str, str]:
    require(payload.get("schema") == FINAL_BINDING_SCHEMA, "FINAL_BINDING_SCHEMA_MISMATCH")
    full = canonical_json_sha256(payload)
    return full[:40], full


def validate_gate_sequence(sequence: Sequence[str]) -> None:
    require(tuple(sequence) == GATE_ORDER, "GATE_ORDER_MISMATCH")


def source_contract(source_sha: str = BASE_HEAD_SHA) -> dict[str, object]:
    validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    validate_gate_sequence(GATE_ORDER)
    return {
        "schema": SCHEMA,
        "state": "SOURCE_CONTRACT_ACCEPTED_NO_EXECUTION_AUTHORITY",
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "current_main_sha": CURRENT_MAIN_SHA,
        "previous_main_sha": PREVIOUS_MAIN_SHA,
        "main_zero_net_tree_correction_accepted": True,
        "pr_176_mergeable_false_accepted_as_non_executional": True,
        "pr_176_modification_permitted": False,
        "base_pull_request": BASE_PULL_REQUEST,
        "base_head_sha": BASE_HEAD_SHA,
        "contract_source_sha": source_sha,
        "repair_source_binding": REPAIR_SOURCE_BINDING,
        "repair_source_binding_is_final_execution_binding": False,
        "new_final_execution_binding_required": True,
        "repair_review_artifact_id": REPAIR_REVIEW_ARTIFACT_ID,
        "repair_review_artifact_sha256": REPAIR_REVIEW_ARTIFACT_SHA256,
        "repair_merged_image_sha256": REPAIR_MERGED_IMAGE_SHA256,
        "run_suffix": RUN_SUFFIX,
        "custody_selection_rule": CUSTODY_SELECTION_RULE,
        "custody_relative_path": CUSTODY_RELATIVE,
        "required_private_files": list(REQUIRED_PRIVATE_FILES),
        "gate_order": list(GATE_ORDER),
        "immutable_independent_build_count": 2,
        "immutable_builds_byte_identical_required": True,
        "locked_recovery_scope": "TEST_PARTITION_ONLY",
        "locked_recovery_max_count": 1,
        "retired_d2_request_id": RETIRED_D2_REQUEST_ID,
        "retired_d2_terminal_status": RETIRED_D2_TERMINAL_STATUS,
        "retired_d2_terminal_state": RETIRED_D2_TERMINAL_STATE,
        "retired_d2_replay_permitted": False,
        "retired_private_material_reuse_permitted": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "secret_generation": False,
        "private_material_created": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_enumeration": False,
        "serial_open": False,
        "esptool_invoked": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
        "activate_executed": False,
        "cleanup_executed": False,
        "ready_authorized": False,
        "merge_authorized": False,
        "release_authorized": False,
        "tag_authorized": False,
        "deployment_authorized": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "private_values_included": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", default=BASE_HEAD_SHA)
    args = parser.parse_args()
    print(json.dumps(source_contract(args.source_sha), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
