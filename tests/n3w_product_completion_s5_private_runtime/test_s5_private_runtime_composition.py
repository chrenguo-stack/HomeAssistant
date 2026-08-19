from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "host" / "greenhouse-manager" / "src"

import sys

sys.path.insert(0, str(RUNTIME))

from greenhouse_manager.runtime.config import Settings  # noqa: E402
from greenhouse_manager.runtime import n3w_product_isolated_app as isolated_app  # noqa: E402
from greenhouse_manager.runtime import n3w_product_isolated_launcher as launcher  # noqa: E402


class _Closable:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.closed = False

    def close(self):
        self.closed = True


class _FakeRegistration(_Closable):
    pass


class _FakeCredentials(_Closable):
    pass


class _FakeApplicationKeys(_Closable):
    pass


class _FakeReplay(_Closable):
    pass


class _FakePeerReplay(_Closable):
    pass


class _FakeMembership:
    def __init__(self, registry, credentials, application_keys, *, system_id):
        self.registry = registry
        self.credentials = credentials
        self.application_keys = application_keys
        self.system_id = system_id


class _FakePathAuthority:
    def __init__(self, replay):
        self.replay = replay


class _FakeEligibility:
    def __init__(self, registry, path_authority, *, system_id):
        self.registry = registry
        self.path_authority = path_authority
        self.system_id = system_id


class _FakePeerService:
    def __init__(self, membership, eligibility, replay):
        self.membership = membership
        self.eligibility = eligibility
        self.replay = replay


class _FakeAdapter:
    def __init__(self, service):
        self.service = service


class _FakeIsolatedService:
    def __init__(self, settings, adapter, application_keys):
        self.settings = settings
        self.adapter = adapter
        self.application_keys = application_keys
        self.ran = False

    def run(self):
        self.ran = True


def _settings(tmp_path: Path) -> Settings:
    settings = Settings(
        system_id="system001",
        n3w_runtime_enabled=True,
        pairing_db_path=str(tmp_path / "registration.sqlite3"),
        n3w_replay_db_path=str(tmp_path / "replay.sqlite3"),
        n3w_relay_authorization_db_path=str(tmp_path / "relay-authorization.sqlite3"),
        n3w_relay_key_dir=str(tmp_path / "relay-keys"),
    )
    settings.validate()
    return settings


