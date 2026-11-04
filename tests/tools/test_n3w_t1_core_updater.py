from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import n3w_t1_core_updater_common as common
import n3w_t1_core_updater_core as core
import n3w_t1_core_updater_host as hostmod
import n3w_t1_core_updater_state as state


class M:
    pass


m = M()
for module in (common, core, state):
    for name in dir(module):
        if not name.startswith("__"):
            setattr(m, name, getattr(module, name))

OLD = "local/greenhouse-manager:fresh-24382caae4a1"
OLD_ID = "sha256:" + "1" * 64
NEW = "local/greenhouse-manager:fresh-3539c8f871e2"
NEW_ID = "sha256:" + "2" * 64
NEW_RUNTIME_ID = "sha256:" + "5" * 64
HA = "local/n3w-homeassistant:2026.10.0-0c73235a"
HA_ID = "sha256:" + "3" * 64
BROKER = "local/n3w-mosquitto:2.1.2-3184566d"
BROKER_ID = "sha256:" + "4" * 64


def target(tmp_path: Path) -> m.Target:
    tar = tmp_path / "manager.tar"
    tar.write_bytes(b"manager")
    doc = {
        "schema": m.TARGET_SCHEMA,
        "component": "manager",
        "source_head": "a" * 40,
        "image": NEW,
        "image_id": NEW_ID,
        "tar_sha256": m.sha256_file(tar),
        "artifact_id": 123,
        "artifact_digest_sha256": "b" * 64,
        "artifact_name": "manager-upgrade",
        "rollback_compatible": True,
        "expected_predecessor_image": OLD,
    }
    path = tmp_path / "target.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return m.Target.load(path)


class FakeHost:
    def __init__(self):
        self.manager = OLD
        self.manager_id = OLD_ID
        self.images = {OLD: OLD_ID}
        self.loaded_target_id = NEW_ID
        self.portable_identity_exact = True
        self.stopped = False
        self.stop_calls = 0
        self.start_calls = 0
        self.fail_load = False
        self.fail_start_on_calls = set()
        self.fail_after_start = False
        self.fail_post_start = False
        self.broker = {
            "container_id": "broker-container",
            "image_ref": BROKER,
            "image_id": BROKER_ID,
            "started_at": "2026-11-01T00:00:00Z",
            "restart_count": 0,
            "network_mode": "bridge",
        }
        self.ha = {
            "container_id": "ha-container",
            "image_ref": HA,
            "image_id": HA_ID,
            "started_at": "2026-11-01T00:00:01Z",
            "restart_count": 0,
            "network_mode": "host",
        }

    def render_compose(self):
        return {
            "services": {
                "broker": {
                    "image": BROKER,
                    "pull_policy": "never",
                },
                "manager": {
                    "image": self.manager,
                    "pull_policy": "never",
                    "network_mode": "host",
                },
                "homeassistant": {
                    "image": HA,
                    "pull_policy": "never",
                    "network_mode": "host",
                },
            }
        }

    def inspect(self):
        if self.stopped:
            raise m.UpdaterError("services_stopped")
        if self.fail_after_start:
            self.fail_after_start = False
            raise m.UpdaterError("simulated_post_failure")
        return {
            "manager_image": self.manager,
            "compose_env_sha256": m.sha256_text("env:" + self.manager),
            "compose_render": self.render_compose(),
            "compose_render_sha256": m.sha256_bytes(
                m.canonical(self.render_compose())
            ),
            "services_unit": {
                "execstart_sha256": "x",
                "execstop_sha256": "y",
            },
            "runtime": {
                "broker": dict(self.broker),
                "manager": {
                    "container_id": "manager-container",
                    "image_ref": self.manager,
                    "image_id": self.manager_id,
                    "started_at": "2026-11-01T00:00:02Z",
                    "restart_count": 0,
                    "network_mode": "host",
                },
                "homeassistant": dict(self.ha),
            },
            "listeners": {
                "tcp_8883": 1,
                "tcp_47110": 1,
                "udp_47111": 1,
                "tcp_47112": 0,
            },
        }

    def image_id(self, reference):
        return self.images.get(reference)

    def verify_image_archive(self, reference, tar_path, expected_sha256):
        if self.images.get(reference) is None:
            raise m.UpdaterError("target_image_missing")
        if not self.portable_identity_exact:
            raise m.UpdaterError(
                "target_image_portable_identity_invalid:config_semantics_mismatch"
            )
        return self.images[reference]

    def load_image(self, tar_path):
        if self.fail_load:
            raise m.UpdaterError("simulated_load_failure")
        self.images[NEW] = self.loaded_target_id

    def stop_services(self):
        self.stop_calls += 1
        self.stopped = True

    def start_services(self):
        self.start_calls += 1
        if self.start_calls in self.fail_start_on_calls:
            raise m.UpdaterError("simulated_start_failure")
        self.stopped = False
        self.manager_id = self.images[self.manager]
        if self.fail_post_start:
            self.fail_after_start = True
            self.fail_post_start = False

    def manager_binding(self):
        return self.manager

    def rewrite_manager_image(self, expected, replacement):
        if self.manager != expected:
            raise m.UpdaterError("manager_image_env_predecessor_drift")
        self.manager = replacement
        return m.sha256_text("env:" + self.manager)

    def broker_continuity(self, baseline):
        for key in (
            "container_id",
            "image_ref",
            "image_id",
            "started_at",
            "restart_count",
        ):
            if key in baseline and self.broker[key] != baseline[key]:
                raise m.UpdaterError("broker_continuity_failed")

    def wait_services(self, timeout=120):
        pass


