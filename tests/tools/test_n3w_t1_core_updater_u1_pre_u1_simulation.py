from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import n3w_t1_core_updater_common as common
import n3w_t1_core_updater_core as core
import n3w_t1_core_updater_state as state


TARGET_PATH = ROOT / "infra/n3w-t1/upgrades/manager-5b32e1ae8210.json"
BASELINE_PATH = ROOT / "infra/n3w-t1/clean-reference/u0-upgrade-baseline-a-20261104.json"
PRE_U1_PATH = ROOT / "infra/n3w-t1/clean-reference/pre-u1-business-runtime-reference-20261104.json"
AUTHORITY_PATH = ROOT / "infra/n3w-t1/production/t1-core-stack-current.json"

BASELINE_SHA256 = "a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc"
PACKAGE_ARTIFACT_ID = 13322275752
PACKAGE_DIGEST_SHA256 = "720611993fa80c1f29a39399183a2adee790a497292ca07c99bc270524d30366"


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


class ReferenceHost:
    def __init__(
        self,
        *,
        target: common.Target,
        pre_u1: dict[str, object],
        authority: dict[str, object],
    ) -> None:
        stack = pre_u1["stack"]
        images = stack["images"]
        services = stack["services"]
        current = authority["current_repository_stack"]
        live = authority["live_deployment"]

        self.target = target
        self.manager = images["manager"]
        self.manager_id = live["current_manager_runtime_image_id"]
        self.images = {self.manager: self.manager_id}
        self.stopped = False
        self.stop_calls = 0
        self.start_calls = 0

        self.broker = {
            "container_id": "pre-u1-broker",
            "image_ref": images["broker"],
            "image_id": current["broker"]["image_id"],
            "started_at": services["broker"]["started_at"],
            "restart_count": services["broker"]["restart_count"],
            "network_mode": "bridge",
        }
        self.homeassistant = {
            "container_id": "pre-u1-homeassistant",
            "image_ref": images["homeassistant"],
            "image_id": current["homeassistant"]["image_id"],
            "started_at": services["homeassistant"]["started_at"],
            "restart_count": services["homeassistant"]["restart_count"],
            "network_mode": "host",
        }
        self.manager_started_at = services["manager"]["started_at"]
        self.manager_restart_count = services["manager"]["restart_count"]

    def render_compose(self) -> dict[str, object]:
        return {
            "services": {
                "broker": {
                    "image": self.broker["image_ref"],
                    "pull_policy": "never",
                },
                "manager": {
                    "image": self.manager,
                    "pull_policy": "never",
                    "network_mode": "host",
                },
                "homeassistant": {
                    "image": self.homeassistant["image_ref"],
                    "pull_policy": "never",
                    "network_mode": "host",
                },
            }
        }

    def inspect(self) -> dict[str, object]:
        if self.stopped:
            raise common.UpdaterError("services_stopped")
        rendered = self.render_compose()
        return {
            "manager_image": self.manager,
            "compose_env_sha256": common.sha256_text("env:" + self.manager),
            "compose_render": rendered,
            "compose_render_sha256": common.sha256_bytes(common.canonical(rendered)),
            "services_unit": {
                "execstart_sha256": "pre-u1-execstart",
                "execstop_sha256": "pre-u1-execstop",
            },
            "runtime": {
                "broker": dict(self.broker),
                "manager": {
                    "container_id": "pre-u1-manager",
                    "image_ref": self.manager,
                    "image_id": self.manager_id,
                    "started_at": self.manager_started_at,
                    "restart_count": self.manager_restart_count,
                    "network_mode": "host",
                },
                "homeassistant": dict(self.homeassistant),
            },
            "listeners": {
                "tcp_8883": 1,
                "tcp_47110": 1,
                "udp_47111": 1,
                "tcp_47112": 0,
            },
        }

    def image_id(self, reference: str) -> str | None:
        return self.images.get(reference)

    def verify_image_archive(
        self,
        reference: str,
        tar_path: Path,
        expected_sha256: str,
    ) -> str:
        if common.sha256_file(tar_path) != expected_sha256:
            raise common.UpdaterError("target_tar_sha256_mismatch")
        value = self.images.get(reference)
        if value is None:
            raise common.UpdaterError("target_image_missing")
        return value

    def load_image(self, tar_path: Path) -> None:
        if common.sha256_file(tar_path) != self.target.tar_sha256:
            raise common.UpdaterError("target_tar_sha256_mismatch")
        self.images[self.target.image] = self.target.image_id

    def stop_services(self) -> None:
        self.stop_calls += 1
        self.stopped = True

    def start_services(self) -> None:
        self.start_calls += 1
        self.stopped = False
        self.manager_id = self.images[self.manager]

    def manager_binding(self) -> str:
        return self.manager

    def rewrite_manager_image(self, expected: str, replacement: str) -> str:
        if self.manager != expected:
            raise common.UpdaterError("manager_image_env_predecessor_drift")
        self.manager = replacement
        return common.sha256_text("env:" + self.manager)

    def broker_continuity(self, baseline: dict[str, object]) -> None:
        for key in ("container_id", "image_ref", "image_id", "started_at", "restart_count"):
            if key in baseline and self.broker[key] != baseline[key]:
                raise common.UpdaterError("broker_continuity_failed")

    def wait_services(self, timeout: int = 120) -> None:
        del timeout


