from __future__ import annotations

import threading
from typing import Any

import paho.mqtt.client as mqtt

from .dynsec_api import DynsecProvisioner, PahoDynsecTransport
from .dynsec_plan import NodeCredentials, NodeProvisioningPlan


class NodeIdentityProvisioningUnavailable(RuntimeError):
    pass


class PahoNodeIdentityProvisioner:
    """Dedicated DynSec provisioning identity for node credentials.

    The normal Manager MQTT identity is intentionally not accepted here.
    Every mutation is serialized because the provisioning service uses one
    fixed Broker client identity.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        client_id: str,
        tls_enabled: bool = False,
        ca_file: str | None = None,
        timeout_s: float = 10.0,
    ) -> None:
        if not host.strip():
            raise ValueError("provisioning broker host is required")
        if not 1 <= port <= 65535:
            raise ValueError("provisioning broker port is invalid")
        if not username or not password or not client_id:
            raise ValueError("provisioning identity is incomplete")
        if tls_enabled and not ca_file:
            raise ValueError("provisioning CA file is required for TLS")
        if timeout_s <= 0:
            raise ValueError("provisioning timeout must be positive")

        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.tls_enabled = tls_enabled
        self.ca_file = ca_file
        self.timeout_s = timeout_s
        self._lock = threading.RLock()

    def _connected_client(self) -> Any:
        connected = threading.Event()
        rejected: list[str] = []

        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
            protocol=mqtt.MQTTv5,
        )
        client.username_pw_set(self.username, self.password)

        if self.tls_enabled:
            client.tls_set(ca_certs=self.ca_file)

        def on_connect(
            _client: Any,
            _userdata: Any,
            _flags: Any,
            reason_code: Any,
            _properties: Any,
        ) -> None:
            if getattr(reason_code, "is_failure", False):
                rejected.append(str(reason_code))
            connected.set()

        client.on_connect = on_connect

        try:
            client.connect(
                self.host,
                self.port,
                keepalive=30,
            )
            client.loop_start()
        except OSError as error:
            raise NodeIdentityProvisioningUnavailable(
                "provisioning broker connection failed"
            ) from error

        if not connected.wait(self.timeout_s):
            client.disconnect()
            client.loop_stop()
            raise NodeIdentityProvisioningUnavailable(
                "provisioning broker connection timed out"
            )

        if rejected:
            client.disconnect()
            client.loop_stop()
            raise NodeIdentityProvisioningUnavailable(
                "provisioning broker rejected identity"
            )

        return client

    def _run(self, operation: str, *args: object) -> None:
        with self._lock:
            client = self._connected_client()
            try:
                transport = PahoDynsecTransport(
                    client,
                    timeout_s=self.timeout_s,
                )
                client.on_message = transport.on_message
                provisioner = DynsecProvisioner(transport)

                if operation == "provision":
                    plan, credentials = args
                    provisioner.provision(plan, credentials)
                    return

                if operation == "deprovision":
                    (plan,) = args
                    provisioner.deprovision(plan)
                    return

                raise RuntimeError("unsupported provisioning operation")
            finally:
                client.disconnect()
                client.loop_stop()

    def provision(
        self,
        plan: NodeProvisioningPlan,
        credentials: NodeCredentials,
    ) -> None:
        self._run(
            "provision",
            plan,
            credentials,
        )

    def deprovision(
        self,
        plan: NodeProvisioningPlan,
    ) -> None:
        self._run(
            "deprovision",
            plan,
        )