def test_rewrite_manager_env_changes_only_unique_line():
    original = (
        b"A=1\nGH_MANAGER_IMAGE="
        + OLD.encode()
        + b"\nSECRET=x\n"
    )
    changed = m.rewrite_manager_env(original, OLD, NEW)
    assert changed == (
        b"A=1\nGH_MANAGER_IMAGE="
        + NEW.encode()
        + b"\nSECRET=x\n"
    )
    assert m.manager_env_image(changed) == NEW


def test_rewrite_manager_env_fails_on_duplicate():
    payload = (
        f"GH_MANAGER_IMAGE={OLD}\n"
        f"GH_MANAGER_IMAGE={OLD}\n"
    ).encode()
    with pytest.raises(m.UpdaterError, match="line_count"):
        m.rewrite_manager_env(payload, OLD, NEW)


def test_validate_candidate_allows_only_manager_image():
    host = FakeHost()
    before = host.render_compose()
    host.manager = NEW
    after = host.render_compose()
    m.validate_candidate(before, after, OLD, NEW)
    after["services"]["homeassistant"]["image"] = "changed"
    with pytest.raises(m.UpdaterError, match="non_manager"):
        m.validate_candidate(before, after, OLD, NEW)


def test_plan_is_readonly_and_binds_predecessor(tmp_path):
    host = FakeHost()
    updater = m.CoreUpdater(host, m.StateStore(tmp_path / "state"))
    target_value = target(tmp_path)
    result = updater.plan(target_value)
    assert result["mutation"] is False
    assert result["current"]["image"] == OLD
    assert result["target"]["image"] == NEW
    assert result["target_image_prestate"] == "ABSENT"


def test_plan_with_tar_accepts_preexisting_cross_store_runtime_id(tmp_path):
    host = FakeHost()
    host.images[NEW] = NEW_RUNTIME_ID
    updater = m.CoreUpdater(host, m.StateStore(tmp_path / "state"))
    target_value = target(tmp_path)
    result = updater.plan(target_value, tmp_path / "manager.tar")
    assert result["mutation"] is False
    assert result["target_image_prestate"] == "PRESENT_AND_EXACT"
    assert result["manager_tar_verified"] is True


def test_plan_without_tar_requires_portable_proof_for_cross_store_id(tmp_path):
    host = FakeHost()
    host.images[NEW] = NEW_RUNTIME_ID
    updater = m.CoreUpdater(host, m.StateStore(tmp_path / "state"))
    target_value = target(tmp_path)
    with pytest.raises(
        m.UpdaterError,
        match="portable_identity_requires_tar",
    ):
        updater.plan(target_value)


