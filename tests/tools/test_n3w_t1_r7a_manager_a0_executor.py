from __future__ import annotations

import importlib.util
import json
import re
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


def test_manifest_is_repaired_and_requires_new_live_authorization() -> None:
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert (
        document["schema"]
        == "gh.n3w-t1-r7a-manager-a0-live-execution-package/1"
    )
    assert document["live_execution_authorized"] is False
    assert document["preconditions"]["updater_state_readonly_before_staging"] is True
    assert document["preconditions"]["remote_staging_exact_file_set_required"] is True
    assert document["preconditions"]["usb_like_disk_count"] == 0
    assert document["execution_contract"]["manager_only_mutation"] is True
    assert document["execution_contract"]["homeassistant_image_mutation"] is False
    assert document["execution_contract"]["broker_image_mutation"] is False
    assert document["execution_contract"]["host_daemon_activation"] is False
    assert document["execution_contract"]["usb_mutation"] is False
    assert document["preconditions"]["approved_manifest_absent"] is True
    assert document["execution_contract"]["one_apply_maximum"] is True
    assert document["execution_contract"]["automatic_retry"] is False
    assert document["execution_contract"]["executor_explicit_rollback"] is False
    assert document["execution_contract"]["updater_internal_failure_rollback"] is True
    assert document["execution_contract"]["post_failure_state_capture_required"] is True


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


def test_authorization_id_matches_generic_v2_contract() -> None:
    executor = load_executor()
    assert re.fullmatch(
        r"^N3W_T1_CORE_UPDATER_[A-Za-z0-9_-]{1,160}$",
        executor.AUTHORIZATION,
    )


def test_live_authority_gate_stops_until_new_authorization() -> None:
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



class FakeUpdaterStateTransport:
    def __init__(self, *, current_status: str = "ROLLED_BACK", ha_usb: bool = False) -> None:
        self.current_status = current_status
        self.ha_usb = ha_usb

    def run_remote(self, argv, *, timeout=300, check=True):
        del timeout, check
        command = list(argv)
        if command[:3] == ["stat", "-c", "%U:%G:%a:%F"]:
            path = command[3]
            if path == "/var/lib/n3w-t1-core-updater":
                return subprocess.CompletedProcess(argv, 0, stdout="root:root:700:directory\n", stderr="")
            return subprocess.CompletedProcess(argv, 0, stdout="root:root:600:regular file\n", stderr="")
        if command[:2] == ["test", "-e"]:
            path = command[2]
            if path.endswith("homeassistant-usb-upgrade.json") and not self.ha_usb:
                return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")
            if path.endswith("manager-upgrade.json"):
                return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        if command[:2] == ["test", "-L"]:
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")
        if command[0] == "cat":
            path = command[1]
            if path.endswith("homeassistant-usb-upgrade.json"):
                payload = {
                    "schema": "gh.n3w-t1-core-updater-homeassistant-usb-transaction/1",
                    "status": "ROLLED_BACK",
                }
            elif path.endswith("/upgrade.json"):
                payload = {
                    "schema": "gh.n3w-t1-core-updater-transaction/2",
                    "status": self.current_status,
                    "phase": self.current_status,
                    "component": "homeassistant",
                }
            else:
                raise AssertionError(path)
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=json.dumps(payload),
                stderr="",
            )
        raise AssertionError(command)


def test_updater_state_is_readonly_and_terminal_before_staging() -> None:
    executor = load_executor()
    observed = executor.collect_updater_state_readonly(FakeUpdaterStateTransport())
    assert observed["recovery_required"] is False
    assert observed["current_transaction"]["status"] == "ROLLED_BACK"
    assert observed["ha_usb_transaction_present"] is False


def test_updater_state_fails_closed_on_nonterminal_or_ha_usb_successor() -> None:
    executor = load_executor()
    with pytest.raises(executor.StopExecution, match="updater_recovery_required"):
        executor.collect_updater_state_readonly(
            FakeUpdaterStateTransport(current_status="APPLYING")
        )
    with pytest.raises(executor.StopExecution, match="ha_usb_successor_state_present"):
        executor.collect_updater_state_readonly(
            FakeUpdaterStateTransport(ha_usb=True)
        )


def test_execute_orders_updater_state_gate_before_remote_staging() -> None:
    executor = load_executor()
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    execute_source = source[source.index("def execute("):source.index("def parser(")]
    assert execute_source.index("collect_updater_state_readonly(transport)") < (
        execute_source.index("stage_package(transport, package)")
    )



def test_state_symlink_checks_precede_existence_checks() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    helper = source[
        source.index("def read_remote_private_json("):
        source.index("def collect_updater_state_readonly(")
    ]
    assert helper.index('["test", "-L", path]') < helper.index('["test", "-e", path]')


def test_apply_failure_path_captures_post_state_before_decision() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    execute_source = source[source.index("def execute("):source.index("def parser(")]
    post_status = execute_source.index('["status"]')
    post_inspect = execute_source.index('["inspect", "--component", "manager"]', post_status)
    decision = execute_source.index('raise StopExecution("apply_not_committed")')
    assert post_status < decision
    assert post_inspect < decision
    assert "apply_transport.json" in execute_source


def test_post_apply_requires_exact_manager_image_id() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    validate_source = source[
        source.index("def validate_post_apply("):
        source.index("def execute(")
    ]
    assert 'target_doc.get("Image") != MANAGER_BUILD_IMAGE_ID' in validate_source
