from __future__ import annotations

import base64
import importlib.util
import json
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u6_predecessor_recovery_r26"
)
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
WORKFLOW = (
    ROOT
    / ".github"
    / "workflows"
    / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
)

GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U6_PREDECESSOR_RECOVERY_R26_20261114_01"
)
CONFIRM = "EXECUTE U6 R26 PREDECESSOR RECOVERY: YES"


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_u6_r26_test", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_granted_bounded_u6_predecessor_gate() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["gate_id"] == GATE
    assert document["authorization_id"] == GATE
    assert document["confirmation"] == CONFIRM
    assert document["live_execution_authorized"] is True
    assert document["authorization_state"] == {
        "granted": True,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }

    contract = document["execution_contract"]
    assert contract["embedded_preflight_read_only"] is True
    assert contract["invoke_existing_product_controller"] is True
    assert contract["source_deployment"] is False
    assert contract["transaction_mutation_on_execute"] is True
    assert contract["usb_mutation_on_execute"] is True
    assert contract["usb_transaction_metadata_mutation_on_execute"] is True
    assert contract["predecessor_recovery_export"] is True
    assert contract["predecessor_recovery_verify"] is True
    assert contract["service_restart"] is False
    assert contract["ha_quiesce"] is False
    assert contract["transaction_authorization_fields_mutated"] is False
    assert contract["u6_transition"] is True
    assert contract["u7_plus"] is False
    assert contract["image_delete"] is False
    assert contract["automatic_retry"] is False
    assert contract["rollback"] is False


def test_manifest_binds_exact_r25_and_u5_prestate() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = document["source_authority"]
    assert authority["r25_granted_head"] == (
        "01dfb390c379764f0f8a4d0da2e92e474e240a9d"
    )
    assert authority["r25_result"] == "U6_R25_SOURCE_ACTIVATION_PASS"

    entry = document["expected_live_entry"]
    assert entry["transaction_id_sha256"] == (
        "ca89774eb4254d0f861cc2aef136eee41e90fd6106559c0fd8d66e3ee00a3738"
    )
    assert entry["transaction_sha256"] == (
        "adfcf60d958c112edf61e2f4e31d73b16229fd027180ed68b87b8953231f0144"
    )
    assert entry["installed_source_sha256"][
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_install.py"
    ] == "9391019fc01004373c16e66a42ac43cd8fc2119c6692448947e6019f1788e530"
    assert entry["installed_source_sha256"][
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_prepare_host.py"
    ] == "0d0c96d7ae2f26c2d2ae8388e6ee75ad0616081a6cdcb98727f2131dab31c30e"


def test_executor_and_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<u6-r26>", "exec")
    assert module.GATE_ID == GATE
    assert module.CONFIRMATION == CONFIRM


def test_embedded_preflight_is_readonly_and_requires_clean_u5() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"U5_INSTALL_REQUESTED_REVALIDATING"' in remote
    assert '"u6_predecessor_residue_present"' in remote
    assert '"r25_claim_invalid"' in remote
    assert '"transaction_mutation": False' in remote
    assert '"usb_mutation": False' in remote
    assert '"service_restart": False' in remote
    assert '"ha_quiesced": False' in remote
    assert '"u6_transition": False' in remote
    assert '"u7_plus": False' in remote


def test_execute_invokes_existing_u6_controller_only() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert "HaUsbU6PredecessorController" in remote
    assert "SubprocessPrepareBackend" in remote
    assert "HaUsbStateStore" in remote
    assert "controller.prepare_or_resume()" in remote
    assert "record_predecessor_recovery_and_ha_quiesced" not in remote
    assert "claim_live_authorization" not in remote
    assert "record_predecessor_capacity_released" not in remote
    assert 'run(["systemctl", "stop"' not in remote
    assert 'run(["systemctl", "restart"' not in remote
    assert '"docker", "image", "rm"' not in remote


