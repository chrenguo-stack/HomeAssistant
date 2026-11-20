from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u7_post_reboot_transaction_diagnostic_r27d"
    / "executor.py"
)


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_u7_r27d_test",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_executor_and_remote_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<r27d>", "exec")


def test_diagnostic_is_strictly_readonly() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    remote = load_executor().REMOTE_SCRIPT
    assert "--diagnostic-only" in source
    assert "--execute" not in source
    for token in (
        '["systemctl", "stop"',
        '["systemctl", "start"',
        '["systemctl", "restart"',
        '["docker", "load"',
        '["mount"',
        '["umount"',
        "transaction_store.write",
        "write_text(",
        "write_bytes(",
        "os.replace(",
        "unlink(",
    ):
        assert token not in remote


def test_diagnostic_breaks_out_all_r27_transaction_predicates() -> None:
    remote = load_executor().REMOTE_SCRIPT
    for key in (
        "phase_exact",
        "status_exact",
        "transaction_id_exact",
        "transaction_file_sha256_exact",
        "target_artifact_verified_true",
        "predecessor_recovery_verified_true",
        "ha_data_backup_verified_false",
        "ha_data_backup_identity_absent",
        "authorization_claimed_false",
        "authorization_consumed_false",
        "authorization_id_absent",
        "recovery_required_false",
        "failure_code_absent",
    ):
        assert key in remote
    assert "transaction_all_r27_predicates_pass" in remote


def test_diagnostic_reports_only_whitelisted_transaction_fields() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"password"' not in remote
    assert '"secret"' not in remote
    assert '"private_key"' not in remote
    assert '"raw_serial"' not in remote
    assert "predecessor_identity_canonical_sha256" in remote
    assert "predecessor_recovery_identity" in remote
    assert '"predecessor_recovery_identity": predecessor' not in remote


def test_diagnostic_correlates_transaction_write_with_current_boot() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert "boot_started_unix" in remote
    assert "transaction_mtime_unix" in remote
    assert "transaction_predates_current_boot" in remote


def test_r26_terminal_state_is_readonly_rechecked() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert "authorization_claim.json" in remote
    assert "success.json" in remote
    assert "r26_all_terminal_predicates_pass" in remote
    assert "claim_replay_false" in remote
    assert "success_replay_false" in remote


def test_expected_r26_u6_authority_is_frozen() -> None:
    module = load_executor()
    assert module.EXPECTED_TRANSACTION_SHA256 == (
        "7f406b5b88f7bd5c3161d7527a001ddcb3414a8ec64fb34cdad444c2c3e62ebe"
    )
    assert module.EXPECTED_TRANSACTION_ID_SHA256 == (
        "ca89774eb4254d0f861cc2aef136eee41e90fd6106559c0fd8d66e3ee00a3738"
    )
    assert module.EXPECTED_PHASE == "U6_PREDECESSOR_RECOVERY_PREPARING"
    assert module.EXPECTED_STATUS == "ACTIVE"
