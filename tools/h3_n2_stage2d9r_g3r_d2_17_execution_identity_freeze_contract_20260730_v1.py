"""D2-17 execution-identity freeze and authorization contract."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any

import h3_n2_stage2d9r_g3r_d2_17_execution_identity_freeze_contract_base_20260730_v1 as base

for _name in dir(base):
    if not _name.startswith("_"):
        globals()[_name] = getattr(base, _name)

IMMUTABLE_ARTIFACT_ID = base.upstream.IMMUTABLE_ARTIFACT_ID
IMMUTABLE_ARCHIVE_SHA256 = base.upstream.IMMUTABLE_ARCHIVE_SHA256
IMMUTABLE_MERGED_SHA256 = base.upstream.IMMUTABLE_MERGED_SHA256
RECOVERY_ARTIFACT_ID = base.upstream.RECOVERY_ARTIFACT_ID
RECOVERY_ARCHIVE_SHA256 = base.upstream.RECOVERY_ARCHIVE_SHA256
RECOVERY_DESCRIPTOR_SHA256 = base.upstream.RECOVERY_DESCRIPTOR_SHA256
PRIVATE_PACKAGE_SHA256 = base.upstream.PRIVATE_PACKAGE_SHA256
PREPARE_COMMAND_SHA256 = base.upstream.PREPARE_COMMAND_SHA256
VERIFY_COMMAND_SHA256 = base.upstream.VERIFY_COMMAND_SHA256
CANDIDATE_DIGEST_SHA256 = base.upstream.CANDIDATE_DIGEST_SHA256
CA_PEM_SHA256 = base.upstream.CA_PEM_SHA256
BUILD_BINDING = base.upstream.BUILD_BINDING

LEGACY_EXACT_FIELD_NAMES = (
    "immutable_artifact_id", "immutable_artifact_archive_sha256", "immutable_payload_tar_sha256",
    "immutable_merged_image_sha256", "recovery_artifact_id", "recovery_artifact_archive_sha256",
    "recovery_payload_tar_sha256", "recovery_descriptor_sha256", "private_package_sha256",
    "prepare_command_sha256", "verify_command_sha256", "candidate_digest_sha256", "ca_pem_sha256",
    "build_binding", "execution_script_sha256", "python_executable_sha256", "openssl_executable_sha256",
    "esptool_executable_sha256", "mosquitto_executable_sha256",
)
LEGACY_HEX_FIELD_NAMES = (
    "request_binding_sha256", "execution_package_sha256", "execution_launcher_sha256",
    "execution_marker_name_sha256", "board_identity_sha256", "serial_identity_sha256",
    "baseline_state_sha256",
)
LEGACY_FIELD_SET_SHA256 = hashlib.sha256(
    "\n".join((*LEGACY_EXACT_FIELD_NAMES, *LEGACY_HEX_FIELD_NAMES)).encode("utf-8")
).hexdigest()
base.LEGACY_FIELD_SET_SHA256 = LEGACY_FIELD_SET_SHA256


def _legacy_exact_from_identity(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "immutable_artifact_id": IMMUTABLE_ARTIFACT_ID,
        "immutable_artifact_archive_sha256": IMMUTABLE_ARCHIVE_SHA256,
        "immutable_payload_tar_sha256": identity["immutable_payload_tar_sha256"],
        "immutable_merged_image_sha256": IMMUTABLE_MERGED_SHA256,
        "recovery_artifact_id": RECOVERY_ARTIFACT_ID,
        "recovery_artifact_archive_sha256": RECOVERY_ARCHIVE_SHA256,
        "recovery_payload_tar_sha256": identity["recovery_payload_tar_sha256"],
        "recovery_descriptor_sha256": RECOVERY_DESCRIPTOR_SHA256,
        "private_package_sha256": PRIVATE_PACKAGE_SHA256,
        "prepare_command_sha256": PREPARE_COMMAND_SHA256,
        "verify_command_sha256": VERIFY_COMMAND_SHA256,
        "candidate_digest_sha256": CANDIDATE_DIGEST_SHA256,
        "ca_pem_sha256": CA_PEM_SHA256,
        "build_binding": BUILD_BINDING,
        "execution_script_sha256": identity["execution_script_sha256"],
        "python_executable_sha256": identity["python_executable_sha256"],
        "openssl_executable_sha256": identity["openssl_executable_sha256"],
        "esptool_executable_sha256": identity["esptool_executable_sha256"],
        "mosquitto_executable_sha256": identity["mosquitto_executable_sha256"],
    }


def authorization_template(*, request: dict[str, Any], identity: dict[str, Any], issued_at: datetime,
                           expires_at: datetime, board_identity_sha256: str, serial_identity_sha256: str,
                           baseline_state_sha256: str, extras: dict[str, Any] | None = None) -> dict[str, Any]:
    issued = issued_at.astimezone(timezone.utc)
    expires = expires_at.astimezone(timezone.utc)
    require(issued < expires and (expires - issued).total_seconds() <= 7200, "AUTHORIZATION_WINDOW_INVALID")
    for digest in (board_identity_sha256, serial_identity_sha256, baseline_state_sha256):
        require(HEX64.fullmatch(digest) is not None, "AUTHORIZATION_IDENTITY_DIGEST_INVALID")
    require(identity.get("authorization_generated_after_freeze") is False, "AUTHORIZATION_IDENTITY_ALREADY_USED")
    field_names = authorization_field_inventory(() if extras is None else extras.keys())
    value: dict[str, Any] = {
        "schema": AUTH_SCHEMA, "stage": STAGE, "decision_id": DECISION_ID, "d2_request_id": D2_REQUEST_ID,
        "source_sha": request["source_sha"], "request_binding_sha256": request["request_binding_sha256"],
        "execution_closure_sha256": identity["execution_closure_sha256"],
        "delivery_equivalence_sha256": identity["delivery_equivalence_sha256"],
        "execution_package_sha256": identity["execution_package_sha256"],
        "execution_outer_sha256": identity["execution_outer_sha256"],
        "execution_launcher_sha256": identity["execution_launcher_sha256"],
        "execution_wrapper_sha256": identity["execution_wrapper_sha256"],
        "execution_contract_sha256": identity["execution_contract_sha256"],
        "canonical_builder_sha256": identity["canonical_builder_sha256"],
        "execution_controller_sha256": identity["execution_controller_sha256"],
        "execution_identity_sha256": identity["execution_identity_sha256"],
        "authorization_field_set_sha256": hashlib.sha256("\n".join(field_names).encode("utf-8")).hexdigest(),
        "execution_marker_name_sha256": hashlib.sha256(D2_REQUEST_ID.encode("utf-8")).hexdigest(),
        "board_identity_sha256": board_identity_sha256, "serial_identity_sha256": serial_identity_sha256,
        "baseline_state_sha256": baseline_state_sha256,
        "issued_at": issued.isoformat().replace("+00:00", "Z"),
        "expires_at": expires.isoformat().replace("+00:00", "Z"),
        "authorized": True, "authorization_created": True, "authorization_claimed": False,
        "authorization_consumed": False, "one_shot": True, "prepare_max_count": 1, "verify_max_count": 1,
        "locked_recovery_authorized": True, "locked_recovery_max_count": 1,
        "locked_recovery_scope": "TEST_PARTITION_ONLY", "replay_permitted": False,
        "automatic_retry_permitted": False, "activate_authorized": False, "cleanup_authorized": False,
        "production_operation_authorized": False, "full_inherited_authorization_preflight_required": True,
        "complete_chain_bind_before_authorization_required": True, "execution_identity_freeze_required": True,
        "hardware_call_sentinels_required": True,
    }
    value.update(_legacy_exact_from_identity(identity))
    if extras:
        for key, item in extras.items():
            require(key not in value and key != "authorization_record_sha256", "AUTHORIZATION_EXTRA_COLLISION")
            value[key] = item
    require(set(value) | {"authorization_record_sha256"} == set(field_names), "AUTHORIZATION_FIELD_INVENTORY_MISMATCH")
    value["authorization_record_sha256"] = canonical_sha256(value)
    return value


def validate_authorization_contract(authorization: dict[str, Any], request: dict[str, Any],
                                    identity: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    fixed = {
        "schema": AUTH_SCHEMA, "stage": STAGE, "decision_id": DECISION_ID, "d2_request_id": D2_REQUEST_ID,
        "source_sha": request["source_sha"], "request_binding_sha256": request["request_binding_sha256"],
        "execution_closure_sha256": identity["execution_closure_sha256"],
        "delivery_equivalence_sha256": identity["delivery_equivalence_sha256"],
        "execution_package_sha256": identity["execution_package_sha256"],
        "execution_outer_sha256": identity["execution_outer_sha256"],
        "execution_launcher_sha256": identity["execution_launcher_sha256"],
        "execution_wrapper_sha256": identity["execution_wrapper_sha256"],
        "execution_contract_sha256": identity["execution_contract_sha256"],
        "canonical_builder_sha256": identity["canonical_builder_sha256"],
        "execution_controller_sha256": identity["execution_controller_sha256"],
        "execution_identity_sha256": identity["execution_identity_sha256"],
        "authorized": True, "authorization_created": True, "authorization_claimed": False,
        "authorization_consumed": False, "one_shot": True, "prepare_max_count": 1, "verify_max_count": 1,
        "locked_recovery_authorized": True, "locked_recovery_max_count": 1,
        "locked_recovery_scope": "TEST_PARTITION_ONLY", "replay_permitted": False,
        "automatic_retry_permitted": False, "activate_authorized": False, "cleanup_authorized": False,
        "production_operation_authorized": False, "full_inherited_authorization_preflight_required": True,
        "complete_chain_bind_before_authorization_required": True, "execution_identity_freeze_required": True,
        "hardware_call_sentinels_required": True,
    }
    for key, expected in fixed.items():
        require(authorization.get(key) == expected, "AUTHORIZATION_" + key.upper() + "_MISMATCH")
    for key, expected in _legacy_exact_from_identity(identity).items():
        require(authorization.get(key) == expected, "AUTHORIZATION_" + key.upper() + "_MISMATCH")
    for key in ("board_identity_sha256", "serial_identity_sha256", "baseline_state_sha256", "execution_marker_name_sha256"):
        require(isinstance(authorization.get(key), str) and HEX64.fullmatch(authorization[key]) is not None,
                "AUTHORIZATION_" + key.upper() + "_INVALID")
    try:
        issued = datetime.fromisoformat(str(authorization.get("issued_at")).replace("Z", "+00:00")).astimezone(timezone.utc)
        expires = datetime.fromisoformat(str(authorization.get("expires_at")).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception as exc:
        raise ContractError("AUTHORIZATION_TIME_INVALID") from exc
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    require(issued <= current <= expires and 0 < (expires - issued).total_seconds() <= 7200, "AUTHORIZATION_NOT_CURRENT")
    observed = dict(authorization)
    supplied = observed.pop("authorization_record_sha256", None)
    require(isinstance(supplied, str) and canonical_sha256(observed) == supplied, "AUTHORIZATION_RECORD_DIGEST_MISMATCH")
    expected_inventory = hashlib.sha256("\n".join(sorted(authorization)).encode("utf-8")).hexdigest()
    require(authorization.get("authorization_field_set_sha256") == expected_inventory,
            "AUTHORIZATION_FIELD_SET_SHA256_MISMATCH")
    return authorization


def __getattr__(name: str) -> Any:
    return getattr(base.upstream, name)
