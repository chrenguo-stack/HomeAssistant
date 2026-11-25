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
        "14980338287",
        "d47d3fc4183805e63431c105682fbd93ed1cdc56b5fdc8681f41277afcd14ed1",
        "c3071a9dcc2a5e54ca6017cfb58d1afad8d715cc47ca0640ae22493472430838",
        "07eefc1e6d87eff464133771191d155fa9ee9d3d",
        "9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa",
        "d7915bc3e42531a829ab22ecb74a7148878c3a2310313e4f1ac07acc8785185e",
        "gh.n3w-t1-ha-recovery-install/1",
        "ARTIFACT_FILE_SET_DRIFT",
        "LOCAL_ARTIFACT_BINDING=PASS",
        "RESULT=R8V13_07_RECOVERY_ARTIFACT_READONLY_DEPLOYMENT_PREFLIGHT_PASS",
    ):
        assert literal in text


def test_recovery_artifact_deployment_preflight_binds_terminal_runtime_and_media() -> None:
    text = source()
    for literal in (
        "d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4",
        '"status": "ROLLED_BACK"',
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
    ):
        assert literal in text
