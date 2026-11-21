from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, BinaryIO, Protocol

from n3w_t1_core_updater_ha_backup import (
    HaDataBackupProvider,
    HaDataBackupRecord,
    backup_record_from_document,
    validate_backup_record,
)
from n3w_t1_core_updater_ha_recovery import (
    ImageRecoveryRecord,
    validate_image_recovery_record,
)
from n3w_t1_core_updater_ha_usb_media import (
    USB_FILESYSTEM,
    USB_LABEL,
    FormatAuthorization,
    UsbCapacityReport,
    require_same_filesystem_uuid,
    validate_filesystem_uuid,
)
from n3w_t1_core_updater_ha_usb_state import (
    HA_DATA_RESTORE_PHASES,
    HA_USB_TERMINAL_STATUSES,
    PHASE_INDEX,
    PRE_CUTOVER_RECOVERY_PHASES,
    U0,
    U1,
    U2,
    U3,
    U4,
    U5,
    U6,
    U7,
    U8,
    U9,
    U10,
    U11,
    U12,
    U13A,
    U13B,
    HaUsbStateStore,
    transition,
    validate_transaction_document,
)
from n3w_t1_core_updater_v2_common import (
    AUTHORIZATION_ID,
    UpdaterV2Error,
    sha256_bytes,
)
from n3w_t1_portable_image_identity import PortableImageIdentity


class HaPredecessorRuntime(Protocol):
    def capture_start_binding(self, transaction: dict[str, Any]) -> dict[str, Any]:
        """Verify the running predecessor and bind its fixed local start configuration."""
        ...

    def quiesce_for_backup(self) -> None:
        """Stop application writers and verify they are quiescent."""
        ...

    def start_predecessor_if_needed(self, binding: dict[str, Any]) -> None:
        """Check the binding against the host, then start only missing services."""
        ...

    def rollback_writers_quiesced(self) -> bool:
        ...

    def capture_predecessor_release(self, document: dict[str, Any]) -> HaPredecessorRelease:
        ...

    def release_exact_predecessor(self, document: dict[str, Any]) -> None:
        ...

    def observe_predecessor_released(self, document: dict[str, Any]) -> bool:
        ...

    def verify_resident_predecessor_health(self, document: dict[str, Any]) -> None:
        ...

    def verify_untouched_release_launch(self, document: dict[str, Any]) -> None:
        ...

    def ensure_rollback_predecessor(
        self, document: dict[str, Any], original_media: Callable[[], HaDataRestoreProvider],
        record_load_intent: Callable[[PortableImageIdentity], None],
    ) -> None:
        ...

    def load_cutover_target(
        self, document: dict[str, Any], media: HaDataRestoreProvider,
        record_load_intent: Callable[[PortableImageIdentity], None],
    ) -> str:
        ...


class HaPredecessorHealth(Protocol):
    def verify_predecessor_health(self, binding: dict[str, Any]) -> None:
        """Verify the old combination and its affected functions have recovered."""
        ...


class HaPublishedRollbackRuntime(Protocol):
    def quiesce_for_data_restore(self, document: dict[str, Any]) -> None:
        ...

    def resume_published_predecessor(self, document: dict[str, Any]) -> None:
        ...

    def ensure_rollback_predecessor(
        self, document: dict[str, Any], original_media: Callable[[], HaDataRestoreProvider],
        record_load_intent: Callable[[PortableImageIdentity], None],
    ) -> None:
        ...

    def verify_published_predecessor_health(self, document: dict[str, Any]) -> None:
        ...


class HaDataRestoreProvider(Protocol):
    def restore_preupgrade_data(self) -> None:
        ...

    def load_predecessor_image(
        self, load: Callable[[BinaryIO, PortableImageIdentity], None],
    ) -> PortableImageIdentity:
        ...

    def load_target_image(
        self, load: Callable[[BinaryIO, PortableImageIdentity], None],
    ) -> PortableImageIdentity:
        ...


@dataclass(frozen=True, slots=True)
class HaPredecessorRelease:
    container_id: str | None


