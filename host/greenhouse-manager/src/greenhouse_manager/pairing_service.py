from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol

from .dynsec_plan import (
    NodeCredentials,
    NodeProvisioningPlan,
    build_node_provisioning_plan,
    generate_node_credentials,
)
from .registration import RegistrationRecord, RegistrationRegistry, RegistrationState

_BASE64URL_32_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")


class PairingError(RuntimeError):
    """Base error for the H3/N2 one-time pairing session core."""


class PairingConflict(PairingError):
    """Raised when a pairing operation would violate the session state machine."""


class PairingExpired(PairingError):
    """Raised when a pairing session is no longer valid."""


class PairingProofRejected(PairingError):
    """Raised when proof of possession is invalid."""


class PairingProvisioningError(PairingError):
    """Raised when broker identity provisioning fails."""


class PairingRollbackError(PairingError):
    """Raised when a provisioned identity cannot be rolled back."""


class PairingSessionState(StrEnum):
    OPEN = "open"
    PROOF_VERIFIED = "proof_verified"
    CREDENTIALS_ISSUED = "credentials_issued"
    CONSUMED = "consumed"
    FAILED = "failed"
    EXPIRED = "expired"


class NodeIdentityProvisioner(Protocol):
    def provision(
        self,
        plan: NodeProvisioningPlan,
        credentials: NodeCredentials,
    ) -> None: ...

    def deprovision(self, plan: NodeProvisioningPlan) -> None: ...


@dataclass(frozen=True, slots=True)
class PairingOffer:
    schema: str
    session_id: str
    hardware_id: str
    pairing_id: str
    manager_nonce: str
    expires_at: datetime
    max_proof_attempts: int


@dataclass(frozen=True, slots=True, repr=False)
class CredentialBundle:
    schema: str
    system_id: str
    node_id: str
    broker_host: str
    broker_port: int
    broker_tls_server_name: str
    ca_pem: str
    mqtt_username: str
    mqtt_client_id: str
    credential_generation: int
    mqtt_password: str = field(repr=False)

    def __repr__(self) -> str:
        return (
            "CredentialBundle("
            f"schema={self.schema!r}, system_id={self.system_id!r}, "
            f"node_id={self.node_id!r}, broker_host={self.broker_host!r}, "
            f"broker_port={self.broker_port!r}, "
            f"broker_tls_server_name={self.broker_tls_server_name!r}, "
            f"ca_pem=<certificate>, mqtt_username={self.mqtt_username!r}, "
            f"mqtt_client_id={self.mqtt_client_id!r}, "
            f"credential_generation={self.credential_generation!r}, "
            "mqtt_password=<redacted>)"
        )


@dataclass(frozen=True, slots=True)
class PairingSessionSnapshot:
    session_id: str
    hardware_id: str
    pairing_id: str
    state: PairingSessionState
    expires_at: datetime
    proof_attempts: int
    credential_generation: int | None


@dataclass(slots=True)
class _PairingSession:
    session_id: str
    hardware_id: str
    pairing_id: str
    manager_nonce: bytes
    secret: bytearray
    expires_at: datetime
    max_proof_attempts: int
    state: PairingSessionState = PairingSessionState.OPEN
    proof_attempts: int = 0
    plan: NodeProvisioningPlan | None = None
    credentials: NodeCredentials | None = None
    bundle: CredentialBundle | None = None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _encode_base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_base64url_32(value: str, *, field_name: str) -> bytes:
    if _BASE64URL_32_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be 32-byte unpadded base64url")
    try:
        decoded = base64.urlsafe_b64decode(value + "=")
    except ValueError as error:
        raise ValueError(
            f"{field_name} must be 32-byte unpadded base64url"
        ) from error
    if len(decoded) != 32:
        raise ValueError(f"{field_name} must decode to exactly 32 bytes")
    return decoded


def _proof_transcript(
    *,
    session_id: str,
    hardware_id: str,
    pairing_id: str,
    node_nonce: str,
    manager_nonce: str,
) -> bytes:
    return "\n".join(
        (
            "gh.pair.proof/1",
            session_id,
            hardware_id,
            pairing_id,
            node_nonce,
            manager_nonce,
        )
    ).encode("ascii")


