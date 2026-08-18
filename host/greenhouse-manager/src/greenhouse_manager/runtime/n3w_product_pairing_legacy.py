from __future__ import annotations

import base64
import json
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from .credential_lifecycle import CredentialLifecycleStore, CredentialState
from .pairing_secure_transport import (
    SecureEnvelope,
    SecurePairingConflict,
    SecurePairingCoordinator,
    SecurePairingRollbackError,
    SecurePairingState,
)
from .pairing_service import (
    CredentialBundle,
    PairingProvisioningError,
    PairingRollbackError,
    PairingSessionManager,
    PairingSessionSnapshot,
    PairingSessionState,
)


class ProductApplicationKeyAdmin(Protocol):
    def stage_key(self, *, node_id: str, key_material: bytes) -> dict[str, object]: ...

    def activate_key(self, *, node_id: str, key_epoch: int) -> dict[str, object]: ...

    def revoke_key(self, *, node_id: str, key_epoch: int) -> dict[str, object]: ...

    def rollback_rotation(self, *, node_id: str, key_epoch: int) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True, repr=False)
class ProductCredentialMaterial:
    hardware_id: str
    pairing_id: str
    node_id: str
    credential_generation: int
    key_epoch: int
    application_key: bytes = field(repr=False)

    def __repr__(self) -> str:
        return (
            "ProductCredentialMaterial("
            f"hardware_id={self.hardware_id!r}, pairing_id={self.pairing_id!r}, "
            f"node_id={self.node_id!r}, credential_generation={self.credential_generation!r}, "
            f"key_epoch={self.key_epoch!r}, application_key=<redacted>)"
        )


class ProductCredentialIssuer(Protocol):
    def stage(
        self,
        *,
        hardware_id: str,
        pairing_id: str,
        node_id: str,
        credential_generation: int,
    ) -> ProductCredentialMaterial: ...

    def commit(self, material: ProductCredentialMaterial, *, now: datetime | None = None) -> None: ...

    def rollback(self, material: ProductCredentialMaterial) -> None: ...


class ManagedProductCredentialIssuer:
    """Stage a node-only N3-W key, then activate it only after encrypted delivery ack."""

    def __init__(
        self,
        application_keys: ProductApplicationKeyAdmin,
        credential_store: CredentialLifecycleStore,
        *,
        random_bytes: Callable[[int], bytes] = secrets.token_bytes,
    ) -> None:
        self.application_keys = application_keys
        self.credential_store = credential_store
        self.random_bytes = random_bytes
        self._lock = threading.RLock()

    def stage(
        self,
        *,
        hardware_id: str,
        pairing_id: str,
        node_id: str,
        credential_generation: int,
    ) -> ProductCredentialMaterial:
        application_key = self.random_bytes(32)
        if len(application_key) != 32:
            raise PairingProvisioningError("product application-key generator returned invalid length")
        try:
            result = self.application_keys.stage_key(
                node_id=node_id,
                key_material=application_key,
            )
        except Exception as error:
            raise PairingProvisioningError("product application-key staging failed") from error
        key_epoch = result.get("key_epoch")
        if not isinstance(key_epoch, int) or isinstance(key_epoch, bool) or key_epoch < 1:
            raise PairingProvisioningError("product application-key staging returned invalid epoch")
        return ProductCredentialMaterial(
            hardware_id=hardware_id,
            pairing_id=pairing_id,
            node_id=node_id,
            credential_generation=credential_generation,
            key_epoch=key_epoch,
            application_key=application_key,
        )

    def commit(self, material: ProductCredentialMaterial, *, now: datetime | None = None) -> None:
        with self._lock:
            try:
                lifecycle = self.credential_store.get(material.hardware_id)
            except KeyError:
                lifecycle = None

            if lifecycle is None:
                self._commit_first_assignment(material, now=now)
                return
            if (
                lifecycle.state is CredentialState.ACTIVE
                and lifecycle.node_id == material.node_id
                and lifecycle.active_generation == material.credential_generation
            ):
                return
            if lifecycle.state is not CredentialState.ACTIVE or lifecycle.node_id != material.node_id:
                raise PairingProvisioningError("product credential lifecycle is not rotatable")
            if material.credential_generation <= lifecycle.active_generation:
                raise PairingProvisioningError("product credential generation did not advance")
            self._commit_rotation(material, now=now)

    def _commit_first_assignment(
        self,
        material: ProductCredentialMaterial,
        *,
        now: datetime | None,
    ) -> None:
        activated = False
        try:
            self.application_keys.activate_key(
                node_id=material.node_id,
                key_epoch=material.key_epoch,
            )
            activated = True
            self.credential_store.activate(
                hardware_id=material.hardware_id,
                pairing_id=material.pairing_id,
                node_id=material.node_id,
                generation=material.credential_generation,
                now=now,
            )
        except Exception as error:
            if activated:
                try:
                    self.application_keys.revoke_key(
                        node_id=material.node_id,
                        key_epoch=material.key_epoch,
                    )
                except Exception as rollback_error:
                    raise PairingRollbackError(
                        "product credential first-assignment rollback failed"
                    ) from rollback_error
            if isinstance(error, (PairingProvisioningError, PairingRollbackError)):
                raise
            raise PairingProvisioningError("product credential activation failed") from error

    def _commit_rotation(
        self,
        material: ProductCredentialMaterial,
        *,
        now: datetime | None,
    ) -> None:
        rotation_started = False
        key_activated = False
        try:
            self.credential_store.begin_rotation(
                material.hardware_id,
                generation=material.credential_generation,
                now=now,
            )
            rotation_started = True
            self.application_keys.activate_key(
                node_id=material.node_id,
                key_epoch=material.key_epoch,
            )
            key_activated = True
            self.credential_store.commit_rotation(material.hardware_id, now=now)
        except Exception as error:
            rollback_failures: list[Exception] = []
            if key_activated:
                try:
                    self.application_keys.rollback_rotation(
                        node_id=material.node_id,
                        key_epoch=material.key_epoch,
                    )
                except Exception as rollback_error:
                    rollback_failures.append(rollback_error)
            else:
                try:
                    self.application_keys.revoke_key(
                        node_id=material.node_id,
                        key_epoch=material.key_epoch,
                    )
                except Exception as rollback_error:
                    rollback_failures.append(rollback_error)
            if rotation_started:
                try:
                    self.credential_store.roll_back_rotation(
                        material.hardware_id,
                        reason="product_key_activation_failed",
                        now=now,
                    )
                except Exception as rollback_error:
                    rollback_failures.append(rollback_error)
            if rollback_failures:
                raise PairingRollbackError(
                    "product credential rotation rollback failed"
                ) from rollback_failures[0]
            raise PairingProvisioningError("product credential rotation failed") from error

    def rollback(self, material: ProductCredentialMaterial) -> None:
        try:
            self.application_keys.revoke_key(
                node_id=material.node_id,
                key_epoch=material.key_epoch,
            )
        except Exception as error:
            raise PairingRollbackError("staged product credential rollback failed") from error


