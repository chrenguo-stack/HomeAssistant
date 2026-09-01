from __future__ import annotations

import base64
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .credential_lifecycle import CredentialState
from .dynsec_plan import (
    NodeCredentials,
    NodeProvisioningPlan,
    build_node_provisioning_plan,
    generate_node_credentials,
)
from .n3w_node_application_keys import (
    NodeApplicationKeyStoreUnavailable,
    SqliteNodeApplicationKeyAdmin,
    SqliteNodeApplicationKeyProvider,
)
from .n3w_node_credentials import (
    ManagedProductCredentialIssuer,
    ProductCredentialBundle,
    ProductCredentialIssuer,
    ProductCredentialMaterial,
)
from .n3w_simplified_credentials import (
    SimplifiedCredentialBundleIssuer,
    SimplifiedProductCredentialBundle,
)
from .pairing_service import (
    CredentialBundle,
    NodeIdentityProvisioner,
    PairingProvisioningError,
    PairingRollbackError,
)


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


@dataclass(slots=True)
class StagedProvisionedSimplifiedBundle:
    """One reversible first-registration Broker + application-key transaction."""

    bundle: SimplifiedProductCredentialBundle
    plan: NodeProvisioningPlan
    credentials: NodeCredentials
    material: ProductCredentialMaterial
    identity_provisioner: NodeIdentityProvisioner
    product_issuer: ProductCredentialIssuer
    committed: bool = False
    rolled_back: bool = False

    def commit(self, *, now: datetime | None = None) -> None:
        if self.rolled_back:
            raise PairingRollbackError("simplified credential stage already rolled back")
        if self.committed:
            return
        try:
            self.product_issuer.commit(self.material, now=now)
        except Exception:
            self._rollback_broker_only()
            raise
        self.committed = True

    def rollback(self) -> None:
        if self.committed or self.rolled_back:
            return
        failures: list[Exception] = []
        try:
            self.product_issuer.rollback(self.material)
        except Exception as error:
            failures.append(error)
        try:
            self.identity_provisioner.deprovision(self.plan)
        except Exception as error:
            failures.append(error)
        self.rolled_back = True
        if failures:
            raise PairingRollbackError("simplified credential rollback failed") from failures[0]

    def _rollback_broker_only(self) -> None:
        try:
            self.identity_provisioner.deprovision(self.plan)
        except Exception as error:
            raise PairingRollbackError("simplified broker rollback failed") from error


@dataclass(slots=True)
class StagedRecoveredSimplifiedBundle:
    """One explicit existing-identity MQTT credential recovery transaction.

    No Broker mutation occurs during stage. The node first persists the
    encrypted recovery bundle. Its final delivery receipt then commits the
    Broker password replacement followed by the secret-free credential
    generation lifecycle. The existing N3-W application key and system peer
    trust are re-delivered without rotation.
    """

    bundle: SimplifiedProductCredentialBundle
    plan: NodeProvisioningPlan
    credentials: NodeCredentials
    hardware_id: str
    pairing_id: str
    identity_provisioner: NodeIdentityProvisioner
    product_issuer: ManagedProductCredentialIssuer
    committed: bool = False
    rolled_back: bool = False
    broker_password_applied: bool = False

    def commit(self, *, now: datetime | None = None) -> None:
        if self.rolled_back:
            raise PairingRollbackError("credential recovery stage already rolled back")
        if self.committed:
            return

        setter = getattr(self.identity_provisioner, "set_password", None)
        if not callable(setter):
            raise PairingProvisioningError(
                "credential recovery identity provisioner unavailable"
            )

        setter(self.plan, self.credentials)
        self.broker_password_applied = True

        # Broker password is the externally authoritative secret mutation.
        # Only after that succeeds may the secret-free local generation move
        # from ROTATING to ACTIVE. A failure between these two operations is
        # deliberately fail-closed and must not be mislabeled as a rollback.
        self.product_issuer.mqtt_credentials.commit_rotation(
            self.hardware_id,
            now=now,
        )
        self.committed = True

    def rollback(self) -> None:
        if self.committed or self.rolled_back:
            return
        if self.broker_password_applied:
            raise PairingRollbackError(
                "credential recovery broker password already applied"
            )
        self.product_issuer.mqtt_credentials.rollback_rotation(
            self.hardware_id,
            reason="credential_recovery_delivery_rolled_back",
        )
        self.rolled_back = True


