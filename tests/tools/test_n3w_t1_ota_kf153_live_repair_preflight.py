from __future__ import annotations

import re
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_kf153"
    / "N3W_T1_V1_3_KF153_LIVE_REPAIR_READONLY_PREFLIGHT_20261124_01.sh"
)


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_preflight_is_environment_neutral_and_read_only() -> None:
    text = source()
    assert 'N3W_T1_SSH_TARGET required' in text
    assert re.search(r"(?<![0-9])(?:10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}|172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})(?![0-9])", text) is None
    forbidden = (
        r"systemctl\s+(?:start|stop|restart|enable|disable)",
        r"docker\s+(?:rm|rmi|load|pull|compose\s+up|compose\s+down)",
        r"docker\s+image\s+rm",
        r"docker\s+container\s+rm",
        r"\b(?:mv|cp|rm|install)\s+/(?:opt|etc|var)/",
    )
    assert all(re.search(pattern, text) is None for pattern in forbidden)
    assert "LIVE_MUTATION=false" in text
    assert "RESULT=KF153_LIVE_REPAIR_READONLY_PREFLIGHT_PASS" in text


def test_preflight_binds_exact_terminal_transaction_and_recovery_successor() -> None:
    text = source()
    for literal in (
        "b5b7120b17539d1c4178450793dcf3d6900d0cba46c518132ad76fade8af04a0",
        "afbfeeb85c3ab579b62d86d347f76b7f6ee7f203b068eac028be1d18761950c3",
        "d3e844a05571e94ef384aa62fd4763f2d53c253f281cb94f30dd37ca19743b30",
        "5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a",
        "90e83d4c4ce2a25e6c9fbce0245344b8c3ba247a4b5ecc58d4e93c4ceb169877",
        "90ce32ce4b6c329fd38c2771e352d129d6d00a86",
        '"status":"ROLLED_BACK"',
        '"phase":"U8_RECOVERY_ADMISSION_COMPLETE"',
        '"failure_code":"ha_usb_release_predecessor_container_drift"',
        '"pre_cutover_predecessor_restored":True',
    ):
        assert literal in text
    assert 'test "$LIVE_SHA" = "$EXPECTED_OLD_PYZ_SHA256"' in text
    assert 'test "$LIVE_SHA" != "$EXPECTED_NEW_PYZ_SHA256"' in text


def test_preflight_requires_exact_runtime_and_all_non_pyz_successor_payloads() -> None:
    text = source()
    for literal in (
        "local/n3w-homeassistant:2026.10.4-5881590f",
        "sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365",
        "local/greenhouse-manager:fresh-1cae18039eee",
        "sha256:c4bcb441de0554ebb20e3feb2b98a65cc435750539a2c951eb7be710ff191221",
        "local/n3w-mosquitto:2.1.2-3184566d",
        "sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563",
        "c6381d8cfa39ffb1fa82ef0bce7705cf7ff80f45ec2144a507cdfc5f69e2b9bd",
        "97c26f3c46977fd0e3954dfbed3e87bdbedbe8c023bf897c2ebe3fa01460f003",
        "dabda554722edbc46fe98535e24591c3d0cd92f6a30a2800fff4a03a14b7d424",
        "94347a2d183fa5ba2a0c3570f48f812f2cd686fecc4d966cc2f904df004b2d1a",
        "101ae89088bf5749e3ec97e853e5c994f2622ac3b72826aba65d89c52a3c4538",
        "3fe49568640fcd84b53e0b20b1c225b678855fbd28993adabab0fb9048cd5c49",
        "581ed80caa6a503e3a0c328963c15ea6a6e89594feac2ce9f2fa4c9e153a200a",
        "98aa71efe365c5ca87cbe52a587a2e156bb53d41ae9bc9162744028149650b41",
        "ad0f033d9c9df54e82b95053c222aa01e42daffcaf4ef103a12f65773ca25058",
        "56122da602fb46af0b3fba6b839dab9cd7ac54905b163a6ed18e124fc14910e2",
        "NON_PYZ_SUCCESSOR_PARITY=PASS",
    ):
        assert literal in text


def test_preflight_never_replays_install_or_recovery_actions() -> None:
    text = source()
    for forbidden in (
        "--install-requested",
        "--resume-pending",
        "retire-precutover-failure",
        "activate-candidate-runtime",
        "materialize-candidate",
        "ha-install-authority",
        "docker image load",
    ):
        assert forbidden not in text
