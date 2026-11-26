from __future__ import annotations

from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8v13_07"
    / "N3W_T1_R8V13_07_RECOVERY_PYZ_REPLACEMENT_20261125_02.py"
)


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_replacement_v2_requires_explicit_gate_and_exact_current_binding() -> None:
    text = source()
    for literal in (
        'APPROVAL_ENV = "N3W_T1_R8V13_07_RECOVERY_PYZ_REPLACEMENT_APPROVED"',
        'EXPECTED_TX_ID = "f6eb053e9eb21b034e98f7651e179194b0b3eed61ce561df978c4743c796467a"',
        'EXPECTED_TX_SHA256 = "4b1cc60e5557b9bc338d3d0469d30aa94c7974c34a0c26dffae5caf9fde4b105"',
        'EXPECTED_OLD_PYZ_SHA256 = "9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa"',
        'EXPECTED_NEW_PYZ_SHA256 = "807110108df6580328e9ecde2ea18321c199b07caab4fb1c087f81d8df1b7cd2"',
        'EXPECTED_NORMALIZED_LAUNCH_SHA256 = "67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26"',
        'EXPECTED_RAW_LAUNCH_SHA256 = "987189ccd61c0784db089b08e51a9ad3ff317372ad8a952dcda7a03a6d844c70"',
        'EXPECTED_AUTHORIZATION_ID_SHA256 = "de25e2d5c8ea8f183a6dca35048f6896c54d3876bea70f6c35afc847819ed136"',
        'STAGE = Path("/tmp/n3w-r8v13-07-recovery-pyz-replacement-20261125-02")',
        'CANDIDATE = STAGE / "new-ha-recovery.pyz"',
        'BACKUP = STAGE / "old-ha-recovery.pyz"',
        '"failure_code": "ha_usb_target_acceptance_evidence_unavailable"',
    ):
        assert literal in text


def test_replacement_v2_uses_published_data_normalized_runtime_contract() -> None:
    text = source()
    for literal in (
        'journal.get("step") != "PUBLISHED"',
        'raw_binding["images"] != expected["images"]',
        'normalized_binding != expected',
        'runtime.verify_published_predecessor_health(document)',
        'EXPECTED_NORMALIZED_LAUNCH_SHA256',
        'EXPECTED_RAW_LAUNCH_SHA256',
    ):
        assert literal in text


def test_replacement_v2_is_narrow_and_has_local_rollback() -> None:
    text = source()
    assert 'LIVE = Path("/opt/n3w-t1-core-updater/ha-recovery.pyz")' in text
    assert 'replacement executor accepts no positional arguments' in text
    assert 'stage_directory_invalid' in text
    assert 'candidate_file_invalid' in text
    assert 'bound_usb_mount_drift' in text
    assert 'atomic_publish(CANDIDATE, LIVE)' in text
    assert 'atomic_publish(backup, LIVE)' in text
    assert 'print("PYZ_ROLLBACK=PASS")' in text
    assert 'run("systemctl", "stop", unit, check=False)' in text
    assert 'run("systemctl", "start", UNITS["timer"])' in text
    for forbidden in (
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


def test_replacement_v2_preserves_terminal_task_boundary() -> None:
    text = source()
    for literal in (
        'print("TERMINAL_TRANSACTION_UNCHANGED=true")',
        'print("TARGET_2026_10_0_PRESENT=false")',
        'print("NEW_TRANSACTION=false")',
        'print("INSTALL_REPLAY=false")',
        'print("R8V13_08_AUTO_ADVANCE=false")',
        'print("RESULT=R8V13_07_RECOVERY_PYZ_REPLACEMENT_PASS")',
    ):
        assert literal in text
