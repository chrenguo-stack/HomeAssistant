from __future__ import annotations

import re
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_kf153"
    / "N3W_T1_V1_3_KF153_LIVE_REPAIR_20261124_01.sh"
)


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_live_repair_is_environment_neutral_and_exactly_bound() -> None:
    text = source()
    assert 'N3W_T1_SSH_TARGET required' in text
    assert re.search(
        r"(?<![0-9])(?:10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}|172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})(?![0-9])",
        text,
    ) is None
    for literal in (
        "14902399722",
        "c19280ac1fcbca7ef0de10ba2a24c0e1993898b0de988693ae14cff2c8e63a66",
        "90e83d4c4ce2a25e6c9fbce0245344b8c3ba247a4b5ecc58d4e93c4ceb169877",
        "90ce32ce4b6c329fd38c2771e352d129d6d00a86",
        "d3e844a05571e94ef384aa62fd4763f2d53c253f281cb94f30dd37ca19743b30",
        "5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a",
        "b5b7120b17539d1c4178450793dcf3d6900d0cba46c518132ad76fade8af04a0",
    ):
        assert literal in text


def test_live_repair_mutates_only_recovery_control_plane_and_pyz() -> None:
    text = source()
    assert "systemctl stop n3w-t1-ha-recovery-retry.timer" in text
    assert "systemctl stop n3w-t1-ha-recovery-retry.service" in text
    assert "systemctl stop n3w-t1-ha-ota-ipc.socket" in text
    assert "systemctl stop n3w-t1-ha-ota-ipc.service" in text
    assert "systemctl start n3w-t1-ha-ota-ipc.socket" in text
    assert "systemctl start n3w-t1-ha-recovery-retry.timer" in text
    for forbidden in (
        "systemctl stop n3wfc4-services-activation.service",
        "systemctl restart n3wfc4-services-activation.service",
        "systemctl stop n3wfc4-broker-activation.service",
        "systemctl restart n3wfc4-broker-activation.service",
        "docker image load",
        "docker image rm",
        "docker container rm",
        "docker compose up",
        "docker compose down",
        "--resume-pending",
        "--install-requested",
        "retire-precutover-failure",
        "materialize-candidate",
        "activate-candidate-runtime",
    ):
        assert forbidden not in text
    assert 'atomic_publish "$NEW" "$LIVE"' in text
    assert 'atomic_publish "$OLD" "$LIVE"' in text


def test_live_repair_fail_closed_requiesces_before_rollback() -> None:
    text = source()
    failure = text.split("failure_recovery() {", 1)[1].split("trap failure_recovery EXIT", 1)[0]
    assert 'if [ "$PATCH_PUBLISHED" = true ] && [ -f "$OLD" ]; then' in failure
    assert 'if [ "$CONTROL_QUIESCED" != true ]; then' in failure
    assert failure.index("systemctl stop n3w-t1-ha-recovery-retry.timer") < failure.index('atomic_publish "$OLD" "$LIVE"')
    assert failure.index("systemctl stop n3w-t1-ha-ota-ipc.socket") < failure.index('atomic_publish "$OLD" "$LIVE"')
    assert failure.index('atomic_publish "$OLD" "$LIVE"') < failure.index("restore_control_plane")


def test_live_repair_keeps_terminal_transaction_and_application_runtime_immutable() -> None:
    text = source()
    for literal in (
        '"status":"ROLLED_BACK"',
        '"phase":"U8_RECOVERY_ADMISSION_COMPLETE"',
        '"failure_code":"ha_usb_release_predecessor_container_drift"',
        '"pre_cutover_predecessor_restored":True',
        "DURABLE_TRANSACTION_UNCHANGED=PASS",
        "APPLICATION_RUNTIME_UNCHANGED=PASS",
        "TARGET_10_0_PRESENT=false",
        "RESULT=KF153_LIVE_REPAIR_PASS",
    ):
        assert literal in text
    assert text.count('test "$(sha256sum "$TX_FILE"') >= 3
    assert "runtime_check" in text


def test_live_repair_artifact_is_verified_before_remote_stage() -> None:
    text = source()
    local = text.split("echo PHASE=LOCAL_ARTIFACT_BINDING", 1)[1].split("echo PHASE=REMOTE_STAGE", 1)[0]
    assert 'gh api "repos/$REPO/actions/artifacts/$ARTIFACT_ID/zip"' in local
    assert 'test "$(shasum -a 256 "$ZIP"' in local
    assert 'test "$(shasum -a 256 "$PKG/manifest.json"' in local
    assert 'test "$(shasum -a 256 "$PKG/ha-recovery.pyz"' in local
    assert "MANIFEST_SOURCE_DRIFT" in local
    assert "MANIFEST_PYZ_DRIFT" in local
