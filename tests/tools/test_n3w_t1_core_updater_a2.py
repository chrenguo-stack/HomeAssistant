from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import n3w_t1_core_updater_a1_policy as policy_mod
import n3w_t1_core_updater_host as hostmod
import n3w_t1_core_updater_v2 as core
from n3w_t1_core_updater_v2_common import (
    A1_CLASSIFICATION_SHA256,
    APPLY_CONFIRMATION_V2,
    TARGET_SCHEMA_V2,
    TX_SCHEMA_V2,
    ComponentTarget,
    UpgradeBaseline,
    UpdaterV2Error,
    parse_image_bindings,
    rewrite_component_env,
    validate_component_candidate,
)
from n3w_t1_core_updater_v2_state import V2StateStore


OLD = {
    "manager": "local/greenhouse-manager:fresh-aaaaaaaaaaaa",
    "homeassistant": "local/n3w-homeassistant:2026.10.0-aaaaaaaa",
    "broker": "local/n3w-mosquitto:2.1.2-aaaaaaaa",
}
NEW = {
    "manager": "local/greenhouse-manager:fresh-bbbbbbbbbbbb",
    "homeassistant": "local/n3w-homeassistant:2026.11.0-bbbbbbbb",
    "broker": "local/n3w-mosquitto:2.1.3-bbbbbbbb",
}
IDS = {
    **{value: "sha256:" + hashlib.sha256(value.encode()).hexdigest() for value in OLD.values()},
    **{value: "sha256:" + hashlib.sha256(value.encode()).hexdigest() for value in NEW.values()},
}


def target(component: str, archive_sha: str) -> ComponentTarget:
    return ComponentTarget(
        component=component,
        mutation_profile="IMAGE_ONLY_V1",
        target_image_ref=NEW[component],
        target_platform="linux/arm64",
        target_archive_sha256=archive_sha,
        artifact_identity={
            "artifact_id": 1,
            "artifact_digest_sha256": "1" * 64,
            "artifact_name": f"target-{component}",
        },
        expected_predecessor_image_ref=OLD[component],
        rollback_compatible=True,
        compatibility_evidence={
            "schema": "gh.n3w-t1-core-updater-compatibility/1",
            "mutation_profile": "IMAGE_ONLY_V1",
            "peer_contracts_compatible": True,
            "persistent_schema_compatible": True,
            "review_evidence_sha256": "2" * 64,
        },
        a1_classification_sha256=A1_CLASSIFICATION_SHA256,
    )


def manifest(component: str, archive_sha: str) -> dict:
    t = target(component, archive_sha)
    return t.public()


def baseline() -> UpgradeBaseline:
    return UpgradeBaseline(
        stack_images=dict(OLD),
        image_binding_modes={name: "dynamic" for name in OLD},
        platforms={name: "linux/arm64" for name in OLD},
        runtime_contract_sha256={
            name: hashlib.sha256((name + "-contract").encode()).hexdigest()
            for name in OLD
        },
        a1_hard_authority={"hard": "stable"},
        a1_classification_sha256=A1_CLASSIFICATION_SHA256,
    )


class FakePolicy:
    def __init__(self) -> None:
        self.generation = 0

    def capture(self):
        self.generation += 1
        return {
            "generation_ignored": 0,
            "hard": "stable",
            "soft": "healthy",
        }

    def hard_authority(self, snapshot):
        return {"hard": snapshot["hard"]}

    def validate_baseline(self, component, snapshot, expected):
        assert component in OLD
        assert self.hard_authority(snapshot) == expected

    def validate_pre(self, component, snapshot):
        assert component in OLD
        assert snapshot["soft"] == "healthy"

    def validate_post(self, component, before, after):
        assert component in OLD
        assert before["hard"] == after["hard"] == "stable"


