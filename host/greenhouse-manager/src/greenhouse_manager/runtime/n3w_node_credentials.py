from __future__ import annotations

import base64
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from .credential_lifecycle import (
    CredentialLifecycle,
    CredentialLifecycleStore,
    CredentialState,
)
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


@dataclass(frozen=True, slots=True, repr=False)
class ProductApplicationKeyMaterial:
    node_id: str
    key_epoch: int
    application_key: bytes = field(repr=False)

    def __repr__(self) -> str:
        return (
            "ProductApplicationKeyMaterial("
            f"node_id={self.node_id!r}, "
            f"key_epoch={self.key_epoch!r}, "
            "application_key=<redacted>)"
        )


class ManagedApplicationKeyLifecycle:
    """Independent N3-W application-key lifecycle.

    This API has no MQTT credential-generation or credential-store
    dependency.
    """

    def __init__(
        self,
        application_keys: ProductApplicationKeyAdmin,
        *,
        random_bytes: Callable[[int], bytes] = secrets.token_bytes,
    ) -> None:
        self.application_keys = application_keys
        self.random_bytes = random_bytes
        self._lock = threading.RLock()

    def _stage(
        self,
        *,
        node_id: str,
    ) -> ProductApplicationKeyMaterial:
        application_key = self.random_bytes(32)

        if len(application_key) != 32:
            raise PairingProvisioningError(
                "product application-key generator returned invalid length"
            )

        try:
            result = self.application_keys.stage_key(
                node_id=node_id,
                key_material=application_key,
            )
        except Exception as error:
            raise PairingProvisioningError(
                "product application-key staging failed"
            ) from error

        key_epoch = result.get("key_epoch")

        if (
            not isinstance(key_epoch, int)
            or isinstance(key_epoch, bool)
            or key_epoch < 1
        ):
            raise PairingProvisioningError(
                "product application-key epoch is invalid"
            )

        return ProductApplicationKeyMaterial(
            node_id=node_id,
            key_epoch=key_epoch,
            application_key=application_key,
        )

    def stage_initial(
        self,
        *,
        node_id: str,
    ) -> ProductApplicationKeyMaterial:
        return self._stage(
            node_id=node_id,
        )

    def activate_initial(
        self,
        material: ProductApplicationKeyMaterial,
    ) -> None:
        try:
            self.application_keys.activate_key(
                node_id=material.node_id,
                key_epoch=material.key_epoch,
            )
        except Exception as error:
            raise PairingProvisioningError(
                "product application-key initial activation failed"
            ) from error

    def rollback_initial(
        self,
        material: ProductApplicationKeyMaterial,
    ) -> None:
        try:
            self.application_keys.revoke_key(
                node_id=material.node_id,
                key_epoch=material.key_epoch,
            )
        except Exception as error:
            raise PairingRollbackError(
                "product application-key initial rollback failed"
            ) from error

    def stage_rotation(
        self,
        *,
        node_id: str,
    ) -> ProductApplicationKeyMaterial:
        return self._stage(
            node_id=node_id,
        )

    def activate_rotation(
        self,
        material: ProductApplicationKeyMaterial,
    ) -> None:
        try:
            self.application_keys.activate_key(
                node_id=material.node_id,
                key_epoch=material.key_epoch,
            )
        except Exception as error:
            raise PairingProvisioningError(
                "product application-key rotation activation failed"
            ) from error

    def rollback_staged_rotation(
        self,
        material: ProductApplicationKeyMaterial,
    ) -> None:
        try:
            self.application_keys.revoke_key(
                node_id=material.node_id,
                key_epoch=material.key_epoch,
            )
        except Exception as error:
            raise PairingRollbackError(
                "staged application-key rotation rollback failed"
            ) from error

    def rollback_active_rotation(
        self,
        material: ProductApplicationKeyMaterial,
    ) -> None:
        try:
            self.application_keys.rollback_rotation(
                node_id=material.node_id,
                key_epoch=material.key_epoch,
            )
        except Exception as error:
            raise PairingRollbackError(
                "active application-key rotation rollback failed"
            ) from error


