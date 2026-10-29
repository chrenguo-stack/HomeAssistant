from __future__ import annotations

import hashlib
import logging
import math
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from .n3w_first_registration_intent import (
    FirstRegistrationIntent,
    FirstRegistrationIntentStore,
)
from .n3w_first_registration_ledger import (
    FirstRegistrationAttemptState,
    FirstRegistrationCleanupState,
    FirstRegistrationLedgerConflict,
)
from .n3w_first_registration_reconciliation import (
    FirstRegistrationCommitClassification,
    FirstRegistrationReconciler,
)
from .pairing_secure_transport import decode_base64url_32
from .registration import RegistrationRegistry

FIRST_REGISTRATION_TTL_SECONDS = 1800

_LOGGER = logging.getLogger(__name__)


class FirstRegistrationTransactionRejected(RuntimeError):
    def __init__(self, reason: str, *, detail: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class FirstRegistrationStatusResult:
    status: str
    transaction_disposition: str
    reason: str | None = None


class FirstRegistrationWindow(Protocol):
    def open_first_registration(
        self,
        intent: FirstRegistrationIntent,
    ) -> dict[str, object]: ...


class FirstRegistrationDeadlineTimer(Protocol):
    def start(self) -> None: ...
    def cancel(self) -> None: ...


DeadlineTimerFactory = Callable[
    [float, Callable[[], None]],
    FirstRegistrationDeadlineTimer,
]


def _default_deadline_timer(
    delay_seconds: float,
    callback: Callable[[], None],
) -> FirstRegistrationDeadlineTimer:
    timer = threading.Timer(delay_seconds, callback)
    timer.daemon = True
    return timer


@dataclass(frozen=True, slots=True)
class FirstRegistrationStartResult:
    manager_id: str
    system_id: str
    pairing_host: str
    pairing_port: int
    pairing_path: str
    expires_at: datetime

    def expires_in_seconds(self, *, now: datetime) -> int:
        return max(
            0,
            math.ceil(
                (
                    self.expires_at
                    - now.astimezone(UTC)
                ).total_seconds()
            ),
        )


class FirstRegistrationTransactionService:
    def __init__(
        self,
        *,
        registry: RegistrationRegistry,
        intents: FirstRegistrationIntentStore,
        window: FirstRegistrationWindow,
        manager_id: str,
        system_id: str,
        clock=lambda: datetime.now(UTC),
        ttl_seconds: int = FIRST_REGISTRATION_TTL_SECONDS,
        reconciler: FirstRegistrationReconciler | None = None,
        deadline_timer_factory: DeadlineTimerFactory = _default_deadline_timer,
    ) -> None:
        if ttl_seconds != FIRST_REGISTRATION_TTL_SECONDS:
            raise ValueError("first registration TTL must be exactly 1800 seconds")
        self.registry = registry
        self.ledger = registry.first_registration_ledger()
        self.intents = intents
        self.window = window
        self.manager_id = manager_id
        self.system_id = system_id
        self.clock = clock
        self.ttl = timedelta(seconds=ttl_seconds)
        self.reconciler = reconciler
        self._start_lock = threading.RLock()
        self._deadline_lock = threading.RLock()
        self._deadline_timer_factory = deadline_timer_factory
        self._prewindow_deadline_timer: FirstRegistrationDeadlineTimer | None = None
        self._prewindow_pairing_id: str | None = None

    def _registration_busy(
        self,
        detail: str,
    ) -> FirstRegistrationTransactionRejected:
        _LOGGER.warning(
            "First-registration confirm busy detail=%s",
            detail,
        )
        return FirstRegistrationTransactionRejected(
            "registration_busy",
            detail=detail,
        )

    def _busy_binding_detail(
        self,
        *,
        hardware_id: str,
        pairing_id: str,
        source_ip: str,
        setup_secret: bytes,
        expires_at: datetime,
    ) -> str:
        current = self.intents.current()
        if current is None:
            return "active_intent_missing"
        if current.pairing_id != pairing_id:
            return "active_intent_pairing_conflict"
        if current.hardware_id != hardware_id:
            return "active_intent_hardware_mismatch"
        if current.source_ip != source_ip:
            return "active_intent_source_ip_mismatch"
        if current.manager_id != self.manager_id:
            return "active_intent_manager_mismatch"
        if current.system_id != self.system_id:
            return "active_intent_system_mismatch"
        if current.expires_at != expires_at:
            return "active_intent_deadline_mismatch"
        if not current.secret_matches(setup_secret):
            return "active_intent_setup_secret_mismatch"
        if not current.active or current.consumed:
            return "active_intent_closed"
        return "active_intent_binding_mismatch"

    def _arm_prewindow_deadline(
        self,
        pairing_id: str,
        expires_at: datetime,
    ) -> None:
        with self._deadline_lock:
            if (
                self._prewindow_pairing_id == pairing_id
                and self._prewindow_deadline_timer is not None
            ):
                return
            previous = self._prewindow_deadline_timer
            if previous is not None:
                previous.cancel()
            delay = max(
                0.0,
                (
                    expires_at
                    - self.clock().astimezone(UTC)
                ).total_seconds(),
            )
            timer = self._deadline_timer_factory(
                delay,
                lambda: self._prewindow_deadline_elapsed(
                    pairing_id,
                    expires_at,
                ),
            )
            self._prewindow_pairing_id = pairing_id
            self._prewindow_deadline_timer = timer
            timer.start()

    def _disarm_prewindow_deadline(
        self,
        pairing_id: str,
    ) -> None:
        with self._deadline_lock:
            if self._prewindow_pairing_id != pairing_id:
                return
            timer = self._prewindow_deadline_timer
            self._prewindow_deadline_timer = None
            self._prewindow_pairing_id = None
        if timer is not None:
            timer.cancel()

    def _prewindow_deadline_elapsed(
        self,
        pairing_id: str,
        expires_at: datetime,
    ) -> None:
        with self._start_lock:
            with self._deadline_lock:
                if self._prewindow_pairing_id != pairing_id:
                    return
                self._prewindow_deadline_timer = None
                self._prewindow_pairing_id = None

            now = self.clock().astimezone(UTC)
            if now < expires_at:
                self._arm_prewindow_deadline(
                    pairing_id,
                    expires_at,
                )
                return

            current = self.intents.current()
            if (
                current is not None
                and current.pairing_id == pairing_id
            ):
                self.intents.close_active()

            reconciler = self.reconciler
            if reconciler is None:
                _LOGGER.error(
                    "First-registration pre-window deadline lacks reconciler"
                )
                return

            try:
                attempt = self.ledger.get(pairing_id)
                if (
                    attempt.state
                    is FirstRegistrationAttemptState.ACTIVE
                ):
                    reconciler.reconcile_deadline(
                        pairing_id,
                        now=now,
                    )
            except Exception as error:
                _LOGGER.error(
                    "First-registration pre-window deadline reconciliation failed "
                    "failure_type=%s",
                    type(error).__name__,
                )

    def start(
        self,
        request: Mapping[str, str],
        *,
        source_ip: str,
    ) -> FirstRegistrationStartResult:
        with self._start_lock:
            return self._start_locked(
                request,
                source_ip=source_ip,
            )

    def _start_locked(
        self,
        request: Mapping[str, str],
        *,
        source_ip: str,
    ) -> FirstRegistrationStartResult:
        if request["manager_id"] != self.manager_id:
            raise FirstRegistrationTransactionRejected("manager_mismatch")
        if request["system_id"] != self.system_id:
            raise FirstRegistrationTransactionRejected("system_mismatch")
        hardware_id = request["hardware_id"]
        pairing_id = request["pairing_id"]
        setup_secret = decode_base64url_32(
            request["setup_secret"],
            field_name="setup_secret",
        )
        now = self.clock().astimezone(UTC)
        hardware_hash = hashlib.sha256(
            hardware_id.encode("utf-8")
        ).hexdigest()

        try:
            existing = self.ledger.get(pairing_id)
        except KeyError:
            existing = None

        if existing is not None:
            if existing.state is FirstRegistrationAttemptState.COMMITTED:
                raise FirstRegistrationTransactionRejected("replay_detected")
            if existing.state is FirstRegistrationAttemptState.EXPIRED:
                raise FirstRegistrationTransactionRejected("expired")
            if existing.state is FirstRegistrationAttemptState.RESTART_INVALIDATED:
                raise FirstRegistrationTransactionRejected("replay_detected")
            if existing.hardware_id_sha256 != hardware_hash:
                raise FirstRegistrationTransactionRejected("replay_detected")
            if (
                existing.state is FirstRegistrationAttemptState.ACTIVE
                and now >= existing.expires_at
            ):
                current_intent = self.intents.current()
                if (
                    current_intent is not None
                    and current_intent.pairing_id == pairing_id
                ):
                    self.intents.close_active()
                reconciler = self.reconciler
                if reconciler is None:
                    raise FirstRegistrationTransactionRejected(
                        "bootstrap_unavailable"
                    )
                try:
                    result = reconciler.reconcile_deadline(
                        pairing_id,
                        now=now,
                    )
                    resolved = self.ledger.get(pairing_id)
                except Exception as error:
                    raise FirstRegistrationTransactionRejected(
                        "bootstrap_unavailable"
                    ) from error
                if (
                    result.classification
                    is FirstRegistrationCommitClassification.UNKNOWN
                    or resolved.cleanup_state
                    is FirstRegistrationCleanupState.FAILED
                ):
                    raise FirstRegistrationTransactionRejected(
                        "bootstrap_unavailable"
                    )
                if resolved.state is FirstRegistrationAttemptState.COMMITTED:
                    raise FirstRegistrationTransactionRejected(
                        "replay_detected"
                    )
                if (
                    resolved.state is FirstRegistrationAttemptState.EXPIRED
                    and resolved.cleanup_state
                    is FirstRegistrationCleanupState.COMPLETE
                ):
                    raise FirstRegistrationTransactionRejected("expired")
                raise FirstRegistrationTransactionRejected(
                    "bootstrap_unavailable"
                )
            intent = self.intents.exact(
                hardware_id=hardware_id,
                pairing_id=pairing_id,
                source_ip=source_ip,
                manager_id=self.manager_id,
                system_id=self.system_id,
            )
            if (
                intent is None
                or intent.expires_at != existing.expires_at
                or not intent.secret_matches(setup_secret)
            ):
                raise self._registration_busy(
                    self._busy_binding_detail(
                        hardware_id=hardware_id,
                        pairing_id=pairing_id,
                        source_ip=source_ip,
                        setup_secret=setup_secret,
                        expires_at=existing.expires_at,
                    )
                )
            if now >= existing.expires_at:
                raise FirstRegistrationTransactionRejected(
                    "bootstrap_unavailable"
                )
        else:
            opened_at = now
            expires_at = opened_at + self.ttl
            intent = FirstRegistrationIntent.prepare(
                hardware_id=hardware_id,
                pairing_id=pairing_id,
                source_ip=source_ip,
                manager_id=self.manager_id,
                system_id=self.system_id,
                setup_secret=setup_secret,
                opened_at=opened_at,
                expires_at=expires_at,
            )
            try:
                durable = self.ledger.create_active(
                    pairing_id=pairing_id,
                    hardware_id_sha256=hardware_hash,
                    opened_at=opened_at,
                    expires_at=expires_at,
                )
            except FirstRegistrationLedgerConflict as error:
                raise self._registration_busy(
                    "active_ledger_conflict"
                ) from error
            if durable.expires_at != expires_at:
                raise self._registration_busy(
                    "durable_deadline_mismatch"
                )
            self.intents.activate(intent)

        self._arm_prewindow_deadline(
            pairing_id,
            intent.expires_at,
        )
        try:
            opened = self.window.open_first_registration(intent)
        except Exception as error:
            _LOGGER.warning(
                "First-registration window open unavailable failure_type=%s",
                type(error).__name__,
            )
            raise FirstRegistrationTransactionRejected(
                "bootstrap_unavailable",
                detail="window_open_unavailable",
            ) from error

        self._disarm_prewindow_deadline(pairing_id)
        pairing_host = opened.get("pairing_host")
        if not isinstance(pairing_host, str) or not pairing_host:
            raise FirstRegistrationTransactionRejected("bootstrap_unavailable")

        return FirstRegistrationStartResult(
            manager_id=self.manager_id,
            system_id=self.system_id,
            pairing_host=pairing_host,
            pairing_port=47112,
            pairing_path="/v2/pairing",
            expires_at=intent.expires_at,
        )

    def status(
        self,
        request: Mapping[str, str],
        *,
        source_ip: str,
    ) -> FirstRegistrationStatusResult:
        del source_ip
        if request["manager_id"] != self.manager_id:
            raise FirstRegistrationTransactionRejected("manager_mismatch")
        if request["system_id"] != self.system_id:
            raise FirstRegistrationTransactionRejected("system_mismatch")

        pairing_id = request["pairing_id"]
        hardware_id = request["hardware_id"]
        delivery_digest = decode_base64url_32(
            request["delivery_digest"],
            field_name="delivery_digest",
        )
        hardware_hash = hashlib.sha256(
            hardware_id.encode("utf-8")
        ).hexdigest()
        delivery_hash = hashlib.sha256(
            delivery_digest
        ).hexdigest()

        try:
            attempt = self.ledger.get(pairing_id)
        except KeyError:
            return FirstRegistrationStatusResult(
                status="unknown",
                transaction_disposition="wait",
            )

        if (
            attempt.hardware_id_sha256 != hardware_hash
            or attempt.delivery_digest_sha256 != delivery_hash
        ):
            return FirstRegistrationStatusResult(
                status="unknown",
                transaction_disposition="wait",
            )

        if attempt.state is FirstRegistrationAttemptState.COMMITTED:
            return FirstRegistrationStatusResult(
                status="committed",
                transaction_disposition="committed",
            )

        if attempt.state in {
            FirstRegistrationAttemptState.EXPIRED,
            FirstRegistrationAttemptState.RESTART_INVALIDATED,
        }:
            if (
                attempt.cleanup_state
                is FirstRegistrationCleanupState.COMPLETE
            ):
                return FirstRegistrationStatusResult(
                    status="rejected",
                    reason=attempt.terminal_reason,
                    transaction_disposition="terminal",
                )
            if (
                attempt.cleanup_state
                is FirstRegistrationCleanupState.FAILED
            ):
                return FirstRegistrationStatusResult(
                    status="unknown",
                    transaction_disposition="wait",
                )
            return FirstRegistrationStatusResult(
                status="pending",
                transaction_disposition="wait",
            )

        reconciler = self.reconciler
        now = self.clock().astimezone(UTC)
        if reconciler is None:
            return FirstRegistrationStatusResult(
                status="pending",
                transaction_disposition="wait",
            )

        if now >= attempt.expires_at:
            try:
                result = reconciler.reconcile_deadline(
                    pairing_id,
                    now=now,
                )
            except Exception:
                return FirstRegistrationStatusResult(
                    status="unknown",
                    transaction_disposition="wait",
                )
            attempt = self.ledger.get(pairing_id)
            if (
                result.classification
                is FirstRegistrationCommitClassification.UNKNOWN
            ):
                return FirstRegistrationStatusResult(
                    status="unknown",
                    transaction_disposition="wait",
                )
            if attempt.state is FirstRegistrationAttemptState.COMMITTED:
                return FirstRegistrationStatusResult(
                    status="committed",
                    transaction_disposition="committed",
                )
            if (
                attempt.state
                in {
                    FirstRegistrationAttemptState.EXPIRED,
                    FirstRegistrationAttemptState.RESTART_INVALIDATED,
                }
                and attempt.cleanup_state
                is FirstRegistrationCleanupState.COMPLETE
            ):
                return FirstRegistrationStatusResult(
                    status="rejected",
                    reason=attempt.terminal_reason,
                    transaction_disposition="terminal",
                )
            return FirstRegistrationStatusResult(
                status="pending",
                transaction_disposition="wait",
            )

        try:
            classification = reconciler.classify(attempt)
        except Exception:
            return FirstRegistrationStatusResult(
                status="unknown",
                transaction_disposition="wait",
            )
        if (
            classification
            is FirstRegistrationCommitClassification.COMMITTED
        ):
            self.ledger.mark_committed(
                pairing_id,
                terminal_at=now,
            )
            return FirstRegistrationStatusResult(
                status="committed",
                transaction_disposition="committed",
            )
        if (
            classification
            is FirstRegistrationCommitClassification.UNKNOWN
        ):
            return FirstRegistrationStatusResult(
                status="unknown",
                transaction_disposition="wait",
            )
        return FirstRegistrationStatusResult(
            status="pending",
            transaction_disposition="wait",
        )


    def window_closed(
        self,
        pairing_id: str,
        reason: str,
    ) -> None:
        self._disarm_prewindow_deadline(pairing_id)
        current = self.intents.current()
        if current is not None and current.pairing_id == pairing_id:
            self.intents.close_active()

        reconciler = self.reconciler
        if reconciler is None or reason in {
            "committed",
            "manager_shutdown",
        }:
            return

        try:
            attempt = self.ledger.get(pairing_id)
        except KeyError:
            return
        if attempt.state is not FirstRegistrationAttemptState.ACTIVE:
            return

        now = self.clock().astimezone(UTC)
        try:
            if reason == "deadline":
                reconciler.reconcile_deadline(
                    pairing_id,
                    now=now,
                )
            elif reason == "worker_failure":
                reconciler.reconcile_attempt(
                    attempt,
                    now=now,
                )
        except Exception:
            return
