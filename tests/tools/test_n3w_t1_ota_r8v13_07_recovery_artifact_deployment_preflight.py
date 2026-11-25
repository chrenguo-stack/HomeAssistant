from __future__ import annotations

import re
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8v13_07"
    / "N3W_T1_R8V13_07_RECOVERY_ARTIFACT_READONLY_DEPLOYMENT_PREFLIGHT_20261125_01.sh"
)


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_recovery_artifact_deployment_preflight_is_t1_read_only() -> None:
    text = source()
    assert 'N3W_T1_SSH_TARGET required' in text
    assert "T1_MUTATION=false" in text
    assert "INSTALL_REPLAY=false" in text
    assert "SECOND_TRANSACTION=false" in text
    assert "scp " not in text
    assert "rsync " not in text
    for forbidden in (
        "systemctl start",
        "systemctl stop",
        "systemctl restart",
        "systemctl enable",
        "systemctl disable",
        "docker load",
        "docker pull",
        "docker image rm",
        "docker rmi",
        "docker rm",
        "docker compose up",
        "docker compose down",
        "--resume-pending",
        "--install-requested",
        "maintenance-submit-approved-release",
        "issue-install-authority",
        "issue-prepare-authority",
        "materialize-candidate",
        "activate-candidate-runtime",
    ):
        assert forbidden not in text
    assert re.search(r"\b(?:cp|mv|install|rm)\s+/(?:opt|etc|var)/", text) is None


def test_recovery_artifact_deployment_preflight_binds_exact_candidate() -> None:
    text = source()
    for literal in (
        "14997816032",
        "0ed412bfc923755d13b9cbe3ab744f173d4281f9730c4ca1baa490272e96a517",
        "e28e6197c867da322528fbf144a1aa06d56a43b1a9ad91b5ba0ff6af51f96080",
        "29ce1eb341289d0275ab064996a035e5d55ae430",
        "807110108df6580328e9ecde2ea18321c199b07caab4fb1c087f81d8df1b7cd2",
        "9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa",
        "gh.n3w-t1-ha-recovery-install/1",
        "ARTIFACT_FILE_SET_DRIFT",
        "LOCAL_ARTIFACT_BINDING=PASS",
        "RESULT=R8V13_07_RECOVERY_ARTIFACT_READONLY_DEPLOYMENT_PREFLIGHT_PASS",
    ):
        assert literal in text


def test_recovery_artifact_deployment_preflight_binds_terminal_runtime_and_media() -> None:
    text = source()
    for literal in (
        "f6eb053e9eb21b034e98f7651e179194b0b3eed61ce561df978c4743c796467a",
        '"status": "ROLLED_BACK"',
        '"failure_code": "ha_usb_target_acceptance_evidence_unavailable"',
        "de25e2d5c8ea8f183a6dca35048f6896c54d3876bea70f6c35afc847819ed136",
        "4b1cc60e5557b9bc338d3d0469d30aa94c7974c34a0c26dffae5caf9fde4b105",
        '"phase": "U13B_ROLLED_BACK"',
        '"recovery_required": False',
        '"authorization_claimed": True',
        '"authorization_consumed": True',
        "local/n3w-homeassistant:2026.10.4-5881590f",
        "sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365",
        "local/n3w-homeassistant:2026.10.0-0c73235a",
        "sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306",
        "verify_resident_predecessor_health",
        "n3w-t1-ha-recovery-retry.timer",
        "n3w-t1-ha-ota-ipc.socket",
        "b72ac2fc-79a0-4fb8-888e-f35b0114f959",
        "USB_AVAILABLE_BYTES=",
        "ROOT_AVAILABLE_BYTES=",
        "TX_FILE_SHA256=",
        "COMPOSE_ENV_SHA256=",
        "ARTIFACT_DELTA_FROM_LIVE_PYZ_ONLY=true",
        "DEPLOYMENT_ELIGIBLE=true",
    ):
        assert literal in text
