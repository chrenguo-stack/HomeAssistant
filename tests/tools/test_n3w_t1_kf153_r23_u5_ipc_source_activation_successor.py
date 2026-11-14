from __future__ import annotations
import ast, importlib.util, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PACKAGE=ROOT/"tools"/"execution_packages"/"n3w"/"r7a"/"kf153_r23_u5_ipc_source_activation_successor"
EXECUTOR=PACKAGE/"executor.py"; MANIFEST=PACKAGE/"manifest.json"; WORKFLOW=ROOT/".github"/"workflows"/"n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
GATE="N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF153_U5_IPC_SOURCE_ACTIVATION_R23_20261113_01"

def load_executor():
    spec=importlib.util.spec_from_file_location("n3w_r23",EXECUTOR); assert spec is not None and spec.loader is not None
    m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m); return m

def test_manifest_authorized_successor_u5_scope():
    d=json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert d["gate_id"]==GATE
    assert d["live_execution_authorized"] is True
    assert d["authorization_state"]=={"granted":True,"claimed":False,"consumed":False,"replay_permitted":False}
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
    compile(m.REMOTE_SCRIPT,"<r23>","exec")
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

def test_workflow_covers_r23():
    w=WORKFLOW.read_text(encoding="utf-8")
    assert w.count("tools/execution_packages/n3w/r7a/kf153_r23_u5_ipc_source_activation_successor/**")==1
    assert w.count("tools/execution_packages/n3w/r7a/kf153_r23_u5_ipc_source_activation_successor/executor.py")==1
    assert w.count("tests/tools/test_n3w_t1_kf153_r23_u5_ipc_source_activation_successor.py")==2


def test_r23_never_uses_fixed_dev_sdx_authority():
    d=json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert "usb_partition_hint" not in d["expected_live_entry"]
    assert d["execution_contract"]["fixed_dev_sdx_authority"] is False
    source=EXECUTOR.read_text(encoding="utf-8")
    assert "/dev/sda1" not in source
    assert "/dev/sdb1" not in source
    assert 'UUID="+plan["usb_filesystem_uuid"]' in load_executor().REMOTE_SCRIPT


def test_r23_claim_is_durable_and_rollback_is_lifecycle_gated():
    remote=load_executor().REMOTE_SCRIPT
    assert 'durable_json(state_root/"authorization_claim.json",claim)' in remote
    assert 'result["lifecycle_mutation_started"]=True' in remote
    assert 'result["rollback_required"]=bool(result["lifecycle_mutation_started"]' in remote

def test_r23_package_source_authority_matches_exact_head():
    m=load_executor()
    head=m.git_text("rev-parse","HEAD")
    d=m.read_manifest(head,execute=True)
    for path,blob in d["package_source_authority"].items():
        assert m.git_text("rev-parse","HEAD:"+path)==blob

def test_r23_persists_raw_remote_transport_evidence_before_verdict():
    source=EXECUTOR.read_text(encoding="utf-8")
    assert 'write_remote_evidence(evidence,"preflight_remote",pre_transport)' in source
    assert 'write_private_json(evidence/"preflight.json",pre)' in source
    assert 'pre_transport.returncode!=0' in source
    assert 'write_remote_evidence(evidence,"execute_remote",ex_transport)' in source
    assert 'stdout_sha256' in source
    assert 'stderr_sha256' in source
    assert 'json.loads(c.stdout)' in source

