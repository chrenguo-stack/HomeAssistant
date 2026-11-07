from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
EXECUTOR_PATH = (
    ROOT
    / "tools/execution_packages/n3w/r7a/manager_a0_live_apply/executor.py"
)
MANIFEST_PATH = EXECUTOR_PATH.with_name("manifest.json")


def load_executor():
    spec = importlib.util.spec_from_file_location("r7a_manager_a0_executor", EXECUTOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_is_source_only_and_not_live_authorized() -> None:
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert (
        document["schema"]
        == "gh.n3w-t1-r7a-manager-a0-live-execution-package/1"
    )
    assert document["live_execution_authorized"] is False
    assert document["preconditions"]["usb_like_disk_count"] == 0
    assert document["execution_contract"]["manager_only_mutation"] is True
    assert document["execution_contract"]["homeassistant_image_mutation"] is False
    assert document["execution_contract"]["broker_image_mutation"] is False
    assert document["execution_contract"]["host_daemon_activation"] is False
    assert document["execution_contract"]["usb_mutation"] is False
    assert document["execution_contract"]["one_apply_maximum"] is True
    assert document["execution_contract"]["automatic_retry"] is False
    assert document["execution_contract"]["automatic_rollback"] is False


def test_exact_package_authority_is_frozen() -> None:
    executor = load_executor()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    authority = manifest["package_authority"]
    assert executor.RUN_ID == authority["workflow_run_id"] == 42349904235
    assert executor.ARTIFACT_ID == authority["artifact_id"] == 13564899377
    assert (
        executor.ARTIFACT_NAME
        == authority["artifact_name"]
        == "n3w-t1-core-updater-manager-v2-bf38e388497b"
    )
    assert executor.ARTIFACT_DIGEST == authority["artifact_digest"]
    assert executor.PACKAGE_CONTROL_HEAD == authority["package_control_head"]
    assert executor.UPDATER_PYZ_SHA256 == authority["updater_pyz_sha256"]
    assert executor.MANAGER_TAR_SHA256 == authority["manager_tar_sha256"]
    assert executor.MANAGER_BUILD_IMAGE_ID == authority["manager_build_image_id"]


def test_live_authority_gate_stops_before_transport() -> None:
    executor = load_executor()
    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()

    with pytest.raises(executor.StopExecution, match="live_execution_not_authorized"):
        executor.validate_local_source(head, require_live=True)


class FakeLsblkTransport:
    def __init__(self, devices: list[dict[str, object]]) -> None:
        self.devices = devices

    def run_remote(self, argv, *, timeout=300, check=True):
        del timeout, check
        assert argv[0] == "lsblk"
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps({"blockdevices": self.devices}),
            stderr="",
        )


@pytest.mark.parametrize(
    ("devices", "expected"),
    [
        (
            [
                {
                    "type": "disk",
                    "rm": False,
                    "tran": "mmc",
                    "size": 32_000_000_000,
                }
            ],
            0,
        ),
        (
            [
                {
                    "type": "disk",
                    "rm": False,
                    "tran": "mmc",
                    "size": 32_000_000_000,
                },
                {
                    "type": "disk",
                    "rm": True,
                    "tran": "usb",
                    "size": 16_000_000_000,
                },
            ],
            1,
        ),
    ],
)
def test_usb_inventory_is_fail_closed(
    devices: list[dict[str, object]],
    expected: int,
) -> None:
    executor = load_executor()
    assert executor.usb_like_disk_count(FakeLsblkTransport(devices)) == expected


def test_target_is_manager_only_and_ota_stays_disabled_for_a0() -> None:
    executor = load_executor()
    target = json.loads(
        (ROOT / executor.TARGET_RELATIVE).read_text(encoding="utf-8")
    )
    baseline = json.loads(
        (ROOT / executor.BASELINE_RELATIVE).read_text(encoding="utf-8")
    )

    assert target["component"] == "manager"
    assert target["expected_predecessor_image_ref"] == executor.EXPECTED_PREDECESSOR
    assert target["target_image_ref"] == executor.TARGET_MANAGER
    assert baseline["stack_images"] == executor.EXPECTED_IMAGES

    config = (
        ROOT
        / "host/greenhouse-manager/src/greenhouse_manager/runtime/config.py"
    ).read_text(encoding="utf-8")
    assert "n3w_t1_ota_enabled: bool = False" in config