class SimplifiedProvisioningStager:
    """Build first-registration or explicit recovery `gh.pair.credentials/2`.

    Ordinary registered pairing still stops before mutation. The recovery path
    is reachable only after the pairing coordinator has consumed a separate,
    bounded credential-recovery authorization for the exact hardware/pairing
    transaction.
    """

    def __init__(
        self,
        *,
        identity_provisioner: NodeIdentityProvisioner,
        product_issuer: ProductCredentialIssuer,
        simplified_issuer: SimplifiedCredentialBundleIssuer,
        system_id: str,
        broker_host: str,
        broker_port: int,
        broker_tls_server_name: str,
        ca_pem: str,
    ) -> None:
        self.identity_provisioner = identity_provisioner
        self.product_issuer = product_issuer
        self.simplified_issuer = simplified_issuer
        self.system_id = system_id
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.broker_tls_server_name = broker_tls_server_name
        self.ca_pem = ca_pem

    def stage(
        self,
        *,
        hardware_id: str,
        pairing_id: str,
        node_id: str,
        credential_generation: int,
    ) -> StagedProvisionedSimplifiedBundle:
        plan = build_node_provisioning_plan(
            system_id=self.system_id,
            node_id=node_id,
            generation=credential_generation,
        )
        credentials = generate_node_credentials(plan)
        self.identity_provisioner.provision(plan, credentials)
        try:
            material = self.product_issuer.stage(
                hardware_id=hardware_id,
                pairing_id=pairing_id,
                node_id=node_id,
                credential_generation=credential_generation,
            )
        except Exception:
            self.identity_provisioner.deprovision(plan)
            raise
        try:
            base = CredentialBundle(
                schema="gh.pair.credentials/1",
                system_id=self.system_id,
                node_id=node_id,
                broker_host=self.broker_host,
                broker_port=self.broker_port,
                broker_tls_server_name=self.broker_tls_server_name,
                ca_pem=self.ca_pem,
                mqtt_username=credentials.username,
                mqtt_client_id=credentials.client_id,
                credential_generation=credentials.generation,
                mqtt_password=credentials.password,
            )
            product = ProductCredentialBundle.from_base(base, material)
            simplified = self.simplified_issuer.issue(product)
            return StagedProvisionedSimplifiedBundle(
                bundle=simplified,
                plan=plan,
                credentials=credentials,
                material=material,
                identity_provisioner=self.identity_provisioner,
                product_issuer=self.product_issuer,
            )
        except Exception:
            failures: list[Exception] = []
            try:
                self.product_issuer.rollback(material)
            except Exception as error:
                failures.append(error)
            try:
                self.identity_provisioner.deprovision(plan)
            except Exception as error:
                failures.append(error)
            if failures:
                raise PairingRollbackError(
                    "simplified credential assembly rollback failed"
                ) from failures[0]
            raise

    def stage_recovery(
        self,
        *,
        hardware_id: str,
        pairing_id: str,
        node_id: str,
    ) -> StagedRecoveredSimplifiedBundle:
        if not isinstance(self.product_issuer, ManagedProductCredentialIssuer):
            raise PairingProvisioningError(
                "credential recovery lifecycle unavailable"
            )

        mqtt = self.product_issuer.mqtt_credentials
        try:
            current = mqtt.credential_store.get(hardware_id)
        except KeyError as error:
            raise PairingProvisioningError(
                "credential recovery lifecycle missing"
            ) from error

        if current.state is not CredentialState.ACTIVE:
            raise PairingProvisioningError(
                "credential recovery lifecycle is not active"
            )
        if current.node_id != node_id:
            raise PairingProvisioningError(
                "credential recovery node binding mismatch"
            )

        generation = current.active_generation + 1
        mqtt.begin_rotation(
            hardware_id,
            credential_generation=generation,
        )

        try:
            plan = build_node_provisioning_plan(
                system_id=self.system_id,
                node_id=node_id,
                generation=generation,
            )
            credentials = generate_node_credentials(plan)
            key_epoch, application_key = self._read_active_application_key(
                node_id
            )
            product = ProductCredentialBundle(
                schema="gh.pair.credentials/1",
                system_id=self.system_id,
                node_id=node_id,
                broker_host=self.broker_host,
                broker_port=self.broker_port,
                broker_tls_server_name=self.broker_tls_server_name,
                ca_pem=self.ca_pem,
                mqtt_username=credentials.username,
                mqtt_client_id=credentials.client_id,
                credential_generation=credentials.generation,
                n3w_key_epoch=key_epoch,
                mqtt_password=credentials.password,
                n3w_application_key=_base64url(application_key),
            )
            simplified = self.simplified_issuer.issue(product)
            return StagedRecoveredSimplifiedBundle(
                bundle=simplified,
                plan=plan,
                credentials=credentials,
                hardware_id=hardware_id,
                pairing_id=pairing_id,
                identity_provisioner=self.identity_provisioner,
                product_issuer=self.product_issuer,
            )
        except Exception:
            mqtt.rollback_rotation(
                hardware_id,
                reason="credential_recovery_stage_failed",
            )
            raise

    def _read_active_application_key(
        self,
        node_id: str,
    ) -> tuple[int, bytes]:
        if not isinstance(self.product_issuer, ManagedProductCredentialIssuer):
            raise PairingProvisioningError(
                "application key recovery source unavailable"
            )

        admin = self.product_issuer.application_keys.application_keys
        if not isinstance(admin, SqliteNodeApplicationKeyAdmin):
            raise PairingProvisioningError(
                "application key recovery source unavailable"
            )

        database = Path(admin.database).resolve()
        try:
            connection = sqlite3.connect(
                f"{database.as_uri()}?mode=ro",
                uri=True,
            )
            try:
                rows = connection.execute(
                    """
                    SELECT key_epoch
                    FROM n3w_relay_key_epochs
                    WHERE node_id=? AND state='ACTIVE' AND enabled=1
                    ORDER BY key_epoch
                    """,
                    (node_id,),
                ).fetchall()
            finally:
                connection.close()
        except sqlite3.Error as error:
            raise PairingProvisioningError(
                "application key recovery metadata unavailable"
            ) from error

        if len(rows) != 1:
            raise PairingProvisioningError(
                "application key recovery active epoch ambiguous"
            )

        key_epoch = int(rows[0][0])
        try:
            with SqliteNodeApplicationKeyProvider(
                admin.database,
                admin.key_dir,
            ) as provider:
                material = provider.resolve_key(
                    node_id=node_id,
                    key_epoch=key_epoch,
                )
        except NodeApplicationKeyStoreUnavailable as error:
            raise PairingProvisioningError(
                "application key recovery material unavailable"
            ) from error

        return key_epoch, material
