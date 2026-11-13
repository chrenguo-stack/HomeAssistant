from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "tools" / "execution_packages" / "n3w" / "r7a" / "kf152_r17_dependency_safe_source_activation_successor"
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
WORKFLOW = ROOT / ".github" / "workflows" / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
GATE = "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF152_DEPENDENCY_SAFE_SOURCE_ACTIVATION_R17_20261113_01"


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_kf152_r17", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_ungranted_and_binds_exact_failed_r16_prestate() -> None:
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert d["gate_id"] == GATE
    assert d["live_execution_authorized"] is False
    assert d["authorization_state"] == {"granted": False, "claimed": False, "consumed": False, "replay_permitted": False}
    f = d["post_r16_forensic"]
    assert f["status"] == "PASS"
    assert f["prepare_host_live_sha256"] == "f8b63b54e0da053a264a6c174a2988dabd75852117a27aec9a383a5d07706172"
    assert f["services_owner_state"] == "failed"
    assert f["manager_container_state"] == "exited_137"
    assert f["homeassistant_container_state"] == "exited_137"
    assert f["broker_container_state"] == "running"
    assert f["transaction_phase"] == "U4_READY_TO_INSTALL"
    assert f["usb_mount_state"] == "UNMOUNTED"
    assert d["predecessor_r16_terminal"]["authorization_consumed"] is True
    assert d["predecessor_r16_terminal"]["replay_permitted"] is False


def test_single_file_activation_target_is_frozen() -> None:
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(d["source_files"]) == 8
    active = [x for x in d["source_files"] if x["activate"]]
    assert len(active) == 1
    item = active[0]
    assert item["repo_path"] == "tools/n3w_t1_core_updater_ha_prepare_host.py"
    assert item["predecessor_sha256"] == "f8b63b54e0da053a264a6c174a2988dabd75852117a27aec9a383a5d07706172"
    assert item["target_sha256"] == "fd2898cf9d63ae143b9620e56a19e9789306c802440bb9424cfc30064bc53005"


def test_executor_compiles_and_binds_failed_prestate() -> None:
    m = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(m.REMOTE_SCRIPT, "<kf152-r17>", "exec")
    assert m.GATE_ID == GATE
    assert "failed_prestate(plan)" in m.REMOTE_SCRIPT
    assert "verify_r16_terminal_residue(plan)" in m.REMOTE_SCRIPT
    assert '("exited", 137)' in m.REMOTE_SCRIPT
    assert '"broker": ("running", 0)' in m.REMOTE_SCRIPT
    assert "r17_usb_prestate_must_be_unmounted" in m.REMOTE_SCRIPT


def test_execute_and_rollback_use_dependency_safe_order() -> None:
    remote = load_executor().REMOTE_SCRIPT
    execute = remote[remote.index("def execute(plan, authorization, confirmation):"):]
    execute = execute[:execute.index("\ndef main():")]
    rollback = remote[remote.index("def rollback(plan, backup_dir):"):]
    rollback = rollback[:rollback.index("\ndef execute(plan, authorization, confirmation):")]
    for section in (execute, rollback):
        assert section.index('run(["systemctl", "stop", SERVICES_UNIT]') < section.index('run(["systemctl", "stop", HOST_UNIT]')
        assert section.index('run(["systemctl", "stop", HOST_UNIT]') < section.index('run(["systemctl", "start", HOST_UNIT]')
        assert section.index('run(["systemctl", "start", HOST_UNIT]') < section.index('run(["systemctl", "start", SERVICES_UNIT]')


def test_postactivation_requires_strict_owner_health() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert 'services.get("SubState") != "running"' in remote
    assert 'services.get("Result") != "success"' in remote
    assert 'services.get("NRestarts") != "0"' in remote
    assert 'broker_owner.get("NRestarts") != "0"' in remote


def test_contract_has_no_install_u5_u6_or_usb_mutation() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"action": "INSTALL"' not in remote
    assert "request_install(" not in remote
    assert "U5_INSTALL_REQUESTED_REVALIDATING" not in remote
    c = json.loads(MANIFEST.read_text(encoding="utf-8"))["execution_contract"]
    assert c["transaction_mutation"] is False
    assert c["usb_mutation"] is False
    assert c["mount"] is False
    assert c["umount"] is False
    assert c["install_intent"] is False
    assert c["u5_transition"] is False
    assert c["u6_plus"] is False
    assert c["automatic_retry"] is False


def test_product_repair_remains_explicit_lsblk_tree() -> None:
    source = (ROOT / "tools/n3w_t1_core_updater_ha_prepare_host.py").read_text(encoding="utf-8")
    assert '"--tree",' in source


def test_workflow_covers_r17() -> None:
    w = WORKFLOW.read_text(encoding="utf-8")
    assert w.count("tools/execution_packages/n3w/r7a/kf152_r17_dependency_safe_source_activation_successor/**") == 1
    assert w.count("tools/execution_packages/n3w/r7a/kf152_r17_dependency_safe_source_activation_successor/executor.py") == 1
    assert w.count("tests/tools/test_n3w_t1_kf152_r17_dependency_safe_source_activation_successor.py") == 2