def test_r23_remote_script_imports_base64_for_payload_decode():
    tree=ast.parse(load_executor().REMOTE_SCRIPT)
    imports=set()
    for node in tree.body:
        if isinstance(node,ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node,ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert "base64" in imports

def test_r23_waits_for_runtime_root_before_forward_and_rollback_mount():
    remote=load_executor().REMOTE_SCRIPT
    assert "def wait_runtime_root(timeout_seconds):" in remote
    execute=remote[remote.index("def execute("):remote.index("def main():")]
    rollback=remote[remote.index("def rollback("):remote.index("def execute(")]
    assert 'wait_unit(HOST_UNIT,"active",60); result["host_daemon_restart"]=True\n        wait_runtime_root(60)\n        mount_exact(plan,partition)' in execute
    assert 'wait_unit(HOST_UNIT,"active",60)\n        wait_runtime_root(60)\n        mount_exact(plan,partition)' in rollback


def test_r23_rollback_runtime_postvalidation_is_bounded_and_retrying():
    remote=load_executor().REMOTE_SCRIPT
    rollback=remote[remote.index("def rollback("):remote.index("def execute(")]
    assert "deadline=time.monotonic()+180" in rollback
    assert 'result["post"]=verify_runtime(plan,target_source=False,require_ipc=True); break' in rollback
    assert 'raise Stop("rollback_runtime_timeout:"' in rollback


def test_r23_preserves_r20_replay_boundary():
    d=json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert d["predecessor"]["r20_authorization_consumed"] is True
    assert d["predecessor"]["r20_replay_permitted"] is False
    assert d["predecessor"]["r21_forensic_classification"]=="ROLLBACK_RUNTIME_RECOVERED"



def test_r23_kf108_transport_exception_after_execute_invocation_is_unknown_consumed():
    source=EXECUTOR.read_text(encoding="utf-8")
    assert 'result["remote_execute_invoked"]=True' in source
    assert 'status="STOP_UNKNOWN",authorization_claimed=True,authorization_consumed=True,replay_permitted=False' in source
    assert 'remote_execute_result_observed=False' in source

def test_r23_invalid_execute_result_cannot_fall_back_to_unconsumed():
    source=EXECUTOR.read_text(encoding="utf-8")
    assert 'if not all(key in remote for key in ("authorization_claimed","authorization_consumed","replay_permitted")):' in source
    assert 'reason="remote_execute_claim_state_unknown"' in source
    assert 'authorization_claimed=True,authorization_consumed=True,replay_permitted=False' in source

def test_r23_remote_preclaim_stop_has_explicit_claim_state():
    remote=load_executor().REMOTE_SCRIPT
    assert '"authorization_claimed":False,"authorization_consumed":False,"replay_permitted":False' in remote

def test_r23_postsuccess_local_or_cleanup_failure_never_reports_plain_pass():
    source=EXECUTOR.read_text(encoding="utf-8")
    assert 'result["status"]="STOP_POSTSUCCESS_LOCAL"' in source
    assert 'result["status"]="STOP_POSTSUCCESS_CLEANUP"' in source
    assert 'result["completed_remote_status"]=result["status"]' in source

def test_r23_manifest_records_r22_supersession_and_kf108_guards():
    d=json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert d["predecessor"]["r22_source_authority_head"]=="aa5eb8b8ccb7628aae782d00d4b97fa8fe741239"
    assert d["predecessor"]["r22_superseded_before_t1_preflight"] is True
    c=d["execution_contract"]
    assert c["unknown_postinvoke_transport_consumes_authorization"] is True
    assert c["invalid_execute_result_consumes_authorization"] is True
    assert c["postsuccess_cleanup_failure_reports_stop"] is True


def test_r23_claim_persistence_failure_is_unknown_consumed_before_mutation():
    remote=load_executor().REMOTE_SCRIPT
    assert 'authorization_claim_persistence_unknown' in remote
    assert 'status="STOP_UNKNOWN"' in remote
    assert 'authorization_claimed=True,authorization_consumed=True,replay_permitted=False,authorization_claim_persistence_unknown=True' in remote
    claim_pos=remote.index('durable_json(state_root/"authorization_claim.json",claim)')
    lifecycle_pos=remote.index('result["lifecycle_mutation_started"]=True')
    assert claim_pos < lifecycle_pos


def test_r23_remote_postsuccess_cleanup_failure_does_not_rollback_success():
    remote=load_executor().REMOTE_SCRIPT
    pass_pos=remote.index('result.update(status="KF153_R23_U5_IPC_SOURCE_ACTIVATION_PASS"')
    cleanup_pos=remote.index('shutil.rmtree(stage_root)',pass_pos)
    stop_pos=remote.index('result["status"]="STOP_POSTSUCCESS_CLEANUP"',cleanup_pos)
    return_pos=remote.index('return result',stop_pos)
    general_except_pos=remote.index('except Exception as error:',return_pos)
    assert pass_pos < cleanup_pos < stop_pos < return_pos < general_except_pos
    segment=remote[cleanup_pos:return_pos]
    assert 'result["rollback_required"]=False' in segment
    assert 'rollback(plan,backup_dir)' not in segment


def test_r23_manifest_freezes_full_kf108_contract():
    d=json.loads(MANIFEST.read_text(encoding="utf-8"))
    c=d["execution_contract"]
    assert c["authorization_claim_persistence_unknown_consumes_authorization"] is True
    assert c["unknown_postinvoke_transport_consumes_authorization"] is True
    assert c["invalid_execute_result_consumes_authorization"] is True
    assert c["postsuccess_remote_cleanup_failure_no_rollback"] is True
    assert c["postsuccess_cleanup_failure_reports_stop"] is True
