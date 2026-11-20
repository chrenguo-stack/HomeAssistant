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
    / "u8_recovery_admission_r33"
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
    "U8_RECOVERY_ADMISSION_R33_20261115_01"
)
CONFIRM = "EXECUTE U8 R33 RECOVERY ADMISSION: YES"
R32_HEAD = "627da8213966ea4e1992c63f8b7c5dcf01265ecf"
U7_SHA = "2648201570dbc4c54809f2c6880a039984aa713d54c2719fd736a4fda13e07ea"


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_u8_r33_test", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_granted_after_explicit_u8_authorization() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["gate_id"] == GATE
    assert document["authorization_id"] == GATE
    assert document["confirmation"] == CONFIRM
    assert document["live_execution_authorized"] is True
    assert document["authorization_state"] == {
        "granted": True,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert document["stop_boundary"] == (
        "STOP_AFTER_U8_RECOVERY_ADMISSION_BEFORE_U9_LIVE_AUTHORIZATION_CLAIM"
    )


def test_manifest_binds_exact_r32_u7_closure() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = document["source_authority"]
    entry = document["expected_live_entry"]
    assert authority["r32_execution_authority_head"] == R32_HEAD
    assert authority["r32_result"] == (
        "U7_R32_REPAIRED_HA_QUIESCE_DATA_BACKUP_PASS"
    )
    assert authority["r32_authorization_consumed"] is True
    assert authority["r32_replay_permitted"] is False
    assert entry["transaction_sha256"] == U7_SHA
    assert entry["r32_execution_id"] == "r32-live01-20261115T133826Z"
    assert entry["backup_identity"]["archive_sha256"] == (
        "9473d5d199fd16c185425f5f0a0676d6cfab1888db28617f5ac4c9e4fa9e1c4c"
    )
    assert entry["backup_identity"]["manifest_sha256"] == (
        "fd9a2f279a6e9fed99c2af6c2d4502227cafebe4d0ea5d5bb0a467e34415a704"
    )


def test_manifest_keeps_u9_and_destructive_cutover_blocked() -> None:
    contract = json.loads(MANIFEST.read_text(encoding="utf-8"))[
        "execution_contract"
    ]
    assert contract["embedded_readonly_preclaim_on_execute"] is True
    assert contract["product_u9_authorization_fields_untouched"] is True
    assert contract["transaction_u7_to_u8_only"] is True
    assert contract["service_mutation"] is False
    assert contract["predecessor_internal_image_preserved"] is True
    assert contract["target_internal_image_must_remain_absent"] is True
    assert contract["destructive_cutover"] is False
    assert contract["predecessor_image_delete"] is False
    assert contract["target_image_load"] is False
    assert contract["automatic_retry"] is False
    assert contract["u9_plus"] is False


def test_executor_and_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<u8-r33>", "exec")
    assert module.GATE_ID == GATE
    assert module.CONFIRMATION == CONFIRM
    assert module.MANIFEST_SCHEMA == (
        "gh.n3w-t1-u8-r33-recovery-admission-manifest/1"
    )
    assert module.LOCAL_RESULT_SCHEMA == "gh.n3w-t1-u8-r33-local-result/1"
    assert module.PREFLIGHT_TIMEOUT_SECONDS == 1200
    assert module.PREFLIGHT_REMOTE_PROCESS_TIMEOUT_SECONDS == 1170


def test_execute_revalidates_prestate_before_claim() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def execute(")
    end = remote.index("def main()", start)
    block = remote[start:end]
    prestate = block.index("pre = verify_prestate(plan)")
    state_root = block.index("state_root.mkdir(mode=0o700)")
    claim = block.index('durable_json_once(state_root / "authorization_claim.json"')
    assert prestate < state_root < claim


def test_u8_uses_existing_product_admission_without_u9_claim() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert "from n3w_t1_core_updater_ha_usb import record_recovery_admission" in remote
    assert "claim_live_authorization" not in remote
    start = remote.index("def execute(")
    end = remote.index("def main()", start)
    block = remote[start:end]
    admission = block.index('product["record_recovery_admission"](')
    usb_sync = block.index("backend.sync_transaction_metadata(admitted, media)")
    host_sync = block.index("store.write(admitted)")
    assert admission < usb_sync < host_sync


def test_preflight_requires_exact_u7_recovery_authority() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"U7_HA_QUIESCED_DATA_BACKUP_PREPARING"' in remote
    assert "verify_r32(plan)" in remote
    assert "provider.verify_backup(" in remote
    assert "backend.recovery_admission_capacity(" in remote
    assert "verify_predecessor_internal_image(plan)" in remote
    assert "verify_target_internal_image_absent(plan)" in remote
    assert '"authorization_claimed") is not False' in remote
    assert '"authorization_consumed") is not False' in remote


def test_quiesced_runtime_accepts_failed_owner_but_preserves_broker() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def verify_quiesced_runtime")
    end = remote.index("def verify_predecessor_internal_image", start)
    block = remote[start:end]
    assert 'not in {"inactive", "failed"}' in remote
    assert 'containers["broker"].get("status") != "running"' in block
    assert 'containers["manager"].get("status") == "running"' in block
    assert 'containers["homeassistant"].get("status") == "running"' in block


def test_u8_terminal_keeps_product_authorization_unclaimed() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def verify_terminal_u8_state")
    end = remote.index("def read_terminal_status", start)
    block = remote[start:end]
    assert '"U8_RECOVERY_ADMISSION_COMPLETE"' in block
    assert 'transaction.get("authorization_claimed") is not False' in block
    assert 'transaction.get("authorization_consumed") is not False' in block
    assert 'transaction.get("authorization_id_sha256") is not None' in block
    assert "recovery_content_manifest_sha256" in block
    assert "verify_predecessor_internal_image(plan)" in block
    assert "verify_target_internal_image_absent(plan)" in block


def test_execute_contains_no_destructive_cutover_or_service_restart() -> None:
    remote = load_executor().REMOTE_SCRIPT
    start = remote.index("def execute(")
    end = remote.index("def main()", start)
    block = remote[start:end]
    assert '"destructive_cutover": False' in block
    assert '"predecessor_image_delete": False' in block
    assert '"target_image_load": False' in block
    assert '"u9_plus": False' in block
    assert "docker image rm" not in block
    assert "docker load" not in block
    assert '["systemctl", "start"' not in block
    assert '["systemctl", "stop"' not in block


def test_postclaim_path_never_retries_u8() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert remote.count('product["record_recovery_admission"](') == 1
    assert '"STOP_POSTCLAIM"' in remote
    assert '"STOP_POSTSUCCESS_LOCAL"' in remote
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["execution_contract"]["automatic_retry"] is False
    assert (
        document["execution_contract"]["postclaim_failure_consumes_authorization"]
        is True
    )


def test_workflow_covers_r33_package_and_test() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/u8_recovery_admission_r33/**"
    )
    executor = (
        "tools/execution_packages/n3w/r7a/u8_recovery_admission_r33/executor.py"
    )
    test_path = "tests/tools/test_n3w_t1_u8_recovery_admission_r33.py"
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor) == 1
    assert workflow.count(test_path) == 2
