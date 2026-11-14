from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PACKAGE=ROOT/"tools"/"execution_packages"/"n3w"/"r7a"/"kf153_r19_post_r18_ipc_timeout_readonly_forensic"
EXECUTOR=PACKAGE/"executor.py"
MANIFEST=PACKAGE/"manifest.json"
WORKFLOW=ROOT/".github"/"workflows"/"n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
GATE="N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF153_POST_R18_IPC_TIMEOUT_READONLY_FORENSIC_R19_20261113_01"

def load_executor():
    spec=importlib.util.spec_from_file_location("n3w_kf153_r19",EXECUTOR)
    assert spec is not None and spec.loader is not None
    module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module

def test_manifest_contract():
    d=json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert d["gate_id"]==GATE
    assert d["live_execution_authorized"] is False
    assert d["authorization_state"]=={"granted":False,"claimed":False,"consumed":False,"replay_permitted":False}
    assert d["predecessor_r18"]["authorization_consumed"] is True
    assert d["predecessor_r18"]["postsubmit_final_state_verified"] is False

def test_executor_and_remote_compile():
    m=load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"),str(EXECUTOR),"exec")
    compile(m.REMOTE_SCRIPT,"<r19>","exec")

def test_readonly_no_install_or_mutation_commands():
    remote=load_executor().REMOTE_SCRIPT
    assert '"operation":"status"' in remote
    assert '"operation":"submit"' not in remote
    assert '"action":"INSTALL"' not in remote
    for token in ('run(["mount"','run(["umount"','run(["systemctl","restart"','run(["systemctl","stop"','run(["systemctl","start"','run(["docker","restart"','run(["docker","stop"'):
        assert token not in remote

def test_classification():
    ns={}
    source=load_executor().REMOTE_SCRIPT
    trailer="\n\nraise SystemExit(main())\n"
    exec(source[:-len(trailer)],ns)
    assert ns["classify"]("U5_INSTALL_REQUESTED_REVALIDATING",{"usb_transaction_phase":"U5_INSTALL_REQUESTED_REVALIDATING","mount_state":"MOUNTED"})=="DELAYED_U5_TRANSITION_COMPLETE"
    assert ns["classify"]("U4_READY_TO_INSTALL",{"usb_transaction_phase":None,"mount_state":"UNMOUNTED"})=="U4_UNCHANGED_UNMOUNTED"
    assert ns["classify"]("U4_READY_TO_INSTALL",{"usb_transaction_phase":"U4_READY_TO_INSTALL","mount_state":"MOUNTED"})=="U4_WITH_MEDIA_REOPENED"

def test_workflow_covers_r19():
    w=WORKFLOW.read_text(encoding="utf-8")
    assert w.count("tools/execution_packages/n3w/r7a/kf153_r19_post_r18_ipc_timeout_readonly_forensic/**")==1
    assert w.count("tools/execution_packages/n3w/r7a/kf153_r19_post_r18_ipc_timeout_readonly_forensic/executor.py")==1
    assert w.count("tests/tools/test_n3w_t1_kf153_r19_post_r18_ipc_timeout_readonly_forensic.py")==2
