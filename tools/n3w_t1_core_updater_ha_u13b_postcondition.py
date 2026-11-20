"""Read-only U13B split-write postcondition admission (no reconciliation write).

An exact USB-ahead successor is only a *candidate*. This module never executes
a rollback operation, writes host transaction state, or rewrites USB metadata.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Any

from n3w_t1_core_updater_ha_u13b import (
    USB_ONE_PHASE_AHEAD_RECONCILABLE,
    U13BSplitReconciliation,
    U13BUsbMetadataSnapshot,
    classify_u13b_usb_host_split,
)
from n3w_t1_core_updater_ha_usb_state import (
    U13B0, U13B1, U13B2, U13B3, U13B4, U13B,
    validate_transaction_document,
)
from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
from n3w_t1_core_updater_v2_common import UpdaterV2Error


class U13BReadOnlyObserver(Protocol):
    def observe_rollback_entry(
        self, *, transaction: Mapping[str, Any], media: PreparedUsbMedia
    ) -> bool: ...
    def observe_target_cleanup(
        self, *, transaction: Mapping[str, Any], media: PreparedUsbMedia
    ) -> bool: ...
    def observe_predecessor_image(
        self, *, transaction: Mapping[str, Any], media: PreparedUsbMedia
    ) -> bool: ...
    def observe_ha_data_restored(
        self, *, transaction: Mapping[str, Any], media: PreparedUsbMedia
    ) -> bool: ...
    def observe_predecessor_runtime(
        self, *, transaction: Mapping[str, Any], media: PreparedUsbMedia
    ) -> bool: ...
    def observe_predecessor_health(
        self, *, transaction: Mapping[str, Any], media: PreparedUsbMedia
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class U13BReadOnlyPostconditionResult:
    eligible_for_later_host_only_reconciliation: bool
    host_phase: str
    usb_phase: str
    observed_postcondition: str


_OBSERVERS = {
    U13B0: "observe_rollback_entry",
    U13B1: "observe_target_cleanup",
    U13B2: "observe_predecessor_image",
    U13B3: "observe_ha_data_restored",
    U13B4: "observe_predecessor_runtime",
    U13B: "observe_predecessor_health",
}


def verify_u13b_usb_ahead_postcondition_readonly(
    *,
    host_transaction: Mapping[str, Any],
    media: PreparedUsbMedia,
    snapshot: U13BUsbMetadataSnapshot,
    observer: U13BReadOnlyObserver,
) -> U13BReadOnlyPostconditionResult:
    """Return a read-only eligibility proof; never persist or replay.

    This is an *observer gate*, not authority to reconcile.  A later,
    separately reviewed host-only writer must revalidate the evidence and
    perform its own locked compare-and-swap.
    """
    host = validate_transaction_document(dict(host_transaction))
    split: U13BSplitReconciliation = classify_u13b_usb_host_split(
        host, media, snapshot
    )
    if split.classification != USB_ONE_PHASE_AHEAD_RECONCILABLE:
        raise UpdaterV2Error("u13b_postcondition_usb_ahead_required")
    successor = split.usb_phase
    method_name = _OBSERVERS.get(successor)
    if method_name is None:
        raise UpdaterV2Error("u13b_postcondition_successor_invalid")
    mirrored = validate_transaction_document(dict(snapshot.host_transaction))
    method = getattr(observer, method_name, None)
    if not callable(method):
        raise UpdaterV2Error("u13b_postcondition_observer_missing")
    # No boolean coercion: a returned evidence object/string/None is not PASS.
    if method(transaction=mirrored, media=media) is not True:
        raise UpdaterV2Error("u13b_postcondition_observation_failed")
    return U13BReadOnlyPostconditionResult(
        eligible_for_later_host_only_reconciliation=True,
        host_phase=host["phase"],
        usb_phase=successor,
        observed_postcondition=method_name,
    )
