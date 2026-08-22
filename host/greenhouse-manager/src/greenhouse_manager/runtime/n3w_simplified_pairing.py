from __future__ import annotations

import base64
import hashlib
import secrets
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol

from .n3w_auto_node_id import AutomaticNodeIdApprover
from .n3w_pairing_recovery import rollback_automatic_approval_preserving_node
from .n3w_simple_pairing_crypto import (
    PairingTranscript,
    build_setup_proof,
    derive_bootstrap_key,
    encrypt_credential_bundle,
    verify_setup_proof,
)
from .n3w_simplified_credentials import SimplifiedProductCredentialBundle
from .registration import RegistrationRegistry, RegistrationState


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str, *, size: int, field: str) -> bytes:
    if not isinstance(value, str) or not value or not value.isascii():
        raise SimplifiedPairingRejected(f"{field}_invalid")
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * ((4 - len(value) % 4) % 4))
    except (ValueError, TypeError) as error:
        raise SimplifiedPairingRejected(f"{field}_invalid") from error
    if len(decoded) != size:
        raise SimplifiedPairingRejected(f"{field}_invalid")
    return decoded


class SimplifiedPairingError(RuntimeError):
    pass


class SimplifiedPairingRejected(SimplifiedPairingError):
    pass


class SimplifiedPairingConflict(SimplifiedPairingError):
    pass


class SimplifiedPairingState(StrEnum):
    OPEN = "open"
    CREDENTIALS_ISSUED = "credentials_issued"
    CONSUMED = "consumed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class SimplifiedPairingOffer:
    schema: str
    session_id: str
    hardware_id: str
    pairing_id: str
    manager_id: str
    manager_nonce: str
    manager_proof: str
    expires_at: datetime


@dataclass(frozen=True, slots=True, repr=False)
class SimplifiedEncryptedCredentials:
    schema: str
    session_id: str
    node_id: str
    nonce: str
    ciphertext: str = ""
    delivery_digest: str = ""

    def __repr__(self) -> str:
        return (
            "SimplifiedEncryptedCredentials("
            f"schema={self.schema!r}, session_id={self.session_id!r}, "
            f"node_id={self.node_id!r}, nonce=<redacted>, "
            "ciphertext=<redacted>, delivery_digest=<redacted>)"
        )


@dataclass(frozen=True, slots=True)
class SimplifiedPairingSnapshot:
    session_id: str
    hardware_id: str
    pairing_id: str
    state: SimplifiedPairingState
    node_id: str | None
    expires_at: datetime


class StagedSimplifiedBundle(Protocol):
    bundle: SimplifiedProductCredentialBundle

    def commit(self, *, now: datetime | None = None) -> None: ...

    def rollback(self) -> None: ...


class SimplifiedBundleStager(Protocol):
    def stage(
        self,
        *,
        hardware_id: str,
        pairing_id: str,
        node_id: str,
        credential_generation: int,
    ) -> StagedSimplifiedBundle: ...


@dataclass(slots=True)
class _Session:
    session_id: str
    hardware_id: str
    pairing_id: str
    transcript: PairingTranscript
    secret: bytearray
    expires_at: datetime
    state: SimplifiedPairingState = SimplifiedPairingState.OPEN
    node_id: str | None = None
    inherited_node_id: str | None = None
    staged: StagedSimplifiedBundle | None = None
    delivery_digest: bytes | None = None
    issued_credentials: SimplifiedEncryptedCredentials | None = None


