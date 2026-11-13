from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "tools" / "execution_packages" / "n3w" / "r7a" / "kf147_official_u5_preflight_successor"
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
WORKFLOW = ROOT / ".github" / "workflows" / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
GATE = "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_OFFICIAL_U5_PREFLIGHT_R14_20261113_01"


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_r14_test", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_binds_r13_and_exact_v12_runtime() -> None:
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert d["gate_id"] == GATE
    assert d["live_execution_authorized"] is False
    assert d["authorization_state"] == {"granted": False, "claimed": False, "consumed": False, "replay_permitted": False}
    assert d["predecessor_terminal"]["expected_status"] == "POST_REBOOT_U4_MOUNT_RESTORATION_PASS"
    assert d["predecessor_terminal"]["authorization_consumed"] is True
    assert d["predecessor_terminal"]["writable_mount_restored"] is True
    assert len(d["expected_live_entry"]["installed_source_sha256"]) == 8
    assert all("container_id" not in x for x in d["expected_live_entry"]["containers"].values())
    assert d["execution_contract"]["read_only_preflight"] is True
    assert d["execution_contract"]["transaction_mutation"] is False
    assert d["execution_contract"]["usb_mutation"] is False
    assert d["execution_contract"]["u5_transition"] is False


def test_executor_and_remote_compile_and_require_r13_terminal() -> None:
    m = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(m.REMOTE_SCRIPT, "<kf147-r14>", "exec")
    assert m.GATE_ID == GATE
    assert "R6_ROOT" not in m.REMOTE_SCRIPT
    assert "R13_ROOT" in m.REMOTE_SCRIPT
    assert 'terminal.get("status") != "POST_REBOOT_U4_MOUNT_RESTORATION_PASS"' in m.REMOTE_SCRIPT
    assert 'raise Stop("r13_terminal_state_invalid")' in m.REMOTE_SCRIPT


def test_preflight_uses_dynamic_container_authority_and_writable_mount() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'observed["container_id"] != expected["container_id"]' not in source
    assert 'observed["runtime_image_id"] != expected["runtime_image_id"]' in source
    assert 'required_options = set(plan["mount_required_options"])' in source
    assert 'raise Stop("usb_mount_not_u5_writable:"' in source
    assert '"official_u5_preflight_pass": True' in source


def test_executor_is_readonly_only() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    assert '--preflight-only' in source
    assert '--execute' not in source
    remote = load_executor().REMOTE_SCRIPT
    assert 'run(["mount"' not in remote
    assert 'run(["umount"' not in remote
    assert 'run(["systemctl", "restart"' not in remote
    assert 'run(["docker", "load"' not in remote
    assert '"action": "INSTALL"' not in remote
    assert "ipc_install(" not in remote


def test_target_binding_workflow_covers_r14() -> None:
    w = WORKFLOW.read_text(encoding="utf-8")
    glob = "tools/execution_packages/n3w/r7a/kf147_official_u5_preflight_successor/**"
    executor = "tools/execution_packages/n3w/r7a/kf147_official_u5_preflight_successor/executor.py"
    test_path = "tests/tools/test_n3w_t1_kf147_official_u5_preflight_successor.py"
    assert w.count(glob) == 1
    assert w.count(executor) == 1
    assert w.count(test_path) == 2
