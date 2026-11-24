from __future__ import annotations

import re
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8v13_07"
    / "N3W_T1_R8V13_07_FRESH_TRANSACTION_A_INSTALL_TO_TERMINAL_20261124_01.sh"
)


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_executor_binds_exact_fresh_transaction_and_guarded_recovery() -> None:
    text = source()
    for literal in (
        "d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4",
        "5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a",
        "b72ac2fc-79a0-4fb8-888e-f35b0114f959",
        "e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663",
        "6502b8cdbf706d746e32311fdaa39ffc5ca703d76f766806bbb21d3c71278d1f",
        "local/n3w-homeassistant:2026.10.0-0c73235a",
        "local/n3w-homeassistant:2026.10.4-5881590f",
    ):
        assert literal in text


def test_executor_enters_from_exact_u4_and_never_replays_prepare() -> None:
    text = source()
    assert '"phase":"U4_READY_TO_INSTALL"' in text
    assert "FRESH_TX_A_U4_REBIND=PASS" in text
    assert "--maintenance-submit-approved-release INSTALL" in text
    assert "--maintenance-submit-approved-release PREPARE" not in text
    assert "--issue-prepare-authority" not in text
    assert "OLD_TRANSACTION_REPLAY" not in text


def test_release_pin_refresh_is_expired_only_and_revalidated() -> None:
    text = source()
    for literal in (
        'if pin["expires_at_unix"]<=now:',
        'pin["expires_at_unix"]=now+21600',
        "RELEASE_PIN_REFRESH=PASS",
        "RELEASE_PIN_REFRESH=NOT_REQUIRED",
        "RELEASE_ADMISSION=PASS",
        "LocalApprovedHaRelease",
        "valid_signed_index",
        "read_signed_index",
    ):
        assert literal in text
    assert "manifest_sha256" in text
    assert "predecessor_image_id" in text


def test_install_authority_is_schema_v3_and_product_prefixed() -> None:
    text = source()
    assert "N3W_T1_CORE_UPDATER_R8V13_07_FRESH_TX_A_INSTALL_CUTOVER_20261124_01" in text
    assert "--issue-install-authority" in text
    assert "requested_install_binding_sha256" in text
    assert "gh.n3w-t1-ha-install-authority/3" in text
    assert "FRESH_INSTALL_AUTHORITY=PASS" in text


def test_executor_uses_product_resume_entrypoint_not_private_cutover_actions() -> None:
    text = source()
    assert '/usr/bin/python3 -I "$LIVE" --resume-pending' in text
    for forbidden in (
        r"docker\s+image\s+load",
        r"docker\s+image\s+rm",
        r"docker\s+container\s+rm",
        r"systemctl\s+(?:start|stop|restart)",
        r"\bmkfs\b",
        r"\bumount\b",
        r"rm\s+-rf",
    ):
        assert re.search(forbidden, text) is None


def test_terminal_classification_stops_before_r8v13_08() -> None:
    text = source()
    for literal in (
        "U13A_COMMITTED",
        "U13B_ROLLED_BACK",
        "FRESH_TX_A_INSTALL_RESULT=PASS",
        "FRESH_TX_A_INSTALL_RESULT=ROLLED_BACK",
        "FRESH_TX_A_INSTALL_RESULT=STOPPED_NONTERMINAL",
        "NEXT_BOUNDARY=STOP_BEFORE_R8V13_08",
        "R8V13_08_BLOCKED=true",
        "DO_NOT_REPLAY=true",
    ):
        assert literal in text
    assert "NEXT_TASK=R8V13_08" not in text


def test_executor_has_no_embedded_network_target() -> None:
    text = source()
    assert "N3W_T1_SSH_TARGET" not in text
    assert re.search(
        r"(?<![0-9])(?:10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}|172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})(?![0-9])",
        text,
    ) is None