@dataclass(frozen=True, slots=True)
class HaInternalSpace:
    available_bytes: int
    install_required_bytes: int
    recovery_required_bytes: int


@dataclass(frozen=True, slots=True)
class HaInstallMaterials:
    filesystem_uuid: str
    target: ImageRecoveryRecord
    predecessor: ImageRecoveryRecord
    capacity: UsbCapacityReport
    production_prestate_exact: bool
    internal_space: HaInternalSpace | None = None


class HaInstallMaterialVerifier(Protocol):
    def verify_install_materials(self, transaction: dict[str, Any]) -> HaInstallMaterials:
        """Reopen the original storage and revalidate the local recovery materials."""
        ...


class HaPredecessorRecovery:
    """Host recovery point for interruptions before destructive HA cutover."""

    def __init__(
        self,
        store: HaUsbStateStore,
        runtime: HaPredecessorRuntime,
        health: HaPredecessorHealth,
    ):
        self.store = store
        self.runtime = runtime
        self.health = health
        self._install_transaction_id: str | None = None

    @contextmanager
    def install_recovery_point(
        self,
        materials: HaInstallMaterialVerifier,
        backups: HaDataBackupProvider,
    ) -> Iterator[dict[str, Any]]:
        """Consume a persisted install request and hold ownership through handoff."""
        with self.store.lock():
            current = self.store.read()
            if (
                current is None
                or current["status"] != "ACTIVE"
                or current["phase"] not in {U5, U6}
                or "predecessor_start" in current
                or current["recovery_required"]
            ):
                raise UpdaterV2Error("ha_usb_install_worker_not_admitted")

            try:
                before = materials.verify_install_materials(current)
                _validate_install_materials(current, before)
                if current["phase"] == U5:
                    current = start_predecessor_recovery(current)
                    self.store.write(current)
            except UpdaterV2Error:
                self.store.write(transition(
                    current, U4, updates={"failure_code": "ha_usb_install_revalidation_failed"}
                ))
                raise

            with self._quiesced_for_backup(before.predecessor) as stopped:
                backup = backups.create_consistent_backup(
                    transaction_id_sha256=stopped["transaction_id_sha256"],
                )
                verified_backup = backups.verify_backup(backup)
                if verified_backup != backup:
                    raise UpdaterV2Error("ha_usb_install_backup_identity_drift")
                after = materials.verify_install_materials(stopped)
                _validate_install_materials(stopped, after)
                if (after.target, after.predecessor) != (before.target, before.predecessor):
                    raise UpdaterV2Error("ha_usb_install_recovery_material_identity_drift")
                ready = record_recovery_admission(
                    stopped,
                    target=after.target,
                    predecessor=after.predecessor,
                    backup=verified_backup,
                    observed_usb_filesystem_uuid=after.filesystem_uuid,
                    capacity_report=after.capacity,
                    production_prestate_exact=after.production_prestate_exact,
                )
                self.store.write(ready)
                self._install_transaction_id = ready["transaction_id_sha256"]
                try:
                    yield ready
                finally:
                    self._install_transaction_id = None
                latest = self.store.read()
                if latest is None or _can_resume_pre_cutover(latest):
                    raise UpdaterV2Error("ha_usb_install_cutover_not_consumed")

    def admit_predecessor_release(
        self, materials: HaInstallMaterialVerifier, backups: HaDataBackupProvider, authorization_id: str,
        *, release_intent: HaPredecessorRelease | None = None,
    ) -> dict[str, Any]:
        """Claim release while install_recovery_point still owns the transaction lock.

        A resumed worker must reconcile the actual image state; this snapshot is
        not a fresh observation after interruption.
        """
        current = self.store.read()
        if (
            current is None or current["phase"] != U8 or not _can_resume_pre_cutover(current)
            or current["transaction_id_sha256"] != self._install_transaction_id
            or current["recovery_required"] or current.get("usb_binding_mode") != "existing_filesystem"
        ):
            raise UpdaterV2Error("ha_usb_predecessor_release_revalidation_not_admitted")
        if not self.runtime.rollback_writers_quiesced():
            raise UpdaterV2Error("ha_usb_predecessor_release_writers_active")
        backup = backup_record_from_document(current["install_recovery_materials"]["backup"])
        if backups.verify_backup(backup) != backup:
            raise UpdaterV2Error("ha_usb_install_backup_identity_drift")
        proof = materials.verify_install_materials(current)
        _validate_install_materials(current, proof)
        frozen = current["install_recovery_materials"]
        if (proof.target.public(), proof.predecessor.public()) != (frozen["target"], frozen["predecessor"]):
            raise UpdaterV2Error("ha_usb_install_recovery_material_identity_drift")
        if self.store.read() != current or not self.runtime.rollback_writers_quiesced():
            raise UpdaterV2Error("ha_usb_predecessor_release_revalidation_changed")
        claimed = claim_live_authorization(
            current, authorization_id, internal_space=proof.internal_space, release_intent=release_intent,
        )
        self.store.write(claimed)
        return claimed

    def release_predecessor_image(
        self, materials: HaInstallMaterialVerifier, backups: HaDataBackupProvider, authorization_id: str,
    ) -> dict[str, Any]:
        """Release the bound image once, inside the locked install recovery point."""
        ready = self.store.read()
        if ready is None or ready["phase"] != U8 or ready["transaction_id_sha256"] != self._install_transaction_id:
            raise UpdaterV2Error("ha_usb_predecessor_release_revalidation_not_admitted")
        intent = self.runtime.capture_predecessor_release(ready)
        claimed = self.admit_predecessor_release(materials, backups, authorization_id, release_intent=intent)
        try:
            self.runtime.release_exact_predecessor(claimed)
            if not self.runtime.observe_predecessor_released(claimed):
                raise UpdaterV2Error("ha_usb_predecessor_release_not_observed")
            released = record_predecessor_capacity_released(claimed, image_release_observed=True)
            self.store.write(released)
            return released
        except Exception as error:
            try:
                _reconcile_predecessor_release(self.store, self.runtime)
            except Exception as recovery_error:
                raise error from recovery_error
            raise

    def load_target_after_release(self, media: HaDataRestoreProvider) -> dict[str, Any]:
        """Import the authorized target, still under the locked install recovery point."""
        current = self.store.read()
        if (
            current is None or current["phase"] != U10 or not destructive_cutover_allowed(current)
            or current["transaction_id_sha256"] != self._install_transaction_id
            or current.get("predecessor_release_observed") is not True or "target_load_identity" in current
        ):
            raise UpdaterV2Error("ha_usb_target_image_load_not_admitted")

        def record_load_intent(identity: PortableImageIdentity) -> None:
            nonlocal current
            current = _record_image_load(self.store, current, "target_load_identity", identity)

        try:
            loaded_id = self.runtime.load_cutover_target(current, media, record_load_intent)
            imported = {**current, "target_loaded_image_id": loaded_id}
            self.store.write(imported)
            return imported
        except Exception as error:
            try:
                _reconcile_predecessor_release(self.store, self.runtime, lambda _: media)
            except Exception as recovery_error:
                raise error from recovery_error
            raise

    @contextmanager
    def quiesced_for_backup(
        self, predecessor: ImageRecoveryRecord
    ) -> Iterator[dict[str, Any]]:
        """Keep the shared execution lock held while the caller backs up data."""
        with self.store.lock():
            with self._quiesced_for_backup(predecessor) as current:
                yield current

    @contextmanager
    def _quiesced_for_backup(
        self, predecessor: ImageRecoveryRecord
    ) -> Iterator[dict[str, Any]]:
        current = self.store.read()
        if (
            current is None
            or current["phase"] != U6
            or current["status"] != "ACTIVE"
            or "predecessor_start" in current
            or current["recovery_required"]
        ):
            raise UpdaterV2Error("ha_usb_first_stop_not_admitted")
        validate_image_recovery_record(
            predecessor,
            expected_kind="predecessor",
            expected_image_ref=current["current_image_ref"],
        )
        source_identity = current["current_image_identity"].get(
            "portable_identity_sha256"
        )
        if (
            source_identity is not None
            and predecessor.portable_identity_sha256 != source_identity
        ):
            raise UpdaterV2Error("ha_usb_predecessor_archive_identity_drift")

        binding = self.runtime.capture_start_binding(current)
        current = validate_transaction_document(
            {
                **current,
                "predecessor_start": binding,
                "updated_at_unix": max(current["updated_at_unix"], int(time.time())),
            }
        )
        self.store.write(current)
        try:
            self.runtime.quiesce_for_backup()
            result = record_predecessor_recovery_and_ha_quiesced(
                current,
                predecessor=predecessor,
                ha_quiesced=True,
            )
            self.store.write(result)
            yield result
        except Exception:
            latest = self.store.read()
            if latest is not None and _can_resume_pre_cutover(latest):
                self._restore(latest)
            raise

    def recover(self) -> bool:
        """Re-enter after an interruption, independently of USB and IPC."""
        with self.store.lock():
            current = self.store.read()
            if current is None or not _can_resume_pre_cutover(current):
                return False
            self._restore(current)
            return True

    def _restore(self, current: dict[str, Any]) -> None:
        current = _start_pre_cutover_predecessor(self.store, self.runtime, current)
        self.health.verify_predecessor_health(current["predecessor_start"])
        self.store.write(
            {
                **current,
                "status": "ROLLED_BACK",
                "recovery_required": False,
                "pre_cutover_predecessor_restored": True,
                "failure_code": "ha_usb_pre_cutover_interrupted",
                "updated_at_unix": max(current["updated_at_unix"], int(time.time())),
            }
        )


