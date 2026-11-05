from __future__ import annotations

import copy
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import n3w_t1_core_updater_v2 as core
from n3w_t1_core_updater_v2_common import (
    A1_CLASSIFICATION_SHA256,
    APPLY_CONFIRMATION_V2,
    ROLLBACK_CONFIRMATION_V2,
    ComponentTarget,
    UpgradeBaseline,
    UpdaterV2Error,
)
from n3w_t1_core_updater_v2_state import V2StateStore


ROOT = Path(__file__).resolve().parents[2]
TARGET_PATH = ROOT / "infra/n3w-t1/upgrades/homeassistant-2026.10.4.json"
MANAGER = "local/greenhouse-manager:fresh-5b32e1ae8210"
BROKER = "local/n3w-mosquitto:2.1.2-3184566d"


def _image_id(reference: str) -> str:
    return "sha256:" + hashlib.sha256(reference.encode()).hexdigest()


def _contract(component: str) -> str:
    return hashlib.sha256((component + "-contract").encode()).hexdigest()


class P3Policy:
    def capture(self):
        return {"hard": "stable", "soft": "healthy"}

    def hard_authority(self, snapshot):
        return {"hard": snapshot["hard"]}

    def validate_baseline(self, component, snapshot, expected):
        assert component == "homeassistant"
        assert self.hard_authority(snapshot) == expected

    def validate_pre(self, component, snapshot):
        assert component == "homeassistant"
        assert snapshot["soft"] == "healthy"

    def validate_post(self, component, before, after):
        assert component == "homeassistant"
        assert before["hard"] == after["hard"] == "stable"


class P3Host:
    def __init__(self, target: ComponentTarget) -> None:
        self.target = target
        self.bindings = {
            "manager": MANAGER,
            "homeassistant": target.expected_predecessor_image_ref,
            "broker": BROKER,
        }
        self.modes = {
            "manager": "dynamic",
            "homeassistant": "legacy_static",
            "broker": "dynamic",
        }
        self.image_ids = {
            MANAGER: _image_id(MANAGER),
            target.expected_predecessor_image_ref: _image_id(
                target.expected_predecessor_image_ref
            ),
            BROKER: _image_id(BROKER),
        }
        self.events: list[str] = []
        self.fail_activate_count = 0

    def _render(self) -> dict:
        return {
            "services": {
                name: {
                    "image": self.bindings[name],
                    "network_mode": (
                        "host"
                        if name in {"manager", "homeassistant"}
                        else "bridge"
                    ),
                }
                for name in ("manager", "homeassistant", "broker")
            }
        }

    def inspect_v2(self) -> dict:
        runtime = {
            name: {
                "image_ref": self.bindings[name],
                "image_id": self.image_ids[self.bindings[name]],
                "network_mode": (
                    "host"
                    if name in {"manager", "homeassistant"}
                    else "bridge"
                ),
                "platform": "linux/arm64",
                "container_id": f"{name}-container",
                "started_at": "2026-11-05T00:00:00Z",
                "restart_count": 0,
                "runtime_contract_sha256": _contract(name),
            }
            for name in ("manager", "homeassistant", "broker")
        }
        return {
            "manager_image": self.bindings["manager"],
            "image_bindings": dict(self.bindings),
            "image_binding_modes": dict(self.modes),
            "compose_env_sha256": "a" * 64,
            "compose_render": self._render(),
            "compose_render_sha256": "b" * 64,
            "services_unit": {
                "execstart_sha256": "c" * 64,
                "execstop_sha256": "d" * 64,
            },
            "runtime": runtime,
            "listeners": {
                "tcp_8883": 1,
                "tcp_47110": 1,
                "udp_47111": 1,
                "tcp_47112": 0,
            },
            "mqtt_authenticated": {
                "manager": True,
                "homeassistant": True,
            },
            "homeassistant_http_status": 200,
        }

    def observe_v2(self):
        return self.inspect_v2()

    def observe_state_v2(self):
        snapshot = self.inspect_v2()
        return {
            "application_state": "running",
            "services_owner_state": "active",
            "running_counts": {
                "manager": 1,
                "homeassistant": 1,
                "broker": 1,
            },
            "image_bindings": dict(self.bindings),
            "image_binding_modes": dict(self.modes),
            "listeners": dict(snapshot["listeners"]),
            "health_state": "HEALTHY",
            "snapshot": snapshot,
        }

    def wait_services(self, timeout=120):
        del timeout

    def assert_mutation_safe(self, component):
        assert component == "homeassistant"

    def assert_component_upgradeable(self, component):
        assert component == "homeassistant"
        assert self.modes[component] in {"legacy_static", "dynamic"}

    def release_component_guard(self):
        self.events.append("release-guard")

    def component_binding_v2(self, component):
        return self.bindings[component]

    def image_id(self, reference):
        return self.image_ids.get(reference)

    def verify_image_archive(self, reference, tar_path, expected_sha256):
        del tar_path, expected_sha256
        value = self.image_ids.get(reference)
        if value is None:
            raise UpdaterV2Error("target_image_missing")
        return value

    def load_image(self, tar_path):
        del tar_path
        self.image_ids[self.target.target_image_ref] = _image_id(
            self.target.target_image_ref
        )
        self.events.append("load:homeassistant")

    def rewrite_component_image(self, component, expected, replacement):
        assert component == "homeassistant"
        assert self.bindings[component] == expected
        if self.modes[component] == "legacy_static":
            assert expected == self.target.expected_predecessor_image_ref
            self.modes[component] = "dynamic"
            self.events.append("converge:homeassistant")
        self.bindings[component] = replacement
        self.events.append("rewrite:homeassistant")
        return "e" * 64

    def restore_component_binding(
        self,
        component,
        expected_current,
        predecessor,
        predecessor_mode,
    ):
        assert component == "homeassistant"
        assert self.bindings[component] in {expected_current, predecessor}
        assert predecessor_mode == "legacy_static"
        self.bindings[component] = predecessor
        self.modes[component] = "legacy_static"
        self.events.append("restore-legacy:homeassistant")

    def render_compose(self):
        return self._render()

    def quiesce_component(self, component):
        assert component == "homeassistant"
        self.events.append("quiesce:homeassistant")

    def activate_component(self, component):
        assert component == "homeassistant"
        self.events.append("activate:homeassistant")
        if self.fail_activate_count:
            self.fail_activate_count -= 1
            raise UpdaterV2Error("injected_activate_failure")


