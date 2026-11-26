from __future__ import annotations

import re
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8v13_07"
    / "N3W_T1_R8V13_07_U10_LIVE_REPAIR_AND_RECOVER_20261125_01.sh"
)


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_executor_is_environment_neutral_and_exactly_bound_to_physical_preflight() -> None:
    text = source()
    assert 'N3W_T1_SSH_TARGET required' in text
    assert re.search(
        r"(?<![0-9])(?:10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}|172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})(?![0-9])",
        text,
    ) is None
    for literal in (
        "14939405227",
        "9843b55453ba0025cbedae228c20e10da6b45b8284e559d2c8035876d98d42e5",
        "489aa375fda2b0fba76ee4e9bd30ab168ce9ee00feff05ee074af5b656d1eca8",
        "a9b76d77c2a930a21089af7fe0cc814f4db60a9a",
        "5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a",
        "d7915bc3e42531a829ab22ecb74a7148878c3a2310313e4f1ac07acc8785185e",
        "d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4",
        "4c68793fb1909366aa9acee7c06b74f3bac12dfae8681b1c4a6407abd6d2bd44",
        "8f4a73bfa8126f9e4ee993197cece40fddcdf140c994687a391014d627c0e8cc",
        "955f0f69553f8f80639fab630dd23e23aec40d9e84a48f23536712701dbb1d05",
        "67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26",
        "/mnt/n3w-ha-r8-predecessor",
    ):
        assert literal in text


def test_executor_revalidates_the_exact_u10_state_before_mutation() -> None:
    text = source()
    precheck = text.split("echo PHASE=LIVE_REPAIR_PRECHECK", 1)[1].split(
        "echo PHASE=QUIESCE_RECOVERY_CONTROL_PLANE", 1
    )[0]
    for literal in (
        '"status":"ACTIVE"',
        '"phase":"U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED"',
        '"recovery_required":True',
        '"authorization_claimed":True',
        '"authorization_consumed":True',
        '"predecessor_release_observed":True',
        '"target_activation":"BINDING"',
        'GH_HOMEASSISTANT_IMAGE")!="local/n3w-homeassistant:2026.10.0-0c73235a"',
        'GH_N3W_T1_OTA_INSTALLED_VERSION")!="2026.10.0"',
        'test "$(sha256sum "$TX_FILE"',
        'test "$(sha256sum "$ENV"',
    ):
        assert literal in precheck
    assert 'candidate_recovery_check "$NEW"' not in precheck

    post_quiesce = text.split("echo PHASE=POST_QUIESCE_EXACT_RECHECK", 1)[1].split(
        "echo PHASE=ATOMIC_RECOVERY_PYZ_PATCH", 1
    )[0]
    for literal in (
        'test "$(sha256sum "$TX_FILE"',
        'test "$(sha256sum "$ENV"',
        'test "$(sha256sum "$LIVE"',
        'test "$(sha256sum "$NEW"',
        'test "$(docker image inspect "$TARGET_REF"',
        'test "$(docker image inspect "$MANAGER_REF"',
        'test "$(docker image inspect "$BROKER_REF"',
        'candidate_recovery_check "$NEW"',
        'POST_QUIESCE_EXACT_RECHECK=PASS',
    ):
        assert literal in post_quiesce


def test_executor_quiesces_a_timer_racing_retry_worker_before_final_recheck() -> None:
    text = source()
    precheck = text.split("echo PHASE=LIVE_REPAIR_PRECHECK", 1)[1].split(
        "echo PHASE=QUIESCE_RECOVERY_CONTROL_PLANE", 1
    )[0]
    assert 'PRE_QUIESCE_RETRY_SERVICE_STATE=' in precheck
    assert 'RETRY_SERVICE_NOT_QUIET=' not in precheck
    assert 'inactive|failed) ;;' not in precheck
    assert 'systemctl stop n3w-t1-ha-recovery-retry.timer' not in precheck

    quiesce = text.split("echo PHASE=QUIESCE_RECOVERY_CONTROL_PLANE", 1)[1].split(
        "echo PHASE=POST_QUIESCE_EXACT_RECHECK", 1
    )[0]
    assert quiesce.index("systemctl stop n3w-t1-ha-recovery-retry.timer") < quiesce.index(
        "systemctl stop n3w-t1-ha-recovery-retry.service"
    )
    assert 'QUIESCED_RETRY_TIMER_STATE=' in quiesce
    assert 'QUIESCED_RETRY_SERVICE_STATE=' in quiesce


