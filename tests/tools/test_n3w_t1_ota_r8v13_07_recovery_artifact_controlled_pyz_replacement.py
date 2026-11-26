from __future__ import annotations

import re
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8v13_07"
    / "N3W_T1_R8V13_07_RECOVERY_ARTIFACT_CONTROLLED_PYZ_REPLACEMENT_20261125_01.sh"
)


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_controlled_pyz_replacement_requires_explicit_gate_and_exact_artifacts() -> None:
    text = source()
    for literal in (
        'N3W_T1_R8V13_07_RECOVERY_PYZ_REPLACEMENT_APPROVED',
        '14939405227',
        '9843b55453ba0025cbedae228c20e10da6b45b8284e559d2c8035876d98d42e5',
        'd7915bc3e42531a829ab22ecb74a7148878c3a2310313e4f1ac07acc8785185e',
        '14980338287',
        'd47d3fc4183805e63431c105682fbd93ed1cdc56b5fdc8681f41277afcd14ed1',
        '9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa',
        '795c89ce2a7b10246da381ed205e7bf3f77c2561197d1d6a6e4ac2fb9e332eed',
        'd139286ebd1379af96851321755a78c8cee795edb64f93ec7b74f2bb1e152d4b',
        '67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26',
    ):
        assert literal in text


def test_controlled_pyz_replacement_proves_only_pyz_changed() -> None:
    text = source()
    for literal in (
        'changed != ["ha-recovery.pyz"]',
        'NON_PYZ_PAYLOAD_DRIFT',
        'CHANGED_PAYLOADS=ha-recovery.pyz',
        'ARTIFACT_DELTA_BINDING=PASS',
    ):
        assert literal in text


def test_controlled_pyz_replacement_has_narrow_mutation_and_rollback() -> None:
    text = source()
    assert 'scp -q "$NEW_PYZ"' in text
    assert 'atomic_publish "$NEW" "$LIVE"' in text
    assert 'atomic_publish "$OLD" "$LIVE"' in text
    assert 'PYZ_ROLLBACK=PASS' in text
    assert 'systemctl stop n3w-t1-ha-recovery-retry.timer' in text
    assert 'systemctl stop n3w-t1-ha-ota-ipc.socket' in text
    assert 'systemctl start n3w-t1-ha-recovery-retry.timer' in text
    assert 'systemctl start n3w-t1-ha-ota-ipc.socket' in text
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
    assert re.search(r"\b(?:rm|mv|cp)\s+/(?:etc|var)/", text) is None


def test_controlled_pyz_replacement_preserves_terminal_runtime_and_task_boundary() -> None:
    text = source()
    for literal in (
        '"status": "ROLLED_BACK"',
        '"phase": "U13B_ROLLED_BACK"',
        '"recovery_required": False',
        '"authorization_claimed": True',
        '"authorization_consumed": True',
        'verify_resident_predecessor_health',
        'TARGET_2026_10_0_PRESENT=false',
        'TERMINAL_TRANSACTION_UNCHANGED=true',
        'NEW_TRANSACTION=false',
        'INSTALL_REPLAY=false',
        'R8V13_08_AUTO_ADVANCE=false',
        'RESULT=R8V13_07_RECOVERY_ARTIFACT_CONTROLLED_PYZ_REPLACEMENT_PASS',
    ):
        assert literal in text
