from __future__ import annotations

import re
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8v13_07"
    / "N3W_T1_R8V13_07_FRESH_REACCEPTANCE_READONLY_REBIND_20261125_08.sh"
)


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_v3_is_environment_neutral_and_read_only() -> None:
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


def test_v3_binds_exact_repaired_terminal_state_and_live_pyz() -> None:
    text = source()
    for literal in (
        "4b1cc60e5557b9bc338d3d0469d30aa94c7974c34a0c26dffae5caf9fde4b105",
        "f6eb053e9eb21b034e98f7651e179194b0b3eed61ce561df978c4743c796467a",
        "807110108df6580328e9ecde2ea18321c199b07caab4fb1c087f81d8df1b7cd2",
        '"status": "ROLLED_BACK"',
        '"phase": "U13B_ROLLED_BACK"',
        '"failure_code": "ha_usb_target_acceptance_evidence_unavailable"',
        '"recovery_required": False',
        '"authorization_claimed": True',
        '"authorization_consumed": True',
        "de25e2d5c8ea8f183a6dca35048f6896c54d3876bea70f6c35afc847819ed136",
        "67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26",
    ):
        assert literal in text


def test_v3_uses_published_data_normalized_health() -> None:
    text = source()
    for literal in (
        "validate_transaction_document",
        'journal.get("step")!="PUBLISHED"',
        'raw_binding["images"]!=expected["images"]',
        "PREDECESSOR_NORMALIZED_BINDING_DRIFT",
        "verify_published_predecessor_health",
        "CURRENT_BINDING_MODE=PUBLISHED_DATA_NORMALIZED",
        "CURRENT_RAW_LAUNCH_SHA256=",
        "CURRENT_NORMALIZED_LAUNCH_SHA256=",
        "MANAGER_BROKER_HA_SELF_TEST=PASS",
    ):
        assert literal in text
    assert "verify_resident_predecessor_health" not in text


def test_v3_classifies_authority_and_verifies_exact_usb_source_from_terminal_tx() -> None:
    text = source()
    for literal in (
        "HA_PREPARE_AUTHORITY_STATE=",
        "HA_INSTALL_AUTHORITY_STATE=",
        "HA_RELEASE_AUTHORITY_STATE=",
        "APPROVED_MANIFEST_SHA256=",
        "ACTIVE_VALID_FOR_FRESH_PREPARE",
        "ACTIVE_OLD_TERMINAL_SAFE_REPLACEABLE",
        'expected_sha=transaction.get("target_archive_sha256")',
        'expected_size=transaction.get("target_archive_size")',
        'source=mount/"N3W-OTA"/old_tx_id/"target.tar"',
        "OLD_USB_TARGET_SOURCE=PASS",
        "OLD_USB_TARGET_SOURCE_SHA256=",
        "BOUND_USB_AVAILABLE_BYTES=",
        "ROOT_AVAILABLE_BYTES=",
    ):
        assert literal in text


def test_v3_preserves_r8v13_07_boundary() -> None:
    text = source()
    for literal in (
        "TARGET_10_0_PRESENT=false",
        "PERSISTENT_CONFIGURATION_MUTATION=false",
        "OLD_TRANSACTION_REPLAY=false",
        "NEW_TRANSACTION=false",
        "RESULT=R8V13_07_POST_PYZ_FRESH_REACCEPTANCE_READONLY_REBIND_V3_PASS",
    ):
        assert literal in text


def test_v3_hashes_large_usb_target_with_bounded_memory() -> None:
    text = source()
    assert 'source.read_bytes()' not in text
    assert 'with source.open("rb") as stream:' in text
    assert 'block=stream.read(1024*1024)' in text
    assert 'hasher.update(block)' in text
