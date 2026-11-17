"""Stage D D3 host-only reconciliation of exact USB-ahead U13B state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
from n3w_t1_core_updater_ha_u13b import (
    DIVERGENT_OR_UNKNOWN_STOP,
    HOST_ONE_PHASE_AHEAD_STOP,
    HOST_USB_EXACT,
    USB_ONE_PHASE_AHEAD_RECONCILABLE,
    U13BUsbMetadataSnapshot,
    classify_u13b_usb_host_split,
)
from n3w_t1_core_updater_ha_u13b_postcondition import (
    U13BReadOnlyObserver,
    verify_u13b_usb_ahead_postcondition_readonly,
)
from n3w_t1_core_updater_ha_usb_state import validate_transaction_document
from n3w_t1_core_updater_v2_common import UpdaterV2Error


RECONCILED = "RECONCILED"
ALREADY_EXACT = "ALREADY_EXACT"


class U13BReconciliationStore(Protocol):
    def lock(self): ...
    def read(self) -> dict[str, Any] | None: ...
    def write(self, document: dict[str, Any]) -> None: ...


class U13BReconciliationBackend(Protocol):
    def resolve_transaction_media_for_reconciliation(
        self, transaction: Mapping[str, Any]
    ) -> PreparedUsbMedia | None: ...
    def read_transaction_metadata(
        self,
        transaction: Mapping[str, Any],
        media: PreparedUsbMedia,
    ) -> U13BUsbMetadataSnapshot: ...


@dataclass(frozen=True, slots=True)
class U13BHostOnlyReconciliationResult:
    status: str
    transaction: dict[str, Any]
    previous_phase: str
    current_phase: str
    host_write_performed: bool


class U13BHostOnlyReconciliationWriter:
    """Repair Host state only; never replay rollback work or rewrite USB."""

    def __init__(
        self,
        *,
        transaction_store: U13BReconciliationStore,
        backend: U13BReconciliationBackend,
        observer: U13BReadOnlyObserver,
    ) -> None:
        self.transaction_store = transaction_store
        self.backend = backend
        self.observer = observer

    @staticmethod
    def _read_current(store: U13BReconciliationStore) -> dict[str, Any]:
        document = store.read()
        if document is None:
            raise UpdaterV2Error(
                "u13b_reconciliation_transaction_missing"
            )
        return validate_transaction_document(document)

    def reconcile(self) -> U13BHostOnlyReconciliationResult:
        with self.transaction_store.lock():
            current = self._read_current(self.transaction_store)
            previous_phase = current["phase"]
            media = self.backend.resolve_transaction_media_for_reconciliation(
                current
            )
            if media is None:
                raise UpdaterV2Error(
                    "u13b_reconciliation_usb_unavailable"
                )
            snapshot = self.backend.read_transaction_metadata(
                current, media
            )
            split = classify_u13b_usb_host_split(
                current, media, snapshot
            )

            if split.classification == HOST_USB_EXACT:
                mirrored = validate_transaction_document(
                    dict(snapshot.host_transaction)
                )
                if mirrored != current:
                    raise UpdaterV2Error(
                        "u13b_reconciliation_exact_mirror_drift"
                    )
                return U13BHostOnlyReconciliationResult(
                    ALREADY_EXACT,
                    current,
                    previous_phase,
                    current["phase"],
                    False,
                )
            if split.classification == HOST_ONE_PHASE_AHEAD_STOP:
                raise UpdaterV2Error(
                    "u13b_reconciliation_host_ahead_stop"
                )
            if split.classification != USB_ONE_PHASE_AHEAD_RECONCILABLE:
                if split.classification == DIVERGENT_OR_UNKNOWN_STOP:
                    raise UpdaterV2Error(
                        "u13b_reconciliation_divergent_stop"
                    )
                raise UpdaterV2Error(
                    "u13b_reconciliation_classification_invalid"
                )

            try:
                verify_u13b_usb_ahead_postcondition_readonly(
                    host_transaction=current,
                    media=media,
                    snapshot=snapshot,
                    observer=self.observer,
                )
            except UpdaterV2Error as error:
                raise UpdaterV2Error(
                    "u13b_reconciliation_postcondition_failed"
                ) from error

            # Re-read USB after the real-world observation. A removed or changed
            # device, transaction file, or phase marker must fail before Host write.
            confirmed_snapshot = self.backend.read_transaction_metadata(
                current, media
            )
            if confirmed_snapshot != snapshot:
                raise UpdaterV2Error(
                    "u13b_reconciliation_usb_snapshot_drift"
                )
            confirmed_split = classify_u13b_usb_host_split(
                current, media, confirmed_snapshot
            )
            if (
                confirmed_split.classification
                != USB_ONE_PHASE_AHEAD_RECONCILABLE
            ):
                raise UpdaterV2Error(
                    "u13b_reconciliation_usb_snapshot_drift"
                )

            successor = validate_transaction_document(
                dict(confirmed_snapshot.host_transaction)
            )

            # The shared directory flock serializes cooperating writers. Re-read
            # immediately before persistence to reject out-of-band state changes.
            guard = self._read_current(self.transaction_store)
            if guard != current:
                raise UpdaterV2Error(
                    "u13b_reconciliation_host_state_drift"
                )

            # D3's only durable mutation: exact USB mirror -> Host transaction.
            self.transaction_store.write(successor)

            try:
                persisted = self._read_current(self.transaction_store)
            except UpdaterV2Error as error:
                raise UpdaterV2Error(
                    "u13b_reconciliation_write_verify_failed"
                ) from error
            if persisted != successor:
                raise UpdaterV2Error(
                    "u13b_reconciliation_write_verify_failed"
                )
            post = classify_u13b_usb_host_split(
                persisted, media, confirmed_snapshot
            )
            if post.classification != HOST_USB_EXACT:
                raise UpdaterV2Error(
                    "u13b_reconciliation_postwrite_split_invalid"
                )
            return U13BHostOnlyReconciliationResult(
                RECONCILED,
                persisted,
                previous_phase,
                persisted["phase"],
                True,
            )
