from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any, Protocol

SCHEMA = "gh.n3w.t1-golden-master-seal/1"
SEAL_CONFIRMATION = "SEAL GOLDEN MASTER: YES"
_SHA256 = re.compile(r"[0-9a-f]{64}")


class GoldenMasterSealError(RuntimeError):
    pass


class GoldenMasterSealAdapters(Protocol):
    def audit_public_release(self, release_id: str) -> Mapping[str, object]: ...
    def audit_instance_absence(self) -> Mapping[str, object]: ...
    def audit_capture_quiescence(self) -> Mapping[str, object]: ...
    def inspect_os_identity(self) -> Mapping[str, object]: ...
    def prepare_os_identity_for_seal(self) -> Mapping[str, object]: ...
    def write_seal_record(self, document: Mapping[str, object]) -> Mapping[str, object]: ...


def _require(
    report: Mapping[str, object],
    expected: Mapping[str, object],
    label: str,
) -> None:
    for key, value in expected.items():
        if report.get(key) != value:
            raise GoldenMasterSealError(f"{label}:{key}_invalid")


def _require_sha256(report: Mapping[str, object], key: str, label: str) -> str:
    value = report.get(key)
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise GoldenMasterSealError(f"{label}:{key}_invalid")
    return value


def _identity_blockers(report: Mapping[str, object]) -> list[str]:
    if report.get("unknown_identity_state") is not False:
        raise GoldenMasterSealError("os_identity:unknown_identity_state")

    ssh_count = report.get("ssh_host_private_key_count")
    if isinstance(ssh_count, bool) or not isinstance(ssh_count, int) or ssh_count < 0:
        raise GoldenMasterSealError("os_identity:ssh_host_private_key_count_invalid")

    fields = (
        "machine_id_populated",
        "network_identity_residue",
        "journal_identity_residue",
        "random_seed_residue",
    )
    for field in fields:
        if not isinstance(report.get(field), bool):
            raise GoldenMasterSealError(f"os_identity:{field}_invalid")

    blockers: list[str] = []
    if report["machine_id_populated"]:
        blockers.append("machine_id_populated")
    if ssh_count:
        blockers.append("ssh_host_private_keys_present")
    if report["network_identity_residue"]:
        blockers.append("network_identity_residue")
    if report["journal_identity_residue"]:
        blockers.append("journal_identity_residue")
    if report["random_seed_residue"]:
        blockers.append("random_seed_residue")

    capture_neutral = report.get("capture_neutral")
    if not isinstance(capture_neutral, bool):
        raise GoldenMasterSealError("os_identity:capture_neutral_invalid")
    if capture_neutral != (not blockers):
        raise GoldenMasterSealError("os_identity:capture_neutral_inconsistent")
    return blockers


def audit_golden_master_seal(
    adapters: GoldenMasterSealAdapters,
    *,
    release_id: str,
) -> dict[str, Any]:
    if not release_id:
        raise GoldenMasterSealError("release_id_invalid")

    public = adapters.audit_public_release(release_id)
    _require(
        public,
        {
            "status": "PASS",
            "release_id": release_id,
            "exact_release_binding": True,
            "secret_values_included": False,
            "production_service_start": False,
        },
        "public_release",
    )
    release_manifest_sha256 = _require_sha256(
        public,
        "release_manifest_sha256",
        "public_release",
    )
    image_lock_sha256 = _require_sha256(
        public,
        "image_lock_sha256",
        "public_release",
    )
    public_audit_sha256 = _require_sha256(
        public,
        "public_audit_sha256",
        "public_release",
    )

    instance = adapters.audit_instance_absence()
    _require(
        instance,
        {
            "status": "PASS",
            "instance_material_absent": True,
            "secret_values_included": False,
            "production_service_start": False,
        },
        "instance_absence",
    )

    quiescence = adapters.audit_capture_quiescence()
    _require(
        quiescence,
        {
            "status": "PASS",
            "product_container_count": 0,
            "product_volume_count": 0,
            "product_listener_count": 0,
            "product_firewall_active": False,
            "production_service_start": False,
        },
        "capture_quiescence",
    )

    identity = adapters.inspect_os_identity()
    _require(
        identity,
        {
            "status": "PASS",
            "target_specific": True,
            "secret_values_included": False,
            "production_service_start": False,
        },
        "os_identity",
    )
    target_identity_contract_sha256 = _require_sha256(
        identity,
        "target_identity_contract_sha256",
        "os_identity",
    )
    os_identity_audit_sha256 = _require_sha256(
        identity,
        "os_identity_audit_sha256",
        "os_identity",
    )
    blockers = _identity_blockers(identity)

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "release_id": release_id,
        "disk_capture_ready": not blockers,
        "identity_blockers": blockers,
        "release_manifest_sha256": release_manifest_sha256,
        "image_lock_sha256": image_lock_sha256,
        "public_audit_sha256": public_audit_sha256,
        "target_identity_contract_sha256": target_identity_contract_sha256,
        "os_identity_audit_sha256": os_identity_audit_sha256,
        "secret_values_included": False,
        "production_service_start": False,
        "board_access": False,
    }


def seal_golden_master(
    adapters: GoldenMasterSealAdapters,
    *,
    release_id: str,
    confirmation: str,
    claim_authorization: Callable[[], None],
) -> dict[str, Any]:
    if confirmation != SEAL_CONFIRMATION:
        raise GoldenMasterSealError("seal_confirmation_invalid")

    preaudit = audit_golden_master_seal(adapters, release_id=release_id)
    claim_authorization()

    if not preaudit["disk_capture_ready"]:
        prepared = adapters.prepare_os_identity_for_seal()
        _require(
            prepared,
            {
                "status": "PASS",
                "capture_neutral": True,
                "target_specific": True,
                "secret_values_included": False,
                "production_service_start": False,
                "rebooted": False,
            },
            "prepare_os_identity",
        )
        prepared_contract_sha256 = _require_sha256(
            prepared,
            "target_identity_contract_sha256",
            "prepare_os_identity",
        )
        if prepared_contract_sha256 != preaudit["target_identity_contract_sha256"]:
            raise GoldenMasterSealError("prepare_os_identity:target_contract_drift")

    postaudit = audit_golden_master_seal(adapters, release_id=release_id)
    if postaudit["disk_capture_ready"] is not True:
        raise GoldenMasterSealError("post_seal_capture_readiness_invalid")
    if (
        postaudit["target_identity_contract_sha256"]
        != preaudit["target_identity_contract_sha256"]
    ):
        raise GoldenMasterSealError("post_seal_target_contract_drift")

    record = {
        "schema": SCHEMA,
        "status": "PASS",
        "release_id": release_id,
        "release_manifest_sha256": postaudit["release_manifest_sha256"],
        "image_lock_sha256": postaudit["image_lock_sha256"],
        "public_audit_sha256": postaudit["public_audit_sha256"],
        "target_identity_contract_sha256": postaudit[
            "target_identity_contract_sha256"
        ],
        "os_identity_audit_sha256": postaudit["os_identity_audit_sha256"],
        "disk_capture_ready": True,
        "shutdown_required": True,
        "reboot_before_capture_forbidden": True,
        "secret_values_included": False,
        "production_service_start": False,
    }
    persisted = adapters.write_seal_record(record)
    _require(
        persisted,
        {
            "status": "PASS",
            "marker_last": True,
            "fsync_complete": True,
            "production_service_start": False,
        },
        "seal_record",
    )

    return {
        **record,
        "authorization_claimed": True,
        "board_access": False,
    }
