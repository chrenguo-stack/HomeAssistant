from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import greenhouse_manager.t1_broker_identity_production_broker_driver as driver_module
from greenhouse_manager.t1_broker_identity_production_broker_driver import (
    BrokerIdentityProductionBrokerDriverError,
    ClientConfig,
    PahoMqttSession,
)


class FakeReasonCode:
    def __init__(self, value: int) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        return other == self.value

    def __int__(self) -> int:
        raise TypeError("ReasonCode must not be coerced with int()")

    def __str__(self) -> str:
        return f"reason-{self.value}"


class FakeClient:
    reason_code = FakeReasonCode(0)

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.on_connect: Any = None

    def username_pw_set(self, _username: str, _password: str) -> None:
        pass

    def connect(self, _host: str, _port: int, keepalive: int) -> None:
        assert keepalive == 30

    def loop_start(self) -> None:
        assert self.on_connect is not None
        self.on_connect(self, None, {}, self.reason_code, None)

    def disconnect(self) -> None:
        pass

    def loop_stop(self) -> None:
        pass


class FakeMqtt:
    CallbackAPIVersion = SimpleNamespace(VERSION2=object())
    MQTTv5 = object()
    Client = FakeClient


def config() -> ClientConfig:
    return ClientConfig(
        host="127.0.0.1",
        port=1883,
        username="test-user",
        password="test-password",
        client_id="test-client",
    )


def test_reason_code_object_is_compared_without_integer_coercion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeClient.reason_code = FakeReasonCode(0)
    monkeypatch.setattr(driver_module, "_load_paho_mqtt", lambda: FakeMqtt)

    client, connected = PahoMqttSession(config(), timeout_s=0.1)._connected_client()

    assert isinstance(client, FakeClient)
    assert connected.is_set()


def test_rejected_reason_code_returns_domain_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeClient.reason_code = FakeReasonCode(135)
    monkeypatch.setattr(driver_module, "_load_paho_mqtt", lambda: FakeMqtt)

    with pytest.raises(
        BrokerIdentityProductionBrokerDriverError,
        match="MQTT connection was rejected",
    ):
        PahoMqttSession(config(), timeout_s=0.1)._connected_client()