class ManagedMqttCredentialLifecycle:
    """Independent MQTT credential-generation lifecycle.

    This API has no N3-W application-key admin or key-epoch dependency.
    """

    def __init__(
        self,
        credential_store: CredentialLifecycleStore,
    ) -> None:
        self.credential_store = credential_store
        self._lock = threading.RLock()

    def ensure_first_registration(
        self,
        *,
        hardware_id: str,
        credential_generation: int,
    ) -> None:
        if (
            not isinstance(credential_generation, int)
            or isinstance(credential_generation, bool)
            or credential_generation != 1
        ):
            raise PairingProvisioningError(
                "first registration credential generation must be 1"
            )

        try:
            self.credential_store.get(
                hardware_id
            )
        except KeyError:
            return

        raise PairingProvisioningError(
            "product credential lifecycle already exists"
        )

    def activate_initial(
        self,
        *,
        hardware_id: str,
        pairing_id: str,
        node_id: str,
        credential_generation: int,
        now: datetime | None = None,
    ) -> CredentialLifecycle:
        with self._lock:
            try:
                existing = (
                    self.credential_store.get(
                        hardware_id
                    )
                )
            except KeyError:
                existing = None

            if existing is not None:
                if (
                    existing.state
                    is CredentialState.ACTIVE
                    and existing.node_id
                    == node_id
                    and existing.active_generation
                    == credential_generation
                    and existing.pairing_id
                    == pairing_id
                ):
                    return existing

                raise PairingProvisioningError(
                    "product credential lifecycle already exists"
                )

            try:
                return self.credential_store.activate(
                    hardware_id=hardware_id,
                    pairing_id=pairing_id,
                    node_id=node_id,
                    generation=credential_generation,
                    now=now,
                )
            except Exception as error:
                raise PairingProvisioningError(
                    "MQTT credential initial activation failed"
                ) from error

    def begin_rotation(
        self,
        hardware_id: str,
        *,
        credential_generation: int,
        now: datetime | None = None,
    ) -> CredentialLifecycle:
        try:
            return self.credential_store.begin_rotation(
                hardware_id,
                generation=credential_generation,
                now=now,
            )
        except Exception as error:
            raise PairingProvisioningError(
                "MQTT credential rotation start failed"
            ) from error

    def commit_rotation(
        self,
        hardware_id: str,
        *,
        now: datetime | None = None,
    ) -> CredentialLifecycle:
        try:
            return self.credential_store.commit_rotation(
                hardware_id,
                now=now,
            )
        except Exception as error:
            raise PairingProvisioningError(
                "MQTT credential rotation commit failed"
            ) from error

    def rollback_rotation(
        self,
        hardware_id: str,
        *,
        reason: str = "candidate_verification_failed",
        now: datetime | None = None,
    ) -> CredentialLifecycle:
        try:
            return self.credential_store.roll_back_rotation(
                hardware_id,
                reason=reason,
                now=now,
            )
        except Exception as error:
            raise PairingRollbackError(
                "MQTT credential rotation rollback failed"
            ) from error

    def require_recovery(
        self,
        hardware_id: str,
        *,
        reason: str,
        now: datetime | None = None,
    ) -> CredentialLifecycle:
        try:
            return self.credential_store.require_recovery(
                hardware_id,
                reason=reason,
                now=now,
            )
        except Exception as error:
            raise PairingProvisioningError(
                "MQTT credential recovery transition failed"
            ) from error


class ManagedProductCredentialIssuer:
    """First-registration composer only.

    Pairing may initialize MQTT generation 1 and the initial N3-W
    application key in one reversible transaction. Rotation of either
    lifecycle is deliberately excluded from this interface.
    """

    def __init__(
        self,
        application_keys: ManagedApplicationKeyLifecycle,
        mqtt_credentials: ManagedMqttCredentialLifecycle,
    ) -> None:
        self.application_keys = application_keys
        self.mqtt_credentials = mqtt_credentials
        self._lock = threading.RLock()

    def stage(
        self,
        *,
        hardware_id: str,
        pairing_id: str,
        node_id: str,
        credential_generation: int,
    ) -> ProductCredentialMaterial:
        self.mqtt_credentials.ensure_first_registration(
            hardware_id=hardware_id,
            credential_generation=credential_generation,
        )

        key_material = (
            self.application_keys.stage_initial(
                node_id=node_id,
            )
        )

        return ProductCredentialMaterial(
            hardware_id=hardware_id,
            pairing_id=pairing_id,
            node_id=node_id,
            credential_generation=credential_generation,
            key_epoch=key_material.key_epoch,
            application_key=key_material.application_key,
        )

    @staticmethod
    def _application_material(
        material: ProductCredentialMaterial,
    ) -> ProductApplicationKeyMaterial:
        return ProductApplicationKeyMaterial(
            node_id=material.node_id,
            key_epoch=material.key_epoch,
            application_key=material.application_key,
        )

    def commit(
        self,
        material: ProductCredentialMaterial,
        *,
        now: datetime | None = None,
    ) -> None:
        with self._lock:
            application_material = (
                self._application_material(
                    material
                )
            )

            self.application_keys.activate_initial(
                application_material
            )

            try:
                self.mqtt_credentials.activate_initial(
                    hardware_id=material.hardware_id,
                    pairing_id=material.pairing_id,
                    node_id=material.node_id,
                    credential_generation=(
                        material.credential_generation
                    ),
                    now=now,
                )
            except Exception:
                try:
                    self.application_keys.rollback_initial(
                        application_material
                    )
                except Exception as rollback_error:
                    raise PairingRollbackError(
                        "first-registration application-key rollback failed"
                    ) from rollback_error
                raise

    def rollback(
        self,
        material: ProductCredentialMaterial,
    ) -> None:
        self.application_keys.rollback_initial(
            self._application_material(
                material
            )
        )

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
