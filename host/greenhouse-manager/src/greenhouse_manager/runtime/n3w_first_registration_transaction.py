from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Mapping, Protocol

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


class FirstRegistrationTransactionRejected(RuntimeError):
    pass


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
            int(
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

    def start(
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
                raise FirstRegistrationTransactionRejected("registration_busy")
            if now > existing.expires_at:
                raise FirstRegistrationTransactionRejected("registration_busy")
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
                raise FirstRegistrationTransactionRejected(
                    "registration_busy"
                ) from error
            if durable.expires_at != expires_at:
                raise FirstRegistrationTransactionRejected(
                    "registration_busy"
                )
            self.intents.activate(intent)

        try:
            opened = self.window.open_first_registration(intent)
        except Exception as error:
            raise FirstRegistrationTransactionRejected(
                "bootstrap_unavailable"
            ) from error

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
