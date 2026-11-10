from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "kf147_usb_confirmation_u1_u4_successor"
)
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"

GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "USB_CONFIRMATION_U1_U4_DESTRUCTIVE_PREPARE_20261110_01"
)


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_kf147_usb_confirmation_u1_u4_successor_test",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_binds_fresh_explicit_user_authorization_once() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert doc["schema"] == "gh.n3w-t1-kf147-usb-confirm-u1-u4-successor/1"
    assert doc["gate_id"] == GATE
    assert doc["authorization_id"] == GATE
    assert doc["live_execution_authorized"] is True
    assert doc["authorization_state"] == {
        "granted": True,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert doc["stop_boundary"] == "STOP_AFTER_U4_READY_TO_INSTALL_BEFORE_U5"


def test_successor_binds_exact_u1_release_candidate_capacity_and_target() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = doc["expected_live_entry"]
    assert live["u1_transaction_sha256"] == (
        "6e1f0b5d262e346674b62ac79bf2ffbc1c63a8dd22379a0a82c952f0e3626b49"
    )
    assert live["transaction_id_sha256"] == (
        "ca89774eb4254d0f861cc2aef136eee41e90fd6106559c0fd8d66e3ee00a3738"
    )
    assert live["release_identity"] == "homeassistant-2026.10.4"
    assert live["baseline_public_fingerprints"] == []
    assert live["usb_candidate_public_fingerprint"] == (
        "e45fba0ad3e9997be2738c7a8f25d5c342ebba66ddbf822b1f6bf6a016c2ed93"
    )
    assert live["usb_candidate_model"] == "Extreme"
    assert live["usb_candidate_capacity_bytes"] == 32017047552
    assert live["usb_required_bytes"] == 4861841375
    assert live["recommended_nominal_usb_gb"] == 32
    assert live["target_image_ref"] == (
        "local/n3w-homeassistant:2026.10.4-5881590f"
    )
    assert live["target_archive_sha256"] == (
        "eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973"
    )
    assert live["target_archive_size_bytes"] == 835309535


def test_execution_contract_is_u1_to_u4_only_and_has_no_automatic_replay() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contract = doc["execution_contract"]
    assert contract["preflight_read_only"] is True
    assert contract["destructive_submit_action"] == "CONFIRM_USB_ERASE"
    assert (
        contract["product_host_revalidates_candidate_after_authorization_claim"]
        is True
    )
    assert contract["prepare_confirmation_consumed_before_physical_format"] is True
    assert contract["usb_wipe_partition_format"] is True
    assert contract["target_download_to_usb"] is True
    assert contract["success_phase"] == "U4_READY_TO_INSTALL"
    assert contract["success_public_phase"] == "READY_TO_INSTALL"
    assert contract["homeassistant_runtime_mutation"] is False
    assert contract["manager_runtime_mutation"] is False
    assert contract["broker_runtime_mutation"] is False
    assert contract["u5_plus"] is False
    assert contract["automatic_retry"] is False
    assert contract["automatic_rollback"] is False
    assert contract["board_access"] is False
    assert contract["merge"] is False
    assert doc["failure_contract"]["same_authorization_replay"] is False


def test_executor_and_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_EXECUTE_SCRIPT, "<kf147-u1-u4-remote>", "exec")
    assert module.GATE_ID == GATE
    assert module.CONFIRMATION == (
        "EXECUTE KF147 USB CONFIRMATION U1 TO U4 DESTRUCTIVE PREPARE: YES"
    )


def test_executor_never_runs_raw_block_device_mutation_commands() -> None:
    module = load_executor()
    source = module.REMOTE_EXECUTE_SCRIPT
    for token in (
        '"wipefs"',
        '"sfdisk"',
        '"mkfs.ext4"',
        '"parted"',
        '["systemctl", "stop"',
        '["systemctl", "start"',
        '["systemctl", "restart"',
        '"docker load"',
        '"docker rm"',
    ):
        assert token not in source
    assert '"action": "CONFIRM_USB_ERASE"' in source
    assert '"operation": "submit"' in source


def test_authorization_is_claimed_before_product_destructive_submit() -> None:
    module = load_executor()
    source = module.REMOTE_EXECUTE_SCRIPT
    execute = source.index("def execute(plan, authorization, confirmation):")
    claim = source.index('state_root / "authorization_claim.json"', execute)
    postclaim = source.index("postclaim = critical(plan)", claim)
    submit = source.index('"action": "CONFIRM_USB_ERASE"', postclaim)
    assert execute < claim < postclaim < submit


def test_failure_contract_has_no_automatic_retry_or_rollback() -> None:
    module = load_executor()
    source = module.REMOTE_EXECUTE_SCRIPT
    assert '"automatic_retry": False' in source
    assert '"rollback_attempted": False' in source
    assert '"manual_recovery_required": False' in source
    assert "systemctl" not in source
    assert "resume_prepare" not in source


def test_success_requires_u4_exact_usb_artifact_and_container_continuity() -> None:
    module = load_executor()
    source = module.REMOTE_EXECUTE_SCRIPT
    assert 'U4 = "U4_READY_TO_INSTALL"' in source
    assert 'status.get("phase") != "READY_TO_INSTALL"' in source
    assert '"target_artifact_verified") is not True' in source
    assert '"usb_capacity_verified") is not True' in source
    assert "u4_target_artifact_sha_drift" in source
    assert "u4_target_artifact_size_drift" in source
    assert "container_continuity_failed:" in source
    assert '"authorization_claimed") is not False' in source
    assert '"authorization_consumed") is not False' in source


def test_preflight_reuses_repaired_readonly_authority() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert doc["inherited_readonly_authority"] == {
        "tools/execution_packages/n3w/r7a/"
        "kf147_usb_u2_readonly_baseline/executor.py": (
            "21a813dcfd45c256684779c04facfab7513016f9"
        ),
        "tools/execution_packages/n3w/r7a/"
        "kf147_usb_u2_readonly_baseline/manifest.json": (
            "c1984de43f85d3517fac626db58c560d242718ae"
        ),
        "tools/n3w_t1_ssh_transport.py": (
            "5bc28b30e696bd3d0f5ae4c98fd81b8f8679aaa7"
        ),
    }


def test_execute_runs_fresh_readonly_preflight_before_authorization_and_destructive_path() -> None:
    module = load_executor()
    source = EXECUTOR.read_text(encoding="utf-8")
    execute_start = source.index("def execute(args: argparse.Namespace)")
    fresh_preflight = source.index("readonly.run_remote(", execute_start)
    validate = source.index("validate_baseline(baseline, manifest)", fresh_preflight)
    state_root = source.index(
        "check_state_root_absent(transport, manifest[\"state_root\"])",
        validate,
    )
    authorization = source.index(
        'manifest.get("live_execution_authorized") is not True',
        state_root,
    )
    live_execute = source.index('result["live_execute_invoked"] = True', authorization)
    remote_execute = source.index("run_remote_execute(", live_execute)
    assert (
        execute_start
        < fresh_preflight
        < validate
        < state_root
        < authorization
        < live_execute
        < remote_execute
    )
    assert module.GATE_ID == GATE
