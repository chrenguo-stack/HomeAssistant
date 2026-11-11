from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "kf147_u4_to_u5_install_intent_preflight"
)
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "U4_TO_U5_INSTALL_INTENT_R7_PREFLIGHT_20261111_01"
)


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_kf147_u4_u5_install_intent_preflight_test",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_read_only_ungranted_u5_preflight() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["gate_id"] == GATE
    assert document["live_execution_authorized"] is False
    assert document["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    contract = document["execution_contract"]
    assert contract["read_only_preflight"] is True
    assert contract["source_deployment"] is False
    assert contract["service_restart"] is False
    assert contract["transaction_mutation"] is False
    assert contract["usb_mutation"] is False
    assert contract["homeassistant_mutation"] is False
    assert contract["u5_transition"] is False
    assert contract["u6_plus"] is False


def test_manifest_binds_exact_u4_live_entry_and_sources() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = document["expected_live_entry"]
    assert live["transaction_sha256"] == (
        "dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259"
    )
    assert live["target_size_bytes"] == 835309535
    assert live["target_sha256"] == (
        "eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973"
    )
    assert live["installed_predecessor_sha256"] == {
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_prepare.py": (
            "9139dc652eb992963c21d4fda171eef2bf685e1bbe0cbcea2319244c7e963475"
        ),
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_prepare_host.py": (
            "a11089ef57cf68c40a648c85ac7e7569a281f7fad13f75a09c0a3b04bad80ecf"
        ),
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_ipc.py": (
            "3aca46350c2fce9818dbc635f5343f01b06ff80081d93205ce7d28fc4ca2f771"
        ),
    }


def test_executor_and_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<kf147-u4-u5-preflight>", "exec")
    assert module.GATE_ID == GATE


def test_remote_preflight_is_read_only_and_requires_exact_u4() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'transaction.get("phase") != "U4_READY_TO_INSTALL"' in source
    assert 'transaction.get("authorization_claimed") is not False' in source
    assert 'transaction.get("authorization_consumed") is not False' in source
    assert 'ipc.get("phase") != "READY_TO_INSTALL"' in source
    assert 'sha_file(target) != plan["target_sha256"]' in source
    forbidden = (
        'run(["systemctl", "restart"',
        'run(["docker", "stop"',
        'run(["docker", "rm"',
        'run(["docker", "load"',
        "scp_to(",
        "request_install(",
        "os.replace(",
    )
    for token in forbidden:
        assert token not in source


def test_product_u5_intent_stops_before_u6_and_u9_claim() -> None:
    prepare = (ROOT / "tools" / "n3w_t1_core_updater_ha_prepare.py").read_text(
        encoding="utf-8"
    )
    ipc = (ROOT / "tools" / "n3w_t1_core_updater_ha_ipc.py").read_text(
        encoding="utf-8"
    )
    assert "def revalidate_and_request_install" in prepare
    assert "self.backend.verify_prepared_target" in prepare
    assert "u5 = request_install(transaction)" in prepare
    assert 'action not in {"PREPARE", "CONFIRM_USB_ERASE", "INSTALL"}' in ipc
    assert "self.prepare_controller.revalidate_and_request_install()" in ipc
    assert 'transition(transaction, "U6_' not in prepare


def test_target_binding_workflow_covers_u5_preflight() -> None:
    workflow = (
        ROOT
        / ".github"
        / "workflows"
        / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
    ).read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_u4_to_u5_install_intent_preflight/**"
    )
    executor_path = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_u4_to_u5_install_intent_preflight/executor.py"
    )
    test_path = "tests/tools/test_n3w_t1_kf147_u4_to_u5_install_intent_preflight.py"
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor_path) == 1
    assert workflow.count(test_path) == 2