def _can_resume_pre_cutover(document: dict[str, Any]) -> bool:
    return (
        document["phase"] in PRE_CUTOVER_RECOVERY_PHASES
        and document["status"] not in HA_USB_TERMINAL_STATUSES
        and "predecessor_start" in document
    )


def _validate_install_materials(document: dict[str, Any], proof: HaInstallMaterials) -> None:
    require_same_filesystem_uuid(document["usb_filesystem_uuid"], proof.filesystem_uuid)
    validate_image_recovery_record(
        proof.target,
        expected_kind="target",
        expected_image_ref=document["target_image_ref"],
        expected_archive_sha256=document["target_archive_sha256"],
    )
    validate_image_recovery_record(
        proof.predecessor,
        expected_kind="predecessor",
        expected_image_ref=document["current_image_ref"],
    )
    if proof.target.archive_size_bytes != document["target_archive_size"]:
        raise UpdaterV2Error("ha_usb_install_target_size_drift")
    if (
        proof.capacity.capacity_pass is not True
        or proof.capacity.measured_usable_bytes != document["usb_measured_usable_bytes"]
        or proof.production_prestate_exact is not True
    ):
        raise UpdaterV2Error("ha_usb_install_materials_unavailable")


def resume_pre_cutover_services(
    store: HaUsbStateStore, runtime: HaPredecessorRuntime
) -> bool:
    """Boot recovery starts the previous services before health verification."""
    with store.lock():
        current = store.read()
        if current is None or not _can_resume_pre_cutover(current):
            return False
        _start_pre_cutover_predecessor(store, runtime, current)
        return True


