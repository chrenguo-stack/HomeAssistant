from __future__ import annotations

import hashlib
import threading
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from .credential_lifecycle import (
    CredentialLifecycleConflict,
    CredentialLifecycleStore,
    CredentialState,
)
from .dynsec_api import DynsecError, DynsecProvisioner
from .dynsec_plan import build_node_provisioning_plan
from .n3w_first_registration_ledger import (
    FirstRegistrationAttempt,
    FirstRegistrationAttemptState,
    FirstRegistrationCleanupState,
    FirstRegistrationLedgerConflict,
    FirstRegistrationPhase,
)
from .n3w_node_application_keys import (
    NodeApplicationKeySnapshot,
    NodeApplicationKeyStoreUnavailable,
    SqliteNodeApplicationKeyAdmin,
)
from .registration import (
    NodeIdLeaseState,
    RegistrationConflict,
    RegistrationRegistry,
    RegistrationState,
)


class FirstRegistrationCommitClassification(StrEnum):
    COMMITTED = "COMMITTED"
    DEFINITELY_NOT_COMMITTED = "DEFINITELY_NOT_COMMITTED"
    UNKNOWN = "UNKNOWN"


class FirstRegistrationReconciliationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FirstRegistrationReconciliationResult:
    pairing_id: str
    classification: FirstRegistrationCommitClassification
    state: FirstRegistrationAttemptState
    cleanup_state: FirstRegistrationCleanupState


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _stage_completion_proven(attempt: FirstRegistrationAttempt) -> bool:
    return (
        attempt.node_id is not None
        and attempt.dynsec_prestate_absent is True
        and attempt.application_key_prestate_absent is True
        and attempt.application_key_epoch is not None
        and attempt.delivery_digest_sha256 is not None
    )


