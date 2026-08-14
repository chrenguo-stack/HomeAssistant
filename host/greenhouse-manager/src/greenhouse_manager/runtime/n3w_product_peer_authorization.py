from __future__ import annotations

import base64
import hashlib
import hmac
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .credential_lifecycle import CredentialLifecycleStore, CredentialState
from .registration import RegistrationRegistry, RegistrationState

_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_SESSION_ID = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_ROLE_CHILD = "child"
_ROLE_RELAY = "relay"
_AUTH_KEY_INFO = b"gh.n3w-product/relay-auth-key/1"
_PROOF_DOMAIN = b"gh.n3w-product/peer-proof/1"
_GRANT_DOMAIN = b"gh.n3w-product/peer-grant/1"
_LMK_DOMAIN = b"gh.n3w-product/espnow-lmk/1"


class PeerAuthorizationRejected(RuntimeError):
    """The requested dynamic peer is not authorized."""


class PeerAuthorizationUnavailable(RuntimeError):
    """Required Manager membership, key, eligibility, or replay state is unavailable."""


class NodeApplicationKeyProvider(Protocol):
    def resolve_node_application_key(self, *, node_id: str, key_epoch: int) -> bytes: ...


class RelayEligibilityProvider(Protocol):
    def get_relay_eligibility(self, *, system_id: str, node_id: str) -> RelayEligibilitySnapshot: ...


@dataclass(frozen=True, slots=True, repr=False)
class NodeMembership:
    system_id: str
    hardware_id: str
    node_id: str
    credential_generation: int
    key_epoch: int
    application_key: bytes = field(repr=False)

    def __repr__(self) -> str:
        return (
            "NodeMembership("
            f"system_id={self.system_id!r}, hardware_id={self.hardware_id!r}, "
            f"node_id={self.node_id!r}, credential_generation={self.credential_generation!r}, "
            f"key_epoch={self.key_epoch!r}, application_key=<redacted>)"
        )


@dataclass(frozen=True, slots=True)
class RelayEligibilitySnapshot:
    registered: bool
    same_system: bool
    wifi_up: bool
    uplink_available: bool
    direct_uplink: bool
    relay_capable: bool
    low_battery: bool
    overloaded: bool
    retired: bool
    revoked: bool
    valid_until_ms: int

    def eligible_at(self, now_ms: int) -> bool:
        return (
            self.registered
            and self.same_system
            and self.wifi_up
            and self.uplink_available
            and self.direct_uplink
            and self.relay_capable
            and not self.low_battery
            and not self.overloaded
            and not self.retired
            and not self.revoked
            and now_ms < self.valid_until_ms
        )


@dataclass(frozen=True, slots=True)
class EndpointHandshake:
    node_id: str
    credential_generation: int
    key_epoch: int
    ephemeral_public_key: bytes
    nonce: bytes
    proof: bytes = b""

    def valid_shape(self) -> bool:
        return (
            _ID.fullmatch(self.node_id) is not None
            and isinstance(self.credential_generation, int)
            and not isinstance(self.credential_generation, bool)
            and self.credential_generation >= 1
            and isinstance(self.key_epoch, int)
            and not isinstance(self.key_epoch, bool)
            and self.key_epoch >= 1
            and len(self.ephemeral_public_key) == 32
            and len(self.nonce) == 32
            and len(self.proof) in {0, 32}
        )


@dataclass(frozen=True, slots=True)
class PeerAuthorizationRequest:
    system_id: str
    session_id: str
    requested_at_ms: int
    child: EndpointHandshake
    relay: EndpointHandshake

    def valid_shape(self) -> bool:
        return (
            _ID.fullmatch(self.system_id) is not None
            and _SESSION_ID.fullmatch(self.session_id) is not None
            and isinstance(self.requested_at_ms, int)
            and not isinstance(self.requested_at_ms, bool)
            and self.requested_at_ms >= 0
            and self.child.valid_shape()
            and self.relay.valid_shape()
            and self.child.node_id != self.relay.node_id
        )


@dataclass(frozen=True, slots=True)
class EndpointGrant:
    role: str
    authorization_id: str
    system_id: str
    session_id: str
    child_node_id: str
    relay_node_id: str
    child_credential_generation: int
    relay_credential_generation: int
    child_key_epoch: int
    relay_key_epoch: int
    child_ephemeral_public_key: bytes
    relay_ephemeral_public_key: bytes
    child_nonce: bytes
    relay_nonce: bytes
    issued_at_ms: int
    expires_at_ms: int
    authorization_epoch: int
    grant_mac: bytes = field(repr=False)

    def pair_binding(self) -> bytes:
        return _grant_binding(self)


