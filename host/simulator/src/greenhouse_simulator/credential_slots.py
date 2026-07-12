from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final


class CredentialDeliveryError(RuntimeError):
    pass


class DeliveryPhase(StrEnum):
    STABLE = "stable"
    STAGED = "staged"
    VERIFIED = "verified"
    CLAIM_SENT = "claim_sent"
    COMMITTED_GRACE = "committed_grace"


class SlotName(StrEnum):
    A = "a"
    B = "b"


@dataclass(frozen=True, slots=True, repr=False)
class NodeMqttCredential:
    host: str
    port: int
    client_id: str
    username: str
    password: str
    generation: int

    def __post_init__(self) -> None:
        if not self.host or any(character.isspace() for character in self.host):
            raise ValueError("MQTT host is invalid")
        if not 1 <= self.port <= 65535:
            raise ValueError("MQTT port is invalid")
        if not self.client_id or any(character.isspace() for character in self.client_id):
            raise ValueError("MQTT client ID is invalid")
        if not self.username or any(character.isspace() for character in self.username):
            raise ValueError("MQTT username is invalid")
        if len(self.password) < 32:
            raise ValueError("MQTT password is too short")
        if self.generation < 1:
            raise ValueError("credential generation must be positive")

    def __repr__(self) -> str:
        return (
            "NodeMqttCredential("
            f"port={self.port}, generation={self.generation}, "
            "host=<redacted>, client_id=<redacted>, username=<redacted>, "
            "password=<redacted>)"
        )


@dataclass(frozen=True, slots=True)
class CredentialAuditEvent:
    code: str
    generation: int | None
    phase: DeliveryPhase
    reason: str | None = None


@dataclass(slots=True)
class _SlotRecord:
    credential: NodeMqttCredential
    checksum: str


