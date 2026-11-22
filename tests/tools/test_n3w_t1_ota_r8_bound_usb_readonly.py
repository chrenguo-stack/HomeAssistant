from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8_bound_usb_readonly"
    / "verify.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("r8_bound_usb_verify", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def passing_report(tool):
    return {
        "status": "R8_SPARE_READONLY_PREFLIGHT_COLLECTED",
        "errors": {},
        "transactions_stable": True,
        "runtime": {
            "homeassistant_version": "2026.10.4",
            "diagnostic_only": False,
            "listeners_match": True,
            "references_match_compose": True,
        },
        "transactions": {
            "homeassistant_usb": {
                "status": "ROLLED_BACK",
                "sha256": tool.EXPECTED_TRANSACTION_SHA256,
            }
        },
        "bound_usb": {
            "status": "BOUND_USB_PRESENT",
            "device": tool.EXPECTED_DEVICE,
            "major_minor": tool.EXPECTED_MAJOR_MINOR,
            "filesystem": "ext4",
            "transaction_sha256": tool.EXPECTED_TRANSACTION_SHA256,
            "mounts": [
                {
                    "target": tool.PRIVATE_MOUNTPOINT,
                    "fstype": "ext4",
                    "options": "ro,noload,nodev,nosuid,noexec",
                }
            ],
        },
        "usb": {
            "status": "OBSERVED",
            "filesystem": "ext4",
            "read_only": True,
        },
        "rollback_materials": {
            "status": tool.EXPECTED_ROLLBACK_STATUS,
        },
        "capacity_policy": {
            "decision_point": "AFTER_RELEASE_BEFORE_NEXT_IMPORT",
            "post_release_available_bytes": None,
            "capacity_decision": "DEFER_UNTIL_POST_RELEASE_MEASUREMENT",
        },
    }


def test_validate_report_accepts_exact_readonly_contract():
    tool = load_module()
    tool.validate_report(passing_report(tool))


def test_validate_report_rejects_wrong_transaction():
    tool = load_module()
    report = passing_report(tool)
    report["transactions"]["homeassistant_usb"]["sha256"] = "0" * 64
    try:
        tool.validate_report(report)
    except RuntimeError as error:
        assert str(error) == "isolated_usb_transaction_binding_drift"
    else:
        raise AssertionError("wrong transaction accepted")


def test_validate_report_rejects_non_readonly_usb():
    tool = load_module()
    report = passing_report(tool)
    report["usb"]["read_only"] = False
    try:
        tool.validate_report(report)
    except RuntimeError as error:
        assert str(error) == "isolated_usb_readonly_contract_invalid"
    else:
        raise AssertionError("writable USB mount accepted")


def test_validate_report_rejects_capacity_pass_before_release_measurement():
    tool = load_module()
    report = passing_report(tool)
    report["capacity_policy"]["capacity_decision"] = "PASS"
    try:
        tool.validate_report(report)
    except RuntimeError as error:
        assert str(error) == "isolated_usb_capacity_policy_drift"
    else:
        raise AssertionError("pre-release capacity pass accepted")


def test_bootstrap_is_private_readonly_no_journal_replay():
    tool = load_module()
    source = tool._bootstrap("pass", "ZHVtbXk=")
    assert "--mount --propagation private" not in source
    assert '"mount", "--internal-only", "-t", "ext4"' in source
    assert '"ro,noload,nodev,nosuid,noexec"' in source
    assert '"umount", "--", MOUNTPOINT' in source
    assert "mkfs" not in source
    assert "docker load" not in source
    assert "docker image rm" not in source
    assert "systemctl stop" not in source
    assert "systemctl start" not in source
    assert "systemctl restart" not in source


def test_operator_unshare_is_private_and_no_persistent_authorization():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "/usr/bin/unshare --mount --propagation private --fork" in source
    assert "LIVE_WRITE_AUTHORIZATION" not in source
    assert "authorization_id" not in source
    assert "grant" not in source.lower()
    assert "mkfs" not in source