def resume_interrupted_predecessor_release(
    store: HaUsbStateStore, runtime: HaPredecessorRuntime,
    original_media: Callable[[dict[str, Any]], HaDataRestoreProvider] | None = None,
) -> str | None:
    """Reconcile an interrupted release without replaying destructive actions."""
    with store.lock():
        return _reconcile_predecessor_release(store, runtime, original_media)


def _record_image_load(
    store: HaUsbStateStore, current: dict[str, Any], key: str, identity: PortableImageIdentity,
) -> dict[str, Any]:
    value = identity.to_dict()
    if key in current:
        if current[key] != value:
            raise UpdaterV2Error("ha_usb_image_load_intent_drift")
        return current
    updated = {**current, key: value}
    store.write(updated)
    return updated


def _reconcile_predecessor_release(
    store: HaUsbStateStore, runtime: HaPredecessorRuntime,
    original_media: Callable[[dict[str, Any]], HaDataRestoreProvider] | None = None,
) -> str | None:
    current = store.read()
    if (
        current is None or current["phase"] not in {U9, U10}
        or "predecessor_release_intent" not in current or "ha_data_restore" in current
    ):
        return None
    if current["status"] != "ACTIVE":
        raise UpdaterV2Error("ha_usb_predecessor_release_status_unresolved")
    released = runtime.observe_predecessor_released(current)
    if released and current["phase"] == U9:
        current = record_predecessor_capacity_released(current, image_release_observed=True)
    if not current["recovery_required"]:
        current = {**current, "recovery_required": True}
        store.write(current)
    if released and original_media is None:
        return "PREDECESSOR_RELEASED_RECOVERY_PENDING"

    runtime.verify_untouched_release_launch(current)
    if original_media is not None:
        def record_reload_intent(identity: PortableImageIdentity) -> None:
            nonlocal current
            current = _record_image_load(store, current, "predecessor_reload_identity", identity)

        runtime.ensure_rollback_predecessor(current, lambda: original_media(current), record_reload_intent)
    runtime.start_predecessor_if_needed(current["predecessor_start"])
    runtime.verify_resident_predecessor_health(current)
    store.write(transition(current, U13B))
    return "ROLLED_BACK"


