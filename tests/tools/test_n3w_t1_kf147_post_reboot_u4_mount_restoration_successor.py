from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT / "tools" / "execution_packages" / "n3w" / "r7a"
    / "kf147_post_reboot_u4_mount_restoration_successor"
)
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
WORKFLOW = ROOT / ".github" / "workflows" / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "POST_REBOOT_U4_MOUNT_RESTORATION_R12_20261112_01"
)
CONFIRMATION = "EXECUTE KF147 POST REBOOT U4 MOUNT RESTORATION R12: YES"


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_kf147_post_reboot_u4_mount_restoration_successor_test",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_remote_namespace():
    source = load_executor().REMOTE_SCRIPT
    trailer = "\n\nraise SystemExit(main())\n"
    assert source.endswith(trailer)
    namespace = {}
    exec(source[: -len(trailer)], namespace)
    return namespace


def test_manifest_is_ungranted_and_binds_exact_post_reboot_u4_state() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["gate_id"] == GATE
    assert document["authorization_id"] == GATE
    assert document["confirmation"] == CONFIRMATION
    assert document["live_execution_authorized"] is False
    assert document["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert document["state_root"].endswith(
        "kf147-post-reboot-u4-mount-restoration-r12-20261112-01"
    )
    live = document["expected_live_entry"]
    assert live["r10_state_root"].endswith(
        "kf147-u5-source-activation-r10-20261111-01"
    )
    assert live["transaction_sha256"] == (
        "dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259"
    )
    assert live["target_sha256"] == (
        "eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973"
    )
    assert live["installed_source_sha256"][
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_ipc.py"
    ] == "a7d335c597771b0297f690d0e97fb3288f5f1c83fd670d8af00d76ca983e56ac"
    assert document["execution_contract"]["expected_prestate"] == (
        "BOUND_USB_PRESENT_UNMOUNTED_AFTER_T1_REBOOT"
    )
    assert document["execution_contract"]["transaction_mutation"] is False
    assert document["execution_contract"]["u5_transition"] is False
    assert document["execution_contract"]["rollback_target"] == "UNMOUNTED_PRESTATE"
    assert document["stop_boundary"].endswith("BEFORE_R11_LIVE_RETRY")


def test_executor_and_remote_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<kf147-r12-post-reboot-mount>", "exec")
    assert module.GATE_ID == GATE
    assert module.CONFIRMATION == CONFIRMATION


def test_preflight_is_read_only_unmounted_admission() -> None:
    namespace = load_remote_namespace()
    namespace["validate_preflight"] = lambda plan: {"baseline": True}
    result = namespace["execute"](
        {"mode": "preflight", "live_execution_authorized": False}
    )
    assert result["status"] == "PASS"
    assert result["read_only"] is True
    assert result["restoration_eligible"] is True
    assert result["authorization_claimed"] is False
    assert result["authorization_consumed"] is False
    assert result["runtime_directory_creation_attempted"] is False
    assert result["writable_mount_attempted"] is False
    assert result["writable_mount_restored"] is False
    assert result["host_state_mutation"] is False
    assert result["usb_mutation"] is False
    assert result["transaction_mutation"] is False
    assert result["u5_transition"] is False
    assert result["u6_plus"] is False


def test_execute_fails_closed_while_ungranted() -> None:
    namespace = load_remote_namespace()
    namespace["validate_preflight"] = lambda plan: {"baseline": True}
    stop_type = namespace["Stop"]
    try:
        namespace["execute"](
            {
                "mode": "execute",
                "live_execution_authorized": False,
                "authorization_state": {
                    "granted": False,
                    "claimed": False,
                    "consumed": False,
                    "replay_permitted": False,
                },
            }
        )
    except stop_type as error:
        assert str(error) == "restoration_live_execution_not_authorized"
    else:
        raise AssertionError("ungranted R12 execute must fail closed")


def test_preflight_requires_unmounted_exact_usb_not_existing_mount() -> None:
    source = load_executor().REMOTE_SCRIPT
    start = source.index("def validate_preflight(plan):")
    end = source.index("\ndef validate_post_writable", start)
    block = source[start:end]
    assert "verify_unmounted_media(plan, transaction)" in block
    assert "verify_bound_media(" not in block
    assert "verify_target(plan)" not in block


def test_execute_claims_before_directory_creation_and_rw_mount() -> None:
    source = load_executor().REMOTE_SCRIPT
    claim = 'durable_json(\n        state_root / "authorization_claim.json"'
    directory = "directory_state = prepare_mount_target(plan)"
    mount = '"rw,nodev,nosuid,noexec"'
    assert claim in source
    assert directory in source
    assert mount in source
    assert source.index(claim) < source.index(directory) < source.index(mount)


def test_postvalidation_rechecks_target_usb_metadata_and_u4() -> None:
    source = load_executor().REMOTE_SCRIPT
    start = source.index("def validate_post_writable(plan, baseline):")
    end = source.index("\ndef durable_json", start)
    block = source[start:end]
    assert 'transaction["phase"]' in block
    assert "verify_bound_media(plan, transaction, runtime[\"service\"], \"writable\")" in block
    assert "verify_target(plan)" in block
    assert "usb_transaction_metadata_view(" in block
    assert '"U4_READY_TO_INSTALL"' in block


def test_rollback_restores_unmounted_prestate_and_never_enters_u5() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert "def rollback_to_unmounted(" in source
    assert 'run(["umount", target], timeout=60)' in source
    assert "verify_unmounted_media(plan, transaction)" in source
    assert 'result["rollback_attempted"] = True' in source
    assert "request_install(" not in source
    assert "ipc_install(" not in source
    assert 'run(["systemctl", "restart"' not in source
    assert 'run(["docker", "stop"' not in source
    assert 'run(["docker", "rm"' not in source
    assert 'run(["docker", "load"' not in source


def test_target_binding_workflow_covers_r12_package() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_post_reboot_u4_mount_restoration_successor/**"
    )
    executor_path = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_post_reboot_u4_mount_restoration_successor/executor.py"
    )
    test_path = (
        "tests/tools/"
        "test_n3w_t1_kf147_post_reboot_u4_mount_restoration_successor.py"
    )
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor_path) == 1
    assert workflow.count(test_path) == 2
