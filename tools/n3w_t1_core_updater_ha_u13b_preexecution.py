"""Read-only preexecution admission for U13B automatic rollback.

This module classifies fresh Host/USB durable state and re-observes the
real-world state required by that durable phase. It never performs rollback
work and never persists Host or USB transaction metadata.
"""
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
from n3w_t1_core_updater_ha_usb_state import (
    U13B0,
    U13B1,
    U13B2,
    U13B3,
    U13B4,
    U13B,
    U13B_ENTRY_PHASES,
    U13B_PROGRESS_PHASES,
    validate_transaction_document,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error


U13B_READONLY_PREEXECUTION_PASS = "U13B_READONLY_PREEXECUTION_PASS"
ROLLBACK_ELIGIBLE = "ROLLBACK_ELIGIBLE"
HOST_RECONCILIATION_REQUIRED = "HOST_RECONCILIATION_REQUIRED"
ALREADY_ROLLED_BACK = "ALREADY_ROLLED_BACK"

_EXACT_PHASE_OBSERVERS = {
    U13B0: "observe_rollback_entry",
    U13B1: "observe_target_cleanup",
    U13B2: "observe_predecessor_image",
    U13B3: "observe_ha_data_restored",
    U13B4: "observe_predecessor_runtime",
    U13B: "observe_predecessor_health",
}


class U13BReadOnlyPreexecutionStore(Protocol):
    def lock(self) -> Any: ...
    def read(self) -> dict[str, Any] | None: ...


class U13BReadOnlyPreexecutionBackend(Protocol):
    def resolve_transaction_media_for_reconciliation(
        self, transaction: Mapping[str, Any]
    ) -> PreparedUsbMedia | None: ...

    def release_transaction_media_for_reconciliation(
        self, media: PreparedUsbMedia
    ) -> None: ...

    def read_transaction_metadata(
        self,
        transaction: Mapping[str, Any],
        media: PreparedUsbMedia,
    ) -> U13BUsbMetadataSnapshot: ...


@dataclass(frozen=True, slots=True)
class U13BReadOnlyPreexecutionResult:
    status: str
    action: str
    host_phase: str
    usb_phase: str
    effective_phase: str
    split_classification: str
    observed_recovery_assets: bool
    observed_postcondition: str
    reconciliation_required: bool
    rollback_execution_required: bool
    terminal_rolled_back: bool
    read_only: bool = True
    transaction_mutation: bool = False
    usb_mutation: bool = False
    service_mutation: bool = False
    image_mutation: bool = False
    rollback_operation_replay: bool = False


def _observe_true(
    observer: U13BReadOnlyObserver,
    method_name: str,
    *,
    transaction: Mapping[str, Any],
    media: PreparedUsbMedia,
) -> None:
    method = getattr(observer, method_name, None)
    if not callable(method):
        raise UpdaterV2Error("u13b_preexecution_observer_missing")
    if method(transaction=transaction, media=media) is not True:
        raise UpdaterV2Error("u13b_preexecution_observation_failed")


def _read_current(
    store: U13BReadOnlyPreexecutionStore,
) -> dict[str, Any]:
    document = store.read()
    if document is None:
        raise UpdaterV2Error("u13b_preexecution_transaction_missing")
    return validate_transaction_document(document)


class U13BReadOnlyPreexecutionInspector:
    """Fresh, fail-closed, read-only admission before any future live rollback."""

    def __init__(
        self,
        *,
        transaction_store: U13BReadOnlyPreexecutionStore,
        backend: U13BReadOnlyPreexecutionBackend,
        observer: U13BReadOnlyObserver,
    ) -> None:
        self.transaction_store = transaction_store
        self.backend = backend
        self.observer = observer

    def _observe_exact(
        self,
        *,
        transaction: Mapping[str, Any],
        media: PreparedUsbMedia,
    ) -> str:
        phase = transaction["phase"]
        _observe_true(
            self.observer,
            "observe_rollback_entry",
            transaction=transaction,
            media=media,
        )
        if phase in U13B_ENTRY_PHASES or phase == U13B0:
            return "observe_rollback_entry"
        method_name = _EXACT_PHASE_OBSERVERS.get(phase)
        if method_name is None:
            raise UpdaterV2Error("u13b_preexecution_exact_phase_invalid")
        _observe_true(
            self.observer,
            method_name,
            transaction=transaction,
            media=media,
        )
        return method_name

    def inspect(self) -> U13BReadOnlyPreexecutionResult:
        with self.transaction_store.lock():
            current = _read_current(self.transaction_store)
            media = self.backend.resolve_transaction_media_for_reconciliation(
                current
            )
            if media is None:
                raise UpdaterV2Error("u13b_preexecution_usb_unavailable")
            try:
                snapshot = self.backend.read_transaction_metadata(
                    current, media
                )
                split = classify_u13b_usb_host_split(
                    current, media, snapshot
                )

                if split.classification == HOST_USB_EXACT:
                    effective = current
                    observed = self._observe_exact(
                        transaction=effective,
                        media=media,
                    )
                    reconciliation_required = False
                elif split.classification == USB_ONE_PHASE_AHEAD_RECONCILABLE:
                    effective = validate_transaction_document(
                        dict(snapshot.host_transaction)
                    )
                    if split.usb_phase != U13B0:
                        _observe_true(
                            self.observer,
                            "observe_rollback_entry",
                            transaction=effective,
                            media=media,
                        )
                    postcondition = (
                        verify_u13b_usb_ahead_postcondition_readonly(
                            host_transaction=current,
                            media=media,
                            snapshot=snapshot,
                            observer=self.observer,
                        )
                    )
                    observed = postcondition.observed_postcondition
                    reconciliation_required = True
                elif split.classification == HOST_ONE_PHASE_AHEAD_STOP:
                    raise UpdaterV2Error(
                        "u13b_preexecution_host_ahead_stop"
                    )
                elif split.classification == DIVERGENT_OR_UNKNOWN_STOP:
                    raise UpdaterV2Error(
                        "u13b_preexecution_divergent_stop"
                    )
                else:
                    raise UpdaterV2Error(
                        "u13b_preexecution_split_classification_invalid"
                    )

                confirmed_current = _read_current(self.transaction_store)
                if confirmed_current != current:
                    raise UpdaterV2Error(
                        "u13b_preexecution_host_state_drift"
                    )
                confirmed_snapshot = self.backend.read_transaction_metadata(
                    confirmed_current, media
                )
                if confirmed_snapshot != snapshot:
                    raise UpdaterV2Error(
                        "u13b_preexecution_usb_snapshot_drift"
                    )
                confirmed_split = classify_u13b_usb_host_split(
                    confirmed_current,
                    media,
                    confirmed_snapshot,
                )
                if (
                    confirmed_split.classification != split.classification
                    or confirmed_split.host_phase != split.host_phase
                    or confirmed_split.usb_phase != split.usb_phase
                ):
                    raise UpdaterV2Error(
                        "u13b_preexecution_split_state_drift"
                    )

                effective_phase = effective["phase"]
                if effective_phase == U13B:
                    action = ALREADY_ROLLED_BACK
                    rollback_execution_required = False
                    terminal_rolled_back = True
                elif (
                    effective_phase in U13B_ENTRY_PHASES
                    or effective_phase in U13B_PROGRESS_PHASES
                ):
                    action = (
                        HOST_RECONCILIATION_REQUIRED
                        if reconciliation_required
                        else ROLLBACK_ELIGIBLE
                    )
                    rollback_execution_required = True
                    terminal_rolled_back = False
                else:
                    raise UpdaterV2Error(
                        "u13b_preexecution_effective_phase_invalid"
                    )

                return U13BReadOnlyPreexecutionResult(
                    status=U13B_READONLY_PREEXECUTION_PASS,
                    action=action,
                    host_phase=current["phase"],
                    usb_phase=split.usb_phase or current["phase"],
                    effective_phase=effective_phase,
                    split_classification=split.classification,
                    observed_recovery_assets=True,
                    observed_postcondition=observed,
                    reconciliation_required=reconciliation_required,
                    rollback_execution_required=rollback_execution_required,
                    terminal_rolled_back=terminal_rolled_back,
                )
            finally:
                self.backend.release_transaction_media_for_reconciliation(
                    media
                )
