from __future__ import annotations

import hashlib
import json
import os
import subprocess
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


TARGET_PATH = ROOT / "infra/n3w-t1/upgrades/manager-7807271e4c48.json"
BASELINE_PATH = (
    ROOT
    / "infra/n3w-t1/clean-reference/"
    "r7a-repaired-manager-predecessor-bf38-baseline-20261108.json"
)
PREDECESSOR_IMAGE = "local/greenhouse-manager:fresh-bf38e388497b"
TARGET_IMAGE = "local/greenhouse-manager:fresh-7807271e4c48"
PREDECESSOR_RUNTIME_IMAGE_ID = (
    "sha256:e88a22b29b93b0db0d3b4f592cb0fd773169d1dc0f043219f14d5247ed859dff"
)
DERIVED_BASELINE_CANONICAL_SHA256 = (
    "2c0f8a9a1b4634eab2a54a42c29ec9a6c9159972d3069043f49fd3ddd5583bc5"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class ReferencePolicy:
    def __init__(self, baseline: UpgradeBaseline) -> None:
        self.baseline = baseline

    def capture(self) -> dict:
        return {"hard": self.baseline.a1_hard_authority, "soft": "healthy"}

    def hard_authority(self, snapshot: dict) -> dict:
        return snapshot["hard"]

    def validate_baseline(
        self,
        component: str,
        snapshot: dict,
        expected: dict,
    ) -> None:
        assert component == "manager"
        assert self.hard_authority(snapshot) == expected

    def validate_pre(self, component: str, snapshot: dict) -> None:
        assert component == "manager"
        assert snapshot["soft"] == "healthy"

    def validate_post(
        self,
        component: str,
        before: dict,
        after: dict,
    ) -> None:
        assert component == "manager"
        assert before["hard"] == after["hard"] == (
            self.baseline.a1_hard_authority
        )


class ReferenceV2Host:
    def __init__(
        self,
        *,
        target: ComponentTarget,
        baseline: UpgradeBaseline,
        package_binding: dict,
    ) -> None:
        self.target = target
        self.baseline = baseline
        self.bindings = dict(baseline.stack_images)
        self.modes = dict(baseline.image_binding_modes)
        self.contracts = dict(baseline.runtime_contract_sha256)
        self.image_ids = {
            self.bindings["manager"]: PREDECESSOR_RUNTIME_IMAGE_ID,
            self.bindings["homeassistant"]: (
                "sha256:b0e1ee82adfb19fa1ff3049034535633"
                "b1c4f0df6606721c0e77383854b99879"
            ),
            self.bindings["broker"]: (
                "sha256:4c199d7c9d377d018313a2199f683997"
                "8f6fd2219c405ad664d0a830c14b9c7b"
            ),
        }
        self.target_image_id = package_binding["manager_build_image_id"]
        self.events: list[str] = []

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
                "started_at": "pre-r7a-repair",
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

    def observe_v2(self) -> dict:
        return self.inspect_v2()

    def observe_state_v2(self) -> dict:
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

    def wait_services(self, timeout: int = 120) -> None:
        del timeout

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

    def verify_image_archive(
        self,
        reference: str,
        tar_path: Path,
        expected_sha256: str,
    ) -> str:
        assert sha256_file(tar_path) == expected_sha256
        value = self.image_ids.get(reference)
        if value is None:
            raise UpdaterV2Error("target_image_missing")
        return value

    def load_image(self, tar_path: Path) -> None:
        assert sha256_file(tar_path) == self.target.target_archive_sha256
        self.image_ids[self.target.target_image_ref] = self.target_image_id
        self.events.append("load")

    def rewrite_component_image(
        self,
        component: str,
        expected: str,
        replacement: str,
    ) -> str:
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


def test_repaired_manager_package_against_bf38_predecessor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_dir = Path(os.environ["U1_MANAGER_PACKAGE_DIR"])
    manager_tar = package_dir / "greenhouse-manager-arm64.tar"
    package_target = package_dir / "manager-target-v2.json"
    package_baseline = package_dir / "upgrade-baseline-a.json"
    package_binding = _read(package_dir / "package-binding.json")
    updater_pyz = package_dir / "t1-core-updater.pyz"

    target = ComponentTarget.load(TARGET_PATH)
    baseline = UpgradeBaseline.load(BASELINE_PATH)

    assert _read(package_target) == _read(TARGET_PATH)
    assert _read(package_baseline) == _read(BASELINE_PATH)
    assert hashlib.sha256(
        _canonical(_read(BASELINE_PATH))
    ).hexdigest() == DERIVED_BASELINE_CANONICAL_SHA256
    assert baseline.stack_images["manager"] == PREDECESSOR_IMAGE
    assert target.expected_predecessor_image_ref == PREDECESSOR_IMAGE
    assert target.target_image_ref == TARGET_IMAGE
    assert target.target_archive_sha256 == sha256_file(manager_tar)
    assert target.rollback_compatible is True

    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    assert package_binding["control_plane_head"] == head
    assert package_binding["schema"] == (
        "gh.n3w-t1-core-updater-manager-package/2"
    )
    assert package_binding["target_source_head"] == (
        "7807271e4c48161f2fad96a7886fa4c24b038321"
    )
    assert package_binding["upstream_run_id"] == 42452239964
    assert package_binding["upstream_artifact_id"] == 13615963302
    assert package_binding["upstream_artifact_digest_sha256"] == (
        "72b05593b91c75912e05ccd3b00bc72"
        "af5bd7ec03e39c283d0ce7acfb513fbe7"
    )
    assert package_binding["manager_image"] == TARGET_IMAGE
    assert package_binding["manager_tar_sha256"] == (
        target.target_archive_sha256
    )
    assert sha256_file(updater_pyz) == package_binding["updater_pyz_sha256"]
    assert package_binding["manager_rebuilt"] is False
    assert package_binding["homeassistant_included"] is False
    assert package_binding["broker_included"] is False
    assert package_binding["t1_mutation"] is False
    assert package_binding["board_access"] is False

    host = ReferenceV2Host(
        target=target,
        baseline=baseline,
        package_binding=package_binding,
    )
    store = V2StateStore(tmp_path / "state")
    store.write(
        {
            "schema": TX_SCHEMA_V2,
            "status": "COMMITTED",
            "phase": "COMMITTED",
            "component": "manager",
        }
    )
    updater = core.MultiComponentCoreUpdater(
        host,
        store,
        ReferencePolicy(baseline),
    )

    status_before = updater.status()
    assert status_before["status"] == "PASS"
    assert status_before["recovery_required"] is False

    inspected = updater.inspect("manager")
    assert inspected["status"] == "PASS"
    assert inspected["mutation"] is False
    assert (
        inspected["snapshot"]["image_bindings"]["manager"]
        == PREDECESSOR_IMAGE
    )

    planned = updater.plan(target, baseline, manager_tar)
    assert planned["status"] == "PASS"
    assert planned["mutation"] is False
    assert planned["current"]["image"] == PREDECESSOR_IMAGE
    assert planned["target"]["target_image_ref"] == TARGET_IMAGE
    assert planned["target_image_prestate"] == "ABSENT"
    assert planned["target_archive_verified"] is True
    assert planned["rollback_available"] is True

    monkeypatch.setattr(core.os, "geteuid", lambda: 0)
    applied = updater.apply(
        target,
        baseline,
        manager_tar,
        authorization_id=(
            "N3W_T1_CORE_UPDATER_R7A_REPAIR_MANAGER_SIMULATION"
        ),
        confirmation=APPLY_CONFIRMATION_V2,
    )
    assert applied["transaction_status"] == "COMMITTED"
    assert host.bindings["manager"] == TARGET_IMAGE
    assert host.bindings["homeassistant"] == (
        baseline.stack_images["homeassistant"]
    )
    assert host.bindings["broker"] == baseline.stack_images["broker"]

    rolled_back = updater.rollback(
        confirmation=ROLLBACK_CONFIRMATION_V2
    )
    assert rolled_back["transaction_status"] == "ROLLED_BACK"
    assert host.bindings["manager"] == PREDECESSOR_IMAGE
    assert host.bindings["homeassistant"] == (
        baseline.stack_images["homeassistant"]
    )
    assert host.bindings["broker"] == baseline.stack_images["broker"]