class FakeHost:
    def __init__(self) -> None:
        self.bindings = dict(OLD)
        self.image_ids = dict(IDS)
        self.events: list[str] = []
        self.fail_activate_count = 0
        self.peer_drift_after_activate: str | None = None

    def _render(self):
        return {
            "services": {
                name: {
                    "image": self.bindings[name],
                    "network_mode": (
                        "host" if name in {"manager", "homeassistant"} else "bridge"
                    ),
                }
                for name in OLD
            }
        }

    def inspect_v2(self):
        runtime = {
            name: {
                "image_ref": self.bindings[name],
                "image_id": self.image_ids[self.bindings[name]],
                "network_mode": (
                    "host" if name in {"manager", "homeassistant"} else "bridge"
                ),
                "platform": "linux/arm64",
                "container_id": f"{name}-container",
                "started_at": "now",
                "restart_count": 0,
                "runtime_contract_sha256": (
                    hashlib.sha256((name + "-contract").encode()).hexdigest()
                ),
            }
            for name in OLD
        }
        return {
            "manager_image": self.bindings["manager"],
            "image_bindings": dict(self.bindings),
            "image_binding_modes": {name: "dynamic" for name in OLD},
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
            "image_bindings": dict(snapshot["image_bindings"]),
            "image_binding_modes": dict(snapshot["image_binding_modes"]),
            "listeners": dict(snapshot["listeners"]),
            "health_state": "HEALTHY",
            "snapshot": snapshot,
        }

    def wait_services(self, timeout=120):
        del timeout

    def assert_mutation_safe(self, component):
        assert component in OLD

    def assert_component_upgradeable(self, component):
        assert component in OLD

    def release_component_guard(self):
        self.events.append("release-guard")

    def component_binding_v2(self, component):
        return self.bindings[component]

    def image_id(self, reference):
        return self.image_ids.get(reference)

    def verify_image_archive(self, reference, tar_path, expected_sha256):
        assert hashlib.sha256(tar_path.read_bytes()).hexdigest() == expected_sha256
        return self.image_ids[reference]

    def load_image(self, tar_path):
        self.events.append("load")

    def rewrite_component_image(self, component, expected, replacement):
        assert self.bindings[component] == expected
        self.bindings[component] = replacement
        self.events.append(f"rewrite:{component}")
        return "e" * 64

    def render_compose(self):
        return self._render()

    def quiesce_component(self, component):
        self.events.append(f"quiesce:{component}")

    def activate_component(self, component):
        self.events.append(f"activate:{component}")
        if self.fail_activate_count:
            self.fail_activate_count -= 1
            raise UpdaterV2Error("injected_activate_failure")
        if self.peer_drift_after_activate is not None:
            peer = self.peer_drift_after_activate
            self.image_ids[self.bindings[peer]] = "sha256:" + "9" * 64


def test_v2_manifest_loads_all_three_components(tmp_path: Path):
    archive_sha = "f" * 64
    for component in OLD:
        path = tmp_path / f"{component}.json"
        path.write_text(
            json.dumps(manifest(component, archive_sha)),
            encoding="utf-8",
        )
        loaded = ComponentTarget.load(path)
        assert loaded.component == component
        assert loaded.target_image_ref == NEW[component]


def test_u0_baseline_round_trip(tmp_path: Path):
    frozen = baseline()
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(frozen.public()), encoding="utf-8")
    loaded = UpgradeBaseline.load(path)
    assert loaded.stack_images == OLD
    assert loaded.a1_hard_authority == {"hard": "stable"}


def test_v2_manifest_rejects_unstructured_compatibility(tmp_path: Path):
    doc = manifest("manager", "f" * 64)
    doc["compatibility_evidence"] = {"peer_contracts": "claimed"}
    path = tmp_path / "bad-compatibility.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(
        UpdaterV2Error,
        match="target_compatibility_evidence_invalid",
    ):
        ComponentTarget.load(path)


def test_v2_manifest_rejects_wrong_a1_authority(tmp_path: Path):
    doc = manifest("manager", "f" * 64)
    doc["a1_classification_sha256"] = "0" * 64
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(UpdaterV2Error, match="target_a1_authority_mismatch"):
        ComponentTarget.load(path)


def test_production_mqtt_identity_formats(tmp_path: Path):
    manager = tmp_path / "runtime.env"
    manager.write_text(
        "GH_MQTT_USERNAME=ghs_greenhouse_manager\n"
        "GH_MQTT_CLIENT_ID=gh-manager-greenhouse\n"
        "GH_MQTT_PASSWORD_FILE=/run/secrets/password\n",
        encoding="utf-8",
    )
    ha = tmp_path / "mqtt-bootstrap.json"
    ha.write_text(
        json.dumps(
            {
                "broker": "127.0.0.1",
                "port": 1883,
                "protocol": "5",
                "username": "ghs_greenhouse_homeassistant",
                "client_id": "gh-homeassistant-greenhouse",
                "password_file": "/run/secrets/password",
            }
        ),
        encoding="utf-8",
    )

    assert policy_mod._mqtt_identity("manager", manager)
    assert policy_mod._mqtt_identity("homeassistant", ha)


