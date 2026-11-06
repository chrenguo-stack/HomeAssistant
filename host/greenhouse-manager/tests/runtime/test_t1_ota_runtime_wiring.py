from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from greenhouse_manager.runtime import n3w_manager_runtime_wiring as wiring
from greenhouse_manager.runtime.config import Settings
from greenhouse_manager.runtime.t1_ota_ipc import (
    ApprovedManifestFileProvider,
    UnixSocketOtaBridge,
)


def test_ota_settings_default_disabled() -> None:
    settings = Settings(system_id="lab")
    assert settings.n3w_t1_ota_enabled is False
    assert wiring.build_t1_ota_manager(settings) is None


def test_ota_enabled_requires_n3w_runtime() -> None:
    settings = Settings(
        system_id="lab",
        n3w_t1_ota_enabled=True,
        n3w_t1_ota_installed_version="2026.10.0",
    )
    with pytest.raises(ValueError, match="requires GH_N3W_RUNTIME_ENABLED"):
        settings.validate()


def test_ota_manager_wiring_uses_file_provider_and_unix_bridge(tmp_path) -> None:
    manifest = tmp_path / "approved.json"
    manifest.write_text(json.dumps({"test": True}), encoding="utf-8")
    settings = Settings(
        system_id="lab",
        n3w_runtime_enabled=True,
        n3w_t1_ota_enabled=True,
        n3w_t1_ota_installed_version="2026.10.0",
        n3w_t1_ota_manifest_path=str(manifest),
        n3w_t1_ota_socket_path=str(tmp_path / "ota.sock"),
    )
    settings.validate()
    manager = wiring.build_t1_ota_manager(settings)
    assert manager is not None
    assert isinstance(manager.manifest_provider, ApprovedManifestFileProvider)
    assert isinstance(manager.intent_sink, UnixSocketOtaBridge)
    assert manager.intent_sink is manager.runtime_state_provider


def test_selector_passes_same_ota_manager_into_simplified_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_service = object()
    expected_ota = object()
    captured = {}

    monkeypatch.setattr(wiring, "build_t1_ota_manager", lambda _settings: expected_ota)

    def build(settings, *, ota_manager):
        captured["settings"] = settings
        captured["ota_manager"] = ota_manager
        return expected_service

    monkeypatch.setattr(wiring, "build_n3w_simplified_manager_service", build)
    settings = SimpleNamespace(
        n3w_runtime_enabled=True,
        n3w_product_pairing_enabled=False,
    )
    assert wiring.build_manager_mqtt_service(settings) is expected_service
    assert captured["ota_manager"] is expected_ota


def test_disabled_ota_preserves_legacy_base_service_call_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = object()
    calls = []

    def legacy_constructor(settings):
        calls.append(settings)
        return expected

    monkeypatch.setattr(wiring, "ManagerMqttService", legacy_constructor)
    settings = SimpleNamespace(n3w_runtime_enabled=False)
    assert wiring.build_manager_mqtt_service(settings) is expected
    assert calls == [settings]


def test_disabled_ota_preserves_legacy_simplified_builder_call_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = object()
    calls = []

    def legacy_builder(settings):
        calls.append(settings)
        return expected

    monkeypatch.setattr(
        wiring,
        "build_n3w_simplified_manager_service",
        legacy_builder,
    )
    settings = SimpleNamespace(
        n3w_runtime_enabled=True,
        n3w_product_pairing_enabled=False,
    )
    assert wiring.build_manager_mqtt_service(settings) is expected
    assert calls == [settings]