def test_success_stops_at_u6_and_preserves_transaction_authorization() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"U6_PREDECESSOR_RECOVERY_PREPARING"' in remote
    assert '"PREDECESSOR_RECOVERY_PREPARING"' in remote
    assert '"u6_post_transaction_invalid"' in remote
    assert 'transaction.get("authorization_claimed") is not False' in remote
    assert 'transaction.get("authorization_consumed") is not False' in remote
    assert '"predecessor_recovery_prepared": False' in remote
    assert 'status="U6_R26_PREDECESSOR_RECOVERY_PASS"' in remote
    assert "u7_plus=True" not in remote
    assert "ha_quiesced=True" not in remote


def test_postclaim_failure_is_consumed_no_replay_without_rollback() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert 'result["status"] = "STOP_PARTIAL"' in remote
    assert '"rollback_required": False' in remote
    assert '"rollback": None' in remote
    assert "authorization_claimed=True" in remote
    assert "authorization_consumed=True" in remote
    assert "replay_permitted=False" in remote


def test_postinvoke_transport_unknown_is_consumed_no_replay() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    assert 'result["remote_execute_invoked"] = True' in source
    assert 'status="STOP_UNKNOWN"' in source
    assert "authorization_claimed=True" in source
    assert "authorization_consumed=True" in source
    assert "replay_permitted=False" in source
    assert '"remote_execute_claim_state_unknown:"' in source


def test_success_requires_same_unit_and_container_identity() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"u6_unit_pid_drift:"' in remote
    assert '"u6_container_identity_drift:"' in remote
    assert '"u6_predecessor_recovery_invalid"' in remote
    assert '"u6_transaction_not_mutated"' in remote
    assert '"U6_R26_PREDECESSOR_RECOVERY_PASS"' in remote


def test_target_binding_workflow_covers_r26() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/u6_predecessor_recovery_r26/**"
    )
    executor = (
        "tools/execution_packages/n3w/r7a/"
        "u6_predecessor_recovery_r26/executor.py"
    )
    test_path = "tests/tools/test_n3w_t1_u6_predecessor_recovery_r26.py"
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor) == 1
    assert workflow.count(test_path) == 2


def test_remote_mode_parses_last_nonempty_json_line() -> None:
    module = load_executor()

    class FakeTransport:
        def run_remote(self, argv, *, timeout, check):
            return SimpleNamespace(
                returncode=0,
                stdout=(
                    "Authorized access only\n"
                    '{"schema":"test","status":"PASS","read_only":true}\n'
                ),
                stderr="",
            )

    completed, result = module.remote_mode(
        FakeTransport(),
        "preflight",
        {"gate_id": GATE},
        timeout=30,
    )
    assert completed.returncode == 0
    assert result["status"] == "PASS"
    assert result["read_only"] is True


def test_remote_mode_rejects_missing_json_result() -> None:
    module = load_executor()

    class FakeTransport:
        def run_remote(self, argv, *, timeout, check):
            return SimpleNamespace(
                returncode=2,
                stdout="Authorized access only\n",
                stderr="remote python failed",
            )

    completed, result = module.remote_mode(
        FakeTransport(),
        "preflight",
        {"gate_id": GATE},
        timeout=30,
    )
    assert completed.returncode == 2
    assert result == {"status": "STOP", "reason": "remote_result_invalid"}


def test_executor_uses_current_ssh_transport_close_epoch_api() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "transport.close_epoch()" in source
    assert "transport.cleanup()" not in source


def test_remote_script_decodes_plan_and_emits_json_before_live_environment() -> None:
    module = load_executor()
    plan = {
        "gate_id": GATE,
        "state_root": "/tmp/n3w-r26-test-state-root-that-must-not-exist",
    }
    payload = base64.b64encode(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    completed = subprocess.run(
        [sys.executable, "-B", "-c", module.REMOTE_SCRIPT, "preflight", payload],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    assert lines
    result = json.loads(lines[-1])
    assert result["status"] == "STOP"
    assert "required_file_invalid" in result["reason"]
    assert "NameError" not in completed.stderr
