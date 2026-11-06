from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from n3w_t1_core_updater_v2_common import SHA256, UpdaterV2Error


ARTIFACT_KINDS = frozenset({"target", "predecessor"})


@dataclass(frozen=True)
class ImageRecoveryRecord:
    kind: str
    image_ref: str
    archive_sha256: str
    archive_size_bytes: int
    portable_identity_sha256: str
    platform: str
    verified: bool
    fsynced: bool

    def public(self) -> dict[str, str | int | bool]:
        return {
            "kind": self.kind,
            "image_ref": self.image_ref,
            "archive_sha256": self.archive_sha256,
            "archive_size_bytes": self.archive_size_bytes,
            "portable_identity_sha256": self.portable_identity_sha256,
            "platform": self.platform,
            "verified": self.verified,
            "fsynced": self.fsynced,
        }


class HaImageRecoveryProvider(Protocol):
    def export_predecessor(
        self,
        *,
        transaction_id_sha256: str,
        expected_image_ref: str,
    ) -> ImageRecoveryRecord:
        ...

    def verify_image_recovery(
        self,
        record: ImageRecoveryRecord,
    ) -> ImageRecoveryRecord:
        ...

    def remove_exact_internal_predecessor(
        self,
        *,
        image_ref: str,
        portable_identity_sha256: str,
    ) -> None:
        ...

    def load_exact_target(
        self,
        record: ImageRecoveryRecord,
    ) -> None:
        ...

    def restore_exact_predecessor(
        self,
        record: ImageRecoveryRecord,
    ) -> None:
        ...


def validate_image_recovery_record(
    record: ImageRecoveryRecord,
    *,
    expected_kind: str,
    expected_image_ref: str | None = None,
    expected_archive_sha256: str | None = None,
) -> ImageRecoveryRecord:
    if expected_kind not in ARTIFACT_KINDS:
        raise UpdaterV2Error("image_recovery_expected_kind_invalid")
    if record.kind != expected_kind:
        raise UpdaterV2Error("image_recovery_kind_mismatch")
    if (
        not isinstance(record.image_ref, str)
        or not record.image_ref.startswith("local/n3w-homeassistant:")
        or record.platform != "linux/arm64"
        or not isinstance(record.archive_sha256, str)
        or SHA256.fullmatch(record.archive_sha256) is None
        or not isinstance(record.portable_identity_sha256, str)
        or SHA256.fullmatch(record.portable_identity_sha256) is None
        or not isinstance(record.archive_size_bytes, int)
        or isinstance(record.archive_size_bytes, bool)
        or record.archive_size_bytes <= 0
    ):
        raise UpdaterV2Error("image_recovery_identity_invalid")
    if expected_image_ref is not None and record.image_ref != expected_image_ref:
        raise UpdaterV2Error("image_recovery_image_ref_mismatch")
    if (
        expected_archive_sha256 is not None
        and record.archive_sha256 != expected_archive_sha256
    ):
        raise UpdaterV2Error("image_recovery_archive_sha256_mismatch")
    if record.verified is not True or record.fsynced is not True:
        raise UpdaterV2Error("image_recovery_not_durable_verified")
    return record