def build_pairing_proof(
    *,
    pairing_secret: str,
    offer: PairingOffer,
    node_nonce: str,
) -> str:
    """Build the proof used by tests and the future ESP32-C6 implementation."""

    secret = _decode_base64url_32(
        pairing_secret,
        field_name="pairing_secret",
    )
    _decode_base64url_32(node_nonce, field_name="node_nonce")
    transcript = _proof_transcript(
        session_id=offer.session_id,
        hardware_id=offer.hardware_id,
        pairing_id=offer.pairing_id,
        node_nonce=node_nonce,
        manager_nonce=offer.manager_nonce,
    )
    return _encode_base64url(
        hmac.new(secret, transcript, hashlib.sha256).digest()
    )


class PairingSessionManager:
    """Thread-safe, single-use H3/N2 pairing and credential issuance core.

    Pairing secrets exist only in memory. Broker credentials are provisioned only
    after the persistent registration record has been explicitly approved.
    Transport encryption and persistent encrypted session recovery are separate
    Stage 2A work packages and are intentionally not claimed by this core.
    """

    def __init__(
        self,
        registry: RegistrationRegistry,
        provisioner: NodeIdentityProvisioner,
        *,
        system_id: str,
        broker_host: str,
        broker_port: int,
        ca_pem: str,
        broker_tls_server_name: str | None = None,
        session_ttl_s: int = 120,
        max_proof_attempts: int = 3,
        random_bytes: Callable[[int], bytes] = secrets.token_bytes,
        uuid_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        if not broker_host or any(character.isspace() for character in broker_host):
            raise ValueError("broker_host must be a non-empty hostname")
        if not 1 <= broker_port <= 65535:
            raise ValueError("broker_port must be between 1 and 65535")
        if not ca_pem.strip():
            raise ValueError("ca_pem must not be empty")
        if session_ttl_s < 1:
            raise ValueError("session_ttl_s must be positive")
        if max_proof_attempts < 1:
            raise ValueError("max_proof_attempts must be positive")

        self.registry = registry
        self.provisioner = provisioner
        self.system_id = system_id
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.broker_tls_server_name = (
            broker_tls_server_name or broker_host
        )
        self.ca_pem = ca_pem
        self.session_ttl = timedelta(seconds=session_ttl_s)
        self.max_proof_attempts = max_proof_attempts
        self.random_bytes = random_bytes
        self.uuid_factory = uuid_factory
        self._lock = threading.RLock()
        self._sessions: dict[str, _PairingSession] = {}
        self._pairings: dict[tuple[str, str], str] = {}

    def open_session(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        pairing_secret: str,
        now: datetime | None = None,
    ) -> PairingOffer:
        observed_at = _utc(now or datetime.now(UTC))
        record = self.registry.get(hardware_id)
        self._require_record_pairing(record, pairing_id)
        if record.state != RegistrationState.PENDING:
            raise PairingConflict(
                "pairing session can only open for a pending registration"
            )

        secret = _decode_base64url_32(
            pairing_secret,
            field_name="pairing_secret",
        )
        manager_nonce = self.random_bytes(32)
        if len(manager_nonce) != 32:
            raise ValueError("random_bytes must return exactly 32 bytes")

        key = (hardware_id, pairing_id)
        with self._lock:
            if key in self._pairings:
                raise PairingConflict(
                    "pairing_id already has a one-time session"
                )
            session_id = str(self.uuid_factory())
            if session_id in self._sessions:
                raise PairingConflict("uuid_factory returned a duplicate session_id")
            expires_at = min(
                observed_at + self.session_ttl,
                record.expires_at,
            )
            if expires_at <= observed_at:
                raise PairingExpired("registration is already expired")

            session = _PairingSession(
                session_id=session_id,
                hardware_id=hardware_id,
                pairing_id=pairing_id,
                manager_nonce=manager_nonce,
                secret=bytearray(secret),
                expires_at=expires_at,
                max_proof_attempts=self.max_proof_attempts,
            )
            self._sessions[session_id] = session
            self._pairings[key] = session_id
            return self._offer(session)

    def verify_proof(
        self,
        session_id: str,
        *,
        proof: str,
        now: datetime | None = None,
    ) -> PairingSessionSnapshot:
        observed_at = _utc(now or datetime.now(UTC))
        supplied = _decode_base64url_32(proof, field_name="proof")

        with self._lock:
            session = self._require_session(session_id)
            self._expire_if_needed(session, observed_at)
            if session.state != PairingSessionState.OPEN:
                raise PairingConflict(
                    f"proof cannot be verified in {session.state} state"
                )

            record = self.registry.get(session.hardware_id)
            self._require_record_pairing(record, session.pairing_id)
            transcript = _proof_transcript(
                session_id=session.session_id,
                hardware_id=session.hardware_id,
                pairing_id=session.pairing_id,
                node_nonce=record.node_nonce,
                manager_nonce=_encode_base64url(session.manager_nonce),
            )
            expected = hmac.new(
                bytes(session.secret),
                transcript,
                hashlib.sha256,
            ).digest()
            session.proof_attempts += 1
            if not hmac.compare_digest(supplied, expected):
                if session.proof_attempts >= session.max_proof_attempts:
                    session.state = PairingSessionState.FAILED
                    self._clear_secret(session)
                raise PairingProofRejected("pairing proof rejected")

            session.state = PairingSessionState.PROOF_VERIFIED
            return self._snapshot(session)

    def issue_credentials(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> CredentialBundle:
        observed_at = _utc(now or datetime.now(UTC))
        with self._lock:
            session = self._require_session(session_id)
            self._expire_if_needed(session, observed_at)
            if (
                session.state == PairingSessionState.CREDENTIALS_ISSUED
                and session.bundle is not None
            ):
                return session.bundle
            if session.state != PairingSessionState.PROOF_VERIFIED:
                raise PairingConflict(
                    "credentials require a verified proof"
                )

            record = self.registry.get(session.hardware_id)
            self._require_record_pairing(record, session.pairing_id)
            if (
                record.state != RegistrationState.APPROVED
                or record.node_id is None
            ):
                raise PairingConflict(
                    "credentials require explicit operator approval and node_id"
                )

            plan = build_node_provisioning_plan(
                system_id=self.system_id,
                node_id=record.node_id,
                generation=record.pairing_epoch,
            )
            credentials = generate_node_credentials(plan)
            try:
                self.provisioner.provision(plan, credentials)
            except Exception as error:
                raise PairingProvisioningError(
                    "node identity provisioning failed"
                ) from error

            bundle = CredentialBundle(
                schema="gh.pair.credentials/1",
                system_id=self.system_id,
                node_id=record.node_id,
                broker_host=self.broker_host,
                broker_port=self.broker_port,
                broker_tls_server_name=self.broker_tls_server_name,
                ca_pem=self.ca_pem,
                mqtt_username=credentials.username,
                mqtt_client_id=credentials.client_id,
                mqtt_password=credentials.password,
                credential_generation=credentials.generation,
            )
            session.plan = plan
            session.credentials = credentials
            session.bundle = bundle
            session.state = PairingSessionState.CREDENTIALS_ISSUED
            return bundle

    def acknowledge_delivery(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> PairingSessionSnapshot:
        observed_at = _utc(now or datetime.now(UTC))
        with self._lock:
            session = self._require_session(session_id)
            self._expire_if_needed(session, observed_at)
            if session.state != PairingSessionState.CREDENTIALS_ISSUED:
                raise PairingConflict(
                    "delivery acknowledgement requires issued credentials"
                )
            generation = (
                session.plan.generation
                if session.plan is not None
                else None
            )
            session.state = PairingSessionState.CONSUMED
            self._clear_sensitive(session)
            return PairingSessionSnapshot(
                session_id=session.session_id,
                hardware_id=session.hardware_id,
                pairing_id=session.pairing_id,
                state=session.state,
                expires_at=session.expires_at,
                proof_attempts=session.proof_attempts,
                credential_generation=generation,
            )

    def abort(
        self,
        session_id: str,
    ) -> PairingSessionSnapshot:
        with self._lock:
            session = self._require_session(session_id)
            if session.state == PairingSessionState.CONSUMED:
                raise PairingConflict("consumed pairing cannot be aborted")
            if session.state in (
                PairingSessionState.FAILED,
                PairingSessionState.EXPIRED,
            ):
                return self._snapshot(session)
            if (
                session.state == PairingSessionState.CREDENTIALS_ISSUED
                and session.plan is not None
            ):
                try:
                    self.provisioner.deprovision(session.plan)
                except Exception as error:
                    raise PairingRollbackError(
                        "node identity rollback failed"
                    ) from error
            session.state = PairingSessionState.FAILED
            self._clear_sensitive(session)
            return self._snapshot(session)

    def expire_sessions(
        self,
        *,
        now: datetime | None = None,
    ) -> int:
        observed_at = _utc(now or datetime.now(UTC))
        expired = 0
        failures: list[str] = []
        with self._lock:
            for session in self._sessions.values():
                if (
                    session.state
                    in (
                        PairingSessionState.CONSUMED,
                        PairingSessionState.FAILED,
                        PairingSessionState.EXPIRED,
                    )
                    or observed_at <= session.expires_at
                ):
                    continue
                try:
                    self._expire_session(session)
                except PairingRollbackError:
                    failures.append(session.session_id)
                    continue
                expired += 1
        if failures:
            raise PairingRollbackError(
                "expired identity rollback failed for sessions: "
                + ",".join(failures)
            )
        return expired

    def status(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> PairingSessionSnapshot:
        observed_at = _utc(now or datetime.now(UTC))
        with self._lock:
            session = self._require_session(session_id)
            self._expire_if_needed(session, observed_at)
            return self._snapshot(session)

    @staticmethod
    def _require_record_pairing(
        record: RegistrationRecord,
        pairing_id: str,
    ) -> None:
        if record.pairing_id != pairing_id:
            raise PairingConflict(
                "pairing_id is not the current registration session"
            )

    def _require_session(self, session_id: str) -> _PairingSession:
        try:
            return self._sessions[session_id]
        except KeyError as error:
            raise PairingConflict("unknown pairing session") from error

    def _expire_if_needed(
        self,
        session: _PairingSession,
        observed_at: datetime,
    ) -> None:
        if (
            observed_at > session.expires_at
            and session.state
            not in (
                PairingSessionState.CONSUMED,
                PairingSessionState.FAILED,
                PairingSessionState.EXPIRED,
            )
        ):
            self._expire_session(session)
            raise PairingExpired("pairing session expired")

    def _expire_session(self, session: _PairingSession) -> None:
        if (
            session.state == PairingSessionState.CREDENTIALS_ISSUED
            and session.plan is not None
        ):
            try:
                self.provisioner.deprovision(session.plan)
            except Exception as error:
                raise PairingRollbackError(
                    "expired node identity rollback failed"
                ) from error
        session.state = PairingSessionState.EXPIRED
        self._clear_sensitive(session)

    @staticmethod
    def _clear_secret(session: _PairingSession) -> None:
        for index in range(len(session.secret)):
            session.secret[index] = 0
        session.secret.clear()

    def _clear_sensitive(self, session: _PairingSession) -> None:
        self._clear_secret(session)
        session.credentials = None
        session.bundle = None
        session.plan = None

    @staticmethod
    def _offer(session: _PairingSession) -> PairingOffer:
        return PairingOffer(
            schema="gh.pair.offer/1",
            session_id=session.session_id,
            hardware_id=session.hardware_id,
            pairing_id=session.pairing_id,
            manager_nonce=_encode_base64url(session.manager_nonce),
            expires_at=session.expires_at,
            max_proof_attempts=session.max_proof_attempts,
        )

    @staticmethod
    def _snapshot(session: _PairingSession) -> PairingSessionSnapshot:
        generation = (
            session.plan.generation
            if session.plan is not None
            else None
        )
        return PairingSessionSnapshot(
            session_id=session.session_id,
            hardware_id=session.hardware_id,
            pairing_id=session.pairing_id,
            state=session.state,
            expires_at=session.expires_at,
            proof_attempts=session.proof_attempts,
            credential_generation=generation,
        )
