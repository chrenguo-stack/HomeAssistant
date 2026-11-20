from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "tools" / "execution_packages" / "n3w" / "r7a"
    / "kf168_ipc_migration_readiness_repair" / "executor.py"
)
MANIFEST = SCRIPT.with_name("manifest.json")


def load_module():
    spec = importlib.util.spec_from_file_location("kf168_readiness_repair", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def install_happy_runtime(monkeypatch, module, clock):
    manager = "a" * 64
    ha = "b" * 64

    def ids(service, *, running=True):
        if service == "manager":
            return [manager] if (not running or clock.now >= 1.0) else []
        if service == "homeassistant":
            if not running:
                return [] if clock.now < 0.5 else [ha]
            return [ha] if clock.now >= 1.5 else []
        raise AssertionError(service)

    def inspect(container, template):
        assert template == ".Image"
        return "manager-image" if container == manager else "ha-image"

    monkeypatch.setattr(module, "docker_ids", ids)
    monkeypatch.setattr(module, "inspect_value", inspect)
    monkeypatch.setattr(module, "manager_bind", lambda container, source: container == manager and source == "/ipc")
    monkeypatch.setattr(module, "prop", lambda unit, key: {
        "ActiveState": "active", "SubState": "running", "Result": "success"
    }[key])
    monkeypatch.setattr(module, "active", lambda unit: True)
    monkeypatch.setattr(module, "emit", lambda *args, **kwargs: None)
    return manager, ha


def test_zero_running_is_retryable_until_exact_runtime_converges(monkeypatch):
    module = load_module()
    clock = FakeClock()
    manager, ha = install_happy_runtime(monkeypatch, module, clock)
    checks = []
    result = module.wait_application_runtime(
        manager,
        manager_image="manager-image",
        manager_source="/ipc",
        ha_image="ha-image",
        validate_invariants=lambda: checks.append(clock.now),
        timeout_seconds=5.0,
        poll_seconds=0.25,
        clock=clock,
        sleeper=clock.sleep,
    )
    assert result == ha
    assert clock.sleeps
    assert checks[0] == 0.0
    assert clock.now >= 1.5


@pytest.mark.parametrize(
    ("manager_all", "error"),
    [
        (["c" * 64], "manager_identity_changed"),
        (["a" * 64, "c" * 64], "manager_identity_changed"),
    ],
)
def test_replaced_or_duplicate_manager_fails_closed(monkeypatch, manager_all, error):
    module = load_module()
    clock = FakeClock()
    manager, _ha = install_happy_runtime(monkeypatch, module, clock)
    original = module.docker_ids
    monkeypatch.setattr(
        module,
        "docker_ids",
        lambda service, running=True: manager_all
        if service == "manager" and not running
        else original(service, running=running),
    )
    with pytest.raises(ValueError, match=error):
        module.wait_application_runtime(
            manager,
            manager_image="manager-image",
            manager_source="/ipc",
            ha_image="ha-image",
            validate_invariants=lambda: None,
            timeout_seconds=2.0,
            poll_seconds=0.25,
            clock=clock,
            sleeper=clock.sleep,
        )


def test_manager_image_or_bind_drift_fails_closed(monkeypatch):
    module = load_module()
    clock = FakeClock()
    manager, _ha = install_happy_runtime(monkeypatch, module, clock)
    monkeypatch.setattr(module, "inspect_value", lambda container, template: "wrong-image")
    with pytest.raises(ValueError, match="manager_image_drift"):
        module.wait_application_runtime(
            manager, manager_image="manager-image", manager_source="/ipc",
            ha_image="ha-image", validate_invariants=lambda: None,
            timeout_seconds=2.0, poll_seconds=0.25, clock=clock, sleeper=clock.sleep,
        )

    module = load_module()
    clock = FakeClock()
    manager, _ha = install_happy_runtime(monkeypatch, module, clock)
    monkeypatch.setattr(module, "manager_bind", lambda *_: False)
    with pytest.raises(ValueError, match="manager_bind_drift"):
        module.wait_application_runtime(
            manager, manager_image="manager-image", manager_source="/ipc",
            ha_image="ha-image", validate_invariants=lambda: None,
            timeout_seconds=2.0, poll_seconds=0.25, clock=clock, sleeper=clock.sleep,
        )


def test_owner_failure_and_ota_failure_fail_closed(monkeypatch):
    module = load_module()
    clock = FakeClock()
    manager, _ha = install_happy_runtime(monkeypatch, module, clock)
    monkeypatch.setattr(module, "prop", lambda unit, key: {
        "ActiveState": "failed", "SubState": "failed", "Result": "exit-code"
    }[key])
    with pytest.raises(ValueError, match="application_owner_not_ready|application_owner_failed"):
        module.wait_application_runtime(
            manager, manager_image="manager-image", manager_source="/ipc",
            ha_image="ha-image", validate_invariants=lambda: None,
            timeout_seconds=2.0, poll_seconds=0.25, clock=clock, sleeper=clock.sleep,
        )

    module = load_module()
    clock = FakeClock()
    manager, _ha = install_happy_runtime(monkeypatch, module, clock)
    monkeypatch.setattr(module, "active", lambda unit: False)
    with pytest.raises(ValueError, match="ota_owner_not_active"):
        module.wait_application_runtime(
            manager, manager_image="manager-image", manager_source="/ipc",
            ha_image="ha-image", validate_invariants=lambda: None,
            timeout_seconds=2.0, poll_seconds=0.25, clock=clock, sleeper=clock.sleep,
        )


def test_host_or_broker_invariant_drift_propagates_without_retry(monkeypatch):
    module = load_module()
    clock = FakeClock()
    manager, _ha = install_happy_runtime(monkeypatch, module, clock)

    def drift():
        raise ValueError("broker_drift")

    with pytest.raises(ValueError, match="broker_drift"):
        module.wait_application_runtime(
            manager, manager_image="manager-image", manager_source="/ipc",
            ha_image="ha-image", validate_invariants=drift,
            timeout_seconds=5.0, poll_seconds=0.25, clock=clock, sleeper=clock.sleep,
        )
    assert clock.sleeps == []


def test_deadline_is_monotonic_and_bounded(monkeypatch):
    module = load_module()
    clock = FakeClock()
    manager, _ha = install_happy_runtime(monkeypatch, module, clock)
    original = module.docker_ids

    def never_running(service, *, running=True):
        if service == "manager" and running:
            return []
        if service == "homeassistant":
            return []
        return original(service, running=running)

    monkeypatch.setattr(module, "docker_ids", never_running)
    with pytest.raises(ValueError, match="application_runtime_readiness_timeout"):
        module.wait_application_runtime(
            manager, manager_image="manager-image", manager_source="/ipc",
            ha_image="ha-image", validate_invariants=lambda: None,
            timeout_seconds=1.0, poll_seconds=0.25, clock=clock, sleeper=clock.sleep,
        )
    assert 1.0 <= clock.now <= 1.25
    assert len(clock.sleeps) <= 4


def test_install_and_rollback_share_one_readiness_barrier():
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.count("wait_application_runtime(") == 3
    assert 'manager_source="/run/n3w-t1-ota"' in text
    assert "manager_source=str(IPC)" in text
    assert '"app_identity_after_start"' not in text
    assert '"rollback_app_identity_drift"' not in text


def test_barrier_does_not_restart_services_or_retry_lifecycle():
    text = SCRIPT.read_text(encoding="utf-8")
    start = text.index("def wait_application_runtime(")
    end = text.index("\ndef validate_state(", start)
    block = text[start:end]
    assert "lifecycle(" not in block
    assert "systemctl" not in block
    assert "restart" not in block
    assert "compose(" not in block


def test_review_artifact_denies_live_execution():
    module = load_module()
    assert module.REVIEW_ONLY_LIVE_EXECUTION_AUTHORIZED is False
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'require(REVIEW_ONLY_LIVE_EXECUTION_AUTHORIZED, "live_execution_not_authorized")' in text


def test_manifest_binds_exact_source_and_keeps_phase_a_open():
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert value["gate_id"] == "N3W_T1_KF168_IPC_MIGRATION_EXECUTOR_READINESS_SOURCE_REPAIR"
    assert value["status"] == "REVIEW_ONLY"
    assert value["production_authority"] is False
    assert value["phase_a_overall"] == "NOT_YET_PASS"
    assert value["live_execution_authorized"] is False
    assert value["authorization_state"] == {
        "granted": False, "claimed": False, "consumed": False, "replay_permitted": False
    }
    relative = str(SCRIPT.relative_to(ROOT))
    blob = subprocess.check_output(
        ["git", "rev-parse", "HEAD:" + relative], cwd=ROOT, text=True
    ).strip()
    assert value["package_source_authority"][relative] == blob


def test_future_readonly_preflight_requires_real_telemetry_and_same_window_ha_mqtt():
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    oracle = value["future_phase_a_oracle_requirements"]
    assert oracle["fresh_simplified_n3w_telemetry_required"] is True
    assert oracle["same_window_ha_mqtt_transport_required"] is True
    assert oracle["availability_must_be_proven_in_readonly_preflight"] is True
    assert value["next_gate"] == "N3W_T1_KF168_IPC_MIGRATION_EXECUTOR_READONLY_DEPLOYMENT_PREFLIGHT"
    assert value["next_gate_scope"] == "READONLY_T1_PREFLIGHT_ONLY"