def _encode_base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


@dataclass(frozen=True, slots=True, repr=False)
class ProductCredentialBundle:
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
    n3w_key_epoch: int
    mqtt_password: str = field(repr=False)
    n3w_application_key: str = field(repr=False)

    @classmethod
    def from_base(
        cls,
        base: CredentialBundle,
        material: ProductCredentialMaterial,
    ) -> ProductCredentialBundle:
        return cls(
            schema=base.schema,
            system_id=base.system_id,
            node_id=base.node_id,
            broker_host=base.broker_host,
            broker_port=base.broker_port,
            broker_tls_server_name=base.broker_tls_server_name,
            ca_pem=base.ca_pem,
            mqtt_username=base.mqtt_username,
            mqtt_client_id=base.mqtt_client_id,
            credential_generation=base.credential_generation,
            mqtt_password=base.mqtt_password,
            n3w_key_epoch=material.key_epoch,
            n3w_application_key=_encode_base64url(material.application_key),
        )

    def __repr__(self) -> str:
        return (
            "ProductCredentialBundle("
            f"schema={self.schema!r}, system_id={self.system_id!r}, node_id={self.node_id!r}, "
            f"broker_host={self.broker_host!r}, broker_port={self.broker_port!r}, "
            f"broker_tls_server_name={self.broker_tls_server_name!r}, ca_pem=<certificate>, "
            f"mqtt_username={self.mqtt_username!r}, mqtt_client_id={self.mqtt_client_id!r}, "
            f"credential_generation={self.credential_generation!r}, "
            f"n3w_key_epoch={self.n3w_key_epoch!r}, mqtt_password=<redacted>, "
            "n3w_application_key=<redacted>)"
        )


