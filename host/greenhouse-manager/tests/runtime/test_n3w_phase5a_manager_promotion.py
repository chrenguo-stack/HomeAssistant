from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import Any

import pytest

from greenhouse_manager.runtime import app
from greenhouse_manager.runtime import n3w_manager_runtime_wiring as wiring
from greenhouse_manager.runtime import n3w_simplified_isolated_mqtt_service as simplified_mqtt
from greenhouse_manager.runtime.config import Settings
from greenhouse_manager.runtime.n3w_compact_relay import (
    StaticNodeApplicationKeyProvider,
)
from greenhouse_manager.runtime.registration import RegistrationRegistry
from greenhouse_manager.runtime.replay_registry import ReplayRegistry


class _FakeService:
    def __init__(self) -> None:
        self.run_count = 0

    def run(self) -> None:
        self.run_count += 1


class _Closable:
    def __init__(self) -> None:
        self.closed = 0

    def close(self) -> None:
        self.closed += 1


def test_normal_app_uses_phase5a_manager_selector() -> None:
    source = inspect.getsource(app)
    assert "from .n3w_manager_runtime_wiring import run_manager_service" in source
    assert "from .c06b2_runtime_wiring import run_manager_service" not in source


def test_selector_preserves_base_service_when_n3w_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _FakeService()
    monkeypatch.setattr(wiring, "ManagerMqttService", lambda _settings: expected)
    settings = SimpleNamespace(n3w_runtime_enabled=False)
    assert wiring.build_manager_mqtt_service(settings) is expected


def test_selector_promotes_simplified_service_when_n3w_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _FakeService()
    called: list[Any] = []

    def build(settings: Any) -> _FakeService:
        called.append(settings)
        return expected

    monkeypatch.setattr(wiring, "build_n3w_simplified_manager_service", build)
    settings = SimpleNamespace(
        n3w_runtime_enabled=True,
        n3w_product_pairing_enabled=False,
    )
    assert wiring.build_manager_mqtt_service(settings) is expected
    assert called == [settings]


def test_c06b2_runtime_keeps_injection_seam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def run(settings: Any, *, service_factory: Any) -> None:
        captured["settings"] = settings
        captured["factory"] = service_factory

    monkeypatch.setattr(wiring, "run_c06b2_manager_service", run)
    settings = SimpleNamespace(n3w_runtime_enabled=False)
    wiring.run_manager_service(settings)
    assert captured == {
        "settings": settings,
        "factory": wiring.build_manager_mqtt_service,
    }


def test_promoted_service_disables_both_legacy_entrypoints() -> None:
    source = inspect.getsource(simplified_mqtt)
    assert "replace(settings, n3w_runtime_enabled=False)" in source
    assert "n3w_product_pairing_enabled=False" in source
    assert "replace(source_settings, pairing_intake_enabled=False)" in source


def test_promoted_service_constructs_with_product_pairing_enabled(
    tmp_path,
) -> None:
    registration_path = tmp_path / "registration.sqlite3"
    replay_path = tmp_path / "replay.sqlite3"
    settings = Settings(
        system_id="lab",
        pairing_db_path=str(registration_path),
        n3w_runtime_enabled=True,
        n3w_product_pairing_enabled=True,
    )

    with (
        RegistrationRegistry(registration_path) as registration,
        ReplayRegistry(replay_path) as replay,
    ):
        service = simplified_mqtt.N3wSimplifiedIsolatedMqttService(
            settings,
            registration=registration,
            replay=replay,
            keys=StaticNodeApplicationKeyProvider({}),
        )

        assert service.settings.n3w_runtime_enabled is False
        assert service.settings.n3w_product_pairing_enabled is False
        assert service.settings.pairing_intake_enabled is False


def test_phase5a_wiring_has_no_path_or_finite_grant_authority() -> None:
    source = inspect.getsource(wiring)
    forbidden = (
        "n3w_runtime_wiring",
        "n3w_path_lease",
        "n3w_product_peer_authorization",
        "PeerAuthorizationService",
        "X25519",
        "N3wPathLeaseCoordinator",
    )
    for marker in forbidden:
        assert marker not in source
    assert "SqliteNodeApplicationKeyProvider" in source
    assert "N3wSimplifiedIsolatedMqttService" in source


def test_promoted_service_always_closes_owned_replay_and_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replay = _Closable()
    keys = _Closable()
    service = object.__new__(wiring.N3wSimplifiedManagerMqttService)
    service._owned_replay = replay
    service._owned_keys = keys

    def fail(_self: Any) -> None:
        raise RuntimeError("injected")

    monkeypatch.setattr(simplified_mqtt.N3wSimplifiedIsolatedMqttService, "run", fail)
    with pytest.raises(RuntimeError, match="injected"):
        service.run()
    assert replay.closed == 1
    assert keys.closed == 1
