from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import n3w_t1_core_updater_v2 as core
from n3w_t1_core_updater_v2_common import (
    APPLY_CONFIRMATION_V2,
    ROLLBACK_CONFIRMATION_V2,
    TX_SCHEMA_V2,
    ComponentTarget,
    UpgradeBaseline,
    UpdaterV2Error,
    sha256_file,
)
from n3w_t1_core_updater_v2_state import V2StateStore

TARGET_PATH = ROOT / "infra/n3w-t1/upgrades/manager-5b32e1ae8210.json"
BASELINE_PATH = ROOT / "infra/n3w-t1/clean-reference/u0-upgrade-baseline-a-20261104.json"
PRE_U1_PATH = ROOT / "infra/n3w-t1/clean-reference/pre-u1-business-runtime-reference-20261104.json"
AUTHORITY_PATH = ROOT / "infra/n3w-t1/production/t1-core-stack-current.json"
BASELINE_FILE_SHA256 = "a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ReferencePolicy:
    def __init__(self, baseline: UpgradeBaseline) -> None:
        self.baseline = baseline

    def capture(self) -> dict:
        return {"hard": self.baseline.a1_hard_authority, "soft": "healthy"}

    def hard_authority(self, snapshot: dict) -> dict:
        return snapshot["hard"]

    def validate_baseline(self, component: str, snapshot: dict, expected: dict) -> None:
        assert component == "manager"
        assert self.hard_authority(snapshot) == expected

    def validate_pre(self, component: str, snapshot: dict) -> None:
        assert component == "manager"
        assert snapshot["soft"] == "healthy"

    def validate_post(self, component: str, before: dict, after: dict) -> None:
        assert component == "manager"
        assert before["hard"] == after["hard"] == self.baseline.a1_hard_authority


