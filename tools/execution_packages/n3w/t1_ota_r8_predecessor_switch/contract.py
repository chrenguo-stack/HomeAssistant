from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

CURRENT_IMAGE = "local/n3w-homeassistant:2026.10.4-5881590f"
CURRENT_IMAGE_ID = "sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365"
PREDECESSOR_IMAGE = "local/n3w-homeassistant:2026.10.0-0c73235a"
PREDECESSOR_IMAGE_ID = "sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879"
PREDECESSOR_ARCHIVE_SIZE = 2448553472
PREDECESSOR_ARCHIVE_SHA256 = "e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663"
CURRENT_ROLLBACK_ARCHIVE_SIZE = 743051918
CURRENT_ROLLBACK_ARCHIVE_SHA256 = "31108a725e6b6530c68834218d9e41579055d7fe2718b3f42902b71237dc8e5f"
CURRENT_ROLLBACK_PORTABLE_SHA256 = "efcf67bd4ff40cd902b43fc531aa9dce58d115ececc8ebd4e324a15e0f4952f3"
CURRENT_ROLLBACK_TX_SHA256 = "a427bef98d2886234bf706eb1347f09148429e44c79ab08f01e1071dd0722492"
BOUND_USB_DEVICE = "/dev/sda1"
BOUND_USB_MAJOR_MINOR = "8:1"
POST_PEAK_RESERVE_BYTES = 1610612736
COMPATIBILITY_REVIEW_SHA256 = "8b02e9bb0143fc4fc7900c4c0e4c52b27f92725cd41f1f03b82ba67ffb9e0267"
EXPECTED_HOST_KEY_SHA256 = "2e6cae2b43ba5d7d0818fa53b4175a6bf58442077b32caf44b0bf886e6e4a901"
SCHEMA = "gh.n3w-t1-r8-predecessor-switch/1"
GRANT_SCHEMA = "gh.n3w-t1-r8-predecessor-switch-grant/1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

PHASE_PREFLIGHT = "PREFLIGHT"
PHASE_QUIESCED = "QUIESCED"
PHASE_BACKUP_VERIFIED = "BACKUP_VERIFIED"
PHASE_DATA_EXCHANGED = "DATA_EXCHANGED"
PHASE_CURRENT_RELEASE_INTENT = "CURRENT_RELEASE_INTENT"
PHASE_CURRENT_RELEASED = "CURRENT_RELEASED"
PHASE_CAPACITY_PASSED = "CAPACITY_PASSED"
PHASE_PREDECESSOR_LOADED = "PREDECESSOR_LOADED"
PHASE_BINDING_SWITCHED = "BINDING_SWITCHED"
PHASE_PREDECESSOR_HEALTHY = "PREDECESSOR_HEALTHY"
PHASE_ROLLED_BACK = "ROLLED_BACK"
PHASE_RECOVERY_REQUIRED = "RECOVERY_REQUIRED"

PHASE_ORDER = (
    PHASE_PREFLIGHT,
    PHASE_QUIESCED,
    PHASE_BACKUP_VERIFIED,
    PHASE_DATA_EXCHANGED,
    PHASE_CURRENT_RELEASE_INTENT,
    PHASE_CURRENT_RELEASED,
    PHASE_CAPACITY_PASSED,
    PHASE_PREDECESSOR_LOADED,
    PHASE_BINDING_SWITCHED,
    PHASE_PREDECESSOR_HEALTHY,
)
PHASE_INDEX = {value: index for index, value in enumerate(PHASE_ORDER)}