@dataclass(frozen=True, slots=True)
class PairAuthorization:
    child_grant: EndpointGrant
    relay_grant: EndpointGrant


class RegistrationMembershipResolver:
    """Bind successor peer authorization to existing registration and credential lifecycle state."""

    def __init__(
        self,
        registry: RegistrationRegistry,
        credential_store: CredentialLifecycleStore,
        application_keys: NodeApplicationKeyProvider,
        *,
        system_id: str,
    ) -> None:
        if _ID.fullmatch(system_id) is None:
            raise ValueError("system_id is invalid")
        self.registry = registry
        self.credential_store = credential_store
        self.application_keys = application_keys
        self.system_id = system_id

    def resolve(
        self,
        *,
        system_id: str,
        node_id: str,
        credential_generation: int,
        key_epoch: int,
    ) -> NodeMembership:
        if system_id != self.system_id:
            raise PeerAuthorizationRejected("cross_system_rejected")
        matches = [
            record
            for record in self.registry.list_current()
            if record.node_id == node_id
            and record.state is RegistrationState.APPROVED
            and record.retired_at is None
        ]
        if len(matches) != 1:
            raise PeerAuthorizationRejected("node_not_active")
        record = matches[0]
        try:
            lifecycle = self.credential_store.get(record.hardware_id)
        except KeyError as error:
            raise PeerAuthorizationRejected("credential_lifecycle_missing") from error
        if (
            lifecycle.state is not CredentialState.ACTIVE
            or lifecycle.node_id != node_id
            or lifecycle.active_generation != credential_generation
        ):
            raise PeerAuthorizationRejected("credential_generation_rejected")
        try:
            application_key = self.application_keys.resolve_node_application_key(
                node_id=node_id,
                key_epoch=key_epoch,
            )
        except PeerAuthorizationRejected:
            raise
        except Exception as error:
            raise PeerAuthorizationUnavailable("application_key_unavailable") from error
        if len(application_key) != 32:
            raise PeerAuthorizationUnavailable("application_key_invalid")
        return NodeMembership(
            system_id=system_id,
            hardware_id=record.hardware_id,
            node_id=node_id,
            credential_generation=credential_generation,
            key_epoch=key_epoch,
            application_key=application_key,
        )


