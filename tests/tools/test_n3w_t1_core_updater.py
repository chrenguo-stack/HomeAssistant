from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import n3w_t1_core_updater_common as common
import n3w_t1_core_updater_core as core
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
        self.stopped = False
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

    def load_image(self, tar_path):
        self.images[NEW] = NEW_ID

    def stop_services(self):
        self.stopped = True

    def start_services(self):
        self.stopped = False
        self.manager_id = self.images[self.manager]
        if self.fail_post_start:
            self.fail_after_start = True
            self.fail_post_start = False

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
            if self.broker[key] != baseline[key]:
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