def test_u1_exact_package_against_frozen_pre_u1_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_dir = Path(os.environ["U1_MANAGER_PACKAGE_DIR"])
    manager_tar = package_dir / "greenhouse-manager-arm64.tar"
    package_target = package_dir / "manager-target.json"
    package_binding = _read(package_dir / "package-binding.json")

    pre_u1 = _read(PRE_U1_PATH)
    baseline = _read(BASELINE_PATH)
    authority = _read(AUTHORITY_PATH)
    target = common.Target.load(TARGET_PATH)

    assert common.sha256_file(BASELINE_PATH) == BASELINE_SHA256
    assert pre_u1["result"] == "CLOSED_PASS"
    safety = pre_u1["upgrade_safety"]
    assert safety["fresh_reads_byte_identical"] is True
    assert safety["fresh_baseline_equals_u0"] is True
    assert safety["u0_baseline_sha256"] == BASELINE_SHA256

    manager_a = pre_u1["stack"]["images"]["manager"]
    assert baseline["stack_images"]["manager"] == manager_a
    assert authority["authority_state"] == "CURRENT_STACK_LIVE_ACCEPTED"
    assert authority["current_repository_stack"]["manager"]["image"] == manager_a
    assert authority["live_deployment"]["current_manager_image"] == manager_a
    assert authority["live_deployment"]["transaction_status"] == "COMMITTED"
    assert authority["live_deployment"]["recovery_required"] is False

    assert target.expected_predecessor_image == manager_a
    assert target.image != manager_a
    assert target.source_head == "5b32e1ae82104a42f9e4e6907fe44d9172e87615"
    assert target.artifact_id == 13319777217
    assert target.artifact_digest_sha256 == (
        "cb8794de2a5dc28f99c44e6369de403bec37db5b251c28e2edeeda22d281ce6c"
    )
    assert target.rollback_compatible is True
    assert common.sha256_file(manager_tar) == target.tar_sha256
    assert _read(package_target) == _read(TARGET_PATH)

    assert package_binding["upstream_artifact_id"] == target.artifact_id
    assert package_binding["manager_image"] == target.image
    assert package_binding["manager_image_id"] == target.image_id
    assert package_binding["manager_tar_sha256"] == target.tar_sha256
    assert package_binding["manager_rebuilt"] is False
    assert package_binding["homeassistant_included"] is False
    assert package_binding["broker_included"] is False
    assert package_binding["t1_mutation"] is False

    host = ReferenceHost(target=target, pre_u1=pre_u1, authority=authority)
    store_root = tmp_path / "state"
    updater = core.CoreUpdater(host, state.StateStore(store_root))

    inspected = updater.inspect()
    assert inspected["status"] == "PASS"
    assert inspected["mutation"] is False
    assert inspected["snapshot"]["manager_image"] == manager_a
    assert not store_root.exists()

    planned = updater.plan(target, manager_tar)
    assert planned["status"] == "PASS"
    assert planned["mutation"] is False
    assert planned["current"]["image"] == manager_a
    assert planned["target"]["image"] == target.image
    assert planned["target_image_prestate"] == "ABSENT"
    assert planned["manager_tar_verified"] is True
    assert planned["broker_mutation"] is False
    assert planned["homeassistant_image_mutation"] is False
    assert planned["host_platform_mutation"] is False
    assert planned["rollback_available"] is True
    assert not store_root.exists()

    monkeypatch.setattr(core.os, "geteuid", lambda: 0)
    applied = updater.apply(
        target,
        manager_tar,
        authorization_id="N3W_T1_CORE_UPDATER_MANAGER_U1_SIMULATION",
        confirmation=common.APPLY_CONFIRMATION,
    )
    assert applied["transaction_status"] == "COMMITTED"
    assert host.manager == target.image
    assert host.broker["image_ref"] == pre_u1["stack"]["images"]["broker"]
    assert host.homeassistant["image_ref"] == pre_u1["stack"]["images"]["homeassistant"]

    rolled_back = updater.rollback(confirmation=common.ROLLBACK_CONFIRMATION)
    assert rolled_back["transaction_status"] == "ROLLED_BACK"
    assert host.manager == manager_a
    assert host.manager_id == authority["live_deployment"]["current_manager_runtime_image_id"]
    assert host.stop_calls == 2
    assert host.start_calls == 2

    assert PACKAGE_ARTIFACT_ID == 13322275752
    assert PACKAGE_DIGEST_SHA256 == (
        "720611993fa80c1f29a39399183a2adee790a497292ca07c99bc270524d30366"
    )