class SqlitePeerAuthorizationReplayStore:
    """Persistent single-use request fingerprint registry for Manager-issued peer grants."""

    def __init__(self, path: str) -> None:
        self._lock = threading.RLock()
        try:
            self._connection = sqlite3.connect(
                path,
                isolation_level="IMMEDIATE",
                check_same_thread=False,
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS n3w_product_peer_requests (
                    request_sha256 TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL UNIQUE,
                    accepted_at_ms INTEGER NOT NULL,
                    expires_at_ms INTEGER NOT NULL
                )
                """
            )
        except sqlite3.Error as error:
            raise PeerAuthorizationUnavailable("peer_replay_store_unavailable") from error

    def claim(
        self,
        *,
        request_sha256: str,
        session_id: str,
        now_ms: int,
        expires_at_ms: int,
    ) -> bool:
        with self._lock:
            try:
                with self._connection:
                    self._connection.execute(
                        "DELETE FROM n3w_product_peer_requests WHERE expires_at_ms <= ?",
                        (now_ms,),
                    )
                    self._connection.execute(
                        """
                        INSERT INTO n3w_product_peer_requests (
                            request_sha256, session_id, accepted_at_ms, expires_at_ms
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (request_sha256, session_id, now_ms, expires_at_ms),
                    )
                return True
            except sqlite3.IntegrityError:
                return False
            except sqlite3.Error as error:
                raise PeerAuthorizationUnavailable("peer_replay_store_unavailable") from error

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class PeerAuthorizationService:
    """Manager authority for registered-node, single-hop, dynamic ESP-NOW peer grants."""

    def __init__(
        self,
        membership: RegistrationMembershipResolver,
        eligibility: RelayEligibilityProvider,
        replay_store: SqlitePeerAuthorizationReplayStore,
        *,
        grant_ttl_ms: int = 30_000,
        max_request_skew_ms: int = 10_000,
        authorization_epoch: int = 1,
        uuid_factory=uuid.uuid4,
    ) -> None:
        if grant_ttl_ms < 1 or max_request_skew_ms < 0 or authorization_epoch < 1:
            raise ValueError("peer authorization policy is invalid")
        self.membership = membership
        self.eligibility = eligibility
        self.replay_store = replay_store
        self.grant_ttl_ms = grant_ttl_ms
        self.max_request_skew_ms = max_request_skew_ms
        self.authorization_epoch = authorization_epoch
        self.uuid_factory = uuid_factory

    def authorize(self, request: PeerAuthorizationRequest, *, now_ms: int) -> PairAuthorization:
        if not request.valid_shape() or len(request.child.proof) != 32 or len(request.relay.proof) != 32:
            raise PeerAuthorizationRejected("request_shape_rejected")
        if abs(now_ms - request.requested_at_ms) > self.max_request_skew_ms:
            raise PeerAuthorizationRejected("request_stale")

        child = self.membership.resolve(
            system_id=request.system_id,
            node_id=request.child.node_id,
            credential_generation=request.child.credential_generation,
            key_epoch=request.child.key_epoch,
        )
        relay = self.membership.resolve(
            system_id=request.system_id,
            node_id=request.relay.node_id,
            credential_generation=request.relay.credential_generation,
            key_epoch=request.relay.key_epoch,
        )
        try:
            relay_eligibility = self.eligibility.get_relay_eligibility(
                system_id=request.system_id,
                node_id=request.relay.node_id,
            )
        except PeerAuthorizationRejected:
            raise
        except Exception as error:
            raise PeerAuthorizationUnavailable("relay_eligibility_unavailable") from error
        if not relay_eligibility.eligible_at(now_ms):
            raise PeerAuthorizationRejected("relay_not_eligible")

        child_auth_key = derive_relay_auth_key(child)
        relay_auth_key = derive_relay_auth_key(relay)
        if not verify_endpoint_proof(request, role=_ROLE_CHILD, relay_auth_key=child_auth_key):
            raise PeerAuthorizationRejected("child_proof_rejected")
        if not verify_endpoint_proof(request, role=_ROLE_RELAY, relay_auth_key=relay_auth_key):
            raise PeerAuthorizationRejected("relay_proof_rejected")

        expires_at_ms = min(now_ms + self.grant_ttl_ms, relay_eligibility.valid_until_ms)
        if expires_at_ms <= now_ms:
            raise PeerAuthorizationRejected("relay_eligibility_expired")
        request_sha256 = hashlib.sha256(
            _request_core(request) + request.child.proof + request.relay.proof
        ).hexdigest()
        if not self.replay_store.claim(
            request_sha256=request_sha256,
            session_id=request.session_id,
            now_ms=now_ms,
            expires_at_ms=expires_at_ms,
        ):
            raise PeerAuthorizationRejected("request_replayed")

        authorization_id = str(self.uuid_factory())
        common = dict(
            authorization_id=authorization_id,
            system_id=request.system_id,
            session_id=request.session_id,
            child_node_id=request.child.node_id,
            relay_node_id=request.relay.node_id,
            child_credential_generation=request.child.credential_generation,
            relay_credential_generation=request.relay.credential_generation,
            child_key_epoch=request.child.key_epoch,
            relay_key_epoch=request.relay.key_epoch,
            child_ephemeral_public_key=request.child.ephemeral_public_key,
            relay_ephemeral_public_key=request.relay.ephemeral_public_key,
            child_nonce=request.child.nonce,
            relay_nonce=request.relay.nonce,
            issued_at_ms=now_ms,
            expires_at_ms=expires_at_ms,
            authorization_epoch=self.authorization_epoch,
        )
        child_unsigned = EndpointGrant(role=_ROLE_CHILD, grant_mac=b"", **common)
        relay_unsigned = EndpointGrant(role=_ROLE_RELAY, grant_mac=b"", **common)
        child_grant = EndpointGrant(
            role=_ROLE_CHILD,
            grant_mac=hmac.new(
                child_auth_key,
                _GRANT_DOMAIN + b"\x00child\x00" + _grant_binding(child_unsigned),
                hashlib.sha256,
            ).digest(),
            **common,
        )
        relay_grant = EndpointGrant(
            role=_ROLE_RELAY,
            grant_mac=hmac.new(
                relay_auth_key,
                _GRANT_DOMAIN + b"\x00relay\x00" + _grant_binding(relay_unsigned),
                hashlib.sha256,
            ).digest(),
            **common,
        )
        return PairAuthorization(child_grant=child_grant, relay_grant=relay_grant)


def derive_relay_auth_key(membership: NodeMembership) -> bytes:
    info = b"\x00".join(
        (
            _AUTH_KEY_INFO,
            membership.system_id.encode("ascii"),
            membership.node_id.encode("ascii"),
            str(membership.credential_generation).encode("ascii"),
            str(membership.key_epoch).encode("ascii"),
        )
    )
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(
        membership.application_key
    )


def build_endpoint_proof(
    request: PeerAuthorizationRequest,
    *,
    role: str,
    relay_auth_key: bytes,
) -> bytes:
    if role not in {_ROLE_CHILD, _ROLE_RELAY} or len(relay_auth_key) != 32:
        raise ValueError("endpoint proof inputs are invalid")
    return hmac.new(
        relay_auth_key,
        _PROOF_DOMAIN + b"\x00" + role.encode("ascii") + b"\x00" + _request_core(request),
        hashlib.sha256,
    ).digest()


def verify_endpoint_proof(
    request: PeerAuthorizationRequest,
    *,
    role: str,
    relay_auth_key: bytes,
) -> bool:
    endpoint = request.child if role == _ROLE_CHILD else request.relay
    if role not in {_ROLE_CHILD, _ROLE_RELAY} or len(endpoint.proof) != 32:
        return False
    expected = build_endpoint_proof(request, role=role, relay_auth_key=relay_auth_key)
    return hmac.compare_digest(endpoint.proof, expected)


def verify_endpoint_grant(
    grant: EndpointGrant,
    *,
    relay_auth_key: bytes,
    now_ms: int,
) -> bool:
    if grant.role not in {_ROLE_CHILD, _ROLE_RELAY} or len(grant.grant_mac) != 32:
        return False
    if now_ms < grant.issued_at_ms or now_ms >= grant.expires_at_ms:
        return False
    expected = hmac.new(
        relay_auth_key,
        _GRANT_DOMAIN + b"\x00" + grant.role.encode("ascii") + b"\x00" + _grant_binding(grant),
        hashlib.sha256,
    ).digest()
    return hmac.compare_digest(grant.grant_mac, expected)


def derive_pair_lmk(
    *,
    local_private_key: bytes,
    peer_public_key: bytes,
    grant: EndpointGrant,
) -> bytes:
    """Node-side reference derivation. Manager authorization code never calls this function."""
    if len(local_private_key) != 32 or len(peer_public_key) != 32:
        raise ValueError("X25519 key material must be 32 bytes")
    shared = X25519PrivateKey.from_private_bytes(local_private_key).exchange(
        X25519PublicKey.from_public_bytes(peer_public_key)
    )
    binding = _grant_binding(grant)
    salt = hashlib.sha256(_LMK_DOMAIN + b"\x00salt\x00" + binding).digest()
    return HKDF(
        algorithm=hashes.SHA256(),
        length=16,
        salt=salt,
        info=_LMK_DOMAIN + b"\x00derive\x00" + binding,
    ).derive(shared)


def _request_core(request: PeerAuthorizationRequest) -> bytes:
    fields = [
        "gh.n3w-product.peer-request/1",
        request.system_id,
        request.session_id,
        str(request.requested_at_ms),
        request.child.node_id,
        str(request.child.credential_generation),
        str(request.child.key_epoch),
        _b64(request.child.ephemeral_public_key),
        _b64(request.child.nonce),
        request.relay.node_id,
        str(request.relay.credential_generation),
        str(request.relay.key_epoch),
        _b64(request.relay.ephemeral_public_key),
        _b64(request.relay.nonce),
    ]
    return "\n".join(fields).encode("ascii")


def _grant_binding(grant: EndpointGrant) -> bytes:
    fields = [
        "gh.n3w-product.peer-grant-binding/1",
        grant.authorization_id,
        grant.system_id,
        grant.session_id,
        grant.child_node_id,
        grant.relay_node_id,
        str(grant.child_credential_generation),
        str(grant.relay_credential_generation),
        str(grant.child_key_epoch),
        str(grant.relay_key_epoch),
        _b64(grant.child_ephemeral_public_key),
        _b64(grant.relay_ephemeral_public_key),
        _b64(grant.child_nonce),
        _b64(grant.relay_nonce),
        str(grant.issued_at_ms),
        str(grant.expires_at_ms),
        str(grant.authorization_epoch),
    ]
    return "\n".join(fields).encode("ascii")


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")