def resume_ha_data_rollback(
    store: HaUsbStateStore,
    runtime: HaPublishedRollbackRuntime,
    restore_provider: Callable[[dict[str, Any]], HaDataRestoreProvider],
    image_provider: Callable[[dict[str, Any]], HaDataRestoreProvider],
) -> bool:
    """Resume an already selected data rollback, including boot reentry."""
    with store.lock():
        current = store.read()
        if (
            current is None or current["phase"] not in HA_DATA_RESTORE_PHASES
            or "ha_data_restore" not in current
        ):
            return False
        if current["status"] != "ACTIVE":
            raise UpdaterV2Error("ha_usb_data_restore_status_unresolved")
        if current["ha_data_restore"]["step"] != "PUBLISHED":
            runtime.quiesce_for_data_restore(current)
            restore_provider(current).restore_preupgrade_data()
            published = store.read()
            if (
                published is None or published["transaction_id_sha256"] != current["transaction_id_sha256"]
                or published.get("ha_data_restore", {}).get("step") != "PUBLISHED"
            ):
                raise UpdaterV2Error("ha_usb_data_restore_publication_not_recorded")
            current = published
        def record_load_intent(identity: PortableImageIdentity) -> None:
            nonlocal current
            value = identity.to_dict()
            journal = current["ha_data_restore"]
            existing = journal.get("predecessor_load_identity")
            if existing is not None:
                if existing != value:
                    raise UpdaterV2Error("ha_usb_rollback_predecessor_load_intent_drift")
                return
            current = {**current, "ha_data_restore": {**journal, "predecessor_load_identity": value}}
            store.write(current)

        runtime.ensure_rollback_predecessor(current, lambda: image_provider(current), record_load_intent)
        runtime.resume_published_predecessor(current)
        runtime.verify_published_predecessor_health(current)
        store.write(transition(current, U13B))
        return True


def _start_pre_cutover_predecessor(
    store: HaUsbStateStore,
    runtime: HaPredecessorRuntime,
    current: dict[str, Any],
) -> dict[str, Any]:
    """Resume services under the caller's lock and leave verification pending."""
    if not current["recovery_required"]:
        current = {**current, "recovery_required": True}
        store.write(current)
    runtime.start_predecessor_if_needed(current["predecessor_start"])
    return current



def request_prepare(document: dict[str, Any]) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U0:
        raise UpdaterV2Error("ha_usb_prepare_phase_invalid")
    return transition(current, U1)


