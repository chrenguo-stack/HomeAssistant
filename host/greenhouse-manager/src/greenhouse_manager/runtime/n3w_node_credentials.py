from __future__ import annotations

import base64
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from .credential_lifecycle import CredentialLifecycleStore, CredentialState
from .pairing_service import (
    CredentialBundle,
    PairingProvisioningError,
    PairingRollbackError,
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