class FirstRegistrationReconciler:
    def __init__(
        self,
        *,
        registry: RegistrationRegistry,
        credential_store: CredentialLifecycleStore,
        application_keys: SqliteNodeApplicationKeyAdmin,
        dynsec: DynsecProvisioner,
        system_id: str,
    ) -> None:
        self.registry = registry
        self.ledger = registry.first_registration_ledger()
        self.credential_store = credential_store
        self.application_keys = application_keys
        self.dynsec = dynsec
        self.system_id = system_id
        self._lock = threading.RLock()

    def _application_snapshot(
        self,
        attempt: FirstRegistrationAttempt,
    ) -> NodeApplicationKeySnapshot | None:
        if attempt.node_id is None:
            return None
        return self.application_keys.snapshot_node(
            node_id=attempt.node_id,
            key_epoch=attempt.application_key_epoch,
        )

    @staticmethod
    def _runtime_key_conflict(
        snapshot: NodeApplicationKeySnapshot,
        *,
        expected_epoch: int,
    ) -> bool:
        for epoch, state, _enabled in snapshot.epochs:
            if state in {"ACTIVE", "GRACE"} and epoch != expected_epoch:
                return True
        return False

    def classify(
        self,
        attempt: FirstRegistrationAttempt,
    ) -> FirstRegistrationCommitClassification:
        if attempt.state is not FirstRegistrationAttemptState.ACTIVE:
            raise FirstRegistrationReconciliationError(
                "only active attempts may be classified"
            )

        try:
            registration = self.registry.get_by_pairing_id(
                attempt.pairing_id
            )
            credentials = self.credential_store.list_for_pairing_id(
                attempt.pairing_id
            )

            if len(credentials) > 1:
                return FirstRegistrationCommitClassification.UNKNOWN

            if registration is None:
                if (
                    attempt.phase
                    is not FirstRegistrationPhase.BOOTSTRAP_ACCEPTED
                    or attempt.node_id is not None
                    or credentials
                ):
                    return FirstRegistrationCommitClassification.UNKNOWN
                return (
                    FirstRegistrationCommitClassification
                    .DEFINITELY_NOT_COMMITTED
                )

            if (
                hashlib.sha256(
                    registration.hardware_id.encode("utf-8")
                ).hexdigest()
                != attempt.hardware_id_sha256
                or registration.current_pairing_id
                != attempt.pairing_id
            ):
                return FirstRegistrationCommitClassification.UNKNOWN

            hardware_history = (
                self.credential_store.list_for_hardware(
                    registration.hardware_id
                )
            )

            if attempt.node_id is None:
                if (
                    registration.node_id is not None
                    or registration.state
                    is not RegistrationState.PENDING
                    or credentials
                    or hardware_history
                ):
                    return FirstRegistrationCommitClassification.UNKNOWN
                return (
                    FirstRegistrationCommitClassification
                    .DEFINITELY_NOT_COMMITTED
                )

            if (
                registration.node_id != attempt.node_id
                or registration.state
                is not RegistrationState.APPROVED
                or registration.lease_hardware_id
                != registration.hardware_id
                or registration.lease_state
                is not NodeIdLeaseState.ACTIVE
            ):
                return FirstRegistrationCommitClassification.UNKNOWN

            for record in hardware_history:
                if record.pairing_id != attempt.pairing_id:
                    return FirstRegistrationCommitClassification.UNKNOWN

            plan = build_node_provisioning_plan(
                system_id=self.system_id,
                node_id=attempt.node_id,
                generation=1,
            )
            dynsec = self.dynsec.inspect_plan(plan)
            application = self._application_snapshot(attempt)
            if application is None:
                return FirstRegistrationCommitClassification.UNKNOWN

            stage_proven = _stage_completion_proven(attempt)

            if credentials:
                credential = credentials[0]
                credential_committed = (
                    credential.hardware_id
                    == registration.hardware_id
                    and credential.state is CredentialState.ACTIVE
                    and credential.pairing_id == attempt.pairing_id
                    and credential.node_id == attempt.node_id
                    and credential.active_generation == 1
                    and credential.pending_generation is None
                )
                if not credential_committed:
                    return FirstRegistrationCommitClassification.UNKNOWN

                if (
                    attempt.phase
                    is not FirstRegistrationPhase.COMMITTING
                    or not stage_proven
                    or attempt.application_key_epoch is None
                    or not application.requested_exists
                    or application.requested_state != "ACTIVE"
                    or application.requested_enabled is not True
                    or application.requested_material_binding_valid
                    is not True
                    or self._runtime_key_conflict(
                        application,
                        expected_epoch=attempt.application_key_epoch,
                    )
                    or not dynsec.exact_match
                ):
                    return FirstRegistrationCommitClassification.UNKNOWN

                return FirstRegistrationCommitClassification.COMMITTED

            if not stage_proven:
                if application.epochs:
                    return FirstRegistrationCommitClassification.UNKNOWN
                if dynsec.client_present or dynsec.role_present:
                    return FirstRegistrationCommitClassification.UNKNOWN
                return (
                    FirstRegistrationCommitClassification
                    .DEFINITELY_NOT_COMMITTED
                )

            if attempt.application_key_epoch is None:
                return FirstRegistrationCommitClassification.UNKNOWN

            if any(
                epoch != attempt.application_key_epoch
                for epoch, _state, _enabled in application.epochs
            ):
                return FirstRegistrationCommitClassification.UNKNOWN

            if (
                application.requested_exists
                and application.requested_state == "GRACE"
            ):
                return FirstRegistrationCommitClassification.UNKNOWN

            if dynsec.client_present and not dynsec.client_matches:
                return FirstRegistrationCommitClassification.UNKNOWN
            if dynsec.role_present and not dynsec.role_matches:
                return FirstRegistrationCommitClassification.UNKNOWN

            return (
                FirstRegistrationCommitClassification
                .DEFINITELY_NOT_COMMITTED
            )

        except (
            CredentialLifecycleConflict,
            DynsecError,
            FirstRegistrationLedgerConflict,
            NodeApplicationKeyStoreUnavailable,
            RegistrationConflict,
            KeyError,
            TypeError,
            ValueError,
        ):
            return FirstRegistrationCommitClassification.UNKNOWN

    def _cleanup_required(
        self,
        attempt: FirstRegistrationAttempt,
        *,
        now: datetime,
    ) -> FirstRegistrationAttempt:
        if (
            attempt.state
            not in {
                FirstRegistrationAttemptState.EXPIRED,
                FirstRegistrationAttemptState.RESTART_INVALIDATED,
            }
            or attempt.cleanup_state
            is not FirstRegistrationCleanupState.REQUIRED
        ):
            raise FirstRegistrationReconciliationError(
                "cleanup requires a terminal REQUIRED attempt"
            )

        try:
            registration = self.registry.get_by_pairing_id(
                attempt.pairing_id
            )

            if registration is None:
                if attempt.node_id is not None:
                    raise FirstRegistrationReconciliationError(
                        "terminal cleanup lost registration binding"
                    )
                return self.ledger.mark_cleanup_complete(
                    attempt.pairing_id
                )

            if (
                hashlib.sha256(
                    registration.hardware_id.encode("utf-8")
                ).hexdigest()
                != attempt.hardware_id_sha256
            ):
                raise FirstRegistrationReconciliationError(
                    "terminal cleanup hardware binding mismatch"
                )

            if _stage_completion_proven(attempt):
                if (
                    attempt.node_id is None
                    or attempt.application_key_epoch is None
                ):
                    raise FirstRegistrationReconciliationError(
                        "terminal cleanup ownership tuple is incomplete"
                    )

                plan = build_node_provisioning_plan(
                    system_id=self.system_id,
                    node_id=attempt.node_id,
                    generation=1,
                )
                self.dynsec.deprovision(plan)

                snapshot = self.application_keys.snapshot_node(
                    node_id=attempt.node_id,
                    key_epoch=attempt.application_key_epoch,
                )
                if any(
                    epoch != attempt.application_key_epoch
                    and state in {"ACTIVE", "GRACE"}
                    for epoch, state, _enabled in snapshot.epochs
                ):
                    raise FirstRegistrationReconciliationError(
                        "terminal cleanup application-key conflict"
                    )
                if (
                    snapshot.requested_exists
                    and snapshot.requested_state != "REVOKED"
                ):
                    self.application_keys.revoke_key(
                        node_id=attempt.node_id,
                        key_epoch=attempt.application_key_epoch,
                    )

            terminal_state = (
                RegistrationState.EXPIRED
                if attempt.state
                is FirstRegistrationAttemptState.EXPIRED
                else RegistrationState.REJECTED
            )
            terminal_reason = (
                "expired"
                if attempt.state
                is FirstRegistrationAttemptState.EXPIRED
                else "replay_detected"
            )
            self.registry.reconcile_first_registration_terminal(
                attempt.pairing_id,
                hardware_id=registration.hardware_id,
                node_id=attempt.node_id,
                terminal_state=terminal_state,
                terminal_reason=terminal_reason,
                now=now,
            )

            remaining = self.credential_store.list_for_pairing_id(
                attempt.pairing_id
            )
            if any(
                record.state is not CredentialState.REVOKED
                for record in remaining
            ):
                raise FirstRegistrationReconciliationError(
                    "terminal cleanup credential assignment remains active"
                )

            return self.ledger.mark_cleanup_complete(
                attempt.pairing_id
            )

        except (
            CredentialLifecycleConflict,
            DynsecError,
            FirstRegistrationLedgerConflict,
            NodeApplicationKeyStoreUnavailable,
            RegistrationConflict,
            FirstRegistrationReconciliationError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            with suppress(FirstRegistrationLedgerConflict):
                self.ledger.mark_cleanup_failed(
                    attempt.pairing_id
                )
            raise FirstRegistrationReconciliationError(
                "first-registration cleanup failed"
            ) from error

    def reconcile_attempt(
        self,
        attempt: FirstRegistrationAttempt,
        *,
        now: datetime | None = None,
    ) -> FirstRegistrationReconciliationResult:
        observed_at = _utc(now or datetime.now(UTC))

        with self._lock:
            if (
                attempt.state
                is FirstRegistrationAttemptState.COMMITTED
                or attempt.cleanup_state
                is FirstRegistrationCleanupState.COMPLETE
            ):
                return FirstRegistrationReconciliationResult(
                    pairing_id=attempt.pairing_id,
                    classification=(
                        FirstRegistrationCommitClassification.COMMITTED
                        if attempt.state
                        is FirstRegistrationAttemptState.COMMITTED
                        else FirstRegistrationCommitClassification
                        .DEFINITELY_NOT_COMMITTED
                    ),
                    state=attempt.state,
                    cleanup_state=attempt.cleanup_state,
                )

            if (
                attempt.state
                in {
                    FirstRegistrationAttemptState.EXPIRED,
                    FirstRegistrationAttemptState.RESTART_INVALIDATED,
                }
            ):
                if (
                    attempt.cleanup_state
                    is FirstRegistrationCleanupState.FAILED
                ):
                    return FirstRegistrationReconciliationResult(
                        pairing_id=attempt.pairing_id,
                        classification=(
                            FirstRegistrationCommitClassification.UNKNOWN
                        ),
                        state=attempt.state,
                        cleanup_state=attempt.cleanup_state,
                    )
                completed = self._cleanup_required(
                    attempt,
                    now=observed_at,
                )
                return FirstRegistrationReconciliationResult(
                    pairing_id=attempt.pairing_id,
                    classification=(
                        FirstRegistrationCommitClassification
                        .DEFINITELY_NOT_COMMITTED
                    ),
                    state=completed.state,
                    cleanup_state=completed.cleanup_state,
                )

            classification = self.classify(attempt)

            if (
                classification
                is FirstRegistrationCommitClassification.COMMITTED
            ):
                committed = self.ledger.mark_committed(
                    attempt.pairing_id,
                    terminal_at=observed_at,
                )
                return FirstRegistrationReconciliationResult(
                    pairing_id=attempt.pairing_id,
                    classification=classification,
                    state=committed.state,
                    cleanup_state=committed.cleanup_state,
                )

            terminal_state = (
                FirstRegistrationAttemptState.EXPIRED
                if observed_at >= attempt.expires_at
                else FirstRegistrationAttemptState.RESTART_INVALIDATED
            )
            cleanup_state = (
                FirstRegistrationCleanupState.REQUIRED
                if classification
                is FirstRegistrationCommitClassification
                .DEFINITELY_NOT_COMMITTED
                else FirstRegistrationCleanupState.FAILED
            )
            terminal_reason = (
                "expired"
                if terminal_state
                is FirstRegistrationAttemptState.EXPIRED
                else "replay_detected"
            )
            terminal = self.ledger.terminalize_not_committed(
                attempt.pairing_id,
                state=terminal_state,
                cleanup_state=cleanup_state,
                terminal_at=observed_at,
                terminal_reason=terminal_reason,
            )

            if (
                classification
                is FirstRegistrationCommitClassification.UNKNOWN
            ):
                return FirstRegistrationReconciliationResult(
                    pairing_id=attempt.pairing_id,
                    classification=classification,
                    state=terminal.state,
                    cleanup_state=terminal.cleanup_state,
                )

            completed = self._cleanup_required(
                terminal,
                now=observed_at,
            )
            return FirstRegistrationReconciliationResult(
                pairing_id=attempt.pairing_id,
                classification=classification,
                state=completed.state,
                cleanup_state=completed.cleanup_state,
            )

    def reconcile_startup(
        self,
        *,
        now: datetime | None = None,
    ) -> tuple[FirstRegistrationReconciliationResult, ...]:
        observed_at = _utc(now or datetime.now(UTC))
        results: list[FirstRegistrationReconciliationResult] = []

        with self._lock:
            for attempt in self.ledger.list_reconcilable():
                results.append(
                    self.reconcile_attempt(
                        attempt,
                        now=observed_at,
                    )
                )

        if any(
            result.classification
            is FirstRegistrationCommitClassification.UNKNOWN
            or result.cleanup_state
            is FirstRegistrationCleanupState.FAILED
            for result in results
        ):
            raise FirstRegistrationReconciliationError(
                "first-registration startup reconciliation failed closed"
            )

        return tuple(results)