def record_media_bound(
    document: dict[str, Any],
    *,
    format_authorization: FormatAuthorization,
    filesystem_uuid: str,
    measured_usable_bytes: int,
    capacity_report: UsbCapacityReport,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U1:
        raise UpdaterV2Error("ha_usb_media_bind_phase_invalid")
    if (
        format_authorization.confirmation_verified is not True
        or format_authorization.filesystem != USB_FILESYSTEM
        or format_authorization.label != USB_LABEL
        or format_authorization.public_fingerprint is None
    ):
        raise UpdaterV2Error("ha_usb_format_authorization_invalid")
    if capacity_report.capacity_pass is not True:
        raise UpdaterV2Error("ha_usb_capacity_not_verified")
    if capacity_report.measured_usable_bytes != measured_usable_bytes:
        raise UpdaterV2Error("ha_usb_measured_capacity_drift")
    return transition(
        current,
        U2,
        updates={
            "usb_device_identity_public_fingerprint": (
                format_authorization.public_fingerprint
            ),
            "usb_filesystem_uuid": filesystem_uuid,
            "usb_measured_usable_bytes": measured_usable_bytes,
            "usb_mount_authority": f"filesystem_uuid:{filesystem_uuid}",
            "usb_capacity_verified": True,
        },
    )


def record_existing_media_bound(
    document: dict[str, Any], *, filesystem_uuid: str, capacity_report: UsbCapacityReport
) -> dict[str, Any]:
    """Bind a qualified existing filesystem without requesting an erase."""
    current = validate_transaction_document(document)
    if current["phase"] != U1:
        raise UpdaterV2Error("ha_usb_media_bind_phase_invalid")
    if capacity_report.capacity_pass is not True:
        raise UpdaterV2Error("ha_usb_capacity_not_verified")
    filesystem_uuid = validate_filesystem_uuid(filesystem_uuid)
    return transition(current, U2, updates={
        "usb_binding_mode": "existing_filesystem",
        "usb_device_identity_public_fingerprint": sha256_bytes(
            (filesystem_uuid + ":" + current["transaction_id_sha256"]).encode()
        ),
        "usb_filesystem_uuid": filesystem_uuid,
        "usb_measured_usable_bytes": capacity_report.measured_usable_bytes,
        "usb_mount_authority": f"filesystem_uuid:{filesystem_uuid}",
        "usb_capacity_verified": True,
    })


def start_target_preparation(document: dict[str, Any]) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U2:
        raise UpdaterV2Error("ha_usb_target_prepare_phase_invalid")
    return transition(current, U3)


def record_target_ready(
    document: dict[str, Any],
    *,
    target: ImageRecoveryRecord,
    predecessor: ImageRecoveryRecord | None = None,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U3:
        raise UpdaterV2Error("ha_usb_target_ready_phase_invalid")
    validate_image_recovery_record(
        target,
        expected_kind="target",
        expected_image_ref=current["target_image_ref"],
        expected_archive_sha256=current["target_archive_sha256"],
    )
    updates: dict[str, Any] = {"target_artifact_verified": True}
    if current.get("usb_binding_mode") == "existing_filesystem":
        if predecessor is None:
            raise UpdaterV2Error("ha_usb_prepared_predecessor_missing")
        updates["prepared_image_materials"] = {
            "target": target.public(), "predecessor": predecessor.public(),
        }
    return transition(current, U4, updates=updates)


def start_predecessor_recovery(document: dict[str, Any]) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U5:
        raise UpdaterV2Error("ha_usb_predecessor_prepare_phase_invalid")
    return transition(current, U6)


def record_predecessor_recovery_and_ha_quiesced(
    document: dict[str, Any],
    *,
    predecessor: ImageRecoveryRecord,
    ha_quiesced: bool,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U6:
        raise UpdaterV2Error("ha_usb_predecessor_ready_phase_invalid")
    validate_image_recovery_record(
        predecessor,
        expected_kind="predecessor",
        expected_image_ref=current["current_image_ref"],
    )
    if ha_quiesced is not True:
        raise UpdaterV2Error("ha_usb_ha_not_quiesced")
    return transition(
        current,
        U7,
        updates={"predecessor_recovery_verified": True},
    )


def record_predecessor_capacity_released(
    document: dict[str, Any],
    *, image_release_observed: bool = False,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U9 or not destructive_cutover_allowed(current):
        raise UpdaterV2Error("ha_usb_predecessor_release_not_allowed")
    if "predecessor_release_intent" in current:
        if image_release_observed is not True:
            raise UpdaterV2Error("ha_usb_predecessor_release_not_observed")
        return transition(current, U10, updates={"predecessor_release_observed": True})
    return transition(current, U10)


def record_target_started(document: dict[str, Any]) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U10 or not destructive_cutover_allowed(current):
        raise UpdaterV2Error("ha_usb_target_start_not_allowed")
    return transition(current, U11)


def record_target_accepted(document: dict[str, Any]) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U11 or not destructive_cutover_allowed(current):
        raise UpdaterV2Error("ha_usb_target_accept_not_allowed")
    return transition(current, U12)


def record_commit(document: dict[str, Any]) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U12 or not destructive_cutover_allowed(current):
        raise UpdaterV2Error("ha_usb_commit_not_allowed")
    return transition(current, U13A)


def record_rollback_complete(
    document: dict[str, Any],
    *,
    observed_usb_filesystem_uuid: str,
    predecessor_image_restored: bool,
    ha_data_backup_restored: bool,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] not in {U9, U10, U11, U12}:
        raise UpdaterV2Error("ha_usb_rollback_phase_invalid")
    require_same_filesystem_uuid(
        current["usb_filesystem_uuid"],
        observed_usb_filesystem_uuid,
    )
    if predecessor_image_restored is not True:
        raise UpdaterV2Error("ha_usb_rollback_predecessor_not_restored")
    if ha_data_backup_restored is not True:
        raise UpdaterV2Error("ha_usb_rollback_data_not_restored")
    return transition(current, U13B)


def classify_power_loss_reentry(
    document: dict[str, Any],
    *,
    usb_present: bool,
    observed_usb_filesystem_uuid: str | None,
) -> str:
    current = validate_transaction_document(document)
    if current["status"] in HA_USB_TERMINAL_STATUSES:
        return "TERMINAL"

    if (
        current["phase"] in PRE_CUTOVER_RECOVERY_PHASES
        and "predecessor_start" in current
    ):
        return "RESTORE_PREDECESSOR_BEFORE_CUTOVER"

    if PHASE_INDEX[current["phase"]] < PHASE_INDEX[U9]:
        return "PRE_U9_PREDECESSOR_AUTHORITY"

    if usb_present is not True:
        return "RECOVERY_MEDIA_REQUIRED"
    if observed_usb_filesystem_uuid is None:
        raise UpdaterV2Error("ha_usb_recovery_uuid_missing")
    require_same_filesystem_uuid(
        current["usb_filesystem_uuid"],
        observed_usb_filesystem_uuid,
    )
    if current["phase"] == U12:
        return "FORWARD_COMMIT_ELIGIBLE"
    return "ROLLBACK_REQUIRED"


def request_install(document: dict[str, Any]) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U4:
        raise UpdaterV2Error("ha_usb_not_ready_to_install")
    result = transition(current, U5, updates={"failure_code": None})
    if (
        result["authorization_claimed"] is not False
        or result["authorization_consumed"] is not False
        or result["authorization_id_sha256"] is not None
    ):
        raise UpdaterV2Error("ha_usb_install_intent_consumed_authorization")
    return result


def record_recovery_admission(
    document: dict[str, Any],
    *,
    target: ImageRecoveryRecord,
    predecessor: ImageRecoveryRecord,
    backup: HaDataBackupRecord,
    observed_usb_filesystem_uuid: str,
    capacity_report: UsbCapacityReport,
    production_prestate_exact: bool,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U7:
        raise UpdaterV2Error("ha_usb_recovery_admission_phase_invalid")
    require_same_filesystem_uuid(
        current["usb_filesystem_uuid"],
        observed_usb_filesystem_uuid,
    )
    if capacity_report.capacity_pass is not True:
        raise UpdaterV2Error("ha_usb_capacity_not_verified")
    if (
        capacity_report.measured_usable_bytes
        != current["usb_measured_usable_bytes"]
    ):
        raise UpdaterV2Error("ha_usb_measured_capacity_drift")
    if production_prestate_exact is not True:
        raise UpdaterV2Error("ha_usb_production_prestate_drift")

    validate_image_recovery_record(
        target,
        expected_kind="target",
        expected_image_ref=current["target_image_ref"],
        expected_archive_sha256=current["target_archive_sha256"],
    )
    validate_image_recovery_record(
        predecessor,
        expected_kind="predecessor",
        expected_image_ref=current["current_image_ref"],
    )
    validate_backup_record(backup)

    if current["target_artifact_verified"] is not True:
        raise UpdaterV2Error("ha_usb_target_not_verified")

    updates: dict[str, Any] = {
        "predecessor_recovery_verified": True,
        "ha_data_backup_verified": True,
        "production_prestate_verified": True,
        "usb_capacity_verified": True,
    }
    if "predecessor_start" in current:
        updates["install_recovery_materials"] = {
            "target": target.public(), "predecessor": predecessor.public(),
            "backup": backup.public(),
        }
    return transition(current, U8, updates=updates)


def claim_live_authorization(
    document: dict[str, Any],
    authorization_id: str,
    *, internal_space: HaInternalSpace | None = None,
    release_intent: HaPredecessorRelease | None = None,
) -> dict[str, Any]:
    current = validate_transaction_document(document)
    if current["phase"] != U8:
        raise UpdaterV2Error("ha_usb_live_authorization_phase_invalid")
    if (
        current["authorization_claimed"] is not False
        or current["authorization_consumed"] is not False
        or current["authorization_id_sha256"] is not None
    ):
        raise UpdaterV2Error("ha_usb_live_authorization_already_claimed")
    if (
        not isinstance(authorization_id, str)
        or AUTHORIZATION_ID.fullmatch(authorization_id) is None
    ):
        raise UpdaterV2Error("ha_usb_live_authorization_id_invalid")

    release_admission = {}
    if current.get("usb_binding_mode") == "existing_filesystem":
        if internal_space is None:
            raise UpdaterV2Error("ha_usb_predecessor_release_admission_missing")
        if internal_space.available_bytes < internal_space.install_required_bytes + internal_space.recovery_required_bytes:
            raise UpdaterV2Error("ha_usb_predecessor_release_recovery_reserve_insufficient")
        release_admission["predecessor_release_admission"] = {
            "internal_available_bytes": internal_space.available_bytes,
            "install_required_bytes": internal_space.install_required_bytes,
            "recovery_required_bytes": internal_space.recovery_required_bytes,
        }
        if release_intent is not None:
            release_admission["predecessor_release_intent"] = {"container_id": release_intent.container_id}
    return transition(
        current,
        U9,
        updates={
            "authorization_id_sha256": sha256_bytes(
                authorization_id.encode("utf-8")
            ),
            "authorization_claimed": True,
            "authorization_consumed": True,
            **release_admission,
        },
    )


def destructive_cutover_allowed(document: dict[str, Any]) -> bool:
    """Check persisted phase prerequisites, separate from current runtime evidence."""
    current = validate_transaction_document(document)
    return (
        current["status"] == "ACTIVE"
        and current["phase"] in {U9, U10, U11, U12}
        and (current["phase"] != U9 or current.get("usb_binding_mode") != "existing_filesystem"
             or "predecessor_release_admission" in current)
        and current["recovery_required"] is False
        and current["authorization_claimed"] is True
        and current["authorization_consumed"] is True
        and current["target_artifact_verified"] is True
        and current["predecessor_recovery_verified"] is True
        and current["ha_data_backup_verified"] is True
        and current["production_prestate_verified"] is True
        and current["usb_capacity_verified"] is True
    )