def test_legacy_static_peer_binding_authority_is_readable(
    tmp_path: Path,
    monkeypatch,
):
    env = tmp_path / "docker-compose.env"
    env.write_text(
        f"GH_MANAGER_IMAGE={OLD['manager']}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(hostmod, "COMPOSE_ENV", env)
    host = hostmod.LocalHost()
    rendered = {
        "services": {
            "manager": {"image": OLD["manager"]},
            "homeassistant": {"image": OLD["homeassistant"]},
            "broker": {"image": OLD["broker"]},
        }
    }

    bindings, modes = host._image_binding_authority_v2(rendered)

    assert bindings == OLD
    assert modes == {
        "manager": "dynamic",
        "homeassistant": "legacy_static",
        "broker": "legacy_static",
    }


def test_manager_rewrite_does_not_require_dynamic_peer_lines():
    payload = f"GH_MANAGER_IMAGE={OLD['manager']}\n".encode()
    updated = rewrite_component_env(
        payload,
        "manager",
        OLD["manager"],
        NEW["manager"],
    )
    assert updated == f"GH_MANAGER_IMAGE={NEW['manager']}\n".encode()


def test_generic_env_binding_rewrites_only_selected_component():
    payload = (
        "PRIVATE=unchanged\n"
        f"GH_MANAGER_IMAGE={OLD['manager']}\n"
        f"GH_HOMEASSISTANT_IMAGE={OLD['homeassistant']}\n"
        f"GH_BROKER_IMAGE={OLD['broker']}\n"
    ).encode()
    for component in OLD:
        updated = rewrite_component_env(
            payload,
            component,
            OLD[component],
            NEW[component],
        )
        bindings = parse_image_bindings(updated)
        assert bindings[component] == NEW[component]
        for peer in OLD:
            if peer != component:
                assert bindings[peer] == OLD[peer]
        assert b"PRIVATE=unchanged\n" in updated


@pytest.mark.parametrize("component", ["manager", "homeassistant", "broker"])
def test_candidate_validation_allows_only_selected_image(component: str):
    before = {
        "services": {
            name: {"image": OLD[name], "x": name}
            for name in OLD
        }
    }
    after = json.loads(json.dumps(before))
    after["services"][component]["image"] = NEW[component]
    validate_component_candidate(
        before,
        after,
        component,
        OLD[component],
        NEW[component],
    )

    peer = next(name for name in OLD if name != component)
    after["services"][peer]["x"] = "drift"
    with pytest.raises(UpdaterV2Error, match="candidate_non_target_drift"):
        validate_component_candidate(
            before,
            after,
            component,
            OLD[component],
            NEW[component],
        )


@pytest.mark.parametrize("component", ["manager", "homeassistant", "broker"])
def test_apply_mutates_only_target_binding(
    tmp_path: Path,
    monkeypatch,
    component: str,
):
    monkeypatch.setattr(core.os, "geteuid", lambda: 0)
    archive = tmp_path / f"{component}.tar"
    archive.write_bytes(f"archive-{component}".encode())
    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    host = FakeHost()
    store = V2StateStore(tmp_path / "state")
    updater = core.MultiComponentCoreUpdater(
        host,
        store,
        FakePolicy(),
    )

    result = updater.apply(
        target(component, archive_sha),
        baseline(),
        archive,
        authorization_id=f"N3W_T1_CORE_UPDATER_{component.upper()}_TEST_01",
        confirmation=APPLY_CONFIRMATION_V2,
    )

    assert result["status"] == "PASS"
    assert result["component"] == component
    assert host.bindings[component] == NEW[component]
    for peer in OLD:
        if peer != component:
            assert host.bindings[peer] == OLD[peer]
    assert host.events == [
        f"quiesce:{component}",
        f"rewrite:{component}",
        f"activate:{component}",
        "release-guard",
    ]
    tx = store.read()
    assert tx["schema"] == TX_SCHEMA_V2
    assert tx["status"] == "COMMITTED"
    assert tx["component"] == component
    assert tx["predecessor_runtime_contract_sha256"] == (
        baseline().runtime_contract_sha256[component]
    )


def test_explicit_rollback_restores_selected_component(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(core.os, "geteuid", lambda: 0)
    archive = tmp_path / "manager.tar"
    archive.write_bytes(b"manager-target")
    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    host = FakeHost()
    store = V2StateStore(tmp_path / "state")
    updater = core.MultiComponentCoreUpdater(host, store, FakePolicy())
    updater.apply(
        target("manager", archive_sha),
        baseline(),
        archive,
        authorization_id="N3W_T1_CORE_UPDATER_MANAGER_TEST_02",
        confirmation=APPLY_CONFIRMATION_V2,
    )

    result = updater.rollback(
        confirmation="T1_CORE_UPDATER_ROLLBACK"
    )
    assert result["status"] == "PASS"
    assert host.bindings == OLD
    assert store.read()["status"] == "ROLLED_BACK"


@pytest.mark.parametrize("component", ["manager", "homeassistant", "broker"])
def test_target_activation_failure_rolls_back_all_components(
    tmp_path: Path,
    monkeypatch,
    component: str,
):
    monkeypatch.setattr(core.os, "geteuid", lambda: 0)
    archive = tmp_path / f"{component}.tar"
    archive.write_bytes(f"failure-{component}".encode())
    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    host = FakeHost()
    host.fail_activate_count = 1
    store = V2StateStore(tmp_path / "state")
    updater = core.MultiComponentCoreUpdater(host, store, FakePolicy())

    with pytest.raises(UpdaterV2Error, match="injected_activate_failure"):
        updater.apply(
            target(component, archive_sha),
            baseline(),
            archive,
            authorization_id=(
                f"N3W_T1_CORE_UPDATER_{component.upper()}_FAIL_01"
            ),
            confirmation=APPLY_CONFIRMATION_V2,
        )

    assert host.bindings == OLD
    assert store.read()["status"] == "ROLLED_BACK"
    assert store.read()["apply_error_code"] == "injected_activate_failure"


def test_peer_hard_drift_fails_closed_after_target_restore(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(core.os, "geteuid", lambda: 0)
    archive = tmp_path / "manager.tar"
    archive.write_bytes(b"peer-drift")
    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    host = FakeHost()
    host.peer_drift_after_activate = "homeassistant"
    store = V2StateStore(tmp_path / "state")
    updater = core.MultiComponentCoreUpdater(host, store, FakePolicy())

    with pytest.raises(
        UpdaterV2Error,
        match="automatic_rollback_failed",
    ):
        updater.apply(
            target("manager", archive_sha),
            baseline(),
            archive,
            authorization_id="N3W_T1_CORE_UPDATER_MANAGER_PEER_DRIFT_01",
            confirmation=APPLY_CONFIRMATION_V2,
        )

    assert host.bindings["manager"] == OLD["manager"]
    assert store.read()["status"] == "FAILED_EMERGENCY"
    assert store.read()["apply_error_code"].startswith("peer_runtime_drift:")
    assert store.read()["rollback_error_code"].startswith("peer_runtime_drift:")
    assert store.read()["last_runtime_class"] == "UNRESOLVED"
    assert store.read()["last_health_state"] == "FAILED"


def test_rolling_back_transaction_is_reentrant(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(core.os, "geteuid", lambda: 0)
    archive = tmp_path / "manager.tar"
    archive.write_bytes(b"reentrant")
    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    host = FakeHost()
    store = V2StateStore(tmp_path / "state")
    updater = core.MultiComponentCoreUpdater(host, store, FakePolicy())
    updater.apply(
        target("manager", archive_sha),
        baseline(),
        archive,
        authorization_id="N3W_T1_CORE_UPDATER_MANAGER_REENTRANT_01",
        confirmation=APPLY_CONFIRMATION_V2,
    )
    tx = store.read()
    tx["status"] = "ROLLING_BACK"
    tx["phase"] = "ROLLBACK_AUTHORIZED"
    store.write(tx)

    result = updater.rollback(
        confirmation="T1_CORE_UPDATER_ROLLBACK"
    )

    assert result["transaction_status"] == "ROLLED_BACK"
    assert host.bindings == OLD


def test_nonterminal_predecessor_healthy_closes_without_mutation(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(core.os, "geteuid", lambda: 0)
    archive = tmp_path / "manager.tar"
    archive.write_bytes(b"predecessor-healthy")
    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    host = FakeHost()
    store = V2StateStore(tmp_path / "state")
    updater = core.MultiComponentCoreUpdater(host, store, FakePolicy())
    updater.apply(
        target("manager", archive_sha),
        baseline(),
        archive,
        authorization_id="N3W_T1_CORE_UPDATER_MANAGER_RECOVERY_01",
        confirmation=APPLY_CONFIRMATION_V2,
    )
    tx = store.read()
    host.bindings["manager"] = OLD["manager"]
    tx["status"] = "APPLYING"
    tx["phase"] = "QUIESCING"
    store.write(tx)
    host.events.clear()

    result = updater.rollback(
        confirmation="T1_CORE_UPDATER_ROLLBACK"
    )

    assert result["t1_mutation"] is False
    assert host.events == []
    assert store.read()["status"] == "ROLLED_BACK"


def test_runtime_state_reports_predecessor_running_without_mutation(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(core.os, "geteuid", lambda: 0)
    archive = tmp_path / "manager.tar"
    archive.write_bytes(b"runtime-state")
    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    host = FakeHost()
    store = V2StateStore(tmp_path / "state")
    updater = core.MultiComponentCoreUpdater(host, store, FakePolicy())

    updater.apply(
        target("manager", archive_sha),
        baseline(),
        archive,
        authorization_id="N3W_T1_CORE_UPDATER_RUNTIME_STATE_01",
        confirmation=APPLY_CONFIRMATION_V2,
    )
    tx = store.read()
    host.bindings["manager"] = OLD["manager"]
    tx["status"] = "FAILED_EMERGENCY"
    tx["phase"] = "FAILED_EMERGENCY"
    store.write(tx)
    host.events.clear()

    result = updater.runtime_state()

    assert result["status"] == "PASS"
    assert result["operation"] == "runtime-state"
    assert result["mutation"] is False
    assert result["runtime_class"] == "PREDECESSOR_BOUND_RUNNING"
    assert result["health_state"] == "HEALTHY"
    assert host.events == []


def test_recovery_waits_for_predecessor_convergence_without_restart(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(core.os, "geteuid", lambda: 0)
    archive = tmp_path / "manager.tar"
    archive.write_bytes(b"converging-predecessor")
    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    host = FakeHost()
    store = V2StateStore(tmp_path / "state")
    updater = core.MultiComponentCoreUpdater(host, store, FakePolicy())

    updater.apply(
        target("manager", archive_sha),
        baseline(),
        archive,
        authorization_id="N3W_T1_CORE_UPDATER_CONVERGE_01",
        confirmation=APPLY_CONFIRMATION_V2,
    )
    tx = store.read()
    host.bindings["manager"] = OLD["manager"]
    tx["status"] = "FAILED_EMERGENCY"
    tx["phase"] = "FAILED_EMERGENCY"
    store.write(tx)
    host.events.clear()

    wait_calls = []

    def observe_converging():
        state = FakeHost.observe_state_v2(host)
        state["health_state"] = "CONVERGING"
        return state

    monkeypatch.setattr(host, "observe_state_v2", observe_converging)
    monkeypatch.setattr(
        host,
        "wait_services",
        lambda timeout=120: wait_calls.append(timeout),
    )

    result = updater.rollback(
        confirmation="T1_CORE_UPDATER_ROLLBACK"
    )

    assert result["transaction_status"] == "ROLLED_BACK"
    assert result["t1_mutation"] is False
    assert wait_calls == [120]
    assert host.events == []


def test_runtime_state_reports_stopped_predecessor(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(core.os, "geteuid", lambda: 0)
    archive = tmp_path / "manager.tar"
    archive.write_bytes(b"stopped-predecessor")
    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    host = FakeHost()
    store = V2StateStore(tmp_path / "state")
    updater = core.MultiComponentCoreUpdater(host, store, FakePolicy())

    updater.apply(
        target("manager", archive_sha),
        baseline(),
        archive,
        authorization_id="N3W_T1_CORE_UPDATER_RUNTIME_STATE_03",
        confirmation=APPLY_CONFIRMATION_V2,
    )
    tx = store.read()
    host.bindings["manager"] = OLD["manager"]
    tx["status"] = "FAILED_EMERGENCY"
    tx["phase"] = "FAILED_EMERGENCY"
    store.write(tx)

    monkeypatch.setattr(
        host,
        "observe_state_v2",
        lambda: {
            "application_state": "stopped",
            "services_owner_state": "inactive",
            "running_counts": {
                "manager": 0,
                "homeassistant": 0,
                "broker": 1,
            },
            "image_bindings": dict(host.bindings),
            "image_binding_modes": {
                "manager": "dynamic",
                "homeassistant": "dynamic",
                "broker": "dynamic",
            },
            "listeners": {
                "tcp_8883": 1,
                "tcp_47110": 0,
                "udp_47111": 0,
                "tcp_47112": 0,
            },
            "health_state": "NOT_RUNNING",
            "snapshot": None,
        },
    )

    result = updater.runtime_state()

    assert result["runtime_class"] == "APPLICATION_STOPPED_PREDECESSOR"
    assert result["health_state"] == "NOT_RUNNING"
    assert result["mutation"] is False


def test_runtime_state_reports_target_running(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(core.os, "geteuid", lambda: 0)
    archive = tmp_path / "manager.tar"
    archive.write_bytes(b"target-running")
    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    host = FakeHost()
    store = V2StateStore(tmp_path / "state")
    updater = core.MultiComponentCoreUpdater(host, store, FakePolicy())

    updater.apply(
        target("manager", archive_sha),
        baseline(),
        archive,
        authorization_id="N3W_T1_CORE_UPDATER_RUNTIME_STATE_02",
        confirmation=APPLY_CONFIRMATION_V2,
    )
    tx = store.read()
    tx["status"] = "FAILED_EMERGENCY"
    tx["phase"] = "FAILED_EMERGENCY"
    store.write(tx)

    result = updater.runtime_state()

    assert result["runtime_class"] == "TARGET_BOUND_RUNNING"
    assert result["health_state"] == "HEALTHY"


def test_system_health_accepts_degraded_only_for_unrelated_failure(
    monkeypatch,
):
    host = hostmod.LocalHost()

    class Result:
        def __init__(self, code: int, stdout: bytes):
            self.returncode = code
            self.stdout = stdout
            self.stderr = b""

    def run(argv, *, timeout=60, check=True):
        del timeout, check
        if tuple(argv) == ("systemctl", "is-system-running"):
            return Result(1, b"degraded\n")
        if tuple(argv) == (
            "systemctl",
            "--failed",
            "--no-legend",
            "--plain",
        ):
            return Result(0, b"unrelated.service loaded failed failed\n")
        raise AssertionError(argv)

    def systemctl(action, unit):
        if unit == hostmod.CERT_LIFECYCLE_UNIT and action == "is-active":
            return "inactive"
        if action in {"is-active", "is-enabled"}:
            return "active" if action == "is-active" else "enabled"
        raise AssertionError((action, unit))

    monkeypatch.setattr(host, "_run", run)
    monkeypatch.setattr(host, "_systemctl", systemctl)

    result = host._system_health_v2()

    assert result["system_state"] == "degraded"
    assert result["relevant_failed_units"] == []


def test_system_health_rejects_relevant_failed_unit(monkeypatch):
    host = hostmod.LocalHost()

    class Result:
        def __init__(self, code: int, stdout: bytes):
            self.returncode = code
            self.stdout = stdout
            self.stderr = b""

    def run(argv, *, timeout=60, check=True):
        del timeout, check
        if tuple(argv) == ("systemctl", "is-system-running"):
            return Result(1, b"degraded\n")
        if tuple(argv) == (
            "systemctl",
            "--failed",
            "--no-legend",
            "--plain",
        ):
            return Result(
                0,
                (
                    hostmod.SERVICES_UNIT
                    + " loaded failed failed\n"
                ).encode(),
            )
        raise AssertionError(argv)

    monkeypatch.setattr(host, "_run", run)

    with pytest.raises(Exception, match="relevant_failed_units"):
        host._system_health_v2()


def test_runtime_service_set_requires_exact_three(monkeypatch):
    host = hostmod.LocalHost()

    class Result:
        returncode = 0
        stderr = b""
        stdout = b"broker\nhomeassistant\nmanager\n"

    monkeypatch.setattr(host, "_run", lambda *args, **kwargs: Result())
    assert host._running_project_services_v2() == [
        "broker",
        "homeassistant",
        "manager",
    ]

    Result.stdout = b"broker\nhomeassistant\nmanager\nextra\n"
    with pytest.raises(Exception, match="runtime_service_set_invalid"):
        host._running_project_services_v2()


def test_runtime_rejects_unsupported_image_platform(monkeypatch):
    host = hostmod.LocalHost()
    monkeypatch.setattr(host, "_container_id", lambda service: "container")

    runtime_document = [
        {
            "Id": "container",
            "Image": "sha256:" + "1" * 64,
            "State": {
                "Running": True,
                "StartedAt": "2026-11-04T00:00:00Z",
            },
            "Config": {
                "Image": OLD["manager"],
                "User": "999:999",
                "Labels": {
                    "com.docker.compose.project": "n3wfc4",
                    "com.docker.compose.service": "manager",
                },
            },
            "HostConfig": {
                "NetworkMode": "host",
                "ReadonlyRootfs": False,
                "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
                "CapDrop": [],
                "SecurityOpt": [],
                "PortBindings": {},
            },
            "Mounts": [],
            "RestartCount": 0,
        }
    ]

    class Result:
        returncode = 0
        stderr = b""
        stdout = json.dumps(runtime_document).encode()

    monkeypatch.setattr(host, "_run", lambda *args, **kwargs: Result())
    monkeypatch.setattr(
        host,
        "_image_document",
        lambda reference: {"Os": "linux", "Architecture": "amd64"},
    )

    with pytest.raises(Exception, match="runtime_platform_unsupported"):
        host._runtime("manager")


def test_legacy_static_peer_is_readable_but_not_upgradeable(monkeypatch):
    host = hostmod.LocalHost()
    monkeypatch.setattr(
        host,
        "image_binding_modes_v2",
        lambda: {
            "manager": "dynamic",
            "homeassistant": "legacy_static",
            "broker": "legacy_static",
        },
    )

    host.assert_component_upgradeable("manager")
    with pytest.raises(
        Exception,
        match="homeassistant_runtime_template_convergence_required",
    ):
        host.assert_component_upgradeable("homeassistant")
    with pytest.raises(
        Exception,
        match="broker_runtime_template_convergence_required",
    ):
        host.assert_component_upgradeable("broker")


def test_broker_certificate_lifecycle_lock_is_exclusive(
    tmp_path: Path,
    monkeypatch,
):
    lock = tmp_path / ".certificate-lifecycle.lock"
    lock.write_text("", encoding="utf-8")
    lock.chmod(0o600)
    monkeypatch.setattr(
        hostmod,
        "BROKER_CERT_LIFECYCLE_LOCK",
        lock,
    )
    first = hostmod.LocalHost()
    second = hostmod.LocalHost()

    first._acquire_broker_certificate_guard()
    try:
        with pytest.raises(
            Exception,
            match="broker_certificate_lifecycle_busy",
        ):
            second._acquire_broker_certificate_guard()
    finally:
        first.release_component_guard()

    second._acquire_broker_certificate_guard()
    second.release_component_guard()


def test_broker_adapter_preserves_owner_order(monkeypatch):
    host = hostmod.LocalHost()
    events: list[str] = []
    monkeypatch.setattr(
        host,
        "_acquire_broker_certificate_guard",
        lambda: events.append("cert-lock"),
    )
    monkeypatch.setattr(
        host,
        "stop_services",
        lambda: events.append("stop-application"),
    )
    monkeypatch.setattr(
        host,
        "stop_broker",
        lambda: events.append("stop-broker"),
    )
    monkeypatch.setattr(
        host,
        "start_broker",
        lambda: events.append("start-broker"),
    )
    monkeypatch.setattr(
        host,
        "start_services",
        lambda: events.append("start-application"),
    )

    host.quiesce_component("broker")
    host.activate_component("broker")

    assert events == [
        "cert-lock",
        "stop-application",
        "stop-broker",
        "start-broker",
        "start-application",
    ]


def test_u0_baseline_can_record_legacy_static_peers(tmp_path: Path):
    host = FakeHost()

    def inspect_legacy():
        snapshot = FakeHost.inspect_v2(host)
        snapshot["image_binding_modes"] = {
            "manager": "dynamic",
            "homeassistant": "legacy_static",
            "broker": "legacy_static",
        }
        return snapshot

    host.inspect_v2 = inspect_legacy
    store = V2StateStore(tmp_path / "state")
    updater = core.MultiComponentCoreUpdater(host, store, FakePolicy())

    frozen = updater.baseline()

    assert frozen["image_binding_modes"] == {
        "manager": "dynamic",
        "homeassistant": "legacy_static",
        "broker": "legacy_static",
    }


def test_u0_baseline_rejects_unsupported_platform(tmp_path: Path):
    frozen = baseline()
    path = tmp_path / "baseline-platform.json"
    payload = frozen.public()
    payload["platforms"]["broker"] = "linux/amd64"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(
        UpdaterV2Error,
        match="baseline_component_authority_invalid",
    ):
        UpgradeBaseline.load(path)


def test_persistent_mode_requires_owner_rwx_and_forbids_group_other_write():
    assert policy_mod._safe_mode("0700") is True
    assert policy_mod._safe_mode("0755") is True
    assert policy_mod._safe_mode("0500") is False
    assert policy_mod._safe_mode("0000") is False
    assert policy_mod._safe_mode("0775") is False


def test_baseline_detects_preexisting_hard_drift(tmp_path: Path):
    host = FakeHost()
    store = V2StateStore(tmp_path / "state")
    updater = core.MultiComponentCoreUpdater(host, store, FakePolicy())
    frozen = baseline()
    current = host.inspect_v2()
    policy = updater.policy.capture()
    updater._validate_baseline("manager", frozen, current, policy)

    bad = UpgradeBaseline(
        stack_images={**OLD, "broker": NEW["broker"]},
        image_binding_modes=frozen.image_binding_modes,
        platforms=frozen.platforms,
        runtime_contract_sha256=frozen.runtime_contract_sha256,
        a1_hard_authority=frozen.a1_hard_authority,
        a1_classification_sha256=A1_CLASSIFICATION_SHA256,
    )
    with pytest.raises(UpdaterV2Error, match="baseline_stack_image_drift"):
        updater._validate_baseline("manager", bad, current, policy)


def test_v2_store_archives_terminal_legacy_transaction(tmp_path: Path):
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    legacy = {
        "schema": "gh.n3w-t1-core-updater-transaction/1",
        "status": "ROLLED_BACK",
        "phase": "ROLLBACK_COMPLETE",
    }
    legacy_path = root / "manager-upgrade.json"
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
    legacy_path.chmod(0o600)

    store = V2StateStore(root)
    store.prepare_new()

    assert not legacy_path.exists()
    archived = list((root / "history").glob("*-legacy-v1-*.json"))
    assert len(archived) == 1


def test_v2_store_rejects_nonterminal_legacy_transaction(tmp_path: Path):
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    legacy_path = root / "manager-upgrade.json"
    legacy_path.write_text(
        json.dumps(
            {
                "schema": "gh.n3w-t1-core-updater-transaction/1",
                "status": "FAILED_EMERGENCY",
                "phase": "ROLLBACK_FAILED",
            }
        ),
        encoding="utf-8",
    )
    legacy_path.chmod(0o600)

    store = V2StateStore(root)
    with pytest.raises(
        UpdaterV2Error,
        match="legacy_transaction_reconciliation_required",
    ):
        store.prepare_new()


def test_ha_storage_snapshot_captures_minor_versions(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(policy_mod, "HA_STORAGE", tmp_path)
    records = {
        "core.config_entries": ("entries", 1, 5),
        "core.device_registry": ("devices", 3, 4),
        "core.entity_registry": ("entities", 1, 23),
    }
    for filename, (key, version, minor_version) in records.items():
        (tmp_path / filename).write_text(
            json.dumps(
                {
                    "version": version,
                    "minor_version": minor_version,
                    "data": {key: []},
                }
            ),
            encoding="utf-8",
        )

    snapshot = policy_mod._ha_storage_snapshot()

    assert snapshot == {
        "config_entries": {
            "present": True,
            "version": 1,
            "minor_version": 5,
        },
        "devices": {
            "present": True,
            "version": 3,
            "minor_version": 4,
        },
        "entities": {
            "present": True,
            "version": 1,
            "minor_version": 23,
        },
    }


def test_image_only_postcheck_rejects_ha_storage_minor_migration(
    monkeypatch,
):
    policy = policy_mod.LocalA1Policy()
    monkeypatch.setattr(
        policy_mod.LocalA1Policy,
        "validate_pre",
        lambda self, component, snapshot: None,
    )
    before = {
        "persistent_paths": {},
        "sqlite": {},
        "trust": {
            "fc4_ca_sha256": "a",
            "system_ca_sha256": "b",
        },
        "dynsec_top_level_keys_sha256": "c",
        "mqtt_identity": {"manager": "d", "homeassistant": "e"},
        "ha_storage": {
            "config_entries": {
                "present": True,
                "version": 1,
                "minor_version": 5,
            },
            "devices": {
                "present": True,
                "version": 3,
                "minor_version": 4,
            },
            "entities": {
                "present": True,
                "version": 1,
                "minor_version": 23,
            },
        },
        "fixed_config": {"homeassistant": "f", "custom_component": "g"},
    }
    after = json.loads(json.dumps(before))
    after["ha_storage"]["entities"]["minor_version"] = 24

    with pytest.raises(
        UpdaterV2Error,
        match="a1_ha_storage_minor_version_drift:entities",
    ):
        policy.validate_post("homeassistant", before, after)
