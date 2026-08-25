from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .dynsec_plan import (
    NodeCredentials,
    NodeProvisioningPlan,
    build_node_provisioning_plan,
    generate_node_credentials,
)
from .n3w_node_credentials import (
    ProductCredentialBundle,
    ProductCredentialIssuer,
    ProductCredentialMaterial,
)
from .n3w_simplified_credentials import (
    SimplifiedCredentialBundleIssuer,
    SimplifiedProductCredentialBundle,
)
from .pairing_service import CredentialBundle, NodeIdentityProvisioner, PairingRollbackError


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


class SimplifiedProvisioningStager:
    """Build first-registration `gh.pair.credentials/2`.

    Registered pairing recovery must stop before this stager. MQTT and
    application-key rotations use their independent lifecycle APIs.
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
                raise PairingRollbackError("simplified credential assembly rollback failed") from failures[0]
            raise