class ContractError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ContractError("predecessor_cache_invalid")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_compatibility_authority(review: dict[str, Any], target: dict[str, Any]) -> None:
    if review.get("schema") != "gh.n3w-t1-core-updater-homeassistant-compatibility-review/1":
        raise ContractError("compatibility_review_schema_invalid")
    if review.get("component") != "homeassistant" or review.get("mutation_profile") != "IMAGE_ONLY_V1":
        raise ContractError("compatibility_review_scope_invalid")
    predecessor = review.get("predecessor")
    candidate = review.get("candidate")
    if (
        not isinstance(predecessor, dict)
        or predecessor.get("version") != "2026.10.0"
        or predecessor.get("image") != PREDECESSOR_IMAGE
        or not isinstance(candidate, dict)
        or candidate.get("version") != "2026.10.4"
    ):
        raise ContractError("compatibility_review_version_invalid")
    storage = review.get("storage_contract")
    expected = {
        "core.config_entries": (1, 5),
        "core.device_registry": (3, 4),
        "core.entity_registry": (1, 23),
    }
    if not isinstance(storage, dict) or set(storage) != set(expected):
        raise ContractError("compatibility_storage_contract_invalid")
    for name, version in expected.items():
        value = storage.get(name)
        if not isinstance(value, dict):
            raise ContractError("compatibility_storage_contract_invalid")
        for side in ("predecessor", "candidate"):
            row = value.get(side)
            if (
                not isinstance(row, dict)
                or (row.get("version"), row.get("minor_version")) != version
            ):
                raise ContractError("compatibility_storage_contract_invalid")
    if (
        review.get("peer_contracts_compatible") is not True
        or review.get("persistent_schema_compatible") is not True
        or review.get("rollback_compatible_source_review") is not True
    ):
        raise ContractError("compatibility_rollback_authority_missing")
    if (
        target.get("schema") != "gh.n3w-t1-core-updater-target/2"
        or target.get("component") != "homeassistant"
        or target.get("mutation_profile") != "IMAGE_ONLY_V1"
        or target.get("target_image_ref") != CURRENT_IMAGE
        or target.get("expected_predecessor_image_ref") != PREDECESSOR_IMAGE
        or target.get("rollback_compatible") is not True
    ):
        raise ContractError("target_rollback_authority_invalid")
    evidence = target.get("compatibility_evidence")
    if (
        not isinstance(evidence, dict)
        or evidence.get("persistent_schema_compatible") is not True
        or evidence.get("peer_contracts_compatible") is not True
        or evidence.get("review_evidence_sha256") != COMPATIBILITY_REVIEW_SHA256
    ):
        raise ContractError("target_compatibility_evidence_invalid")


def validate_predecessor_cache(path: Path) -> None:
    if path.stat().st_size != PREDECESSOR_ARCHIVE_SIZE:
        raise ContractError("predecessor_cache_size_mismatch")
    if sha256_file(path) != PREDECESSOR_ARCHIVE_SHA256:
        raise ContractError("predecessor_cache_sha256_mismatch")


def import_worst_case_bytes(unpacked_layer_sizes: Iterable[int]) -> int:
    sizes = tuple(unpacked_layer_sizes)
    if (
        not sizes
        or any(type(value) is not int or value <= 0 for value in sizes)
    ):
        raise ContractError("predecessor_import_layer_sizes_invalid")
    return sum(sizes)


def post_release_capacity(
    *,
    available_bytes: int,
    import_bytes: int,
    reserve_bytes: int = POST_PEAK_RESERVE_BYTES,
) -> dict[str, int | bool | str]:
    if (
        type(available_bytes) is not int
        or type(import_bytes) is not int
        or type(reserve_bytes) is not int
        or min(available_bytes, import_bytes, reserve_bytes) <= 0
    ):
        raise ContractError("post_release_capacity_input_invalid")
    required = import_bytes + reserve_bytes
    return {
        "decision_point": "AFTER_RELEASE_BEFORE_NEXT_IMPORT",
        "available_bytes": available_bytes,
        "import_worst_case_bytes": import_bytes,
        "post_peak_reserve_bytes": reserve_bytes,
        "required_bytes": required,
        "capacity_pass": available_bytes >= required,
    }


