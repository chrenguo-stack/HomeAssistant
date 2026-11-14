from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "tools" / "execution_packages" / "n3w" / "r7a" / "kf147_post_r2_u4_writable_mount_restoration_successor"
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
WORKFLOW = ROOT / ".github" / "workflows" / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
GATE = "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_POST_R2_U4_WRITABLE_MOUNT_RESTORATION_R13_20261113_01"
CONFIRMATION = "EXECUTE KF147 POST R2 U4 WRITABLE MOUNT RESTORATION R13: YES"


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_r13_test", EXECUTOR)
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


def test_manifest_is_terminal_consumed_after_r13_pass() -> None:
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert d["gate_id"] == GATE
    assert d["authorization_id"] == GATE
    assert d["confirmation"] == CONFIRMATION
    assert d["live_execution_authorized"] is False
    assert d["authorization_state"] == {"granted": False, "claimed": True, "consumed": True, "replay_permitted": False}
    assert d["authorization_grant"]["terminal"] == (
        "consumed_by_real_t1_r13_writable_mount_restoration_pass"
    )
    terminal = d["terminal_execution_record"]
    assert terminal["status"] == "POST_REBOOT_U4_MOUNT_RESTORATION_PASS"
    assert terminal["remote_returncode"] == 0
    assert terminal["authorization_claimed"] is True
    assert terminal["authorization_consumed"] is True
    assert terminal["replay_permitted"] is False
    assert terminal["writable_mount_restored"] is True
    assert terminal["transaction_phase"] == "U4_READY_TO_INSTALL"
    assert terminal["transaction_mutation"] is False
    assert terminal["u5_transition"] is False
    assert terminal["u6_plus"] is False
    assert d["predecessor_terminal"]["expected_status"] == "V1_2_SOURCE_ACTIVATION_PASS"
    assert d["predecessor_terminal"]["authorization_consumed"] is True
    assert d["predecessor_terminal"]["source_target_count"] == 8
    assert d["predecessor_terminal"]["u4_preserved"] is True
    assert len(d["expected_live_entry"]["installed_source_sha256"]) == 8
    assert all("container_id" not in x for x in d["expected_live_entry"]["containers"].values())
    assert d["execution_contract"]["expected_prestate"] == "BOUND_USB_PRESENT_UNMOUNTED_AFTER_R2_SOURCE_ACTIVATION"
    assert d["execution_contract"]["fixed_container_id_authority"] is False
    assert d["execution_contract"]["u5_transition"] is False


def test_executor_and_remote_compile() -> None:
    m = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(m.REMOTE_SCRIPT, "<kf147-r13>", "exec")
    assert m.GATE_ID == GATE
    assert m.CONFIRMATION == CONFIRMATION
    assert "r10_state_root" not in m.REMOTE_SCRIPT
    assert "r2_state_root" in m.REMOTE_SCRIPT
    assert '"V1_2_SOURCE_ACTIVATION_PASS"' in m.REMOTE_SCRIPT


def test_r2_terminal_and_dynamic_container_authority() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'r2_root = Path(plan["r2_state_root"])' in source
    assert 'raise Stop("r2_terminal_state_invalid")' in source
    start = source.index("def runtime_view(plan):")
    end = source.index("\ndef validate_transaction", start)
    block = source[start:end]
    assert 'observed["container_id"] != expected["container_id"]' not in block
    assert 'observed["runtime_image_id"] != expected["runtime_image_id"]' in block
    assert 'observed["restart_count"] != 0' in block
    assert 'ipc_status(containers["manager"]["container_id"])' in block


def test_preflight_is_read_only_unmounted_admission() -> None:
    ns = load_remote_namespace()
    ns["validate_preflight"] = lambda plan: {"baseline": True}
    result = ns["execute"]({"mode": "preflight", "live_execution_authorized": False})
    assert result["status"] == "PASS"
    assert result["read_only"] is True
    assert result["restoration_eligible"] is True
    assert result["authorization_claimed"] is False
    assert result["authorization_consumed"] is False
    assert result["runtime_directory_creation_attempted"] is False
    assert result["writable_mount_attempted"] is False
    assert result["usb_mutation"] is False
    assert result["transaction_mutation"] is False
    assert result["u5_transition"] is False


def test_execute_fails_closed_while_ungranted() -> None:
    ns = load_remote_namespace()
    ns["validate_preflight"] = lambda plan: {"baseline": True}
    stop = ns["Stop"]
    try:
        ns["execute"]({"mode": "execute", "live_execution_authorized": False, "authorization_state": {"granted": False, "claimed": False, "consumed": False, "replay_permitted": False}})
    except stop as error:
        assert str(error) == "restoration_live_execution_not_authorized"
    else:
        raise AssertionError("ungranted R13 execute must fail closed")


def test_preflight_postvalidation_and_rollback_boundaries() -> None:
    source = load_executor().REMOTE_SCRIPT
    p0 = source.index("def validate_preflight(plan):")
    p1 = source.index("\ndef validate_post_writable", p0)
    pre = source[p0:p1]
    assert "verify_unmounted_media(plan, transaction)" in pre
    assert "verify_target(plan)" not in pre
    post0 = source.index("def validate_post_writable(plan, baseline):")
    post1 = source.index("\ndef durable_json", post0)
    post = source[post0:post1]
    assert 'verify_bound_media(plan, transaction, runtime["service"], "writable")' in post
    assert "verify_target(plan)" in post
    assert "usb_transaction_metadata_view(" in post
    assert '"U4_READY_TO_INSTALL"' in post
    assert "def rollback_to_unmounted(" in source
    assert "request_install(" not in source
    assert "ipc_install(" not in source
    assert 'run(["systemctl", "restart"' not in source
    assert 'run(["docker", "load"' not in source


def test_target_binding_workflow_covers_r13() -> None:
    w = WORKFLOW.read_text(encoding="utf-8")
    glob = "tools/execution_packages/n3w/r7a/kf147_post_r2_u4_writable_mount_restoration_successor/**"
    executor = "tools/execution_packages/n3w/r7a/kf147_post_r2_u4_writable_mount_restoration_successor/executor.py"
    test_path = "tests/tools/test_n3w_t1_kf147_post_r2_u4_writable_mount_restoration_successor.py"
    assert w.count(glob) == 1
    assert w.count(executor) == 1
    assert w.count(test_path) == 2
