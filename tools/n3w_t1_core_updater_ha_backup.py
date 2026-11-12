from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from n3w_t1_core_updater_v2_common import SHA256, UpdaterV2Error


@dataclass(frozen=True)
class HaDataBackupRecord:
    archive_sha256: str
    archive_size_bytes: int
    manifest_sha256: str
    verified: bool
    fsynced: bool
    consistent_preupgrade_point: bool
    complete_production_config: bool
    storage_integrity_verified: bool
    ownership_metadata_present: bool
    confidentiality_protected: bool
    authenticity_protected: bool
    unsupported_external_state: bool

    def public(self) -> dict[str, str | int | bool]:
        return {
            "archive_sha256": self.archive_sha256,
            "archive_size_bytes": self.archive_size_bytes,
            "manifest_sha256": self.manifest_sha256,
            "verified": self.verified,
            "fsynced": self.fsynced,
            "consistent_preupgrade_point": self.consistent_preupgrade_point,
            "complete_production_config": self.complete_production_config,
            "storage_integrity_verified": self.storage_integrity_verified,
            "ownership_metadata_present": self.ownership_metadata_present,
            "confidentiality_protected": self.confidentiality_protected,
            "authenticity_protected": self.authenticity_protected,
            "unsupported_external_state": self.unsupported_external_state,
        }


class HaDataBackupProvider(Protocol):
    def create_consistent_backup(
        self,
        *,
        transaction_id_sha256: str,
    ) -> HaDataBackupRecord:
        ...

    def verify_backup(
        self,
        record: HaDataBackupRecord,
    ) -> HaDataBackupRecord:
        ...

    def restore_preupgrade_backup(
        self,
        record: HaDataBackupRecord,
    ) -> None:
        ...


def validate_backup_record(record: HaDataBackupRecord) -> HaDataBackupRecord:
    if (
        not isinstance(record.archive_sha256, str)
        or SHA256.fullmatch(record.archive_sha256) is None
        or not isinstance(record.manifest_sha256, str)
        or SHA256.fullmatch(record.manifest_sha256) is None
        or not isinstance(record.archive_size_bytes, int)
        or isinstance(record.archive_size_bytes, bool)
        or record.archive_size_bytes <= 0
    ):
        raise UpdaterV2Error("ha_data_backup_identity_invalid")
    if record.unsupported_external_state is True:
        raise UpdaterV2Error("ha_data_backup_external_state_unsupported")
    required_true = (
        record.verified,
        record.fsynced,
        record.consistent_preupgrade_point,
        record.complete_production_config,
        record.storage_integrity_verified,
        record.ownership_metadata_present,
        record.confidentiality_protected,
        record.authenticity_protected,
    )
    if any(value is not True for value in required_true):
        raise UpdaterV2Error("ha_data_backup_contract_incomplete")
    return record


def backup_record_from_document(value: object) -> HaDataBackupRecord:
    expected_fields = {
        "archive_sha256",
        "archive_size_bytes",
        "manifest_sha256",
        "verified",
        "fsynced",
        "consistent_preupgrade_point",
        "complete_production_config",
        "storage_integrity_verified",
        "ownership_metadata_present",
        "confidentiality_protected",
        "authenticity_protected",
        "unsupported_external_state",
    }
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise UpdaterV2Error("ha_data_backup_document_invalid")
    try:
        record = HaDataBackupRecord(**value)
    except TypeError as error:
        raise UpdaterV2Error("ha_data_backup_document_invalid") from error
    return validate_backup_record(record)