@dataclass(slots=True)
class NodeCredentialSlots:
    """Transport-neutral dual-slot node credential model.

    The class models the NVS ordering required by ESP32-C6 firmware. It never
    logs or returns credential fields through its public summary or audit trail.
    """

    legacy_fallback_available: bool = True
    _slots: dict[SlotName, _SlotRecord | None] = field(
        default_factory=lambda: {SlotName.A: None, SlotName.B: None},
        init=False,
        repr=False,
    )
    _active_slot: SlotName | None = field(default=None, init=False, repr=False)
    _pending_slot: SlotName | None = field(default=None, init=False, repr=False)
    _rollback_slot: SlotName | None = field(default=None, init=False, repr=False)
    _phase: DeliveryPhase = field(
        default=DeliveryPhase.STABLE,
        init=False,
        repr=False,
    )
    _events: list[CredentialAuditEvent] = field(
        default_factory=list,
        init=False,
        repr=False,
    )

    _CHECKSUM_SCHEMA: Final[str] = "gh.node.mqtt-credential-slot/1"

    @property
    def phase(self) -> DeliveryPhase:
        return self._phase

    @property
    def local_operation_available(self) -> bool:
        return True

    @property
    def active_generation(self) -> int | None:
        record = self._record(self._active_slot)
        return record.credential.generation if record is not None else None

    @property
    def pending_generation(self) -> int | None:
        record = self._record(self._pending_slot)
        return record.credential.generation if record is not None else None

    @property
    def rollback_generation(self) -> int | None:
        record = self._record(self._rollback_slot)
        return record.credential.generation if record is not None else None

    @property
    def events(self) -> tuple[CredentialAuditEvent, ...]:
        return tuple(self._events)

    def install_existing_active(self, credential: NodeMqttCredential) -> None:
        if self._phase is not DeliveryPhase.STABLE or self._active_slot is not None:
            raise CredentialDeliveryError("active credentials already exist")
        self._write_slot(SlotName.A, credential)
        self._active_slot = SlotName.A
        self.legacy_fallback_available = False
        self._event("existing_active_installed", credential.generation)

    def stage(self, credential: NodeMqttCredential) -> None:
        if self._phase is not DeliveryPhase.STABLE:
            raise CredentialDeliveryError("credential delivery is already in progress")
        active_generation = self.active_generation or 0
        if credential.generation <= active_generation:
            raise CredentialDeliveryError("credential generation must increase")
        target = self._inactive_slot()
        self._write_slot(target, credential)
        if not self._slot_valid(target):
            self._slots[target] = None
            raise CredentialDeliveryError("pending credential slot verification failed")
        self._pending_slot = target
        self._rollback_slot = None
        self._phase = DeliveryPhase.STAGED
        self._event("candidate_staged", credential.generation)

    def verify_candidate(
        self,
        generation: int,
        *,
        connection_accepted: bool,
        observed_client_id: str,
    ) -> bool:
        credential = self._require_pending(generation, DeliveryPhase.STAGED)
        if not connection_accepted or not hmac.compare_digest(
            observed_client_id,
            credential.client_id,
        ):
            self._rollback_pending("candidate_verification_failed")
            return False
        self._phase = DeliveryPhase.VERIFIED
        self._event("candidate_verified", generation)
        return True

    def mark_claim_sent(self, generation: int) -> None:
        self._require_pending(generation, DeliveryPhase.VERIFIED)
        self._phase = DeliveryPhase.CLAIM_SENT
        self._event("claim_sent", generation)

    def commit(self, generation: int) -> None:
        self._require_pending(generation, DeliveryPhase.CLAIM_SENT)
        previous_active = self._active_slot
        new_active = self._pending_slot
        if new_active is None or not self._slot_valid(new_active):
            self._rollback_pending("pending_slot_invalid_before_commit")
            raise CredentialDeliveryError("pending credential slot is invalid")

        # Production order: persist the new active-slot pointer atomically only
        # after the candidate connection and manager commit are confirmed.
        self._rollback_slot = previous_active
        self._active_slot = new_active
        self._pending_slot = None
        self._phase = DeliveryPhase.COMMITTED_GRACE
        self._event("active_pointer_committed", generation)

    def finalize_grace(self, generation: int) -> None:
        if self._phase is not DeliveryPhase.COMMITTED_GRACE:
            raise CredentialDeliveryError("credential grace period is not active")
        if self.active_generation != generation:
            raise CredentialDeliveryError("credential generation does not match active slot")
        if self._rollback_slot is not None:
            self._slots[self._rollback_slot] = None
        self._rollback_slot = None
        self.legacy_fallback_available = False
        self._phase = DeliveryPhase.STABLE
        self._event("grace_finalized", generation)

    def roll_back(self, reason: str) -> None:
        if not reason:
            raise ValueError("rollback reason must not be empty")
        if self._phase in {
            DeliveryPhase.STAGED,
            DeliveryPhase.VERIFIED,
            DeliveryPhase.CLAIM_SENT,
        }:
            self._rollback_pending(reason)
            return
        if self._phase is DeliveryPhase.COMMITTED_GRACE:
            failed_generation = self.active_generation
            failed_slot = self._active_slot
            self._active_slot = self._rollback_slot
            self._rollback_slot = None
            if failed_slot is not None:
                self._slots[failed_slot] = None
            self._phase = DeliveryPhase.STABLE
            self._event("committed_candidate_rolled_back", failed_generation, reason)
            return
        raise CredentialDeliveryError("no credential delivery can be rolled back")

    def recover_after_boot(self) -> None:
        if self._phase in {
            DeliveryPhase.STAGED,
            DeliveryPhase.VERIFIED,
            DeliveryPhase.CLAIM_SENT,
        }:
            self._rollback_pending("boot_before_commit")
            return
        if self._phase is DeliveryPhase.COMMITTED_GRACE:
            if self._active_slot is not None and self._slot_valid(self._active_slot):
                self._event("grace_resumed_after_boot", self.active_generation)
                return
            failed_slot = self._active_slot
            self._active_slot = self._rollback_slot
            self._rollback_slot = None
            if failed_slot is not None:
                self._slots[failed_slot] = None
            self._phase = DeliveryPhase.STABLE
            self._event(
                "invalid_committed_slot_rolled_back_after_boot",
                self.active_generation,
                "active_slot_invalid",
            )
            return
        if self._active_slot is not None and not self._slot_valid(self._active_slot):
            self._active_slot = None
            self.legacy_fallback_available = True
            self._event("active_slot_invalid_recovery_required", None, "active_slot_invalid")

    def summary(self) -> dict[str, object]:
        return {
            "schema": "gh.node.credential-slots-summary/1",
            "phase": self._phase,
            "active_generation": self.active_generation,
            "pending_generation": self.pending_generation,
            "rollback_generation": self.rollback_generation,
            "active_slot_present": self._active_slot is not None,
            "pending_slot_present": self._pending_slot is not None,
            "rollback_slot_present": self._rollback_slot is not None,
            "legacy_fallback_available": self.legacy_fallback_available,
            "local_operation_available": self.local_operation_available,
            "secret_fields_emitted": False,
        }

    def simulate_slot_corruption(self, slot: SlotName) -> None:
        """Simulator-only fault injection used to exercise boot recovery."""
        record = self._slots[slot]
        if record is None:
            raise CredentialDeliveryError("cannot corrupt an empty slot")
        record.checksum = "0" * 64

    def _inactive_slot(self) -> SlotName:
        return SlotName.B if self._active_slot is SlotName.A else SlotName.A

    def _record(self, slot: SlotName | None) -> _SlotRecord | None:
        return self._slots[slot] if slot is not None else None

    def _write_slot(self, slot: SlotName, credential: NodeMqttCredential) -> None:
        self._slots[slot] = _SlotRecord(
            credential=credential,
            checksum=self._checksum(credential),
        )

    def _slot_valid(self, slot: SlotName) -> bool:
        record = self._slots[slot]
        return record is not None and hmac.compare_digest(
            record.checksum,
            self._checksum(record.credential),
        )

    def _require_pending(
        self,
        generation: int,
        phase: DeliveryPhase,
    ) -> NodeMqttCredential:
        if self._phase is not phase:
            raise CredentialDeliveryError(f"credential phase must be {phase}")
        record = self._record(self._pending_slot)
        if record is None or not self._slot_valid(self._pending_slot):
            raise CredentialDeliveryError("pending credential slot is invalid")
        if record.credential.generation != generation:
            raise CredentialDeliveryError("pending credential generation does not match")
        return record.credential

    def _rollback_pending(self, reason: str) -> None:
        generation = self.pending_generation
        if self._pending_slot is not None:
            self._slots[self._pending_slot] = None
        self._pending_slot = None
        self._rollback_slot = None
        self._phase = DeliveryPhase.STABLE
        self._event("pending_candidate_rolled_back", generation, reason)

    def _event(
        self,
        code: str,
        generation: int | None,
        reason: str | None = None,
    ) -> None:
        self._events.append(
            CredentialAuditEvent(
                code=code,
                generation=generation,
                phase=self._phase,
                reason=reason,
            )
        )

    @classmethod
    def _checksum(cls, credential: NodeMqttCredential) -> str:
        payload = json.dumps(
            {
                "schema": cls._CHECKSUM_SCHEMA,
                "host": credential.host,
                "port": credential.port,
                "client_id": credential.client_id,
                "username": credential.username,
                "password": credential.password,
                "generation": credential.generation,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
