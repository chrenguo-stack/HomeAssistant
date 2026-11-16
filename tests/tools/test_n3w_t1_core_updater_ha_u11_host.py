from __future__ import annotations

import json
from pathlib import Path

import pytest

import n3w_t1_core_updater_ha_u11_host as u11host
from n3w_t1_core_updater_common import BROKER_UNIT, SERVICES_UNIT, UpdaterError


TARGET = "local/n3w-homeassistant:2026.10.4-5881590f"
TARGET_ID = "sha256:" + "a" * 64
MANAGER_REF = "local/greenhouse-manager:fresh-44e7d7472714"
MANAGER_ID = "sha256:" + "b" * 64
MANAGER_CONTAINER = "1" * 64
BROKER_REF = "local/n3w-mosquitto:2.1.2-3184566d"
BROKER_ID = "sha256:" + "c" * 64
BROKER_CONTAINER = "2" * 64
HA_CONTAINER = "3" * 64
PREDECESSOR = "local/n3w-homeassistant:2026.10.0-0c73235a"


class Result:
    def __init__(self, stdout=b""):
        self.stdout = stdout
        self.returncode = 0


class FakeHost:
    def __init__(
        self,
        *,
        peer_drift: str | None = None,
        config_mount: bool = True,
        owner_prestate: str = "failed",
        manager_pre_running: int = 0,
    ):
        self.started = False
        self.binding = PREDECESSOR
        self.peer_drift = peer_drift
        self.config_mount = config_mount
        self.owner_prestate = owner_prestate
        self.manager_pre_running = manager_pre_running
        self.calls = []

    def image_id(self, image_ref):
        self.calls.append(("image_id", image_ref))
        return None

    def component_binding_v2(self, component):
        self.calls.append(("component_binding_v2", component))
        return self.binding

    def load_image(self, archive):
        self.calls.append(("load_image", Path(archive)))

    def verify_image_archive(self, image_ref, archive, expected_sha256):
        self.calls.append(
            ("verify_image_archive", image_ref, Path(archive), expected_sha256)
        )
        return TARGET_ID

    def rewrite_component_image(self, component, expected, replacement):
        self.calls.append(
            ("rewrite_component_image", component, expected, replacement)
        )
        assert self.binding == expected
        self.binding = replacement

    def _activation_env(self):
        self.calls.append(("_activation_env",))

    def _service_unit(self):
        self.calls.append(("_service_unit",))
        return {"execstart_sha256": "x", "execstop_sha256": "y"}

    def _systemctl(self, action, unit):
        self.calls.append(("_systemctl", action, unit))
        assert action == "is-active"
        if unit == BROKER_UNIT:
            return "active"
        if unit == SERVICES_UNIT:
            return "active" if self.started else self.owner_prestate
        raise AssertionError(unit)

    def _running_count(self, service):
        self.calls.append(("_running_count", service))
        if service == "broker":
            return 1
        if not self.started:
            if service == "manager":
                return self.manager_pre_running
            return 0
        return 1

    def _runtime(self, service):
        self.calls.append(("_runtime", service))
        if service == "manager":
            value = {
                "container_id": MANAGER_CONTAINER,
                "image_ref": MANAGER_REF,
                "image_id": MANAGER_ID,
                "restart_count": 0,
            }
            if self.peer_drift == "manager":
                value["container_id"] = "9" * 64
            return value
        if service == "broker":
            value = {
                "container_id": BROKER_CONTAINER,
                "image_ref": BROKER_REF,
                "image_id": BROKER_ID,
                "restart_count": 0,
            }
            if self.peer_drift == "broker":
                value["image_id"] = "sha256:" + "9" * 64
            return value
        if service == "homeassistant":
            return {
                "container_id": HA_CONTAINER,
                "image_ref": TARGET,
                "image_id": TARGET_ID,
                "restart_count": 0,
            }
        raise AssertionError(service)

    def _run(self, argv, *, timeout=60, check=True):
        self.calls.append(("_run", tuple(argv), timeout, check))
        if tuple(argv) == ("systemctl", "start", SERVICES_UNIT):
            self.started = True
            return Result()
        if tuple(argv) == ("docker", "inspect", HA_CONTAINER):
            mounts = []
            if self.config_mount:
                mounts.append(
                    {
                        "Type": "bind",
                        "Source": u11host.PRODUCTION_HA_CONFIG,
                        "Destination": "/config",
                        "RW": True,
                    }
                )
            return Result(json.dumps([{"Mounts": mounts}]).encode())
        raise AssertionError(argv)


