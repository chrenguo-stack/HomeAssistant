from __future__ import annotations

import re
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8v13_07"
    / "N3W_T1_R8V13_07_FRESH_REACCEPTANCE_READONLY_REBIND_20261124_04.sh"
)


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_rebind_is_environment_neutral_and_has_no_persistent_mutation_commands() -> None:
    text = source()
    assert "N3W_T1_SSH_TARGET required" in text
    assert re.search(
        r"(?<![0-9])(?:10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}|172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})(?![0-9])",
        text,
    ) is None
    for forbidden in (
        r"systemctl\s+(?:start|stop|restart|enable|disable)",
        r"docker\s+(?:rm|rmi|load|pull)",
        r"docker\s+image\s+(?:rm|load|pull)",
        r"docker\s+compose\s+(?:up|down|restart)",
        r"\bmount\s+",
        r"\bumount\s+",
        r"\bmkfs\b",
        r"\b(?:rm|mv|cp|install)\s+/(?:opt|etc|var|mnt)/",
        "--resume-pending",
        "--install-requested",
        "retire-precutover-failure",
        "materialize-candidate",
        "activate-candidate-runtime",
    ):
        assert re.search(forbidden, text) is None
    assert "PERSISTENT_CONFIGURATION_MUTATION=false" in text


def test_rebind_binds_guarded_kf153_live_state() -> None:
    text = source()
    for literal in (
        "b5b7120b17539d1c4178450793dcf3d6900d0cba46c518132ad76fade8af04a0",
        "afbfeeb85c3ab579b62d86d347f76b7f6ee7f203b068eac028be1d18761950c3",
        "5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a",
        "b72ac2fc-79a0-4fb8-888e-f35b0114f959",
        "67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26",
        "local/n3w-homeassistant:2026.10.4-5881590f",
        "sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365",
        "local/greenhouse-manager:fresh-1cae18039eee",
        "sha256:c4bcb441de0554ebb20e3feb2b98a65cc435750539a2c951eb7be710ff191221",
        "local/n3w-mosquitto:2.1.2-3184566d",
        "sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563",
    ):
        assert literal in text


def test_rebind_proves_old_transaction_terminal_and_target_absent() -> None:
    text = source()
    for literal in (
        '"status": "ROLLED_BACK"',
        '"phase": "U8_RECOVERY_ADMISSION_COMPLETE"',
        '"failure_code": "ha_usb_release_predecessor_container_drift"',
        '"pre_cutover_predecessor_restored": True',
        "OLD_TRANSACTION_TERMINAL_NO_REPLAY=PASS",
        "TARGET_10_0_PRESENT=false",
        "OLD_TRANSACTION_REPLAY=false",
    ):
        assert literal in text


def test_rebind_checks_control_plane_authorities_usb_capacity_and_business_health() -> None:
    text = source()
    for literal in (
        "n3w-t1-ha-recovery-retry.timer",
        "n3w-t1-ha-ota-ipc.socket",
        "ha-prepare-authority.json",
        "ha-install-authority.json",
        "ha-release-pin.json",
        "approved-homeassistant.json",
        "BOUND_USB_PRESENT=PASS",
        "ROOT_AVAILABLE_BYTES=",
        "MANAGER_BROKER_HA_SELF_TEST=PASS",
        "candidate_manager_monitoring_self_test_available",
        "run_monitoring_self_test",
    ):
        assert literal in text


def test_rebind_has_single_success_terminal_marker() -> None:
    text = source()
    marker = "RESULT=R8V13_07_FRESH_REACCEPTANCE_READONLY_REBIND_PASS"
    assert text.count(marker) == 1
