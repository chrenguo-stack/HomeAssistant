from __future__ import annotations

import re
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8v13_07"
    / "N3W_T1_R8V13_07_FRESH_TX_A_U4_INSTALL_READONLY_PREFLIGHT_20261125_01.sh"
)


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_u4_install_preflight_is_read_only() -> None:
    text = source()
    for forbidden in (
        "--maintenance-submit-approved-release",
        "--issue-install-authority",
        "--install-requested",
        "--resume-pending",
        "materialize-candidate",
        "activate-candidate-runtime",
        r"systemctl\s+(?:start|stop|restart|enable|disable)",
        r"docker\s+(?:load|pull|rm|rmi)",
        r"\b(?:cp|mv|rm|install)\s+/(?:opt|etc|var)/",
        r"\bmkfs\b",
        r"\bumount\b",
    ):
        assert re.search(forbidden, text) is None
    for literal in (
        "PERSISTENT_CONFIGURATION_MUTATION=false",
        "INSTALL_INTENT=false",
        "INSTALL_AUTHORITY_ISSUED=false",
        "PRODUCT_WORKER_DISPATCH=false",
        "HA_INSTALL_OR_CUTOVER=false",
        "R8V13_08_AUTO_ADVANCE=false",
    ):
        assert literal in text


def test_u4_install_preflight_binds_exact_new_transaction_and_runtime() -> None:
    text = source()
    for literal in (
        "f6eb053e9eb21b034e98f7651e179194b0b3eed61ce561df978c4743c796467a",
        "9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa",
        "5fbae3dedc6af008fec90efc24e75349ce82fc3a538e935806bef6ab3cbc4a36",
        "b72ac2fc-79a0-4fb8-888e-f35b0114f959",
        "67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26",
        '"status": "ACTIVE"',
        '"phase": "U4_READY_TO_INSTALL"',
        "U4_TRANSACTION=PASS",
        "CURRENT_LAUNCH_SHA256=",
        "MANAGER_BROKER_HA_SELF_TEST=PASS",
        "INSTALL_BINDING_SHA256=",
    ):
        assert literal in text


def test_u4_install_preflight_validates_prepared_materials_and_target_absence() -> None:
    text = source()
    for literal in (
        "e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663",
        'EXPECTED_TARGET_SIZE="2448553472"',
        "6502b8cdbf706d746e32311fdaa39ffc5ca703d76f766806bbb21d3c71278d1f",
        'EXPECTED_PREDECESSOR_SIZE="2447090176"',
        "prepared_image_materials",
        "TARGET_MATERIAL_DRIFT",
        "PREDECESSOR_MATERIAL_DRIFT",
        "TARGET_10_0_PRESENT=false",
    ):
        assert literal in text


def test_u4_install_preflight_classifies_release_and_install_authority_without_refreshing() -> None:
    text = source()
    for literal in (
        "RELEASE_PIN_EXPIRES_AT_UNIX=",
        "RELEASE_PIN_EXPIRED=",
        "RELEASE_AUTHORITY_STATE=ACTIVE_VALID_FOR_INSTALL",
        "RELEASE_AUTHORITY_STATE=REFRESH_REQUIRED",
        "PREPARE_AUTHORITY_STATE=CURRENT_TX_RESIDUE",
        "INSTALL_AUTHORITY_STATE=CURRENT_BINDING",
        "INSTALL_AUTHORITY_STATE=OLD_TERMINAL_SAFE_REPLACEABLE",
    ):
        assert literal in text


def test_u4_install_preflight_reports_exact_file_and_capacity_evidence() -> None:
    text = source()
    for literal in (
        "TX_FILE_SHA256=",
        "RELEASE_PIN_SHA256=",
        "USB_MOUNT=",
        "USB_AVAILABLE_BYTES=",
        "ROOT_AVAILABLE_BYTES=",
        "RESULT=R8V13_07_FRESH_TX_A_U4_INSTALL_READONLY_PREFLIGHT_PASS",
    ):
        assert literal in text
