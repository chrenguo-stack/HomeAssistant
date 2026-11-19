"""Automatic U13B orchestration and bounded U9+ restart recovery."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Protocol

from n3w_t1_core_updater_ha_u13b import U13BRollbackResult
from n3w_t1_core_updater_ha_u13b_reconcile import (
    ALREADY_EXACT,
    RECONCILED,
    U13BHostOnlyReconciliationResult,
)
from n3w_t1_core_updater_ha_usb_state import (
    U13A,
    U13B,
    U13B_ENTRY_PHASES,
    U13B_PROGRESS_PHASES,
    validate_transaction_document,
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


@dataclass(frozen=True, slots=True)
class U9PlusRecoveryCompletionEvidence:
    """Customer-visible recovery completion oracle.

    A restored container alone is never sufficient. Every field must be true
    before the product may expose ROLLED_BACK as complete.
    """

    predecessor_runtime_healthy: bool
    homeassistant_http_ready: bool
    manager_ready: bool
    broker_ready: bool
    fresh_greenhouse_telemetry_visible: bool
    preupgrade_history_readable: bool
    host_usb_terminal_exact: bool
    authorization_replay_absent: bool

    def validate(self) -> "U9PlusRecoveryCompletionEvidence":
        if any(
            value is not True
            for value in (
                self.predecessor_runtime_healthy,
                self.homeassistant_http_ready,
                self.manager_ready,
                self.broker_ready,
                self.fresh_greenhouse_telemetry_visible,
                self.preupgrade_history_readable,
                self.host_usb_terminal_exact,
                self.authorization_replay_absent,
            )
        ):
            raise UpdaterV2Error(
                "u9_plus_recovery_customer_oracle_incomplete"
            )
        return self


class U9PlusRecoveryStore(Protocol):
    def read(self) -> dict[str, Any] | None: ...


class U9PlusRecoveryCompletionOracle(Protocol):
    def verify(
        self,
        transaction: dict[str, Any],
        *,
        recovery_started_unix: int,
    ) -> U9PlusRecoveryCompletionEvidence: ...


_POSTCLAIM_RECOVERY_PHASES = frozenset(
    {*U13B_ENTRY_PHASES, *U13B_PROGRESS_PHASES, U13B}
)
_RECOVERY_MEDIA_CODES = frozenset(
    {
        "usb_transaction_media_unavailable",
        "usb_bound_media_unavailable",
        "usb_bound_device_identity_mismatch",
        "usb_filesystem_uuid_mismatch",
        "u13b_bound_media_uuid_drift",
        "u13b_reconciliation_usb_unavailable",
    }
)


class U9PlusBoundedRecoveryCoordinator:
    """Conservative boot/re-entry owner for an already-consumed U9 transaction.

    This coordinator never claims or replays authorization and never invents a
    replacement USB. On a restart in U9-U12 it deliberately chooses the legal
    rollback edge instead of guessing that an interrupted forward mutation
    completed. Already-started U13B is resumed through the same controller.
    """

    def __init__(
        self,
        *,
        transaction_store: U9PlusRecoveryStore,
        rollback_coordinator: U13BAutomaticRollbackCoordinator,
        completion_oracle: U9PlusRecoveryCompletionOracle,
        clock=time.time,
    ) -> None:
        if (
            rollback_coordinator.rollback_controller.transaction_store
            is not transaction_store
        ):
            raise UpdaterV2Error(
                "u9_plus_recovery_transaction_store_binding_invalid"
            )
        self.transaction_store = transaction_store
        self.rollback_coordinator = rollback_coordinator
        self.completion_oracle = completion_oracle
        self.clock = clock
        self._lock = threading.Lock()
        self._status: dict[str, object] = {
            "phase": "RECOVERY_PENDING",
            "error_code": None,
        }

    def _set_status(
        self,
        phase: str,
        *,
        error_code: str | None = None,
    ) -> dict[str, object]:
        value: dict[str, object] = {
            "phase": phase,
            "error_code": error_code,
        }
        with self._lock:
            self._status = value
        return dict(value)

    def public_status(self) -> dict[str, object]:
        with self._lock:
            return dict(self._status)

    def _read(self) -> dict[str, Any] | None:
        value = self.transaction_store.read()
        if value is None:
            return None
        return validate_transaction_document(value)

    @staticmethod
    def _require_consumed_authorization(
        transaction: dict[str, Any],
    ) -> None:
        if (
            transaction.get("authorization_claimed") is not True
            or transaction.get("authorization_consumed") is not True
        ):
            raise UpdaterV2Error(
                "u9_plus_recovery_authorization_not_consumed"
            )

    def recover_once(self) -> dict[str, object]:
        started = int(self.clock())
        current = self._read()
        if current is None:
            return self._set_status("RECOVERY_IDLE")

        phase = current["phase"]
        if phase == U13A:
            return self._set_status("COMMITTED")
        if phase not in _POSTCLAIM_RECOVERY_PHASES:
            return self._set_status("RECOVERY_IDLE")

        self._require_consumed_authorization(current)
        self._set_status("ROLLING_BACK")

        if phase != U13B:
            try:
                self.rollback_coordinator.rollback(
                    failure_code="u9_plus_restart_bounded_recovery"
                )
            except UpdaterV2Error as error:
                code = str(error)
                if code in _RECOVERY_MEDIA_CODES:
                    return self._set_status(
                        "RECOVERY_MEDIA_REQUIRED",
                        error_code=None,
                    )
                self._set_status("ERROR", error_code=code)
                raise

        terminal = self._read()
        if terminal is None or terminal["phase"] != U13B:
            self._set_status(
                "ERROR",
                error_code="u9_plus_recovery_terminal_missing",
            )
            raise UpdaterV2Error(
                "u9_plus_recovery_terminal_missing"
            )
        evidence = self.completion_oracle.verify(
            terminal,
            recovery_started_unix=started,
        ).validate()
        if evidence.authorization_replay_absent is not True:
            raise UpdaterV2Error(
                "u9_plus_recovery_authorization_replay_detected"
            )
        return self._set_status("ROLLED_BACK")