def owner(host=None):
    return u11host.LocalU11RuntimeOwner(
        expected_manager_container_id=MANAGER_CONTAINER,
        expected_manager_image_ref=MANAGER_REF,
        expected_manager_runtime_image_id=MANAGER_ID,
        expected_broker_container_id=BROKER_CONTAINER,
        expected_broker_image_ref=BROKER_REF,
        expected_broker_runtime_image_id=BROKER_ID,
        host=host or FakeHost(),
    )


def test_u11_host_adapter_delegates_image_and_binding_primitives(tmp_path):
    host = FakeHost()
    adapter = owner(host)
    archive = tmp_path / "target.tar.gz"

    assert adapter.target_image_id(TARGET) is None
    assert adapter.homeassistant_binding() == PREDECESSOR
    adapter.load_target_archive(archive)
    assert (
        adapter.verify_loaded_target(
            image_ref=TARGET,
            archive=archive,
            expected_archive_sha256="e" * 64,
        )
        == TARGET_ID
    )
    adapter.publish_homeassistant_target_binding(
        expected_predecessor=PREDECESSOR,
        target=TARGET,
    )
    assert adapter.homeassistant_binding() == TARGET


def test_u11_host_start_uses_production_owner_without_u12_health(monkeypatch):
    host = FakeHost()
    adapter = owner(host)
    monkeypatch.setattr(u11host.time, "sleep", lambda _seconds: None)

    evidence = adapter.start_target_owner(
        target_image_ref=TARGET,
        target_runtime_image_id=TARGET_ID,
    )

    assert evidence.owner_active is True
    assert evidence.manager_running is True
    assert evidence.broker_running is True
    assert evidence.homeassistant_running is True
    assert evidence.production_config_mounted is True
    assert (
        "_run",
        ("systemctl", "start", SERVICES_UNIT),
        u11host.START_TIMEOUT_SECONDS,
        True,
    ) in host.calls

    source = Path(u11host.__file__).read_text(encoding="utf-8")
    assert ".wait_services(" not in source
    assert ".observe_v2(" not in source
    assert "_listener_snapshot(" not in source
    assert "_mqtt_authenticated(" not in source
    assert "_homeassistant_http_status(" not in source


@pytest.mark.parametrize("service", ("manager", "broker"))
def test_u11_host_rejects_peer_identity_drift(monkeypatch, service):
    host = FakeHost(peer_drift=service)
    adapter = owner(host)
    monkeypatch.setattr(u11host.time, "sleep", lambda _seconds: None)

    with pytest.raises(UpdaterError, match="u11_peer_identity_drift"):
        adapter.start_target_owner(
            target_image_ref=TARGET,
            target_runtime_image_id=TARGET_ID,
        )


def test_u11_host_requires_exact_production_config_mount(monkeypatch):
    host = FakeHost(config_mount=False)
    adapter = owner(host)
    monkeypatch.setattr(u11host.time, "sleep", lambda _seconds: None)

    with pytest.raises(
        UpdaterError,
        match="u11_homeassistant_production_config_missing",
    ):
        adapter.start_target_owner(
            target_image_ref=TARGET,
            target_runtime_image_id=TARGET_ID,
        )


def test_u11_host_rejects_nonquiesced_owner_before_start():
    host = FakeHost(owner_prestate="active")
    adapter = owner(host)

    with pytest.raises(
        UpdaterError,
        match="u11_services_owner_not_quiesced",
    ):
        adapter.start_target_owner(
            target_image_ref=TARGET,
            target_runtime_image_id=TARGET_ID,
        )


def test_u11_host_rejects_running_manager_before_start():
    host = FakeHost(manager_pre_running=1)
    adapter = owner(host)

    with pytest.raises(
        UpdaterError,
        match="u11_manager_running_before_start",
    ):
        adapter.start_target_owner(
            target_image_ref=TARGET,
            target_runtime_image_id=TARGET_ID,
        )


def test_u11_host_runtime_identity_must_be_exact(monkeypatch):
    class WrongHaHost(FakeHost):
        def _runtime(self, service):
            value = super()._runtime(service)
            if service == "homeassistant":
                value["image_id"] = "sha256:" + "f" * 64
            return value

    host = WrongHaHost()
    adapter = owner(host)
    monkeypatch.setattr(u11host.time, "sleep", lambda _seconds: None)

    with pytest.raises(
        UpdaterError,
        match="u11_homeassistant_target_identity_drift",
    ):
        adapter.start_target_owner(
            target_image_ref=TARGET,
            target_runtime_image_id=TARGET_ID,
        )
