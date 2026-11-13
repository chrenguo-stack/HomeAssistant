from __future__ import annotations
import importlib.util, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PACKAGE=ROOT/"tools"/"execution_packages"/"n3w"/"r7a"/"kf153_r20_u5_ipc_source_activation_successor"
EXECUTOR=PACKAGE/"executor.py"; MANIFEST=PACKAGE/"manifest.json"; WORKFLOW=ROOT/".github"/"workflows"/"n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
GATE="N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF153_U5_IPC_SOURCE_ACTIVATION_R20_20261113_01"

def load_executor():
    spec=importlib.util.spec_from_file_location("n3w_r20",EXECUTOR); assert spec is not None and spec.loader is not None
    m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m); return m

def test_manifest_ungranted_u5_scope():
    d=json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert d["gate_id"]==GATE
    assert d["live_execution_authorized"] is False
    assert d["authorization_state"]=={"granted":False,"claimed":False,"consumed":False,"replay_permitted":False}
    c=d["execution_contract"]
    assert c["activated_source_file_count"]==1
    assert c["activated_source_file"]=="tools/n3w_t1_core_updater_ha_ipc.py"
    assert c["install_resubmit"] is False
    assert c["transaction_mutation"] is False
    assert c["usb_transaction_metadata_mutation"] is False
    assert c["u6_plus"] is False

def test_executor_remote_compile_and_no_install_submit():
    m=load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"),str(EXECUTOR),"exec")
    compile(m.REMOTE_SCRIPT,"<r20>","exec")
    remote=m.REMOTE_SCRIPT
    assert '"action":"INSTALL"' not in remote
    assert '"operation":"submit"' not in remote

def test_dependency_safe_u5_mount_lifecycle_order():
    remote=load_executor().REMOTE_SCRIPT
    execute=remote[remote.index("def execute("):remote.index("def main():")]
    stop_services=execute.index('run(["systemctl","stop",SERVICES_UNIT]')
    unmount=execute.index("partition=unmount_exact(plan)")
    stop_host=execute.index('run(["systemctl","stop",HOST_UNIT]')
    install=execute.index("atomic_install(staged,plan[")
    start_host=execute.index('run(["systemctl","start",HOST_UNIT]')
    remount=execute.index("mount_exact(plan,partition)")
    start_services=execute.index('run(["systemctl","start",SERVICES_UNIT]')
    assert stop_services < unmount < stop_host < install < start_host < remount < start_services

def test_preflight_binds_exact_u5():
    d=json.loads(MANIFEST.read_text(encoding="utf-8"))
    live=d["expected_live_entry"]
    assert live["transaction_sha256"]=="adfcf60d958c112edf61e2f4e31d73b16229fd027180ed68b87b8953231f0144"
    assert live["usb_phase_sha256"]=="acec5c51c5b8dc4ef5b1860dc61c77d377c923730c13a74ede0bf41d1e88d468"
    assert live["installed_source_sha256"]["/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_ipc.py"]=="b080e20bf272ed22c51a91c96832759fcc88175825ab1740ae6b98aff8ff3a1b"

def test_workflow_covers_r20():
    w=WORKFLOW.read_text(encoding="utf-8")
    assert w.count("tools/execution_packages/n3w/r7a/kf153_r20_u5_ipc_source_activation_successor/**")==1
    assert w.count("tools/execution_packages/n3w/r7a/kf153_r20_u5_ipc_source_activation_successor/executor.py")==1
    assert w.count("tests/tools/test_n3w_t1_kf153_r20_u5_ipc_source_activation_successor.py")==2
