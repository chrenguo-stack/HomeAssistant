from __future__ import annotations

import re
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8v13_07"
    / "N3W_T1_R8V13_07_NEW_FRESH_TRANSACTION_A_PREPARE_TO_U4_20261124_01.sh"
)


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_executor_is_environment_neutral_and_stops_before_install() -> None:
    text = source()
    assert "N3W_T1_SSH_TARGET required" in text
    assert re.search(
        r"(?<![0-9])(?:10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}|172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})(?![0-9])",
        text,
    ) is None
    for forbidden in (
        "--issue-install-authority",
        "--install-requested",
        "maintenance-submit-approved-release INSTALL",
        "activate-candidate-runtime",
        "docker image load",
        r"systemctl\s+(?:start|stop|restart)",
        r"\bumount\s+",
        r"\bmkfs\b",
        "U13A_COMMITTED",
        "U13B_ROLLED_BACK",
    ):
        assert re.search(forbidden, text) is None
    assert "NEXT_BOUNDARY=STOP_BEFORE_NEW_INSTALL_AUTHORIZATION" in text
    assert "INSTALL_INTENT=false" in text
    assert "HA_INSTALL_OR_CUTOVER=false" in text


def test_executor_binds_exact_recovered_entry_state() -> None:
    text = source()
    for literal in (
        "b5b7120b17539d1c4178450793dcf3d6900d0cba46c518132ad76fade8af04a0",
        "afbfeeb85c3ab579b62d86d347f76b7f6ee7f203b068eac028be1d18761950c3",
        "5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a",
        "b72ac2fc-79a0-4fb8-888e-f35b0114f959",
        "5fbae3dedc6af008fec90efc24e75349ce82fc3a538e935806bef6ab3cbc4a36",
        "local/n3w-homeassistant:2026.10.4-5881590f",
        "local/n3w-homeassistant:2026.10.0-0c73235a",
        "local/greenhouse-manager:fresh-1cae18039eee",
        "local/n3w-mosquitto:2.1.2-3184566d",
    ):
        assert literal in text


def test_executor_uses_exact_external_target_as_read_only_byte_source() -> None:
    text = source()
    for literal in (
        "e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663",
        'EXPECTED_TARGET_SIZE="2448553472"',
        '"N3W-OTA"/txid/"target.tar"',
        "OLD_USB_TARGET_SOURCE=PASS",
        "materialize-candidate",
        "--target-archive",
        "INTERNAL_CANDIDATE_REQUIRED_BYTES=",
        "INTERNAL_CANDIDATE_CAPACITY=PASS",
    ):
        assert literal in text
    assert "usb_reserve_bytes" not in text
    assert "max_predecessor_bytes" not in text


def test_executor_creates_new_transaction_and_never_reuses_terminal_id() -> None:
    text = source()
    for literal in (
        "--maintenance-submit-approved-release PREPARE",
        "--release-identity",
        "FRESH_TRANSACTION_ID_REUSED",
        'd["transaction_id_sha256"]==old_id',
        "NEW_FRESH_TRANSACTION_U1=PASS",
        "--issue-prepare-authority",
        "--resume-pending",
    ):
        assert literal in text


def test_executor_requires_exact_fresh_u4_and_keeps_install_separate() -> None:
    text = source()
    for literal in (
        'd["status"]!="ACTIVE" or d["phase"]!="U4_READY_TO_INSTALL"',
        "NEW_FRESH_TRANSACTION_A_U4=PASS",
        "target_artifact_verified",
        "prepared_image_materials",
        "verified",
        "fsynced",
        "INSTALL_AUTHORITY_RESIDUE=OLD_TERMINAL_SAFE_REPLACEABLE",
        "TARGET_10_0_PRESENT_AFTER_PREPARE=false",
        "NEW_FRESH_TRANSACTION_A_PREPARE_RESULT=PASS",
        "R8V13_07_SUBSTATE=NEW_FRESH_U4_READY_TO_INSTALL",
    ):
        assert literal in text


def test_executor_has_single_success_marker() -> None:
    text = source()
    assert text.count("NEW_FRESH_TRANSACTION_A_PREPARE_RESULT=PASS") == 1