class SimplifiedPairingCoordinator:
    """Setup-Secret bootstrap with automatic NODE_ID assignment.

    This is the Phase 4 replacement for the endpoint X25519 pairing path. The
    one-time Setup Secret is imported by the trusted local UI, never compiled in
    firmware. A node proves possession, Manager proves possession back, and only
    then is a NODE_ID allocated and the complete post-registration credential
    bundle encrypted with AES-256-GCM. No peer MAC/LMK or gateway relation is
    delivered by this channel.
    """

    def __init__(
        self,
        registry: RegistrationRegistry,
        stager: SimplifiedBundleStager,
        *,
        manager_id: str,
        session_ttl_s: int = 120,
        random_bytes: Callable[[int], bytes] = secrets.token_bytes,
        uuid_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        if not manager_id or not manager_id.isascii():
            raise ValueError("manager_id_invalid")
        if not 30 <= session_ttl_s <= 600:
            raise ValueError("session_ttl_invalid")
        self.registry = registry
        self.approver = AutomaticNodeIdApprover(registry, random_bytes=random_bytes)
        self.stager = stager
        self.manager_id = manager_id
        self.session_ttl = timedelta(seconds=session_ttl_s)
        self.random_bytes = random_bytes
        self.uuid_factory = uuid_factory
        self._lock = threading.RLock()
        self._setup: dict[tuple[str, str], bytearray] = {}
        self._sessions: dict[str, _Session] = {}

    def import_setup_secret(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        setup_secret: bytes,
    ) -> None:
        if not isinstance(setup_secret, bytes) or len(setup_secret) != 32:
            raise SimplifiedPairingRejected("setup_secret_invalid")
        record = self.registry.get(hardware_id)
        if record.pairing_id != pairing_id or record.state is not RegistrationState.PENDING:
            raise SimplifiedPairingConflict("registration_not_pending")
        key = (hardware_id, pairing_id)
        with self._lock:
            existing = self._setup.get(key)
            if existing is not None:
                if secrets.compare_digest(bytes(existing), setup_secret):
                    return
                raise SimplifiedPairingConflict(
                    "setup_secret_conflicting_import"
                )
            self._setup[key] = bytearray(setup_secret)

    def begin(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        node_nonce: str,
        now: datetime | None = None,
    ) -> SimplifiedPairingOffer:
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        nonce = _unb64(node_nonce, size=16, field="node_nonce")
        key = (hardware_id, pairing_id)
        with self._lock:
            secret = self._setup.get(key)
            if secret is None:
                raise SimplifiedPairingRejected("setup_secret_unavailable")
            record = self.registry.get(hardware_id)
            if record.pairing_id != pairing_id or record.state is not RegistrationState.PENDING:
                raise SimplifiedPairingConflict("registration_not_pending")
            if any(
                s.hardware_id == hardware_id
                and s.pairing_id == pairing_id
                and s.state in {
                    SimplifiedPairingState.OPEN,
                    SimplifiedPairingState.CREDENTIALS_ISSUED,
                }
                for s in self._sessions.values()
            ):
                raise SimplifiedPairingConflict("pairing_session_exists")
            manager_nonce = self.random_bytes(16)
            if not isinstance(manager_nonce, bytes) or len(manager_nonce) != 16:
                raise SimplifiedPairingError("manager_nonce_generation_failed")
            transcript = PairingTranscript(
                pairing_id=pairing_id,
                hardware_id=hardware_id,
                manager_id=self.manager_id,
                node_nonce=nonce,
                manager_nonce=manager_nonce,
            )
            session_id = str(self.uuid_factory())
            expires_at = min(observed_at + self.session_ttl, record.expires_at)
            if expires_at <= observed_at:
                raise SimplifiedPairingConflict("registration_expired")
            session = _Session(
                session_id=session_id,
                hardware_id=hardware_id,
                pairing_id=pairing_id,
                transcript=transcript,
                secret=bytearray(secret),
                expires_at=expires_at,
            )
            self._sessions[session_id] = session
            manager_proof = build_setup_proof(
                bytes(session.secret), transcript, role="manager"
            )
            return SimplifiedPairingOffer(
                schema="gh.pair.simple-offer/1",
                session_id=session_id,
                hardware_id=hardware_id,
                pairing_id=pairing_id,
                manager_id=self.manager_id,
                manager_nonce=_b64(manager_nonce),
                manager_proof=_b64(manager_proof),
                expires_at=expires_at,
            )

    def establish(
        self,
        session_id: str,
        *,
        node_proof: str,
        now: datetime | None = None,
    ) -> SimplifiedEncryptedCredentials:
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        proof = _unb64(node_proof, size=32, field="node_proof")
        with self._lock:
            session = self._require_session(session_id)
            self._expire_if_needed(session, observed_at)
            if session.state not in {
                SimplifiedPairingState.OPEN,
                SimplifiedPairingState.CREDENTIALS_ISSUED,
            }:
                raise SimplifiedPairingConflict("pairing_session_not_open")
            proof_valid = verify_setup_proof(
                bytes(session.secret),
                session.transcript,
                role="node",
                proof=proof,
            )
            if not proof_valid:
                if session.state is SimplifiedPairingState.OPEN:
                    session.state = SimplifiedPairingState.FAILED
                    self._clear_secret(session)
                raise SimplifiedPairingRejected("node_proof_rejected")
            if session.state is SimplifiedPairingState.CREDENTIALS_ISSUED:
                if session.issued_credentials is None:
                    raise SimplifiedPairingError("issued_credentials_missing")
                return session.issued_credentials

            pre_approval = self.registry.get(
                session.hardware_id
            )
            session.inherited_node_id = pre_approval.node_id
            approved = self.approver.approve(
                session.hardware_id,
                session.pairing_id,
                now=observed_at,
            )
            if approved.node_id is None:
                raise SimplifiedPairingError("automatic_node_id_missing")
            try:
                staged = self.stager.stage(
                    hardware_id=session.hardware_id,
                    pairing_id=session.pairing_id,
                    node_id=approved.node_id,
                    credential_generation=approved.pairing_epoch,
                )
            except Exception:
                self._rollback_automatic_approval(
                    session,
                    now=observed_at,
                    reason="credential_stage_failed",
                )
                raise

            if staged.bundle.node_id != approved.node_id:
                try:
                    staged.rollback()
                finally:
                    self._rollback_automatic_approval(
                        session,
                        now=observed_at,
                        reason="credential_node_binding_mismatch",
                    )
                raise SimplifiedPairingError(
                    "credential_node_binding_mismatch"
                )

            try:
                nonce = self.random_bytes(12)
                if (
                    not isinstance(nonce, bytes)
                    or len(nonce) != 12
                ):
                    raise SimplifiedPairingError(
                        "credential_nonce_generation_failed"
                    )

                bootstrap_key = derive_bootstrap_key(
                    bytes(session.secret),
                    session.transcript,
                )

                ciphertext = encrypt_credential_bundle(
                    bootstrap_key,
                    session.transcript,
                    nonce=nonce,
                    plaintext=staged.bundle.to_json_bytes(),
                )

                digest = hashlib.sha256(
                    nonce + ciphertext
                ).digest()

                issued = SimplifiedEncryptedCredentials(
                    schema="gh.pair.simple-credentials/1",
                    session_id=session_id,
                    node_id=approved.node_id,
                    nonce=_b64(nonce),
                    ciphertext=_b64(ciphertext),
                    delivery_digest=_b64(digest),
                )
            except Exception:
                try:
                    staged.rollback()
                finally:
                    self._rollback_automatic_approval(
                        session,
                        now=observed_at,
                        reason="credential_assembly_failed",
                    )
                raise

            session.node_id = approved.node_id
            session.staged = staged
            session.delivery_digest = digest
            session.issued_credentials = issued
            session.state = SimplifiedPairingState.CREDENTIALS_ISSUED
            return issued

    def acknowledge(
        self,
        session_id: str,
        *,
        delivery_digest: str,
        now: datetime | None = None,
    ) -> SimplifiedPairingSnapshot:
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        supplied = _unb64(delivery_digest, size=32, field="delivery_digest")
        with self._lock:
            session = self._require_session(session_id)
            self._expire_if_needed(session, observed_at)
            if (
                session.state is not SimplifiedPairingState.CREDENTIALS_ISSUED
                or session.staged is None
            ):
                raise SimplifiedPairingConflict("credentials_not_issued")
            if session.delivery_digest is None or not secrets.compare_digest(
                supplied, session.delivery_digest
            ):
                raise SimplifiedPairingRejected("delivery_digest_rejected")
            try:
                session.staged.commit(
                    now=observed_at
                )
            except Exception as commit_error:
                rollback_error = None
                approval_error = None

                try:
                    self._rollback_staged(
                        session
                    )
                except Exception as error:
                    rollback_error = error

                try:
                    self._rollback_automatic_approval(
                        session,
                        now=observed_at,
                        reason="credential_commit_failed",
                    )
                except Exception as error:
                    approval_error = error

                session.state = (
                    SimplifiedPairingState.FAILED
                )
                self._clear_secret(session)

                if (
                    rollback_error is not None
                    or approval_error is not None
                ):
                    raise SimplifiedPairingError(
                        "credential_commit_rollback_failed"
                    ) from (
                        rollback_error
                        or approval_error
                    )

                raise commit_error

            session.staged = None
            session.delivery_digest = None
            session.issued_credentials = None
            session.state = SimplifiedPairingState.CONSUMED
            self._clear_secret(session)
            self._erase_imported_secret(session.hardware_id, session.pairing_id)
            return self._snapshot(session)

    def abort(self, session_id: str) -> SimplifiedPairingSnapshot:
        with self._lock:
            session = self._require_session(session_id)
            if session.state is SimplifiedPairingState.CONSUMED:
                raise SimplifiedPairingConflict("consumed_pairing_cannot_abort")
            rollback_error = None

            try:
                self._rollback_staged(session)
            except Exception as error:
                rollback_error = error

            self._rollback_automatic_approval(
                session,
                now=datetime.now(UTC),
                reason="pairing_aborted",
            )

            session.state = SimplifiedPairingState.FAILED
            self._clear_secret(session)

            if rollback_error is not None:
                raise SimplifiedPairingError(
                    "pairing_abort_rollback_failed"
                ) from rollback_error
            return self._snapshot(session)

    def status(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> SimplifiedPairingSnapshot:
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        with self._lock:
            session = self._require_session(session_id)
            self._expire_if_needed(session, observed_at)
            return self._snapshot(session)

    def expire_sessions(self, *, now: datetime | None = None) -> int:
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        expired = 0
        with self._lock:
            for session in self._sessions.values():
                if session.state in {
                    SimplifiedPairingState.CONSUMED,
                    SimplifiedPairingState.FAILED,
                    SimplifiedPairingState.EXPIRED,
                } or observed_at <= session.expires_at:
                    continue
                rollback_error = None

                try:
                    self._rollback_staged(session)
                except Exception as error:
                    rollback_error = error

                self._rollback_automatic_approval(
                    session,
                    now=observed_at,
                    reason="pairing_session_expired",
                )

                session.state = SimplifiedPairingState.EXPIRED
                self._clear_secret(session)

                if rollback_error is not None:
                    raise SimplifiedPairingError(
                        "pairing_expiry_rollback_failed"
                    ) from rollback_error

                expired += 1
        return expired

    def _require_session(self, session_id: str) -> _Session:
        try:
            return self._sessions[session_id]
        except KeyError as error:
            raise SimplifiedPairingConflict("pairing_session_unknown") from error

    def _expire_if_needed(self, session: _Session, now: datetime) -> None:
        if now <= session.expires_at or session.state in {
            SimplifiedPairingState.CONSUMED,
            SimplifiedPairingState.FAILED,
            SimplifiedPairingState.EXPIRED,
        }:
            return
        rollback_error = None

        try:
            self._rollback_staged(session)
        except Exception as error:
            rollback_error = error

        self._rollback_automatic_approval(
            session,
            now=now,
            reason="pairing_session_expired",
        )

        session.state = SimplifiedPairingState.EXPIRED
        self._clear_secret(session)

        if rollback_error is not None:
            raise SimplifiedPairingError(
                "pairing_expiry_rollback_failed"
            ) from rollback_error

        raise SimplifiedPairingConflict(
            "pairing_session_expired"
        )

    def _rollback_automatic_approval(
        self,
        session: _Session,
        *,
        now: datetime,
        reason: str,
    ) -> None:
        try:
            record = self.registry.get(
                session.hardware_id
            )
        except KeyError:
            return

        if (
            record.pairing_id
            != session.pairing_id
        ):
            raise SimplifiedPairingError(
                "registration_rollback_binding_failed"
            )

        if record.state is RegistrationState.PENDING:
            if (
                session.inherited_node_id is None
                and record.node_id is None
            ) or (
                session.inherited_node_id is not None
                and record.node_id == session.inherited_node_id
            ):
                session.node_id = None
                return

        try:
            if session.inherited_node_id is not None:
                rollback_automatic_approval_preserving_node(
                    self.registry,
                    session.hardware_id,
                    session.pairing_id,
                    preserve_node_id=session.inherited_node_id,
                    reason=reason,
                    now=now,
                )
            else:
                self.registry.rollback_automatic_approval(
                    session.hardware_id,
                    session.pairing_id,
                    reason=reason,
                    now=now,
                )
        except Exception as error:
            raise SimplifiedPairingError(
                "registration_rollback_failed"
            ) from error

        session.node_id = None

    def _rollback_staged(self, session: _Session) -> None:
        staged = session.staged
        session.staged = None
        session.delivery_digest = None
        session.issued_credentials = None
        if staged is not None:
            staged.rollback()

    def _erase_imported_secret(self, hardware_id: str, pairing_id: str) -> None:
        value = self._setup.pop((hardware_id, pairing_id), None)
        if value is not None:
            for index in range(len(value)):
                value[index] = 0
            value.clear()

    @staticmethod
    def _clear_secret(session: _Session) -> None:
        for index in range(len(session.secret)):
            session.secret[index] = 0
        session.secret.clear()

    @staticmethod
    def _snapshot(session: _Session) -> SimplifiedPairingSnapshot:
        return SimplifiedPairingSnapshot(
            session_id=session.session_id,
            hardware_id=session.hardware_id,
            pairing_id=session.pairing_id,
            state=session.state,
            node_id=session.node_id,
            expires_at=session.expires_at,
        )
