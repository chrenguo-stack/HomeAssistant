"""Stage D D4 automatic U13B reconciliation orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from n3w_t1_core_updater_ha_u13b import U13BRollbackResult
from n3w_t1_core_updater_ha_u13b_reconcile import (
    ALREADY_EXACT,
    RECONCILED,
    U13BHostOnlyReconciliationResult,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error


class U13BReconciliationWriter(Protocol):
    transaction_store: object
    backend: object
    def reconcile(self) -> U13BHostOnlyReconciliationResult: ...


class U13BRollbackController(Protocol):
    transaction_store: object
    backend: object
    def rollback(self, *, failure_code: str) -> U13BRollbackResult: ...


@dataclass(frozen=True, slots=True)
class U13BAutomaticRollbackResult:
    reconciliation: U13BHostOnlyReconciliationResult
    rollback: U13BRollbackResult


class U13BAutomaticRollbackCoordinator:
    """Reconcile durable split first, then enter the normal rollback controller.

    The two components intentionally acquire the shared transaction lock
    separately. D3 must release its strict RO USB mount before the normal
    rollback controller resolves the same media for writable transaction
    persistence. The normal controller then rereads/reclassifies state under
    its own lock, so no reconciliation result is treated as stale authority.
    """

    def __init__(
        self,
        *,
        reconciliation_writer: U13BReconciliationWriter,
        rollback_controller: U13BRollbackController,
    ) -> None:
        if (
            reconciliation_writer.transaction_store
            is not rollback_controller.transaction_store
        ):
            raise UpdaterV2Error(
                "u13b_automatic_transaction_store_binding_invalid"
            )
        if reconciliation_writer.backend is not rollback_controller.backend:
            raise UpdaterV2Error(
                "u13b_automatic_backend_binding_invalid"
            )
        self.reconciliation_writer = reconciliation_writer
        self.rollback_controller = rollback_controller

    def rollback(self, *, failure_code: str) -> U13BAutomaticRollbackResult:
        reconciliation = self.reconciliation_writer.reconcile()
        if reconciliation.status not in {ALREADY_EXACT, RECONCILED}:
            raise UpdaterV2Error(
                "u13b_automatic_reconciliation_result_invalid"
            )
        rollback = self.rollback_controller.rollback(
            failure_code=failure_code
        )
        return U13BAutomaticRollbackResult(
            reconciliation=reconciliation,
            rollback=rollback,
        )
