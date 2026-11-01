from __future__ import annotations

from types import SimpleNamespace

import pytest

from greenhouse_manager.runtime.dynsec_plan import (
    build_node_provisioning_plan,
    generate_node_credentials,
)
from greenhouse_manager.runtime.n3w_node_identity_provisioner import (
    PahoNodeIdentityProvisioner,
)


class FakeClient:
    instances = []

    def __init__(
        self,
        *,
        callback_api_version,
        client_id,
        protocol,
    ):
        self.callback_api_version = callback_api_version
        self.client_id = client_id
        self.protocol = protocol
        self.username = None
        self.password = None
        self.on_connect = None
        self.on_message = None
        self.connected_to = None
        self.loop_started = False
        self.disconnected = False
        FakeClient.instances.append(self)

    def username_pw_set(self, username, password):
        self.username = username
        self.password = password

    def tls_set(self, *, ca_certs):
        self.ca_certs = ca_certs

    def connect(self, host, port, keepalive):
        self.connected_to = (
            host,
            port,
            keepalive,
        )

    def loop_start(self):
        self.loop_started = True
        self.on_connect(
            self,
            None,
            None,
            SimpleNamespace(is_failure=False),
            None,
        )

    def disconnect(self):
        self.disconnected = True

    def loop_stop(self):
        self.loop_started = False


class FakeDynsecProvisioner:
    calls = []

    def __init__(self, transport):
        self.transport = transport

    def provision(self, plan, credentials):
        self.calls.append(
            ("provision", plan, credentials)
        )

    def deprovision(self, plan):
        self.calls.append(
            ("deprovision", plan)
        )


class FakeTransport:
    def __init__(self, client, *, timeout_s):
        self.client = client
        self.timeout_s = timeout_s

    def on_message(self, *args):
        return None


def build_provisioner(monkeypatch):
    import greenhouse_manager.runtime.n3w_node_identity_provisioner as module

    FakeClient.instances.clear()
    FakeDynsecProvisioner.calls.clear()

    monkeypatch.setattr(
        module.mqtt,
        "Client",
        FakeClient,
    )
    monkeypatch.setattr(
        module,
        "PahoDynsecTransport",
        FakeTransport,
    )
    monkeypatch.setattr(
        module,
        "DynsecProvisioner",
        FakeDynsecProvisioner,
    )

    return PahoNodeIdentityProvisioner(
        host="mosquitto",
        port=1883,
        username="ghs_lab_provisioning",
        password="secret",
        client_id="gh-provisioning-lab",
    )


def test_provision_uses_dedicated_identity(monkeypatch) -> None:
    provisioner = build_provisioner(monkeypatch)

    plan = build_node_provisioning_plan(
        system_id="lab",
        node_id="node_abc",
        generation=1,
    )
    credentials = generate_node_credentials(
        plan,
        random_bytes=lambda size: b"x" * size,
    )

    provisioner.provision(
        plan,
        credentials,
    )

    client = FakeClient.instances[-1]

    assert client.username == "ghs_lab_provisioning"
    assert client.client_id == "gh-provisioning-lab"
    assert client.connected_to == (
        "mosquitto",
        1883,
        30,
    )
    assert client.disconnected is True
    assert FakeDynsecProvisioner.calls[0][0] == "provision"


def test_deprovision_uses_same_serialized_identity(
    monkeypatch,
) -> None:
    provisioner = build_provisioner(monkeypatch)

    plan = build_node_provisioning_plan(
        system_id="lab",
        node_id="node_abc",
        generation=1,
    )

    provisioner.deprovision(plan)

    assert (
        FakeDynsecProvisioner.calls[0][0]
        == "deprovision"
    )


def test_tls_requires_ca() -> None:
    with pytest.raises(
        ValueError,
        match="CA file",
    ):
        PahoNodeIdentityProvisioner(
            host="mosquitto",
            port=8883,
            username="u",
            password="p",
            client_id="c",
            tls_enabled=True,
        )