@dataclass(frozen=True, slots=True)
class SwitchGrant:
    authorization_id: str
    expires_at_unix: int
    source_head: str
    ssh_host_key_sha256: str
    current_image: str
    current_image_id: str
    rollback_transaction_sha256: str
    rollback_archive_sha256: str
    rollback_archive_size: int
    usb_device: str
    usb_major_minor: str
    predecessor_image: str
    predecessor_image_id: str
    predecessor_archive_sha256: str
    predecessor_archive_size: int
    predecessor_import_worst_case_bytes: int

    @classmethod
    def from_document(cls, value: dict[str, Any]) -> "SwitchGrant":
        if not isinstance(value, dict) or value.get("schema") != GRANT_SCHEMA:
            raise ContractError("switch_grant_schema_invalid")
        fields = {
            "authorization_id",
            "expires_at_unix",
            "source_head",
            "ssh_host_key_sha256",
            "current_image",
            "current_image_id",
            "rollback_transaction_sha256",
            "rollback_archive_sha256",
            "rollback_archive_size",
            "usb_device",
            "usb_major_minor",
            "predecessor_image",
            "predecessor_image_id",
            "predecessor_archive_sha256",
            "predecessor_archive_size",
            "predecessor_import_worst_case_bytes",
        }
        if set(value) != fields | {"schema"}:
            raise ContractError("switch_grant_fields_invalid")
        try:
            grant = cls(**{field: value[field] for field in fields})
        except TypeError as error:
            raise ContractError("switch_grant_fields_invalid") from error
        grant.validate()
        return grant

    def validate(self) -> None:
        if (
            not isinstance(self.authorization_id, str)
            or not re.fullmatch(r"N3W_T1_R8_PREDECESSOR_SWITCH_[A-Z0-9_]{8,96}", self.authorization_id)
            or type(self.expires_at_unix) is not int
            or self.expires_at_unix <= 0
            or not isinstance(self.source_head, str)
            or not re.fullmatch(r"[0-9a-f]{40}", self.source_head)
            or self.ssh_host_key_sha256 != EXPECTED_HOST_KEY_SHA256
            or self.current_image != CURRENT_IMAGE
            or self.current_image_id != CURRENT_IMAGE_ID
            or self.rollback_transaction_sha256 != CURRENT_ROLLBACK_TX_SHA256
            or self.rollback_archive_sha256 != CURRENT_ROLLBACK_ARCHIVE_SHA256
            or self.rollback_archive_size != CURRENT_ROLLBACK_ARCHIVE_SIZE
            or self.usb_device != BOUND_USB_DEVICE
            or self.usb_major_minor != BOUND_USB_MAJOR_MINOR
            or self.predecessor_image != PREDECESSOR_IMAGE
            or self.predecessor_image_id != PREDECESSOR_IMAGE_ID
            or self.predecessor_archive_sha256 != PREDECESSOR_ARCHIVE_SHA256
            or self.predecessor_archive_size != PREDECESSOR_ARCHIVE_SIZE
            or type(self.predecessor_import_worst_case_bytes) is not int
            or self.predecessor_import_worst_case_bytes <= 0
        ):
            raise ContractError("switch_grant_binding_invalid")


def transaction_id(grant: SwitchGrant) -> str:
    document = {
        "schema": SCHEMA,
        "authorization_id": grant.authorization_id,
        "source_head": grant.source_head,
        "current_image": grant.current_image,
        "current_image_id": grant.current_image_id,
        "rollback_transaction_sha256": grant.rollback_transaction_sha256,
        "predecessor_image": grant.predecessor_image,
        "predecessor_image_id": grant.predecessor_image_id,
        "predecessor_archive_sha256": grant.predecessor_archive_sha256,
        "predecessor_import_worst_case_bytes": grant.predecessor_import_worst_case_bytes,
    }
    return sha256_bytes(canonical(document))


def transition_allowed(current: str, next_phase: str) -> bool:
    if current in {PHASE_ROLLED_BACK, PHASE_RECOVERY_REQUIRED, PHASE_PREDECESSOR_HEALTHY}:
        return False
    if current not in PHASE_INDEX or next_phase not in PHASE_INDEX:
        return False
    return PHASE_INDEX[next_phase] == PHASE_INDEX[current] + 1


def require_transition(current: str, next_phase: str) -> None:
    if not transition_allowed(current, next_phase):
        raise ContractError("switch_phase_transition_invalid")
