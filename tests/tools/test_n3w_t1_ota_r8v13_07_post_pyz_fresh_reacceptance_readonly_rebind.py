from __future__ import annotations

import re
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8v13_07"
    / "N3W_T1_R8V13_07_FRESH_REACCEPTANCE_READONLY_REBIND_20261125_06.sh"
)


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_post_pyz_rebind_is_environment_neutral_and_read_only() -> None:
    text = source()
    assert "N3W_T1_SSH_TARGET required" in text
    assert re.search(
        r"(?<![0-9])(?:10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}|172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})(?![0-9])",
        text,
    ) is None
    for forbidden in (
        r"systemctl\s+(?:start|stop|restart|enable|disable)",
        r"docker\s+(?:load|pull|rm|rmi|compose\s+up|compose\s+down)",
        r"\b(?:cp|mv|rm|install)\s+/(?:opt|etc|var)/",
        "--resume-pending",
        "--install-requested",
        "--issue-prepare-authority",
        "--issue-install-authority",
        "maintenance-submit-approved-release",
        "materialize-candidate",
        "activate-candidate-runtime",
    ):
        assert re.search(forbidden, text) is None
    assert "PERSISTENT_CONFIGURATION_MUTATION=false" in text
    assert "OLD_TRANSACTION_REPLAY=false" in text
    assert "NEW_TRANSACTION=false" in text


def test_post_pyz_rebind_binds_exact_terminal_state_and_live_pyz() -> None:
    text = source()
    for literal in (
        "795c89ce2a7b10246da381ed205e7bf3f77c2561197d1d6a6e4ac2fb9e332eed",
        "d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4",
        "9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa",
        '"status": "ROLLED_BACK"',
        '"phase": "U13B_ROLLED_BACK"',
        '"recovery_required": False',
        '"authorization_claimed": True',
        '"authorization_consumed": True',
        "6976d68fd1b6828b630fd05751c2855afd84efc65639753f1a318189fff62f50",
        "67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26",
    ):
        assert literal in text


def test_post_pyz_rebind_requires_runtime_health_authority_classification_and_usb_source() -> None:
    text = source()
    for literal in (
        "RUNTIME_IDENTITIES=PASS",
        "verify_resident_predecessor_health",
        "MANAGER_BROKER_HA_SELF_TEST=PASS",
        "HA_PREPARE_AUTHORITY_STATE=",
        "HA_INSTALL_AUTHORITY_STATE=",
        "HA_RELEASE_AUTHORITY_STATE=",
        "APPROVED_MANIFEST_SHA256=",
        "ACTIVE_VALID_FOR_FRESH_PREPARE",
        "ACTIVE_OLD_TERMINAL_SAFE_REPLACEABLE",
        "OLD_USB_TARGET_SOURCE=PASS",
        "OLD_USB_TARGET_SOURCE_SHA256=",
        "BOUND_USB_AVAILABLE_BYTES=",
        "ROOT_AVAILABLE_BYTES=",
    ):
        assert literal in text


def test_post_pyz_rebind_preserves_r8v13_07_boundary() -> None:
    text = source()
    for literal in (
        "TARGET_10_0_PRESENT=false",
        "PERSISTENT_CONFIGURATION_MUTATION=false",
        "OLD_TRANSACTION_REPLAY=false",
        "NEW_TRANSACTION=false",
        "RESULT=R8V13_07_POST_PYZ_FRESH_REACCEPTANCE_READONLY_REBIND_PASS",
    ):
        assert literal in text
