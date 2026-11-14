from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "tools" / "execution_packages" / "n3w" / "r7a" / "kf152_r18_u4_to_u5_install_intent_successor"
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
WORKFLOW = ROOT / ".github" / "workflows" / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
GATE = "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF152_R18_U4_TO_U5_INSTALL_INTENT_20261113_01"
CONFIRMATION = "EXECUTE KF152 R18 U4 TO U5 INSTALL INTENT: YES"


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_r18_test", EXECUTOR)
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


def test_manifest_authorization_state_and_binds_r17_closed_u4() -> None:
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
        terminal = d["terminal_live_result"]
        assert terminal["status"] == "STOP"
        assert terminal["reason"] == "Stop:ipc_request_unavailable:1"
        assert terminal["authorization_consumed"] is True
        assert terminal["replay_permitted"] is False
        assert terminal["postsubmit_final_state_verified"] is False
        assert terminal["replay_forbidden"] is True
        granted = False
    else:
        granted = d["live_execution_authorized"] is True
        assert d["authorization_state"] == {
            "granted": granted,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    if granted:
        grant = d["authorization_grant"]
        assert grant["boundary"] == "R18_NEW_ONE_SHOT_INSTALL_U5_AUTHORIZATION"
        assert grant["scope"] == "kf152_r18_u4_to_u5_install_intent_only"
        assert grant["source_ci_head"] == "323a64ff24e1c846546140a20bf294aef78b4434"
        assert grant["source_ci_result"] == "16_OF_16_SUCCESS"
        assert grant["readonly_preflight_closure_head"] == "ce3e02e289fe90766ec331e096b8306db6ff5bee"
        assert grant["readonly_preflight_status"] == "PASS"
        assert grant["readonly_preflight_pr807_comment_id"] == 6846820786
        assert grant["readonly_preflight_transaction_phase"] == "U4_READY_TO_INSTALL"
        assert grant["readonly_preflight_transaction_sha256"] == "dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259"
        assert grant["readonly_preflight_usb_mount_state"] == "UNMOUNTED"
        assert grant["product_media_reopen_on_execute"] is True
        assert grant["transaction_mutation_authorized"] is True
        assert grant["usb_mount_and_metadata_mutation_authorized"] is True
        assert grant["maximum_phase"] == "U5_INSTALL_REQUESTED_REVALIDATING"
        assert grant["u6_plus_authorized"] is False
        assert grant["source_deployment_authorized"] is False
        assert grant["service_restart_authorized"] is False
        assert grant["manager_mutation_authorized"] is False
        assert grant["homeassistant_mutation_authorized"] is False
        assert grant["broker_mutation_authorized"] is False
        assert grant["board_access"] is False
        assert grant["merge"] is False
        assert grant["automatic_retry"] is False
        assert grant["rollback_permitted"] is False
    r17 = d["r17_predecessor"]
    assert r17["authorized_head"] == "f96f7d85983b6bc3b05de15b48528d6fe9f16fcd"
    assert r17["terminal_closure_head"] == "700dde01555ef252d16b326013b247c9a752778f"
    assert r17["status"] == "KF152_R17_RECOVERY_ACTIVATION_PASS"
    assert r17["authorization_consumed"] is True
    assert r17["replay_permitted"] is False
    assert r17["prepare_host_live_sha256"] == "fd2898cf9d63ae143b9620e56a19e9789306c802440bb9424cfc30064bc53005"
    assert r17["ipc_phase"] == "READY_TO_INSTALL"
    assert r17["transaction_phase"] == "U4_READY_TO_INSTALL"
    assert r17["usb_mount_state"] == "UNMOUNTED"
    live = d["expected_live_entry"]
    assert len(live["installed_source_sha256"]) == 8
    assert live["installed_source_sha256"]["/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_prepare_host.py"] == "fd2898cf9d63ae143b9620e56a19e9789306c802440bb9424cfc30064bc53005"
    assert live["transaction_sha256"] == "dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259"
    assert live["target_release_id"] == "homeassistant-2026.10.4"


def test_executor_and_remote_compile_and_drop_r14_local_evidence_dependency() -> None:
    m = load_executor()
    source = EXECUTOR.read_text(encoding="utf-8")
    compile(source, str(EXECUTOR), "exec")
    compile(m.REMOTE_SCRIPT, "<kf152-r18>", "exec")
    assert m.GATE_ID == GATE
    assert m.CONFIRMATION == CONFIRMATION
    assert "--r14-preflight-evidence" not in source
    assert "validate_r14_evidence(" not in source
    assert "R15_20261113_01" not in source


def test_preflight_requires_exact_unmounted_bound_media_and_fixed_source() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert "verify_compatible_media_unmounted" in remote
    assert "r18_usb_prestate_must_be_unmounted" in remote
    assert "r18_mount_target_must_be_unmounted" in remote
    assert '"--tree",' in remote
    assert 'transaction.get("usb_device_identity_public_fingerprint")' in remote
    assert "validate_installed_sources(plan)" in remote


def test_preflight_is_read_only_and_execute_requires_grant() -> None:
    ns = load_remote_namespace()
    ns["validate_u4"] = lambda plan: {"baseline": True}
    pre = ns["execute"]({"mode": "preflight", "live_execution_authorized": False})
    assert pre["status"] == "PASS"
    assert pre["authorization_claimed"] is False
    assert pre["transaction_mutation"] is False
    assert pre["usb_mutation"] is False
    stop_type = ns["Stop"]
    try:
        ns["execute"]({
            "mode": "execute",
            "live_execution_authorized": False,
            "authorization_state": {
                "granted": False,
                "claimed": False,
                "consumed": False,
                "replay_permitted": False,
            },
        })
    except stop_type as error:
        assert str(error) == "u5_transition_live_execution_not_authorized"
    else:
        raise AssertionError("ungranted R18 execute must fail closed")


def test_transition_uses_product_install_revalidation_and_stops_at_u5() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"action": "INSTALL"' in remote
    assert '"U4_READY_TO_INSTALL"' in remote
    assert '"U5_INSTALL_REQUESTED_REVALIDATING"' in remote
    assert '"INSTALL_REQUESTED_REVALIDATING"' in remote
    assert "split_state_detected" in remote
    assert 'run(["systemctl", "restart"' not in remote
    assert 'run(["docker", "stop"' not in remote
    assert 'run(["docker", "load"' not in remote
    assert 'run(["umount"' not in remote
    assert 'run(["mount"' not in remote


def test_authorized_execute_claims_once_and_stops_at_u5(tmp_path: Path, monkeypatch) -> None:
    ns = load_remote_namespace()
    baseline = {
        "containers": {"manager": {"container_id": "manager-id"}},
        "transaction_sha256": "a" * 64,
        "service": {"ActiveState": "active"},
        "usb_binding": {
            "partition": "/dev/sda1",
            "parent": "/dev/sda",
            "public_fingerprint": "f" * 64,
            "filesystem_uuid": "uuid",
            "filesystem_type": "ext4",
            "filesystem_label": "N3W-UPDATE",
            "mount_state": "UNMOUNTED",
        },
    }
    ns["validate_u4"] = lambda plan: baseline
    ns["ipc_install"] = lambda manager_id, release_id: {
        "accepted": True,
        "phase": "INSTALL_REQUESTED_REVALIDATING",
    }
    ns["validate_u5"] = lambda plan, before: {
        "transaction_phase": "U5_INSTALL_REQUESTED_REVALIDATING"
    }
    monkeypatch.setattr(ns["os"], "chown", lambda *args: None)
    result = ns["execute"]({
        "mode": "execute",
        "live_execution_authorized": True,
        "authorization_state": {
            "granted": True,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        },
        "authorization": GATE,
        "authorization_id": GATE,
        "confirmation": CONFIRMATION,
        "expected_confirmation": CONFIRMATION,
        "state_root": str(tmp_path / "state"),
        "transaction_id_sha256": "1" * 64,
        "usb_filesystem_uuid": "uuid",
        "target_release_id": "homeassistant-2026.10.4",
    })
    assert result["status"] == "U5_INSTALL_INTENT_TRANSITION_PASS"
    assert result["authorization_claimed"] is True
    assert result["authorization_consumed"] is True
    assert result["u5_transition"] is True
    assert result["u6_plus"] is False
    assert result["split_state_detected"] is False


def test_workflow_covers_r18() -> None:
    w = WORKFLOW.read_text(encoding="utf-8")
    assert w.count("tools/execution_packages/n3w/r7a/kf152_r18_u4_to_u5_install_intent_successor/**") == 1
    assert w.count("tools/execution_packages/n3w/r7a/kf152_r18_u4_to_u5_install_intent_successor/executor.py") == 1
    assert w.count("tests/tools/test_n3w_t1_kf152_r18_u4_to_u5_install_intent_successor.py") == 2


def test_superseded_r18_is_terminal_consumed_nonreplayable() -> None:
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert d["superseded"] is True
    assert d["live_execution_authorized"] is False
    assert d["authorization_state"] == {
        "granted": False,
        "claimed": True,
        "consumed": True,
        "replay_permitted": False,
    }