class ProductPairingCore:
    """Product wrapper around the existing pairing core with staged N3-W node credentials."""

    def __init__(self, core: PairingSessionManager, issuer: ProductCredentialIssuer) -> None:
        self.core = core
        self.issuer = issuer
        self._lock = threading.RLock()
        self._materials: dict[str, ProductCredentialMaterial] = {}
        self._bundles: dict[str, ProductCredentialBundle] = {}

    def open_session(self, *args, **kwargs):
        return self.core.open_session(*args, **kwargs)

    def verify_proof(self, *args, **kwargs):
        return self.core.verify_proof(*args, **kwargs)

    def issue_credentials(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> ProductCredentialBundle:
        with self._lock:
            existing = self._bundles.get(session_id)
            if existing is not None:
                return existing
            base = self.core.issue_credentials(session_id, now=now)
            snapshot = self.core.status(session_id, now=now)
            try:
                material = self.issuer.stage(
                    hardware_id=snapshot.hardware_id,
                    pairing_id=snapshot.pairing_id,
                    node_id=base.node_id,
                    credential_generation=base.credential_generation,
                )
            except Exception as error:
                try:
                    self.core.abort(session_id)
                except Exception as rollback_error:
                    raise PairingRollbackError(
                        "broker identity rollback after product staging failure failed"
                    ) from rollback_error
                if isinstance(error, (PairingProvisioningError, PairingRollbackError)):
                    raise
                raise PairingProvisioningError("product credential staging failed") from error
            bundle = ProductCredentialBundle.from_base(base, material)
            self._materials[session_id] = material
            self._bundles[session_id] = bundle
            return bundle

    def acknowledge_delivery(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> PairingSessionSnapshot:
        with self._lock:
            material = self._materials.get(session_id)
            if material is None:
                raise PairingProvisioningError("product credentials were not staged")
            snapshot = self.core.status(session_id, now=now)
            if snapshot.state is not PairingSessionState.CREDENTIALS_ISSUED:
                raise PairingProvisioningError("product credential acknowledgement state is invalid")
            self.issuer.commit(material, now=now)
            consumed = self.core.acknowledge_delivery(session_id, now=now)
            self._materials.pop(session_id, None)
            self._bundles.pop(session_id, None)
            return consumed

    def abort(self, session_id: str) -> PairingSessionSnapshot:
        with self._lock:
            material = self._materials.pop(session_id, None)
            self._bundles.pop(session_id, None)
            failures: list[Exception] = []
            if material is not None:
                try:
                    self.issuer.rollback(material)
                except Exception as error:
                    failures.append(error)
            try:
                snapshot = self.core.abort(session_id)
            except Exception as error:
                failures.append(error)
                snapshot = None
            if failures:
                raise PairingRollbackError("product pairing rollback failed") from failures[0]
            if snapshot is None:
                raise PairingRollbackError("product pairing rollback produced no snapshot")
            return snapshot

    def expire_sessions(self, *, now: datetime | None = None) -> int:
        try:
            expired = self.core.expire_sessions(now=now)
        finally:
            self._rollback_terminal_materials(now=now)
        return expired

    def status(self, session_id: str, *, now: datetime | None = None) -> PairingSessionSnapshot:
        snapshot = self.core.status(session_id, now=now)
        self._rollback_if_terminal(session_id, snapshot)
        return snapshot

    def _rollback_terminal_materials(self, *, now: datetime | None) -> None:
        with self._lock:
            for session_id in tuple(self._materials):
                snapshot = self.core.status(session_id, now=now)
                self._rollback_if_terminal(session_id, snapshot)

    def _rollback_if_terminal(self, session_id: str, snapshot: PairingSessionSnapshot) -> None:
        if snapshot.state not in {PairingSessionState.EXPIRED, PairingSessionState.FAILED}:
            return
        material = self._materials.pop(session_id, None)
        self._bundles.pop(session_id, None)
        if material is not None:
            self.issuer.rollback(material)


class ProductSecurePairingCoordinator(SecurePairingCoordinator):
    """Encrypt the node's own N3-W application key inside the existing secure pairing channel."""

    def issue_encrypted_credentials(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> SecureEnvelope:
        with self._lock:
            session = self._require_session(session_id)
            if session.state == SecurePairingState.CREDENTIALS_ENCRYPTED and session.envelope is not None:
                return session.envelope
            if session.state != SecurePairingState.CHANNEL_ESTABLISHED or session.channel is None:
                raise SecurePairingConflict("credentials require an established secure channel")
            bundle = self.core.issue_credentials(session_id, now=now)
            if not isinstance(bundle, ProductCredentialBundle):
                raise SecurePairingConflict("product pairing core returned legacy credentials")
            try:
                document = {
                    "broker_host": bundle.broker_host,
                    "broker_port": bundle.broker_port,
                    "broker_tls_server_name": bundle.broker_tls_server_name,
                    "ca_pem": bundle.ca_pem,
                    "credential_generation": bundle.credential_generation,
                    "mqtt_client_id": bundle.mqtt_client_id,
                    "mqtt_password": bundle.mqtt_password,
                    "mqtt_username": bundle.mqtt_username,
                    "n3w_application_key": bundle.n3w_application_key,
                    "n3w_key_epoch": bundle.n3w_key_epoch,
                    "node_id": bundle.node_id,
                    "schema": bundle.schema,
                    "system_id": bundle.system_id,
                }
                plaintext = json.dumps(
                    document,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                ).encode("utf-8")
                envelope = session.channel.encrypt(
                    plaintext,
                    content_type="gh.pair.credentials/1",
                )
            except Exception as encryption_error:
                try:
                    self.core.abort(session_id)
                except Exception:
                    session.state = SecurePairingState.FAILED
                    self._clear_sensitive(session)
                    raise SecurePairingRollbackError(
                        "product credential encryption cleanup failed"
                    ) from encryption_error
                session.state = SecurePairingState.FAILED
                self._clear_sensitive(session)
                raise SecurePairingConflict("product credential encryption failed") from encryption_error
            session.envelope = envelope
            session.bundle = bundle
            session.credential_generation = bundle.credential_generation
            session.state = SecurePairingState.CREDENTIALS_ENCRYPTED
            return envelope