def test_isolated_authority_assembly_reuses_existing_s4_authorities_without_network(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(launcher, "RegistrationRegistry", _FakeRegistration)
    monkeypatch.setattr(launcher, "CredentialLifecycleStore", _FakeCredentials)
    monkeypatch.setattr(launcher, "ProductNodeApplicationKeyProvider", _FakeApplicationKeys)
    monkeypatch.setattr(launcher, "ReplayRegistry", _FakeReplay)
    monkeypatch.setattr(launcher, "SqlitePeerAuthorizationReplayStore", _FakePeerReplay)
    monkeypatch.setattr(launcher, "RegistrationMembershipResolver", _FakeMembership)
    monkeypatch.setattr(launcher, "ReplayRegistryPathAuthority", _FakePathAuthority)
    monkeypatch.setattr(launcher, "ManagerRelayEligibilityProvider", _FakeEligibility)
    monkeypatch.setattr(launcher, "PeerAuthorizationService", _FakePeerService)
    monkeypatch.setattr(launcher, "PeerAuthorizationMqttAdapter", _FakeAdapter)

    resources = launcher.build_isolated_peer_authority(_settings(tmp_path))
    assert isinstance(resources.adapter, _FakeAdapter)
    peer_service = resources.adapter.service
    assert peer_service.membership.system_id == "system001"
    assert peer_service.eligibility.system_id == "system001"
    assert peer_service.membership.registry is resources.registration_registry
    assert peer_service.membership.credentials is resources.credential_store
    assert peer_service.membership.application_keys is resources.application_keys
    assert peer_service.eligibility.path_authority.replay is resources.replay_registry
    assert peer_service.replay is resources.peer_replay_store

    resources.close()
    assert resources.registration_registry.closed
    assert resources.credential_store.closed
    assert resources.application_keys.closed
    assert resources.replay_registry.closed
    assert resources.peer_replay_store.closed


def test_isolated_service_factory_injects_s4_adapter_and_closes_owned_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    application_keys = object()
    authority = type(
        "Authority",
        (),
        {"adapter": object(), "application_keys": application_keys, "closed": False},
    )()

    def close() -> None:
        authority.closed = True

    authority.close = close
    monkeypatch.setattr(launcher, "build_isolated_peer_authority", lambda settings: authority)
    monkeypatch.setattr(launcher, "N3wProductIsolatedMqttService", _FakeIsolatedService)

    assembly = launcher.assemble_isolated_manager_service(_settings(tmp_path))
    assert assembly.service.adapter is authority.adapter
    assert assembly.service.application_keys is application_keys
    assembly.run()
    assert assembly.service.ran
    assert authority.closed


def test_launcher_check_config_is_explicit_opt_in_and_does_not_open_state_or_network(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("GH_N3W_S5_ISOLATED_MANAGER_ENABLED", "true")
    monkeypatch.setenv("GH_SYSTEM_ID", "system001")
    monkeypatch.setenv("GH_N3W_RUNTIME_ENABLED", "true")
    called = False

    def fail_run(_settings):
        nonlocal called
        called = True
        raise AssertionError("check-config must not assemble live service")

    monkeypatch.setattr(isolated_app, "run_isolated_manager", fail_run)
    assert isolated_app.main(["--check-config"]) == 0
    assert called is False
    report = json.loads(capsys.readouterr().out)
    assert report["configuration_valid"] is True
    assert report["isolated_launcher_explicitly_enabled"] is True
    assert report["network_attempted"] is False
    assert report["secret_values_included"] is False


def test_public_app_and_profiles_do_not_select_private_composition() -> None:
    app = (
        ROOT
        / "host"
        / "greenhouse-manager"
        / "src"
        / "greenhouse_manager"
        / "runtime"
        / "app.py"
    ).read_text(encoding="utf-8")
    child = (
        ROOT / "firmware" / "esphome_rc" / "board_lab" / "n3w_product_completion_s5" / "child.yml"
    ).read_text(encoding="utf-8")
    relay = (
        ROOT / "firmware" / "esphome_rc" / "board_lab" / "n3w_product_completion_s5" / "relay.yml"
    ).read_text(encoding="utf-8")
    assert "n3w_product_isolated_app" not in app
    assert "n3w_product_isolated_launcher" not in app
    assert "greenhouse_n3w_s5_private_runtime" not in child
    assert "greenhouse_n3w_s5_private_runtime" not in relay
    assert "execution_enabled: false" in child
    assert "execution_enabled: false" in relay


def test_private_component_has_only_self_material_and_no_peer_or_pair_lmk_fields() -> None:
    component = (
        ROOT
        / "firmware"
        / "esphome_rc"
        / "components"
        / "greenhouse_n3w_s5_private_runtime"
        / "__init__.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "peer_mac",
        "peer_node_id",
        "gateway_id",
        "pair_lmk",
        "relay_lmk",
    ):
        assert forbidden not in component
    for required in (
        "system_id",
        "node_id",
        "credential_generation",
        "key_epoch",
        "application_key_hex",
        "local_mac",
    ):
        assert required in component


def test_private_compile_fixtures_bind_relay_wifi_mqtt_and_channel_without_real_secrets() -> None:
    root = (
        ROOT
        / "firmware"
        / "esphome_rc"
        / "board_lab"
        / "n3w_product_completion_s5"
        / "private_runtime_compile"
    )
    child = (root / "child_private_runtime_compile.yml").read_text(encoding="utf-8")
    relay = (root / "relay_private_runtime_compile.yml").read_text(encoding="utf-8")
    assert "role: child" in child
    assert "execution_enabled: true" in child
    assert "role: relay" in relay
    assert "execution_enabled: true" in relay
    assert 'ssid: "s5-isolated-fixture"' in relay
    assert 'broker: "192.0.2.10"' in relay
    assert 'client_id: "gh-s5-relay-fixture"' in relay
    assert relay.count("channel: 6") >= 1
    assert "password:" not in relay
