from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "tools" / "execution_packages" / "n3w" / "r7a" / "kf151_usb_media_resolver_source_activation_successor"
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
WORKFLOW = ROOT / ".github" / "workflows" / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
GATE = "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF151_USB_MEDIA_RESOLVER_SOURCE_ACTIVATION_R16_20261113_01"


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_kf151_r16", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_authorization_state_and_single_file_activation_full_eight_file_validation() -> None:
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert d["gate_id"] == GATE
    granted = d["live_execution_authorized"] is True
    assert d["authorization_state"] == {
        "granted": granted,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    if granted:
        grant = d["authorization_grant"]
        assert grant["scope"] == "kf151_exact_single_file_prepare_host_source_activation_only"
        assert grant["source_ci_head"] == "3513742801758bc44981c7bf3f0e9ffe6fa5fd56"
        assert grant["source_ci_result"] == "16_OF_16_SUCCESS"
        assert grant["maximum_phase"] == "U4_READY_TO_INSTALL"
        assert grant["install_intent_authorized"] is False
        assert grant["u5_authorized"] is False
        assert grant["u6_plus_authorized"] is False
        assert grant["automatic_retry"] is False
    assert len(d["source_files"]) == 8
    activated = [x for x in d["source_files"] if x["activate"]]
    assert len(activated) == 1
    item = activated[0]
    assert item["repo_path"] == "tools/n3w_t1_core_updater_ha_prepare_host.py"
    assert item["predecessor_sha256"] == "f8b63b54e0da053a264a6c174a2988dabd75852117a27aec9a383a5d07706172"
    assert item["target_sha256"] == "fd2898cf9d63ae143b9620e56a19e9789306c802440bb9424cfc30064bc53005"
    assert d["physical_root_cause"]["status"] == "PHYSICAL_PROVEN"
    assert d["predecessor_r15_terminal"]["authorization_consumed"] is True
    assert d["predecessor_r15_terminal"]["replay_permitted"] is False


def test_executor_compiles_and_binds_single_file_scope() -> None:
    m = load_executor()
    source = EXECUTOR.read_text(encoding="utf-8")
    compile(source, str(EXECUTOR), "exec")
    compile(m.REMOTE_SCRIPT, "<kf151-r16>", "exec")
    assert m.GATE_ID == GATE
    assert 'activated != ["tools/n3w_t1_core_updater_ha_prepare_host.py"]' in source
    assert "source_activation_scope_invalid" in source


def test_product_repair_explicitly_requests_lsblk_tree() -> None:
    source = (ROOT / "tools/n3w_t1_core_updater_ha_prepare_host.py").read_text(encoding="utf-8")
    assert '"--tree",' in source


def test_successor_only_restarts_host_and_never_submits_install() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'systemctl", "stop", SERVICES_UNIT' not in source
    assert 'systemctl", "start", SERVICES_UNIT' not in source
    assert 'systemctl", "stop", HOST_UNIT' in source
    assert 'systemctl", "start", HOST_UNIT' in source
    assert '"action": "INSTALL"' not in source
    assert "request_install(" not in source


def test_only_activate_true_items_are_staged_backed_up_and_installed() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    remote = load_executor().REMOTE_SCRIPT
    assert source.count('if not item.get("activate", False):') >= 1
    assert remote.count('if not item.get("activate", False):') >= 4
    assert "atomic_install(" in remote


def test_contract_stops_before_u5() -> None:
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    c = d["execution_contract"]
    assert c["activated_source_file_count"] == 1
    assert c["host_daemon_restart_on_execute"] is True
    assert c["services_owner_restart_on_execute"] is False
    assert c["transaction_mutation"] is False
    assert c["usb_mutation"] is False
    assert c["install_intent"] is False
    assert c["u5_transition"] is False
    assert c["u6_plus"] is False
    assert c["homeassistant_mutation"] is False
    assert c["manager_mutation"] is False
    assert c["broker_mutation"] is False
    assert c["automatic_retry"] is False


def test_workflow_covers_r16() -> None:
    w = WORKFLOW.read_text(encoding="utf-8")
    assert w.count("tools/execution_packages/n3w/r7a/kf151_usb_media_resolver_source_activation_successor/**") == 1
    assert w.count("tools/execution_packages/n3w/r7a/kf151_usb_media_resolver_source_activation_successor/executor.py") == 1
    assert w.count("tests/tools/test_n3w_t1_kf151_usb_media_resolver_source_activation_successor.py") == 2
