from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u9_live_authorization_r36_successor"
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
    "U9_LIVE_AUTHORIZATION_R36_20261115_01"
)
PRODUCT_AUTHORIZATION = (
    "N3W_T1_CORE_UPDATER_HOMEASSISTANT_USB_U9_R36_20261115_01"
)
AUTHORIZATION_RE = re.compile(
    r"^N3W_T1_CORE_UPDATER_[A-Za-z0-9_-]{1,160}$"
)


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_u9_r36_test", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_pre_authorization_successor_only() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["gate_id"] == GATE
    assert document["authorization_id"] == PRODUCT_AUTHORIZATION
    assert document["authorization_id"] != document["gate_id"]
    assert AUTHORIZATION_RE.fullmatch(document["authorization_id"])
    assert document["live_execution_authorized"] is False
    assert document["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert document["execution_contract"][
        "explicit_r36_user_authorization_required"
    ] is True
    assert document["execution_contract"][
        "explicit_r36_user_authorization_granted"
    ] is False


def test_manifest_binds_consumed_r35_safe_stop() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = document["source_authority"]
    entry = document["expected_live_entry"]
    assert authority["r35_source_head"] == (
        "c3a154820f8aff193c31db55f5043e04bdbbb428"
    )
    assert authority["r35_execution_id"] == "r35-live01-20261115T161150Z"
    assert authority["r35_result"] == "STOP_POSTCLAIM"
    assert authority["r35_failure_operation"] == (
        "UpdaterV2Error:ha_usb_live_authorization_id_invalid"
    )
    assert authority["r35_authorization_claimed"] is True
    assert authority["r35_authorization_consumed"] is True
    assert authority["r35_replay_permitted"] is False
    assert authority["r35_transaction_mutation"] is False
    assert authority["r35_usb_mutation"] is False
    assert authority["r35_u9_transition"] is False
    assert authority["r35_transaction_phase"] == (
        "U8_RECOVERY_ADMISSION_COMPLETE"
    )
    assert entry["r35_gate_id"] == (
        "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
        "U9_LIVE_AUTHORIZATION_R35_20261115_01"
    )
    assert entry["r35_execution_id"] == "r35-live01-20261115T161150Z"


def test_executor_and_remote_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<u9-r36>", "exec")
    assert module.GATE_ID == GATE
    assert module.PRODUCT_AUTHORIZATION_ID == PRODUCT_AUTHORIZATION
    assert module.GATE_ID != module.PRODUCT_AUTHORIZATION_ID


def test_read_manifest_requires_product_authorization_not_gate_id() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    start = source.index("def read_manifest")
    end = source.index("def remote_mode", start)
    block = source[start:end]
    assert 'document.get("authorization_id") != PRODUCT_AUTHORIZATION_ID' in block
    assert 'document.get("authorization_id") != GATE_ID' not in block


def test_local_execute_argument_uses_product_authorization_id() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    start = source.rindex("def main() -> int:")
    block = source[start:]
    assert "args.authorization_id != PRODUCT_AUTHORIZATION_ID" in block
    assert "args.authorization_id != GATE_ID" not in block


def test_remote_preclaim_requires_r35_consumed_safe_stop() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def verify_r35_consumed_failure")
    end = remote.index("def verify_prestate_u9", start)
    block = remote[start:end]
    assert '"STOP_POSTCLAIM"' in block
    assert '"UpdaterV2Error:ha_usb_live_authorization_id_invalid"' in block
    assert 'failure.get("transaction_mutation") is not False' in block
    assert 'failure.get("usb_mutation") is not False' in block
    assert 'failure.get("u9_transition") is not False' in block
    assert '"U8_RECOVERY_ADMISSION_COMPLETE"' in block
    assert 'failure.get("u10_plus") is not False' in block
    assert 'failure.get("destructive_cutover") is not False' in block


def test_r35_ledger_is_revalidated_before_r36_claim() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.rindex("def execute(")
    end = remote.rindex("def main()")
    execute = remote[start:end]
    prestate_call = execute.index("pre = verify_prestate_u9(plan)")
    state_root = execute.index("state_root.mkdir(mode=0o700)")
    assert prestate_call < state_root

    start = remote.index("def verify_prestate_u9")
    end = remote.index("def verify_terminal_u9_state", start)
    prestate = remote[start:end]
    assert "r35_ledger = verify_r35_consumed_failure(plan)" in prestate
    assert '"r35_ledger": r35_ledger' in prestate


def test_successor_still_stops_before_u10() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.rindex("def execute(")
    end = remote.rindex("def main()")
    block = remote[start:end]
    assert '"u10_plus": False' in block
    assert '"destructive_cutover": False' in block
    assert '"predecessor_image_delete": False' in block
    assert '"target_image_load": False' in block
    assert '"service_mutation": False' in block
    assert "docker image rm" not in block
    assert "docker load" not in block


def test_workflow_covers_r36_successor() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "u9_live_authorization_r36_successor/**"
    )
    executor = (
        "tools/execution_packages/n3w/r7a/"
        "u9_live_authorization_r36_successor/executor.py"
    )
    test_path = "tests/tools/test_n3w_t1_u9_live_authorization_r36_successor.py"
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor) == 1
    assert workflow.count(test_path) == 2
