from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "tools" / "execution_packages" / "n3w" / "r7a" / "kf147_v12_u4_to_u5_install_intent_successor"
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
WORKFLOW = ROOT / ".github" / "workflows" / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
GATE = "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_V12_U4_TO_U5_INSTALL_INTENT_R15_20261113_01"
CONFIRMATION = "EXECUTE KF147 V1.2 U4 TO U5 INSTALL INTENT R15: YES"


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_r15_test", EXECUTOR)
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


def test_manifest_binds_r14_v12_and_dynamic_runtime_identity() -> None:
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert d["gate_id"] == GATE
    assert d["authorization_id"] == GATE
    assert d["confirmation"] == CONFIRMATION
    if d.get("superseded") is True:
        assert d["live_execution_authorized"] is False
        assert d["authorization_state"] == {
            "granted": False,
            "claimed": True,
            "consumed": True,
            "replay_permitted": False,
        }
        assert d["terminal_live_result"] == {
            "status": "STOP",
            "reason": "ipc_request_rejected:usb_transaction_media_unavailable",
            "authorization_claimed": True,
            "authorization_consumed": True,
            "transaction_mutation": False,
            "usb_mutation": False,
            "u5_transition": False,
            "split_state_detected": False,
            "u6_plus": False,
        }
    else:
        granted = d["live_execution_authorized"] is True
        assert d["authorization_state"] == {
            "granted": granted,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    assert d["r14_predecessor"]["source_head"] == "340d5b4641735acd49c822139d4be75fea86aae0"
    assert d["r14_predecessor"]["expected_status"] == "PASS"
    live = d["expected_live_entry"]
    assert len(live["installed_source_sha256"]) == 8
    assert all("container_id" not in item for item in live["containers"].values())
    assert live["transaction_sha256"] == "dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259"
    assert live["target_sha256"] == "eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973"
    assert live["usb_filesystem_uuid"] == "967cf065-abe5-49ee-8499-7c3f50d2c48f"
    assert live["target_release_id"] == "homeassistant-2026.10.4"
    assert d["execution_contract"]["u5_transition_on_execute"] is True
    assert d["execution_contract"]["u6_plus"] is False
    assert d["execution_contract"]["fixed_container_id_authority"] is False
    assert d["execution_contract"]["fixed_dev_sdx_authority"] is False


def test_executor_and_remote_compile_without_stale_r11_contract() -> None:
    m = load_executor()
    source = EXECUTOR.read_text(encoding="utf-8")
    compile(source, str(EXECUTOR), "exec")
    compile(m.REMOTE_SCRIPT, "<kf147-r15>", "exec")
    assert m.GATE_ID == GATE
    assert m.CONFIRMATION == CONFIRMATION
    assert "R11_20261112_01" not in source
    assert "r10_state_root" not in source
    assert "installed_runtime_git_blob_sha1" not in source


def test_r14_local_evidence_is_required_before_transition() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "--r14-preflight-evidence" in source
    assert "validate_r14_evidence(" in source
    assert 'value.get("official_u5_preflight_pass") is not True' in source
    assert 'value.get("transaction_phase") != "U4_READY_TO_INSTALL"' in source
    assert 'value.get("installed_source_sha256") != live["installed_source_sha256"]' in source


def test_dynamic_container_and_v12_sources_are_revalidated() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'if len(sha256_view) != 8:' in source
    assert 'observed["container_id"] != expected["container_id"]' not in source
    assert 'observed["runtime_image_id"] != expected["runtime_image_id"]' in source
    assert 'required_options = set(plan["mount_required_options"])' in source


def test_preflight_is_read_only_and_execute_requires_grant() -> None:
    ns = load_remote_namespace()
    ns["validate_u4"] = lambda plan: {"baseline": True}
    pre = ns["execute"]({"mode": "preflight", "live_execution_authorized": False})
    assert pre["status"] == "PASS"
    assert pre["authorization_claimed"] is False
    assert pre["transaction_mutation"] is False
    stop_type = ns["Stop"]
    try:
        ns["execute"]({"mode": "execute", "live_execution_authorized": False, "authorization_state": {"granted": False, "claimed": False, "consumed": False, "replay_permitted": False}})
    except stop_type as error:
        assert str(error) == "u5_transition_live_execution_not_authorized"
    else:
        raise AssertionError("ungranted R15 execute must fail closed")


def test_transition_is_install_intent_only_and_stops_at_u5() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert '"action": "INSTALL"' in source
    assert '"U4_READY_TO_INSTALL"' in source
    assert '"U5_INSTALL_REQUESTED_REVALIDATING"' in source
    assert '"INSTALL_REQUESTED_REVALIDATING"' in source
    assert "split_state_detected" in source
    assert 'run(["systemctl", "restart"' not in source
    assert 'run(["docker", "stop"' not in source
    assert 'run(["docker", "load"' not in source
    assert 'run(["umount"' not in source
    assert 'run(["mount"' not in source


def test_authorized_execute_claims_once_and_stops_at_u5(tmp_path: Path, monkeypatch) -> None:
    ns = load_remote_namespace()
    baseline = {"containers": {"manager": {"container_id": "manager-id"}}, "usb_transaction_metadata": {"manifest_sha256": "a"*64, "phase_sha256": "b"*64, "checksums_sha256": "c"*64}}
    ns["validate_u4"] = lambda plan: baseline
    ns["ipc_install"] = lambda manager_id, release_id: {"accepted": True, "phase": "INSTALL_REQUESTED_REVALIDATING"}
    ns["validate_u5"] = lambda plan, before: {"transaction_phase": "U5_INSTALL_REQUESTED_REVALIDATING"}
    monkeypatch.setattr(ns["os"], "chown", lambda *args: None)
    result = ns["execute"]({"mode": "execute", "live_execution_authorized": True, "authorization_state": {"granted": True, "claimed": False, "consumed": False, "replay_permitted": False}, "authorization": GATE, "authorization_id": GATE, "confirmation": CONFIRMATION, "expected_confirmation": CONFIRMATION, "state_root": str(tmp_path/"state"), "transaction_id_sha256": "1"*64, "usb_filesystem_uuid": "uuid", "target_release_id": "homeassistant-2026.10.4"})
    assert result["status"] == "U5_INSTALL_INTENT_TRANSITION_PASS"
    assert result["authorization_claimed"] is True
    assert result["authorization_consumed"] is True
    assert result["u5_transition"] is True
    assert result["u6_plus"] is False
    assert result["split_state_detected"] is False


def test_workflow_covers_r15() -> None:
    w = WORKFLOW.read_text(encoding="utf-8")
    assert w.count("tools/execution_packages/n3w/r7a/kf147_v12_u4_to_u5_install_intent_successor/**") == 1
    assert w.count("tools/execution_packages/n3w/r7a/kf147_v12_u4_to_u5_install_intent_successor/executor.py") == 1
    assert w.count("tests/tools/test_n3w_t1_kf147_v12_u4_to_u5_install_intent_successor.py") == 2


def test_superseded_r15_is_terminal_consumed_and_nonreplayable() -> None:
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if d.get("superseded") is not True:
        pytest.skip("R15 has not reached terminal superseded state")
    assert d["superseded_reason"] == (
        "r15_live_claim_consumed_stop_kf151_usb_media_resolver_lsblk_tree_defect"
    )
    assert d["live_execution_authorized"] is False
    assert d["authorization_state"]["claimed"] is True
    assert d["authorization_state"]["consumed"] is True
    assert d["authorization_state"]["replay_permitted"] is False
