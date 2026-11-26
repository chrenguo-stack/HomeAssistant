from __future__ import annotations

import re
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8v13_07"
    / "N3W_T1_R8V13_07_NEW_FRESH_TRANSACTION_A_PREPARE_TO_U4_20261125_03.sh"
)


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_v3_requires_explicit_prepare_authorization_and_exact_current_binding() -> None:
    text = source()
    for literal in (
        "N3W_T1_R8V13_07_NEW_FRESH_TRANSACTION_A_PREPARE_APPROVED",
        "4b1cc60e5557b9bc338d3d0469d30aa94c7974c34a0c26dffae5caf9fde4b105",
        "f6eb053e9eb21b034e98f7651e179194b0b3eed61ce561df978c4743c796467a",
        "807110108df6580328e9ecde2ea18321c199b07caab4fb1c087f81d8df1b7cd2",
        "67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26",
        "987189ccd61c0784db089b08e51a9ad3ff317372ad8a952dcda7a03a6d844c70",
        "e99e5d494fd8c39172dcf2d25ae50ae3dfcbdc8f15377eebc6c488b1f0209351",
        "50eda7d64dce2fe9de2196316c2acb7b63297f3e1aff1d927824a72a7f7742ca",
        "814a7f974c5c7eb3ddd8703c5200d6b5bb89a15145851da15868db94dcda16fc",
        '"failure_code": "ha_usb_target_acceptance_evidence_unavailable"',
        "de25e2d5c8ea8f183a6dca35048f6896c54d3876bea70f6c35afc847819ed136",
    ):
        assert literal in text


def test_v3_accepts_only_terminal_bound_old_install_authority_without_replay() -> None:
    text = source()
    for literal in (
        "OLD_PREPARE_AUTHORITY_STATE=EXPIRED_OLD_TERMINAL",
        "ACTIVE_OLD_TERMINAL_SAFE_REPLACEABLE",
        "EXPIRED_OLD_TERMINAL_SAFE_REPLACEABLE",
        "OLD_INSTALL_AUTHORITY_BINDING_SHA256=",
        "OLD_RELEASE_AUTHORITY_STATE=REFRESH_REQUIRED",
        "STALE_INSTALL_AUTHORITY_COLLIDES_WITH_NEW_TRANSACTION",
        "INSTALL_AUTHORITY_RESIDUE=OLD_TERMINAL_SAFE_REPLACEABLE",
        "OLD_INSTALL_AUTHORITY_REPLAY=false",
    ):
        assert literal in text
    assert "EXPECTED_OLD_AUTHORITY_NOT_EXPIRED" not in text


def test_v3_distinguishes_old_normalized_launch_from_new_raw_baseline() -> None:
    text = source()
    for literal in (
        "verify_published_predecessor_health",
        "OLD_TERMINAL_NORMALIZED_BINDING_DRIFT",
        "CURRENT_RAW_BASELINE_LAUNCH_DRIFT",
        "OLD_TERMINAL_NORMALIZED_LAUNCH_SHA256=",
        "NEW_TRANSACTION_BASELINE_LAUNCH_SHA256=",
        "FINAL_NEW_BASELINE_LAUNCH_DRIFT",
    ):
        assert literal in text


def test_v3_fails_before_mutation_when_sequential_usb_capacity_is_insufficient() -> None:
    text = source()
    assert text.index("FRESH_PREPARE_SEQUENTIAL_REQUIRED_BYTES=") < text.index("MUTATION_STARTED=true")
    assert text.index("FRESH_PREPARE_USB_SPACE_INSUFFICIENT_PREMUTATION") < text.index("MUTATION_STARTED=true")
    for literal in (
        "_measure_predecessor_archive",
        "PREDECESSOR_ARCHIVE_MEASUREMENT_DRIFT",
        "TARGET_WRITE_REQUIRED_BYTES=",
        "MEASURED_PREDECESSOR_ARCHIVE_BYTES=",
        "PREDECESSOR_WRITE_REQUIRED_BYTES=",
        "FRESH_PREPARE_SEQUENTIAL_REQUIRED_BYTES=",
        "FRESH_PREPARE_SEQUENTIAL_CAPACITY=PASS",
    ):
        assert literal in text


def test_v3_creates_fresh_transaction_only_after_capacity_pass_and_stops_at_u4() -> None:
    text = source()
    assert text.index("FRESH_PREPARE_SEQUENTIAL_CAPACITY=PASS") < text.index("MUTATION_STARTED=true")
    for literal in (
        "materialize-candidate",
        "--maintenance-submit-approved-release PREPARE",
        "--issue-prepare-authority",
        "--resume-pending",
        "NEW_FRESH_TRANSACTION_A_U4=PASS",
        "NEW_FRESH_TRANSACTION_A_PREPARE_V3_RESULT=PASS",
        "R8V13_07_SUBSTATE=NEW_FRESH_U4_READY_TO_INSTALL",
        "INSTALL_INTENT=false",
        "INSTALL_AUTHORITY_ISSUED_FOR_NEW_TRANSACTION=false",
        "HA_INSTALL_OR_CUTOVER=false",
        "NEW_TRANSACTION_CREATED=true",
        "NEXT_BOUNDARY=STOP_BEFORE_NEW_INSTALL_AUTHORIZATION",
    ):
        assert literal in text


def test_v3_does_not_install_or_cutover() -> None:
    text = source()
    for forbidden in (
        "maintenance-submit-approved-release INSTALL",
        "--issue-install-authority",
        "docker image load",
        "docker load",
        "docker image rm",
        "docker rmi",
        "systemctl stop n3wfc4-services-activation.service",
        "systemctl start n3wfc4-services-activation.service",
    ):
        assert forbidden not in text
    assert re.search(r"\bTARGET_10_0_PRESENT_AFTER_PREPARE=false\b", text)
