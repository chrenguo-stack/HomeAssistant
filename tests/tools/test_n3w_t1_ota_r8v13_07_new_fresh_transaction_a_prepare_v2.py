from __future__ import annotations

import re
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8v13_07"
    / "N3W_T1_R8V13_07_NEW_FRESH_TRANSACTION_A_PREPARE_TO_U4_20261125_02.sh"
)


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_v2_requires_explicit_physical_prepare_authorization_and_stops_before_install() -> None:
    text = source()
    assert "N3W_T1_R8V13_07_NEW_FRESH_TRANSACTION_A_PREPARE_APPROVED" in text
    assert ' = "YES"' in text
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
    ):
        assert re.search(forbidden, text) is None
    assert "NEXT_BOUNDARY=STOP_BEFORE_NEW_INSTALL_AUTHORIZATION" in text
    assert "INSTALL_INTENT=false" in text
    assert "HA_INSTALL_OR_CUTOVER=false" in text
    assert '"phase": "U13B_ROLLED_BACK"' in text
    assert 'd["status"]!="ACTIVE" or d["phase"]!="U4_READY_TO_INSTALL"' in text
    assert "NEW_FRESH_TRANSACTION_A_U4=PASS" in text


def test_v2_binds_exact_post_recovery_terminal_entry_state() -> None:
    text = source()
    for literal in (
        "795c89ce2a7b10246da381ed205e7bf3f77c2561197d1d6a6e4ac2fb9e332eed",
        "d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4",
        "9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa",
        "67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26",
        "9eb8f178020cbba23a0436c1b914bf82f9ccb7a499e8845c64fa2492955cdf79",
        "304683dee3ff75785215710c5a4a8ffbb12ae0b0912101474b969a46e035c83b",
        "2df25242a476d28758b5de4c78f6d6c11bd85a71b49aa27d5c845345513c1cc6",
        '"status": "ROLLED_BACK"',
        '"phase": "U13B_ROLLED_BACK"',
        '"failure_code": None',
        '"authorization_claimed": True',
        '"authorization_consumed": True',
        "6976d68fd1b6828b630fd05751c2855afd84efc65639753f1a318189fff62f50",
        '"predecessor_release_observed": True',
        "OLD_TRANSACTION_TERMINAL_NO_REPLAY=PASS",
        "OLD_AUTHORITIES_AND_RELEASE_PIN_EXPIRED=PASS",
    ):
        assert literal in text


def test_v2_reuses_exact_usb_target_as_read_only_source_and_checks_dynamic_internal_capacity() -> None:
    text = source()
    for literal in (
        "e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663",
        'EXPECTED_TARGET_SIZE="2448553472"',
        '"N3W-OTA"/txid/"target.tar"',
        "OLD_USB_TARGET_SOURCE=PASS",
        "INTERNAL_CANDIDATE_PREEXISTING_EXACT=",
        "INTERNAL_CANDIDATE_REQUIRED_BYTES=",
        "INTERNAL_CANDIDATE_CAPACITY=PASS",
        'part=stream.read(1024*1024)',
    ):
        assert literal in text
    assert "source.read_bytes()" not in text


def test_v2_refreshes_release_authority_only_through_existing_materialize_candidate_path() -> None:
    text = source()
    for literal in (
        "materialize-candidate",
        "--approved-manifest",
        "--approved-manifest-sha256",
        "--target-archive",
        "RELEASE_AUTHORITY_REFRESH=PASS",
        "REFRESHED_RELEASE_PIN_EXPIRES_AT_UNIX=",
        "LocalApprovedHaRelease",
        "REFRESHED_RELEASE_ADMISSION_DRIFT",
    ):
        assert literal in text
    assert "ha-release-pin.json" in text


def test_v2_creates_new_transaction_and_fresh_prepare_authority_then_stops_at_u4() -> None:
    text = source()
    for literal in (
        "--maintenance-submit-approved-release PREPARE",
        "FRESH_TRANSACTION_ID_REUSED",
        "NEW_FRESH_TRANSACTION_U1=PASS",
        "--issue-prepare-authority",
        "--resume-pending",
        'd["status"]!="ACTIVE" or d["phase"]!="U4_READY_TO_INSTALL"',
        "NEW_FRESH_TRANSACTION_A_U4=PASS",
        "target_artifact_verified",
        "prepared_image_materials",
        "INSTALL_AUTHORITY_RESIDUE=OLD_TERMINAL_SAFE_REPLACEABLE",
        "TARGET_10_0_PRESENT_AFTER_PREPARE=false",
        "NEW_FRESH_TRANSACTION_A_PREPARE_RESULT=PASS",
        "R8V13_07_SUBSTATE=NEW_FRESH_U4_READY_TO_INSTALL",
        "RELEASE_AUTHORITY_REFRESHED=true",
        "NEW_TRANSACTION_CREATED=true",
    ):
        assert literal in text


def test_v2_has_single_success_marker() -> None:
    text = source()
    assert text.count("NEW_FRESH_TRANSACTION_A_PREPARE_RESULT=PASS") == 1