def test_apply_wrong_confirmation_creates_no_state(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    root = tmp_path / "state"
    updater = m.CoreUpdater(host, m.StateStore(root))
    target_value = target(tmp_path)
    with pytest.raises(
        m.UpdaterError,
        match="apply_confirmation_missing",
    ):
        updater.apply(
            target_value,
            tmp_path / "manager.tar",
            authorization_id="N3W_T1_CORE_UPDATER_MANAGER_TEST_BAD_CONFIRM",
            confirmation="WRONG",
        )
    assert not root.exists()


def test_rollback_wrong_confirmation_creates_no_state(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    root = tmp_path / "state"
    updater = m.CoreUpdater(host, m.StateStore(root))
    with pytest.raises(
        m.UpdaterError,
        match="rollback_confirmation_missing",
    ):
        updater.rollback(confirmation="WRONG")
    assert not root.exists()


def test_apply_commits_manager_only_and_preserves_broker_ha(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)
    result = updater.apply(
        target_value,
        tmp_path / "manager.tar",
        authorization_id="N3W_T1_CORE_UPDATER_MANAGER_TEST_01",
        confirmation=m.APPLY_CONFIRMATION,
    )
    assert result["transaction_status"] == "COMMITTED"
    assert host.manager == NEW
    assert host.manager_id == NEW_ID
    assert host.broker["image_id"] == BROKER_ID
    assert host.ha["image_id"] == HA_ID
    assert store.read()["status"] == "COMMITTED"


def test_apply_accepts_cross_store_runtime_id_with_portable_match(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    host.loaded_target_id = NEW_RUNTIME_ID
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)
    result = updater.apply(
        target_value,
        tmp_path / "manager.tar",
        authorization_id="N3W_T1_CORE_UPDATER_MANAGER_TEST_CROSS_STORE",
        confirmation=m.APPLY_CONFIRMATION,
    )
    assert result["transaction_status"] == "COMMITTED"
    assert host.manager == NEW
    assert host.manager_id == NEW_RUNTIME_ID
    assert store.read()["target"]["image_id"] == NEW_ID
    assert store.read()["target_runtime_image_id"] == NEW_RUNTIME_ID


def test_apply_portable_mismatch_rolls_back_before_service_stop(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    host.loaded_target_id = NEW_RUNTIME_ID
    host.portable_identity_exact = False
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)
    with pytest.raises(
        m.UpdaterError,
        match="target_image_portable_identity_invalid",
    ):
        updater.apply(
            target_value,
            tmp_path / "manager.tar",
            authorization_id="N3W_T1_CORE_UPDATER_MANAGER_TEST_PORTABLE_BAD",
            confirmation=m.APPLY_CONFIRMATION,
        )
    assert host.manager == OLD
    assert host.stopped is False
    assert store.read()["status"] == "ROLLED_BACK"
    assert store.read()["phase"] == "ROLLBACK_COMPLETE_PRESTOP"


def test_explicit_rollback_uses_local_runtime_id_after_cross_store_apply(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    host.loaded_target_id = NEW_RUNTIME_ID
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)
    updater.apply(
        target_value,
        tmp_path / "manager.tar",
        authorization_id="N3W_T1_CORE_UPDATER_MANAGER_TEST_CROSS_ROLLBACK",
        confirmation=m.APPLY_CONFIRMATION,
    )
    assert host.manager_id == NEW_RUNTIME_ID
    result = updater.rollback(
        confirmation=m.ROLLBACK_CONFIRMATION
    )
    assert result["transaction_status"] == "ROLLED_BACK"
    assert host.manager == OLD
    assert host.manager_id == OLD_ID


def test_apply_post_failure_automatically_rolls_back(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    host.fail_post_start = True
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)
    with pytest.raises(m.UpdaterError, match="simulated_post_failure"):
        updater.apply(
            target_value,
            tmp_path / "manager.tar",
            authorization_id="N3W_T1_CORE_UPDATER_MANAGER_TEST_02",
            confirmation=m.APPLY_CONFIRMATION,
        )
    assert host.manager == OLD
    assert host.manager_id == OLD_ID
    assert store.read()["status"] == "ROLLED_BACK"


def test_explicit_rollback_restores_predecessor(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)
    updater.apply(
        target_value,
        tmp_path / "manager.tar",
        authorization_id="N3W_T1_CORE_UPDATER_MANAGER_TEST_03",
        confirmation=m.APPLY_CONFIRMATION,
    )
    result = updater.rollback(
        confirmation=m.ROLLBACK_CONFIRMATION
    )
    assert result["transaction_status"] == "ROLLED_BACK"
    assert host.manager == OLD
    assert host.manager_id == OLD_ID
    assert store.read()["status"] == "ROLLED_BACK"


def test_interrupted_poststop_transaction_can_be_recovered(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    host.images[NEW] = NEW_ID
    host.manager = NEW
    host.manager_id = NEW_ID
    host.stopped = True
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)
    store.write({
        "schema": m.TX_SCHEMA,
        "status": "APPLYING",
        "phase": "MANAGER_BINDING_PUBLISHED",
        "component": "manager",
        "predecessor_image": OLD,
        "predecessor_image_id": OLD_ID,
        "target": target_value.public(),
        "pre_stable_runtime": {
            "broker": {
                "image_ref": BROKER,
                "image_id": BROKER_ID,
            },
            "homeassistant": {
                "image_ref": HA,
                "image_id": HA_ID,
                "network_mode": "host",
            },
        },
    })
    result = updater.rollback(
        confirmation=m.ROLLBACK_CONFIRMATION
    )
    assert result["transaction_status"] == "ROLLED_BACK"
    assert result["recovered_from_status"] == "APPLYING"
    assert result["recovered_from_phase"] == "MANAGER_BINDING_PUBLISHED"
    assert host.manager == OLD
    assert host.manager_id == OLD_ID
    assert store.read()["phase"] == "RECOVERY_ROLLBACK_COMPLETE"


@pytest.mark.parametrize(
    "phase",
    ["AUTHORIZED", "TARGET_IMAGE_LOADED"],
)
def test_interrupted_prestop_transaction_recovers_without_restart(
    tmp_path,
    monkeypatch,
    phase,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    host.images[NEW] = NEW_ID
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)
    store.write({
        "schema": m.TX_SCHEMA,
        "status": "APPLYING",
        "phase": phase,
        "component": "manager",
        "predecessor_image": OLD,
        "predecessor_image_id": OLD_ID,
        "target": target_value.public(),
        "pre_stable_runtime": {
            "broker": {
                "image_ref": BROKER,
                "image_id": BROKER_ID,
            },
            "homeassistant": {
                "image_ref": HA,
                "image_id": HA_ID,
                "network_mode": "host",
            },
        },
    })
    result = updater.rollback(
        confirmation=m.ROLLBACK_CONFIRMATION
    )
    assert result["transaction_status"] == "ROLLED_BACK"
    assert result["t1_mutation"] is False
    assert host.manager == OLD
    assert host.stopped is False
    assert store.read()["phase"] == "RECOVERY_COMPLETE_PRESTOP"


def test_status_marks_interrupted_transaction_recovery_required(tmp_path):
    host = FakeHost()
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    store.write({
        "schema": m.TX_SCHEMA,
        "status": "APPLYING",
        "phase": "APPLICATION_SERVICES_STOPPED",
    })
    result = updater.status()
    assert result["recovery_required"] is True


def test_terminal_transaction_archived_before_next_apply(tmp_path):
    store = m.StateStore(tmp_path / "state")
    store.write({
        "schema": m.TX_SCHEMA,
        "status": "COMMITTED",
    })
    store.prepare_new()
    assert store.read() is None
    assert len(
        list((tmp_path / "state" / "history").glob("*.json"))
    ) == 1


def test_transaction_lock_is_exclusive(tmp_path):
    store = m.StateStore(tmp_path / "state")
    with store.lock():
        with pytest.raises(
            m.UpdaterError,
            match="transaction_busy",
        ):
            with store.lock():
                pass


def test_transaction_root_symlink_fails_closed(tmp_path):
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    root = tmp_path / "state"
    root.symlink_to(real, target_is_directory=True)
    store = m.StateStore(root)
    with pytest.raises(
        m.UpdaterError,
        match="root_symlink",
    ):
        with store.lock():
            pass


def test_nonterminal_transaction_blocks_new_apply(tmp_path):
    store = m.StateStore(tmp_path / "state")
    store.write({
        "schema": m.TX_SCHEMA,
        "status": "APPLYING",
    })
    with pytest.raises(
        m.UpdaterError,
        match="transaction_active",
    ):
        store.prepare_new()


def test_target_rejects_unproven_rollback(tmp_path):
    path = tmp_path / "target.json"
    path.write_text(
        json.dumps({
            "schema": m.TARGET_SCHEMA,
            "component": "manager",
            "source_head": "a" * 40,
            "image": NEW,
            "image_id": NEW_ID,
            "tar_sha256": "c" * 64,
            "artifact_id": 1,
            "artifact_digest_sha256": "d" * 64,
            "artifact_name": "x",
            "rollback_compatible": False,
        }),
        encoding="utf-8",
    )
    with pytest.raises(
        m.UpdaterError,
        match="rollback_compatibility",
    ):
        m.Target.load(path)


def test_target_requires_exact_predecessor(tmp_path):
    path = tmp_path / "target.json"
    path.write_text(
        json.dumps({
            "schema": m.TARGET_SCHEMA,
            "component": "manager",
            "source_head": "a" * 40,
            "image": NEW,
            "image_id": NEW_ID,
            "tar_sha256": "c" * 64,
            "artifact_id": 1,
            "artifact_digest_sha256": "d" * 64,
            "artifact_name": "x",
            "rollback_compatible": True,
        }),
        encoding="utf-8",
    )
    with pytest.raises(
        m.UpdaterError,
        match="predecessor_image",
    ):
        m.Target.load(path)


def test_source_has_no_kf131_or_e03_specific_identity():
    source = "\n".join(
        (
            Path(__file__).resolve().parents[2]
            / "tools"
            / name
        ).read_text(encoding="utf-8")
        for name in (
            "n3w_t1_core_updater.py",
            "n3w_t1_core_updater_common.py",
            "n3w_t1_core_updater_core.py",
            "n3w_t1_core_updater_host.py",
            "n3w_t1_core_updater_state.py",
        )
    )
    assert "KF-131" not in source
    assert "PAIRING_SHA256" not in source
    assert "HARDWARE_SHA256" not in source
    assert "R10_E03_MANAGER_SUCCESSOR_REFRESH" not in source

def test_stop_services_accepts_failed_unit_state_when_containers_stopped(
    monkeypatch,
):
    host = hostmod.LocalHost()
    calls = []

    def run(argv, *, timeout=60, check=True):
        calls.append(tuple(argv))

        class Result:
            returncode = 0
            stdout = b""
            stderr = b""

        return Result()

    monkeypatch.setattr(host, "_run", run)
    monkeypatch.setattr(
        host,
        "_systemctl",
        lambda verb, unit: "failed",
    )
    monkeypatch.setattr(host, "_running_count", lambda service: 0)

    host.stop_services()

    assert calls == [
        ("systemctl", "stop", hostmod.SERVICES_UNIT),
    ]


def test_stop_services_failed_unit_state_still_requires_containers_stopped(
    monkeypatch,
):
    host = hostmod.LocalHost()

    monkeypatch.setattr(
        host,
        "_run",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        host,
        "_systemctl",
        lambda verb, unit: "failed",
    )
    monkeypatch.setattr(
        host,
        "_running_count",
        lambda service: 1 if service == "manager" else 0,
    )

    with pytest.raises(
        m.UpdaterError,
        match="application_container_still_running",
    ):
        host.stop_services()


def test_stop_services_rejects_active_unit_state(monkeypatch):
    host = hostmod.LocalHost()

    monkeypatch.setattr(
        host,
        "_run",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        host,
        "_systemctl",
        lambda verb, unit: "active",
    )

    with pytest.raises(
        m.UpdaterError,
        match="services_not_inactive",
    ):
        host.stop_services()


def test_wait_services_waits_for_listener_contract(monkeypatch):
    host = hostmod.LocalHost()
    monkeypatch.setattr(host, "_systemctl", lambda verb, unit: "active")
    monkeypatch.setattr(
        host,
        "_container_id",
        lambda service: f"{service}-container",
    )
    listeners = [
        {
            "tcp_8883": 1,
            "tcp_47110": 0,
            "udp_47111": 0,
            "tcp_47112": 0,
        },
        dict(hostmod.EXPECTED_LISTENERS),
    ]
    monkeypatch.setattr(
        host,
        "_listener_snapshot",
        lambda: listeners.pop(0),
    )
    monkeypatch.setattr(
        host,
        "observe_v2",
        lambda: {
            "listeners": dict(hostmod.EXPECTED_LISTENERS),
            "mqtt_authenticated": {
                "manager": True,
                "homeassistant": True,
            },
            "homeassistant_http_status": 401,
        },
    )
    ticks = iter((0.0, 0.1, 0.2, 0.3))
    monkeypatch.setattr(hostmod.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(hostmod.time, "sleep", lambda seconds: None)

    host.wait_services(timeout=10)

    assert listeners == []


def test_wait_services_waits_for_soft_health_convergence(monkeypatch):
    host = hostmod.LocalHost()
    monkeypatch.setattr(host, "_systemctl", lambda verb, unit: "active")
    monkeypatch.setattr(
        host,
        "_container_id",
        lambda service: f"{service}-container",
    )
    monkeypatch.setattr(
        host,
        "_listener_snapshot",
        lambda: dict(hostmod.EXPECTED_LISTENERS),
    )
    samples = [
        {
            "listeners": dict(hostmod.EXPECTED_LISTENERS),
            "mqtt_authenticated": {
                "manager": False,
                "homeassistant": False,
            },
            "homeassistant_http_status": None,
        },
        {
            "listeners": dict(hostmod.EXPECTED_LISTENERS),
            "mqtt_authenticated": {
                "manager": True,
                "homeassistant": False,
            },
            "homeassistant_http_status": 401,
        },
        {
            "listeners": dict(hostmod.EXPECTED_LISTENERS),
            "mqtt_authenticated": {
                "manager": True,
                "homeassistant": True,
            },
            "homeassistant_http_status": None,
        },
        {
            "listeners": dict(hostmod.EXPECTED_LISTENERS),
            "mqtt_authenticated": {
                "manager": True,
                "homeassistant": True,
            },
            "homeassistant_http_status": 401,
        },
    ]
    monkeypatch.setattr(host, "observe_v2", lambda: samples.pop(0))
    clock = [0.0]
    monkeypatch.setattr(hostmod.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        hostmod.time,
        "sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )

    host.wait_services(timeout=20)

    assert samples == []


def test_wait_services_does_not_mask_hard_runtime_drift(monkeypatch):
    host = hostmod.LocalHost()
    monkeypatch.setattr(host, "_systemctl", lambda verb, unit: "active")
    monkeypatch.setattr(
        host,
        "_container_id",
        lambda service: f"{service}-container",
    )
    monkeypatch.setattr(
        host,
        "_listener_snapshot",
        lambda: dict(hostmod.EXPECTED_LISTENERS),
    )

    def fail_hard():
        raise m.UpdaterError("manager_runtime_image_drift")

    monkeypatch.setattr(host, "observe_v2", fail_hard)

    with pytest.raises(
        m.UpdaterError,
        match="manager_runtime_image_drift",
    ):
        host.wait_services(timeout=120)


def test_observe_v2_keeps_structural_snapshot_while_mqtt_converges(
    monkeypatch,
):
    host = hostmod.LocalHost()
    base = {
        "manager_image": "local/greenhouse-manager:fresh-a",
        "compose_env_sha256": "a" * 64,
        "compose_render": {
            "services": {
                "manager": {"image": "local/greenhouse-manager:fresh-a"},
                "homeassistant": {"image": "local/n3w-homeassistant:x"},
                "broker": {"image": "local/n3w-mosquitto:x"},
            }
        },
        "compose_render_sha256": "b" * 64,
        "services_unit": {},
        "runtime": {
            "manager": {"image_ref": "local/greenhouse-manager:fresh-a"},
            "homeassistant": {"image_ref": "local/n3w-homeassistant:x"},
            "broker": {"image_ref": "local/n3w-mosquitto:x"},
        },
        "listeners": dict(hostmod.EXPECTED_LISTENERS),
        "runtime_services": ["broker", "homeassistant", "manager"],
        "system_health": {},
    }
    bindings = {
        "manager": "local/greenhouse-manager:fresh-a",
        "homeassistant": "local/n3w-homeassistant:x",
        "broker": "local/n3w-mosquitto:x",
    }
    monkeypatch.setattr(host, "_observe_running_base_v2", lambda: base)
    monkeypatch.setattr(
        host,
        "_image_binding_authority_v2",
        lambda rendered=None: (
            bindings,
            {
                "manager": "dynamic",
                "homeassistant": "legacy_static",
                "broker": "legacy_static",
            },
        ),
    )
    monkeypatch.setattr(
        host,
        "_mqtt_authenticated",
        lambda service: service == "manager",
    )
    monkeypatch.setattr(
        host,
        "_homeassistant_http_status",
        lambda allow_unavailable=False: None,
    )

    snapshot = host.observe_v2()

    assert snapshot["image_bindings"] == bindings
    assert snapshot["mqtt_authenticated"] == {
        "manager": True,
        "homeassistant": False,
    }
    assert snapshot["homeassistant_http_status"] is None
    with pytest.raises(
        m.UpdaterError,
        match="mqtt_current_authentication_missing",
    ):
        host._validate_converged_health_v2(snapshot)


def test_failed_emergency_can_close_without_runtime_mutation(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)
    store.write({
        "schema": m.TX_SCHEMA,
        "status": "FAILED_EMERGENCY",
        "phase": "ROLLBACK_FAILED",
        "component": "manager",
        "predecessor_image": OLD,
        "predecessor_image_id": OLD_ID,
        "target": target_value.public(),
        "target_runtime_image_id": NEW_RUNTIME_ID,
        "pre_stable_runtime": {
            "broker": {
                "image_ref": BROKER,
                "image_id": BROKER_ID,
            },
            "homeassistant": {
                "image_ref": HA,
                "image_id": HA_ID,
                "network_mode": "host",
            },
        },
    })

    result = updater.rollback(
        confirmation=m.ROLLBACK_CONFIRMATION
    )

    assert result["transaction_status"] == "ROLLED_BACK"
    assert result["recovered_from_status"] == "FAILED_EMERGENCY"
    assert result["recovered_from_phase"] == "ROLLBACK_FAILED"
    assert result["t1_mutation"] is False
    assert host.manager == OLD
    assert host.manager_id == OLD_ID
    assert store.read()["status"] == "ROLLED_BACK"
    assert (
        store.read()["phase"]
        == "RECOVERY_COMPLETE_FAILED_EMERGENCY"
    )


def _write_nonterminal_transaction(
    store,
    target_value,
    *,
    status,
    phase,
):
    store.write({
        "schema": m.TX_SCHEMA,
        "status": status,
        "phase": phase,
        "component": "manager",
        "predecessor_image": OLD,
        "predecessor_image_id": OLD_ID,
        "target": target_value.public(),
        "target_runtime_image_id": NEW_RUNTIME_ID,
        "pre_stable_runtime": {
            "broker": {
                "image_ref": BROKER,
                "image_id": BROKER_ID,
            },
            "homeassistant": {
                "image_ref": HA,
                "image_id": HA_ID,
                "network_mode": "host",
            },
        },
    })


def test_stopping_phase_with_predecessor_healthy_closes_without_restart(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)
    _write_nonterminal_transaction(
        store,
        target_value,
        status="APPLYING",
        phase="STOPPING_APPLICATION_SERVICES",
    )

    result = updater.rollback(
        confirmation=m.ROLLBACK_CONFIRMATION
    )

    assert result["transaction_status"] == "ROLLED_BACK"
    assert result["t1_mutation"] is False
    assert host.manager == OLD
    assert host.manager_id == OLD_ID
    assert host.stop_calls == 0
    assert host.start_calls == 0


def test_target_runtime_started_nonterminal_rolls_back_to_predecessor(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    host.images[NEW] = NEW_RUNTIME_ID
    host.manager = NEW
    host.manager_id = NEW_RUNTIME_ID
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)
    _write_nonterminal_transaction(
        store,
        target_value,
        status="APPLYING",
        phase="TARGET_RUNTIME_STARTED",
    )

    result = updater.rollback(
        confirmation=m.ROLLBACK_CONFIRMATION
    )

    assert result["transaction_status"] == "ROLLED_BACK"
    assert host.manager == OLD
    assert host.manager_id == OLD_ID
    assert host.stop_calls == 1
    assert host.start_calls == 1


def test_rolling_back_with_predecessor_healthy_is_reentrant_without_restart(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)
    _write_nonterminal_transaction(
        store,
        target_value,
        status="ROLLING_BACK",
        phase="RECOVERY_ROLLBACK_AUTHORIZED",
    )

    result = updater.rollback(
        confirmation=m.ROLLBACK_CONFIRMATION
    )

    assert result["transaction_status"] == "ROLLED_BACK"
    assert result["t1_mutation"] is False
    assert host.manager == OLD
    assert host.manager_id == OLD_ID
    assert host.stop_calls == 0
    assert host.start_calls == 0


def test_rolling_back_with_target_active_is_reentrant_and_restores_predecessor(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    host.images[NEW] = NEW_RUNTIME_ID
    host.manager = NEW
    host.manager_id = NEW_RUNTIME_ID
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)
    _write_nonterminal_transaction(
        store,
        target_value,
        status="ROLLING_BACK",
        phase="RECOVERY_ROLLBACK_AUTHORIZED",
    )

    result = updater.rollback(
        confirmation=m.ROLLBACK_CONFIRMATION
    )

    assert result["transaction_status"] == "ROLLED_BACK"
    assert host.manager == OLD
    assert host.manager_id == OLD_ID
    assert host.stop_calls == 1
    assert host.start_calls == 1


def test_failed_emergency_with_target_active_can_restore_predecessor(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    host.images[NEW] = NEW_RUNTIME_ID
    host.manager = NEW
    host.manager_id = NEW_RUNTIME_ID
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)
    _write_nonterminal_transaction(
        store,
        target_value,
        status="FAILED_EMERGENCY",
        phase="ROLLBACK_FAILED",
    )

    result = updater.rollback(
        confirmation=m.ROLLBACK_CONFIRMATION
    )

    assert result["transaction_status"] == "ROLLED_BACK"
    assert host.manager == OLD
    assert host.manager_id == OLD_ID
    assert host.stop_calls == 1
    assert host.start_calls == 1


def test_failed_emergency_unknown_binding_fails_before_service_mutation(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    host.manager = "local/greenhouse-manager:fresh-deadbeefdead"
    host.manager_id = "sha256:" + "9" * 64
    host.images[host.manager] = host.manager_id
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)
    _write_nonterminal_transaction(
        store,
        target_value,
        status="FAILED_EMERGENCY",
        phase="ROLLBACK_FAILED",
    )

    with pytest.raises(m.UpdaterError):
        updater.rollback(
            confirmation=m.ROLLBACK_CONFIRMATION
        )

    assert host.stop_calls == 0
    assert host.start_calls == 0
    assert store.read()["status"] == "FAILED_EMERGENCY"


def test_terminal_rolled_back_recovery_does_not_replay(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    store.write({
        "schema": m.TX_SCHEMA,
        "status": "ROLLED_BACK",
        "phase": "RECOVERY_ROLLBACK_COMPLETE",
    })

    with pytest.raises(
        m.UpdaterError,
        match="recoverable_transaction_required",
    ):
        updater.rollback(
            confirmation=m.ROLLBACK_CONFIRMATION
        )

    assert host.stop_calls == 0
    assert host.start_calls == 0

def test_target_load_failure_rolls_back_prestop_without_service_restart(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    host.fail_load = True
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)

    with pytest.raises(
        m.UpdaterError,
        match="simulated_load_failure",
    ):
        updater.apply(
            target_value,
            tmp_path / "manager.tar",
            authorization_id="N3W_T1_CORE_UPDATER_MANAGER_TEST_LOAD_FAIL",
            confirmation=m.APPLY_CONFIRMATION,
        )

    assert host.manager == OLD
    assert host.stop_calls == 0
    assert host.start_calls == 0
    assert store.read()["status"] == "ROLLED_BACK"
    assert store.read()["phase"] == "ROLLBACK_COMPLETE_PRESTOP"


def test_target_start_failure_automatically_restores_predecessor(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    host.fail_start_on_calls = {1}
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)

    with pytest.raises(
        m.UpdaterError,
        match="simulated_start_failure",
    ):
        updater.apply(
            target_value,
            tmp_path / "manager.tar",
            authorization_id="N3W_T1_CORE_UPDATER_MANAGER_TEST_START_FAIL",
            confirmation=m.APPLY_CONFIRMATION,
        )

    assert host.manager == OLD
    assert host.manager_id == OLD_ID
    assert host.stop_calls == 2
    assert host.start_calls == 2
    assert store.read()["status"] == "ROLLED_BACK"


def test_rollback_start_failure_is_recoverable_on_next_explicit_recovery(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    host.fail_post_start = True
    host.fail_start_on_calls = {2}
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)

    with pytest.raises(
        m.UpdaterError,
        match="automatic_rollback_failed",
    ):
        updater.apply(
            target_value,
            tmp_path / "manager.tar",
            authorization_id="N3W_T1_CORE_UPDATER_MANAGER_TEST_RB_START_FAIL",
            confirmation=m.APPLY_CONFIRMATION,
        )

    assert store.read()["status"] == "FAILED_EMERGENCY"
    assert store.read()["phase"] == "ROLLBACK_FAILED"
    assert host.manager == OLD
    assert host.stopped is True

    host.fail_start_on_calls = set()

    result = updater.rollback(
        confirmation=m.ROLLBACK_CONFIRMATION
    )

    assert result["transaction_status"] == "ROLLED_BACK"
    assert host.manager == OLD
    assert host.manager_id == OLD_ID
    assert host.stopped is False
    assert store.read()["status"] == "ROLLED_BACK"


def test_application_stopped_with_predecessor_binding_recovers_by_starting_a(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    host.stopped = True
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)
    _write_nonterminal_transaction(
        store,
        target_value,
        status="APPLYING",
        phase="APPLICATION_SERVICES_STOPPED",
    )

    result = updater.rollback(
        confirmation=m.ROLLBACK_CONFIRMATION
    )

    assert result["transaction_status"] == "ROLLED_BACK"
    assert result["t1_mutation"] is True
    assert host.manager == OLD
    assert host.manager_id == OLD_ID
    assert host.stopped is False
    assert host.stop_calls == 1
    assert host.start_calls == 1

def test_wait_services_times_out_if_listener_contract_never_converges(
    monkeypatch,
):
    host = hostmod.LocalHost()
    monkeypatch.setattr(host, "_systemctl", lambda verb, unit: "active")
    monkeypatch.setattr(
        host,
        "_container_id",
        lambda service: f"{service}-container",
    )
    monkeypatch.setattr(
        host,
        "_listener_snapshot",
        lambda: {
            "tcp_8883": 1,
            "tcp_47110": 0,
            "udp_47111": 0,
            "tcp_47112": 0,
        },
    )
    clock = [0.0]
    monkeypatch.setattr(hostmod.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        hostmod.time,
        "sleep",
        lambda seconds: clock.__setitem__(
            0,
            clock[0] + seconds,
        ),
    )

    with pytest.raises(
        m.UpdaterError,
        match="services_readiness_timeout",
    ):
        host.wait_services(timeout=5)


def test_homeassistant_identity_drift_fails_closed_after_restoring_manager_a(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    original_start = host.start_services

    def start_with_ha_drift():
        original_start()
        if host.start_calls == 1:
            host.ha["image_id"] = "sha256:" + "8" * 64

    host.start_services = start_with_ha_drift
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)

    with pytest.raises(
        m.UpdaterError,
        match="automatic_rollback_failed",
    ):
        updater.apply(
            target_value,
            tmp_path / "manager.tar",
            authorization_id="N3W_T1_CORE_UPDATER_MANAGER_TEST_HA_DRIFT",
            confirmation=m.APPLY_CONFIRMATION,
        )

    assert host.manager == OLD
    assert host.manager_id == OLD_ID
    assert host.ha["image_id"] != HA_ID
    assert store.read()["status"] == "FAILED_EMERGENCY"
    assert store.read()["phase"] == "ROLLBACK_FAILED"


def test_broker_identity_drift_fails_closed_without_broker_mutation(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(m.os, "geteuid", lambda: 0)
    host = FakeHost()
    original_start = host.start_services

    def start_with_broker_drift():
        original_start()
        if host.start_calls == 1:
            host.broker["image_id"] = "sha256:" + "7" * 64

    host.start_services = start_with_broker_drift
    store = m.StateStore(tmp_path / "state")
    updater = m.CoreUpdater(host, store)
    target_value = target(tmp_path)

    with pytest.raises(
        m.UpdaterError,
        match="automatic_rollback_failed",
    ):
        updater.apply(
            target_value,
            tmp_path / "manager.tar",
            authorization_id="N3W_T1_CORE_UPDATER_MANAGER_TEST_BROKER_DRIFT",
            confirmation=m.APPLY_CONFIRMATION,
        )

    assert host.manager == OLD
    assert host.manager_id == OLD_ID
    assert host.broker["image_id"] != BROKER_ID
    assert store.read()["status"] == "FAILED_EMERGENCY"
    assert store.read()["phase"] == "ROLLBACK_FAILED"