def _baseline(host: P3Host) -> UpgradeBaseline:
    snapshot = host.inspect_v2()
    return UpgradeBaseline(
        stack_images=dict(snapshot["image_bindings"]),
        image_binding_modes=dict(snapshot["image_binding_modes"]),
        platforms={
            name: snapshot["runtime"][name]["platform"]
            for name in ("manager", "homeassistant", "broker")
        },
        runtime_contract_sha256={
            name: snapshot["runtime"][name]["runtime_contract_sha256"]
            for name in ("manager", "homeassistant", "broker")
        },
        a1_hard_authority={"hard": "stable"},
        a1_classification_sha256=A1_CLASSIFICATION_SHA256,
    )


def _updater(tmp_path: Path):
    target = ComponentTarget.load(TARGET_PATH)
    host = P3Host(target)
    state = tmp_path / "state"
    updater = core.MultiComponentCoreUpdater(
        host,
        V2StateStore(state),
        P3Policy(),
    )
    return target, host, state, updater


def test_p3_frozen_ha_inspect_and_plan_are_readonly(
    tmp_path: Path,
    monkeypatch,
):
    target, host, state, updater = _updater(tmp_path)
    baseline = _baseline(host)
    archive = tmp_path / "homeassistant-arm64.tar.gz"
    archive.write_bytes(b"p3-source-simulation")
    monkeypatch.setattr(
        core,
        "sha256_file",
        lambda path: target.target_archive_sha256,
    )
    before = (
        copy.deepcopy(host.bindings),
        copy.deepcopy(host.modes),
        list(host.events),
    )

    inspected = updater.inspect("homeassistant")
    planned = updater.plan(target, baseline, archive)

    assert inspected["status"] == "PASS"
    assert inspected["mutation"] is False
    assert planned["status"] == "PASS"
    assert planned["mutation"] is False
    assert planned["current"]["image"] == target.expected_predecessor_image_ref
    assert planned["current"]["binding_mode"] == "legacy_static"
    assert "converge_homeassistant_runtime_template" in planned["actions"]
    assert planned["rollback_available"] is True
    assert (
        host.bindings,
        host.modes,
        host.events,
    ) == before
    assert not state.exists()


