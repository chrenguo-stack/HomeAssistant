from __future__ import annotations

import re
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8v13_07"
    / "N3W_T1_R8V13_07_U10_LIVE_REPAIR_READONLY_PREFLIGHT_20261124_01.sh"
)


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_u10_repair_preflight_is_environment_neutral_and_read_only() -> None:
    text = source()
    assert 'N3W_T1_SSH_TARGET required' in text
    assert re.search(
        r"(?<![0-9])(?:10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}|172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})(?![0-9])",
        text,
    ) is None
    for pattern in (
        r"systemctl\s+(?:start|stop|restart|enable|disable)",
        r"docker\s+(?:rm|rmi|load|pull|compose\s+up|compose\s+down)",
        r"docker\s+image\s+rm",
        r"docker\s+container\s+rm",
        r"\b(?:mv|cp|rm|install)\s+/(?:opt|etc|var)/",
    ):
        assert re.search(pattern, text) is None
    for forbidden in (
        "--install-requested",
        "--resume-pending",
        "maintenance-submit-approved-release",
        "issue-install-authority",
        "materialize-candidate",
        "activate-candidate-runtime",
    ):
        assert forbidden not in text
    assert "LIVE_MUTATION=false" in text
    assert "INSTALL_REPLAY=false" in text


def test_u10_repair_preflight_binds_exact_transaction_and_repair_artifact() -> None:
    text = source()
    for literal in (
        "d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4",
        "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED",
        "6976d68fd1b6828b630fd05751c2855afd84efc65639753f1a318189fff62f50",
        "sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306",
        "5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a",
        "d7915bc3e42531a829ab22ecb74a7148878c3a2310313e4f1ac07acc8785185e",
        "489aa375fda2b0fba76ee4e9bd30ab168ce9ee00feff05ee074af5b656d1eca8",
        "a9b76d77c2a930a21089af7fe0cc814f4db60a9a",
        "14939405227",
        "9843b55453ba0025cbedae228c20e10da6b45b8284e559d2c8035876d98d42e5",
        "RESULT=R8V13_07_U10_LIVE_REPAIR_READONLY_PREFLIGHT_PASS",
    ):
        assert literal in text


def test_u10_repair_preflight_requires_target_binding_and_recovery_owner() -> None:
    text = source()
    for literal in (
        '"status":"ACTIVE"',
        '"phase":"U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED"',
        '"recovery_required":True',
        '"authorization_claimed":True',
        '"authorization_consumed":True',
        '"predecessor_release_observed":True',
        '"target_activation":"BINDING"',
        'GH_HOMEASSISTANT_IMAGE',
        'GH_N3W_T1_OTA_INSTALLED_VERSION',
        '2026.10.0',
        'ROLLBACK_WRITERS_QUIESCED=',
        'n3w-t1-ha-recovery-retry.timer',
        'PREDECESSOR_IMAGE_PRESENT=',
        'TX_FILE_SHA256=',
        'COMPOSE_ENV_SHA256=',
    ):
        assert literal in text
