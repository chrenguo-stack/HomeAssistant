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
    / "u7_post_r30_repair_source_activation_r31"
)
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
WORKFLOW = (
    ROOT
    / ".github"
    / "workflows"
    / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
)

GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U7_POST_R30_REPAIR_SOURCE_ACTIVATION_R31_20261115_01"
)
CONFIRM = "EXECUTE U7 POST-R30 REPAIR SOURCE ACTIVATION R31: YES"


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_u7_r31_test", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_ungranted_and_stops_before_new_live_authorization() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["gate_id"] == GATE
    assert document["authorization_id"] == GATE
    assert document["confirmation"] == CONFIRM
    assert document["live_execution_authorized"] is False
    assert document["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert document["stop_boundary"] == (
        "STOP_AFTER_R31_REPAIR_SOURCE_ACTIVATION_"
        "BEFORE_NEW_U7_LIVE_AUTHORIZATION"
    )


def test_manifest_activates_only_two_repaired_sources() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["execution_contract"]["activated_source_file_count"] == 2
    assert set(document["remote_paths"]) == {"install", "host"}
    assert document["fixed_predecessor_sha256"] == {
        "install": "ccf182a939c2bc82a31cb13af31de45611fb4e53e46e964143632750aecfee8e",
        "host": "29b414fc31d3ef8c58707803be758dfbf954888a444d3f37b5dcc5d10f2930a6",
    }
    assert len(document["unchanged_source_sha256"]) == 13
    contract = document["execution_contract"]
    assert contract["service_stop"] is False
    assert contract["service_restart"] is False
    assert contract["transaction_mutation"] is False
    assert contract["usb_mutation"] is False
    assert contract["u7_transition"] is False
    assert contract["u8_plus"] is False
    assert contract["automatic_retry"] is False


def test_manifest_binds_kf158_and_consumed_r30_authority() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = document["source_authority"]
    assert authority["kf158_status"] == "RESOLVED_CLOSED_PASS"
    assert authority["kf158_root_cause"] == (
        "INCONSISTENT_SYSTEMD_OWNER_STATE_PREDICATE"
    )
    assert authority["kf158_fresh_ci_head"] == (
        "88f30bccfa47e899ee41fc68c517611b0acab846"
    )
    assert authority["kf158_fresh_ci"] == "16_OF_16_SUCCESS"
    assert authority["r30_result"] == "STOP_RECOVERED"
    assert authority["r30_authorization_consumed"] is True
    assert authority["r30_replay_permitted"] is False
    assert authority["target_install_blob"] == (
        "6ef197e0c36010649e3d6b162e184d3fbdb440c3"
    )
    assert authority["target_host_blob"] == (
        "4dbeef4fda1a0b4efaf4e9de6dfab13cf75d6eae"
    )


def test_target_sources_contain_both_kf158_repairs() -> None:
    host = (ROOT / "tools" / "n3w_t1_core_updater_host.py").read_text(
        encoding="utf-8"
    )
    install = (
        ROOT / "tools" / "n3w_t1_core_updater_ha_install.py"
    ).read_text(encoding="utf-8")
    assert 'owner_state in {"inactive", "failed"}' in host
    assert '"ha_usb_u7_failure_recovery_failed:"' in install
    assert '"operation="' in install
    assert '";recovery="' in install


def test_executor_and_embedded_remote_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<u7-r31>", "exec")
    assert module.GATE_ID == GATE
    assert module.CONFIRMATION == CONFIRM
    assert set(module.TARGETS) == {"install", "host"}
    assert set(module.REMOTE_NAMES) == {"install", "host"}


def test_preflight_requires_consumed_r30_and_preserved_u6() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert "def verify_r30(plan):" in remote
    assert '"STOP_RECOVERED"' in remote
    assert '"r30_claim_invalid"' in remote
    assert '"r30_failure_ledger_invalid"' in remote
    assert '"U6_PREDECESSOR_RECOVERY_PREPARING"' in remote
    assert "r30 = verify_r30(plan)" in remote
    assert '"source_activation_eligible": True' in remote
    assert '"service_stop": False' in remote
    assert '"service_restart": False' in remote
    assert '"transaction_mutation": False' in remote
    assert '"usb_mutation": False' in remote
    assert '"u7_transition": False' in remote
    assert '"u8_plus": False' in remote


def test_staged_import_is_before_claim_and_rollback_is_bounded() -> None:
    remote = load_executor().REMOTE_SCRIPT
    staged = remote.index("staged_import = staged_import_preflight(plan)")
    claim = remote.index('durable_json(state_root / "authorization_claim.json", claim)')
    armed = remote.index('result["host_source_mutation"] = True')
    replace_loop = remote.index('for key, destination in plan["remote_paths"].items():')
    assert staged < claim < armed < replace_loop
    assert "def rollback(plan, pre, backup_root):" in remote
    assert 'result["rollback_required"] = bool(result["host_source_mutation"])' in remote


def test_source_activation_cannot_stop_services_or_cross_u7() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '["systemctl", "stop"' not in remote
    assert '["systemctl", "start"' not in remote
    assert '["systemctl", "restart"' not in remote
    assert "create_consistent_backup" not in remote
    assert "record_predecessor_recovery_and_ha_quiesced" not in remote
    assert "transaction_store.write" not in remote
    assert '"U7_R31_REPAIR_SOURCE_ACTIVATION_PASS"' in remote


def test_workflow_covers_r31_package_and_test() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "u7_post_r30_repair_source_activation_r31/**"
    )
    executor = (
        "tools/execution_packages/n3w/r7a/"
        "u7_post_r30_repair_source_activation_r31/executor.py"
    )
    test_path = (
        "tests/tools/test_n3w_t1_u7_post_r30_repair_source_activation_r31.py"
    )
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor) == 1
    assert workflow.count(test_path) == 2
