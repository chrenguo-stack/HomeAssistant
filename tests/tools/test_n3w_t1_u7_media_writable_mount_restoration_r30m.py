from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "tools" / "execution_packages" / "n3w" / "r7a" / "u7_media_writable_mount_restoration_r30m"
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
WORKFLOW = ROOT / ".github" / "workflows" / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
GATE = "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_U7_MEDIA_WRITABLE_MOUNT_RESTORATION_R30M_20261115_01"
CONFIRMATION = "EXECUTE U7 R30M WRITABLE MOUNT RESTORATION: YES"


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_u7_r30m_test", EXECUTOR)
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


def test_manifest_is_granted_after_explicit_writable_mount_authorization() -> None:
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert d["gate_id"] == GATE
    assert d["authorization_id"] == GATE
    assert d["confirmation"] == CONFIRMATION
    assert d["live_execution_authorized"] is True
    assert d["authorization_state"] == {
        "granted": True,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    entry = d["expected_live_entry"]
    assert entry["transaction_sha256"] == "7f406b5b88f7bd5c3161d7527a001ddcb3414a8ec64fb34cdad444c2c3e62ebe"
    assert entry["usb_filesystem_uuid"] == "967cf065-abe5-49ee-8499-7c3f50d2c48f"
    assert entry["usb_public_fingerprint"] == "e45fba0ad3e9997be2738c7a8f25d5c342ebba66ddbf822b1f6bf6a016c2ed93"
    assert len(entry["installed_source_sha256"]) == 15
    contract = d["execution_contract"]
    assert contract["fixed_dev_sdx_authority"] is False
    assert contract["filesystem_clean_required"] is True
    assert contract["u7_transition"] is False
    assert contract["u8_plus"] is False


def test_executor_and_remote_compile() -> None:
    m = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(m.REMOTE_SCRIPT, "<u7-r30m>", "exec")
    assert m.GATE_ID == GATE
    assert m.CONFIRMATION == CONFIRMATION


def test_preflight_is_read_only_and_unmounted_only() -> None:
    ns = load_remote_namespace()
    ns["validate_preflight"] = lambda plan: {"baseline": True}
    result = ns["execute"]({"mode": "preflight", "live_execution_authorized": False})
    assert result["status"] == "PASS"
    assert result["read_only"] is True
    assert result["restoration_eligible"] is True
    assert result["authorization_claimed"] is False
    assert result["authorization_consumed"] is False
    assert result["runtime_directory_creation_attempted"] is False
    assert result["writable_mount_attempted"] is False
    assert result["usb_mutation"] is False
    assert result["transaction_mutation"] is False
    assert result["u7_transition"] is False
    assert result["u8_plus"] is False


def test_execute_fails_closed_while_ungranted() -> None:
    ns = load_remote_namespace()
    ns["validate_preflight"] = lambda plan: {"baseline": True}
    stop = ns["Stop"]
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
    except stop as error:
        assert str(error) == "restoration_live_execution_not_authorized"
    else:
        raise AssertionError("ungranted R30M execute must fail closed")


def test_current_authority_and_mount_guards_are_frozen() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert '"U6_PREDECESSOR_RECOVERY_PREPARING"' in source
    assert '"U6_R26_PREDECESSOR_RECOVERY_PASS"' in source
    assert '"U7_R29_SOURCE_ACTIVATION_PASS"' in source
    assert '"U7_R30S_PREPARE_HOST_SOURCE_ACTIVATION_PASS"' in source
    assert "usb_filesystem_not_clean" in source
    assert "tune2fs" in source
    assert '"rw,nodev,nosuid,noexec"' in source
    assert "/dev/sda1" not in source
    assert "/dev/sdb1" not in source
    assert "verify_predecessor(plan)" in source
    assert "request_install(" not in source
    assert 'run(["systemctl", "restart"' not in source


def test_workflow_covers_r30m() -> None:
    w = WORKFLOW.read_text(encoding="utf-8")
    assert w.count("tools/execution_packages/n3w/r7a/u7_media_writable_mount_restoration_r30m/**") == 1
    assert w.count("tools/execution_packages/n3w/r7a/u7_media_writable_mount_restoration_r30m/executor.py") == 1
    assert w.count("tests/tools/test_n3w_t1_u7_media_writable_mount_restoration_r30m.py") == 2