class ReferenceV2Host:
    def __init__(
        self,
        *,
        target: ComponentTarget,
        baseline: UpgradeBaseline,
        authority: dict,
        package_binding: dict,
    ) -> None:
        current = authority["current_repository_stack"]
        live = authority["live_deployment"]
        self.target = target
        self.baseline = baseline
        self.bindings = dict(baseline.stack_images)
        self.modes = dict(baseline.image_binding_modes)
        self.contracts = dict(baseline.runtime_contract_sha256)
        self.image_ids = {
            self.bindings["manager"]: live["current_manager_runtime_image_id"],
            self.bindings["homeassistant"]: current["homeassistant"]["image_id"],
            self.bindings["broker"]: current["broker"]["image_id"],
        }
        self.target_image_id = package_binding["manager_build_image_id"]
        self.events: list[str] = []

    def _render(self) -> dict:
        return {
            "services": {
                name: {
                    "image": self.bindings[name],
                    "network_mode": "host" if name in {"manager", "homeassistant"} else "bridge",
                }
                for name in ("manager", "homeassistant", "broker")
            }
        }

    def inspect_v2(self) -> dict:
        runtime = {
            name: {
                "image_ref": self.bindings[name],
                "image_id": self.image_ids[self.bindings[name]],
                "network_mode": "host" if name in {"manager", "homeassistant"} else "bridge",
                "platform": "linux/arm64",
                "container_id": f"{name}-container",
                "started_at": "pre-u1",
                "restart_count": 0,
                "runtime_contract_sha256": self.contracts[name],
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
            "services_unit": {"execstart_sha256": "c" * 64, "execstop_sha256": "d" * 64},
            "runtime": runtime,
            "listeners": {"tcp_8883": 1, "tcp_47110": 1, "udp_47111": 1, "tcp_47112": 0},
            "mqtt_authenticated": {"manager": True, "homeassistant": True},
            "homeassistant_http_status": 200,
        }

    def assert_mutation_safe(self, component: str) -> None:
        assert component == "manager"

    def assert_component_upgradeable(self, component: str) -> None:
        assert component == "manager"
        assert self.modes[component] == "dynamic"

    def release_component_guard(self) -> None:
        self.events.append("release-guard")

    def component_binding_v2(self, component: str) -> str:
        return self.bindings[component]

    def image_id(self, reference: str) -> str | None:
        return self.image_ids.get(reference)

    def verify_image_archive(self, reference: str, tar_path: Path, expected_sha256: str) -> str:
        assert sha256_file(tar_path) == expected_sha256
        value = self.image_ids.get(reference)
        if value is None:
            raise UpdaterV2Error("target_image_missing")
        return value

    def load_image(self, tar_path: Path) -> None:
        assert sha256_file(tar_path) == self.target.target_archive_sha256
        self.image_ids[self.target.target_image_ref] = self.target_image_id
        self.events.append("load")

    def rewrite_component_image(self, component: str, expected: str, replacement: str) -> str:
        assert self.bindings[component] == expected
        self.bindings[component] = replacement
        self.events.append(f"rewrite:{component}")
        return "e" * 64

    def render_compose(self) -> dict:
        return self._render()

    def quiesce_component(self, component: str) -> None:
        self.events.append(f"quiesce:{component}")

    def activate_component(self, component: str) -> None:
        self.events.append(f"activate:{component}")


def test_u1_v2_exact_package_against_frozen_pre_u1_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_dir = Path(os.environ["U1_MANAGER_PACKAGE_DIR"])
    manager_tar = package_dir / "greenhouse-manager-arm64.tar"
    package_target = package_dir / "manager-target-v2.json"
    package_baseline = package_dir / "upgrade-baseline-a.json"
    package_binding = _read(package_dir / "package-binding.json")

    pre_u1 = _read(PRE_U1_PATH)
    authority = _read(AUTHORITY_PATH)
    target = ComponentTarget.load(TARGET_PATH)
    baseline = UpgradeBaseline.load(BASELINE_PATH)

    assert sha256_file(BASELINE_PATH) == BASELINE_FILE_SHA256
    assert _read(package_target) == _read(TARGET_PATH)
    assert _read(package_baseline) == _read(BASELINE_PATH)
    assert pre_u1["result"] == "CLOSED_PASS"
    assert pre_u1["upgrade_safety"]["fresh_reads_byte_identical"] is True
    assert pre_u1["upgrade_safety"]["fresh_baseline_equals_u0"] is True

    manager_a = pre_u1["stack"]["images"]["manager"]
    assert baseline.stack_images["manager"] == manager_a
    assert target.expected_predecessor_image_ref == manager_a
    assert target.target_image_ref == "local/greenhouse-manager:fresh-5b32e1ae8210"
    assert target.target_archive_sha256 == sha256_file(manager_tar)
    assert target.rollback_compatible is True

    assert package_binding["schema"] == "gh.n3w-t1-core-updater-manager-package/2"
    assert package_binding["target_schema"] == "gh.n3w-t1-core-updater-target/2"
    assert package_binding["transaction_schema"] == TX_SCHEMA_V2
    assert package_binding["manager_image"] == target.target_image_ref
    assert package_binding["manager_tar_sha256"] == target.target_archive_sha256
    assert package_binding["manager_rebuilt"] is False
    assert package_binding["t1_mutation"] is False

    host = ReferenceV2Host(
        target=target,
        baseline=baseline,
        authority=authority,
        package_binding=package_binding,
    )
    store = V2StateStore(tmp_path / "state")
    store.write({
        "schema": TX_SCHEMA_V2,
        "status": "COMMITTED",
        "phase": "COMMITTED",
        "component": "manager",
    })
    updater = core.MultiComponentCoreUpdater(host, store, ReferencePolicy(baseline))

    status_before = updater.status()
    assert status_before["status"] == "PASS"
    assert status_before["recovery_required"] is False
    assert status_before["transaction"]["status"] == "COMMITTED"

    inspected = updater.inspect("manager")
    assert inspected["status"] == "PASS"
    assert inspected["mutation"] is False
    assert inspected["snapshot"]["image_bindings"]["manager"] == manager_a

    planned = updater.plan(target, baseline, manager_tar)
    assert planned["status"] == "PASS"
    assert planned["mutation"] is False
    assert planned["current"]["image"] == manager_a
    assert planned["target"]["target_image_ref"] == target.target_image_ref
    assert planned["target_image_prestate"] == "ABSENT"
    assert planned["target_archive_verified"] is True
    assert planned["rollback_available"] is True

    monkeypatch.setattr(core.os, "geteuid", lambda: 0)
    applied = updater.apply(
        target,
        baseline,
        manager_tar,
        authorization_id="N3W_T1_CORE_UPDATER_MANAGER_U1_V2_SIMULATION",
        confirmation=APPLY_CONFIRMATION_V2,
    )
    assert applied["transaction_status"] == "COMMITTED"
    assert host.bindings["manager"] == target.target_image_ref
    assert host.bindings["homeassistant"] == baseline.stack_images["homeassistant"]
    assert host.bindings["broker"] == baseline.stack_images["broker"]
    assert len(list((tmp_path / "state" / "history").glob("*-v2-*.json"))) == 1

    status_after = updater.status()
    assert status_after["transaction"]["status"] == "COMMITTED"
    assert status_after["transaction"]["target"]["schema"] == "gh.n3w-t1-core-updater-target/2"

    rolled_back = updater.rollback(confirmation=ROLLBACK_CONFIRMATION_V2)
    assert rolled_back["transaction_status"] == "ROLLED_BACK"
    assert host.bindings["manager"] == manager_a
    assert host.bindings["homeassistant"] == baseline.stack_images["homeassistant"]
    assert host.bindings["broker"] == baseline.stack_images["broker"]