def test_p3_frozen_ha_apply_and_rollback_restore_image_binding_and_peers(
    tmp_path: Path,
    monkeypatch,
):
    target, host, state, updater = _updater(tmp_path)
    baseline = _baseline(host)
    archive = tmp_path / "homeassistant-arm64.tar.gz"
    archive.write_bytes(b"p3-source-simulation")
    monkeypatch.setattr(core.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        core,
        "sha256_file",
        lambda path: target.target_archive_sha256,
    )
    peer_before = {
        name: copy.deepcopy(host.inspect_v2()["runtime"][name])
        for name in ("manager", "broker")
    }

    applied = updater.apply(
        target,
        baseline,
        archive,
        authorization_id="N3W_T1_CORE_UPDATER_HA_P3_SIMULATION",
        confirmation=APPLY_CONFIRMATION_V2,
    )

    assert applied["transaction_status"] == "COMMITTED"
    assert host.bindings["homeassistant"] == target.target_image_ref
    assert host.modes["homeassistant"] == "dynamic"
    assert host.bindings["manager"] == MANAGER
    assert host.bindings["broker"] == BROKER
    tx = updater.store.read()
    assert tx["predecessor_binding_mode"] == "legacy_static"
    for name in ("manager", "broker"):
        assert host.inspect_v2()["runtime"][name] == peer_before[name]

    rolled_back = updater.rollback(
        confirmation=ROLLBACK_CONFIRMATION_V2,
    )

    assert rolled_back["transaction_status"] == "ROLLED_BACK"
    assert host.bindings["homeassistant"] == target.expected_predecessor_image_ref
    assert host.modes["homeassistant"] == "legacy_static"
    assert host.bindings["manager"] == MANAGER
    assert host.bindings["broker"] == BROKER
    for name in ("manager", "broker"):
        assert host.inspect_v2()["runtime"][name] == peer_before[name]
    assert state.is_dir()


def test_p3_activation_failure_automatically_restores_legacy_binding(
    tmp_path: Path,
    monkeypatch,
):
    target, host, state, updater = _updater(tmp_path)
    baseline = _baseline(host)
    archive = tmp_path / "homeassistant-arm64.tar.gz"
    archive.write_bytes(b"p3-source-simulation")
    monkeypatch.setattr(core.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        core,
        "sha256_file",
        lambda path: target.target_archive_sha256,
    )
    host.fail_activate_count = 1

    with pytest.raises(
        UpdaterV2Error,
        match="injected_activate_failure",
    ):
        updater.apply(
            target,
            baseline,
            archive,
            authorization_id="N3W_T1_CORE_UPDATER_HA_P3_FAILURE_SIMULATION",
            confirmation=APPLY_CONFIRMATION_V2,
        )

    tx = updater.store.read()
    assert tx["status"] == "ROLLED_BACK"
    assert host.bindings["homeassistant"] == target.expected_predecessor_image_ref
    assert host.modes["homeassistant"] == "legacy_static"
    assert host.bindings["manager"] == MANAGER
    assert host.bindings["broker"] == BROKER
    assert state.is_dir()


def test_p3_predecessor_image_with_wrong_binding_mode_is_not_false_pass(
    tmp_path: Path,
    monkeypatch,
):
    target, host, _, updater = _updater(tmp_path)
    baseline = _baseline(host)
    archive = tmp_path / "homeassistant-arm64.tar.gz"
    archive.write_bytes(b"p3-source-simulation")
    monkeypatch.setattr(core.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        core,
        "sha256_file",
        lambda path: target.target_archive_sha256,
    )

    updater.apply(
        target,
        baseline,
        archive,
        authorization_id="N3W_T1_CORE_UPDATER_HA_P3_FALSE_PASS",
        confirmation=APPLY_CONFIRMATION_V2,
    )
    tx = updater.store.read()

    host.bindings["homeassistant"] = target.expected_predecessor_image_ref
    host.modes["homeassistant"] = "dynamic"
    runtime_class, health = updater._classify_transaction_state(
        tx,
        host.observe_state_v2(),
    )

    assert runtime_class == "UNRESOLVED"
    assert health == "FAILED"