def test_candidate_successor_proves_the_normalized_predecessor_binding_before_publish() -> None:
    text = source()
    check = text.split("candidate_recovery_check() {", 1)[1].split(
        "echo PHASE=LIVE_REPAIR_PRECHECK", 1
    )[0]
    assert "rollback_writers_quiesced" in check
    assert "observe_predecessor_released" in check
    assert "_verify_original_launch(d,allow_target_binding=True)" in check
    assert 'binding != d["predecessor_start"]' in check
    assert "PREDECESSOR_LAUNCH_SHA_DRIFT" in check


def test_executor_mutates_only_recovery_control_plane_then_uses_existing_recovery_owner() -> None:
    text = source()
    assert 'atomic_publish "$NEW" "$LIVE"' in text
    assert "systemctl stop n3w-t1-ha-recovery-retry.timer" in text
    assert "systemctl stop n3w-t1-ha-recovery-retry.service" in text
    assert "systemctl stop n3w-t1-ha-ota-ipc.socket" in text
    assert "systemctl start n3w-t1-ha-recovery-retry.service" in text
    assert text.index('atomic_publish "$NEW" "$LIVE"') < text.index(
        "systemctl start n3w-t1-ha-recovery-retry.service"
    )
    for forbidden in (
        "--install-requested",
        "--issue-install-authority",
        "--maintenance-submit-approved-release",
        "docker image load",
        "docker image rm",
        "docker compose up",
        "docker compose down",
        "mkfs",
        "reboot",
    ):
        assert forbidden not in text


def test_executor_accepts_failed_as_a_quiet_retry_service_after_stop() -> None:
    text = source()
    quiesce = text.split("echo PHASE=QUIESCE_RECOVERY_CONTROL_PLANE", 1)[1].split(
        "echo PHASE=ATOMIC_RECOVERY_PYZ_PATCH", 1
    )[0]
    assert 'RETRY_SERVICE_STATE="$(systemctl is-active n3w-t1-ha-recovery-retry.service || true)"' in quiesce
    assert 'inactive|failed) ;;' in quiesce
    assert 'QUIESCED_RETRY_SERVICE_STATE=' in quiesce
    assert 'QUIESCED_IPC_SOCKET_STATE=' in quiesce
    assert 'QUIESCED_IPC_SERVICE_STATE=' in quiesce
    assert 'test "$RETRY_SERVICE_STATE" = inactive' not in quiesce


def test_executor_preserves_pre_patch_control_plane_state_on_failure() -> None:
    text = source()
    restore = text.split("restore_control_plane() {", 1)[1].split(
        "failure_recovery() {", 1
    )[0]
    assert 'if [ "$RECOVERY_STARTED" = true ]' in restore
    assert 'if [ "$CONTROL_QUIESCED" != true ]' in restore
    assert 'case "$PRE_IPC_SOCKET_STATE" in' in restore
    assert 'case "$PRE_RETRY_TIMER_STATE" in' in restore
    assert 'active|activating) systemctl start n3w-t1-ha-ota-ipc.socket' in restore
    assert 'active|activating) systemctl start n3w-t1-ha-recovery-retry.timer' in restore
    assert 'systemctl stop n3w-t1-ha-recovery-retry.timer' in restore


def test_executor_rolls_back_only_the_pyz_if_recovery_has_not_started() -> None:
    text = source()
    failure = text.split("failure_recovery() {", 1)[1].split(
        "trap failure_recovery EXIT", 1
    )[0]
    assert '[ "$PATCH_PUBLISHED" = true ] && [ "$RECOVERY_STARTED" != true ]' in failure
    assert 'atomic_publish "$OLD" "$LIVE"' in failure
    assert 'echo RECOVERY_STARTED="$RECOVERY_STARTED"' in failure
    assert "restore_control_plane" in failure


def test_executor_requires_terminal_rollback_and_healthy_predecessor() -> None:
    text = source()
    closure = text.split("echo PHASE=VERIFY_TERMINAL_RECOVERY", 1)[1]
    for literal in (
        '"status":"ROLLED_BACK"',
        '"phase":"U13B_ROLLED_BACK"',
        '"recovery_required":False',
        'GH_HOMEASSISTANT_IMAGE")!="local/n3w-homeassistant:2026.10.4-5881590f"',
        'GH_N3W_T1_OTA_INSTALLED_VERSION")!="2026.10.4"',
        'test "$(docker image inspect "$PRED_REF"',
        "TARGET_IMAGE_STILL_PRESENT=true",
        "verify_resident_predecessor_health",
        "TERMINAL_TRANSACTION=PASS",
        "RECOVERED_ENV=PASS",
        "RECOVERED_RUNTIME_HEALTH=PASS",
        "INSTALL_REPLAY=false",
        "SECOND_TRANSACTION=false",
        "RESULT=R8V13_07_U10_LIVE_REPAIR_AND_RECOVERY_PASS",
    ):
        assert literal in closure
