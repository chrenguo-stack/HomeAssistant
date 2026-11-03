from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

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
        compatibility_evidence={"peer_contracts": "proved"},
        a1_classification_sha256=A1_CLASSIFICATION_SHA256,
    )


def manifest(component: str, archive_sha: str) -> dict:
    t = target(component, archive_sha)
    return t.public()


def baseline() -> UpgradeBaseline:
    return UpgradeBaseline(
        stack_images=dict(OLD),
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

    def assert_mutation_safe(self, component):
        assert component in OLD

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


def test_v2_manifest_rejects_wrong_a1_authority(tmp_path: Path):
    doc = manifest("manager", "f" * 64)
    doc["a1_classification_sha256"] = "0" * 64
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(UpdaterV2Error, match="target_a1_authority_mismatch"):
        ComponentTarget.load(path)


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


def test_candidate_validation_rejects_cross_component_drift():
    before = {
        "services": {
            name: {"image": OLD[name], "x": name}
            for name in OLD
        }
    }
    after = json.loads(json.dumps(before))
    after["services"]["manager"]["image"] = NEW["manager"]
    validate_component_candidate(
        before,
        after,
        "manager",
        OLD["manager"],
        NEW["manager"],
    )
    after["services"]["homeassistant"]["x"] = "drift"
    with pytest.raises(UpdaterV2Error, match="candidate_non_target_drift"):
        validate_component_candidate(
            before,
            after,
            "manager",
            OLD["manager"],
            NEW["manager"],
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
    ]
    tx = store.read()
    assert tx["schema"] == TX_SCHEMA_V2
    assert tx["status"] == "COMMITTED"
    assert tx["component"] == component


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
