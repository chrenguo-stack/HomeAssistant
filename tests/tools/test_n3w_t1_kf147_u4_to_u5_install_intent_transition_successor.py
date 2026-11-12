from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT / "tools" / "execution_packages" / "n3w" / "r7a"
    / "kf147_u4_to_u5_install_intent_transition_successor"
)
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
WORKFLOW = ROOT / ".github" / "workflows" / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "U4_TO_U5_INSTALL_INTENT_TRANSITION_R11_20261112_01"
)
CONFIRMATION = "EXECUTE KF147 U4 TO U5 INSTALL INTENT TRANSITION R11: YES"


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_kf147_u4_to_u5_install_intent_transition_successor_test",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_remote_namespace():
    source = load_executor().REMOTE_SCRIPT
    trailer = "\n\nraise SystemExit(main())\n"
    assert source.endswith(trailer)
    namespace = {}
    exec(source[: -len(trailer)], namespace)
    return namespace


def test_manifest_is_authorized_once_and_binds_r10_u4_state() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["gate_id"] == GATE
    assert document["authorization_id"] == GATE
    assert document["confirmation"] == CONFIRMATION
    assert document["live_execution_authorized"] is True
    assert document["authorization_state"] == {
        "granted": True,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert document["predecessor_terminal"] == {
        "gate": "R10_U5_SOURCE_ACTIVATION",
        "state_root": (
            "/var/lib/n3w-t1-core-updater/"
            "kf147-u5-source-activation-r10-20261111-01"
        ),
        "expected_status": "U5_SOURCE_ACTIVATION_PASS",
        "authorization_consumed": True,
        "replay_permitted": False,
        "u4_preserved": True,
    }
    assert document["state_root"].endswith(
        "kf147-u4-u5-install-intent-r11-20261112-01"
    )
    live = document["expected_live_entry"]
    assert live["r10_state_root"] == document["predecessor_terminal"]["state_root"]
    assert live["transaction_sha256"] == (
        "dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259"
    )
    assert live["target_release_id"] == "homeassistant-2026.10.4"
    assert live["usb_filesystem_uuid"] == "967cf065-abe5-49ee-8499-7c3f50d2c48f"
    assert live["mount_required_options"] == ["rw", "nodev", "nosuid", "noexec"]
    assert live["mount_forbidden_options"] == ["ro", "noload", "norecovery"]
    assert live["installed_source_sha256"] == {
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_prepare.py":
            "4dc6226ae493f18b3dab2c8773c1d3687a8f5f1750a6b4d9fa791cebe22db596",
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_prepare_host.py":
            "d7f1e5468e24446f3ade0e22778cebecc8cda0fed07179a8fccb55b9f7e4ff8a",
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_ipc.py":
            "a7d335c597771b0297f690d0e97fb3288f5f1c83fd670d8af00d76ca983e56ac",
    }
    runtime_blobs = live["installed_runtime_git_blob_sha1"]
    assert runtime_blobs[
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_usb.py"
    ] == "495dc29d7d4850cd485a07b739199a282446477f"
    assert runtime_blobs[
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_usb_state.py"
    ] == "64cfcab9d1c62acd28ef4abeb161b88f8a63d2bc"
    assert runtime_blobs[
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_daemon.py"
    ] == "98c879f65840c237e7ee8855412806e346d880f5"
    assert len(runtime_blobs) == 10
    contract = document["execution_contract"]
    assert contract["transaction_mutation_on_execute"] is True
    assert contract["u5_transition_on_execute"] is True
    assert contract["u6_plus"] is False
    assert contract["source_deployment"] is False
    assert contract["service_restart"] is False
    assert contract["usb_mutation_on_preflight"] is False
    assert contract["usb_mutation_on_execute"] is True
    assert contract["usb_transaction_metadata_write_on_execute"] is True
    assert contract["target_archive_mutation"] is False
    assert contract["split_state_fail_closed"] is True
    assert contract["homeassistant_mutation"] is False
    assert contract["manager_mutation"] is False
    assert contract["broker_mutation"] is False
    assert contract["automatic_retry"] is False
    assert contract["rollback_permitted"] is False
    assert document["stop_boundary"] == (
        "STOP_AFTER_U5_INSTALL_INTENT_TRANSITION_BEFORE_U6_PREDECESSOR_RECOVERY"
    )


def test_r10_terminal_state_is_required_as_successor_prestate() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'r10_root = Path(plan["r10_state_root"])' in source
    assert 'terminal.get("status") != "U5_SOURCE_ACTIVATION_PASS"' in source
    assert 'terminal.get("source_activated") is not True' in source
    assert 'terminal.get("u4_preserved") is not True' in source
    assert 'terminal.get("rollback_required") is not False' in source
    assert 'terminal.get("transaction_mutation") is not False' in source
    assert 'terminal.get("usb_mutation") is not False' in source
    assert 'terminal.get("u5_transition") is not False' in source
    assert 'terminal.get("u6_plus") is not False' in source
    assert 'raise Stop("r10_terminal_state_invalid")' in source


def test_executor_and_remote_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<kf147-u4-u5-install-intent-transition>", "exec")
    assert module.GATE_ID == GATE
    assert module.CONFIRMATION == CONFIRMATION


def test_execute_requires_granted_unclaimed_unconsumed_nonreplayable_authorization() -> None:
    source = load_executor().REMOTE_SCRIPT
    execute_start = source.index("def execute(plan):")
    execute_body = source[execute_start:]
    assert 'plan.get("live_execution_authorized") is not True' in execute_body
    assert '"granted": True' in execute_body
    assert '"claimed": False' in execute_body
    assert '"consumed": False' in execute_body
    assert '"replay_permitted": False' in execute_body
    assert 'plan.get("authorization") != plan.get("authorization_id")' in execute_body
    assert 'plan.get("confirmation") != plan.get("expected_confirmation")' in execute_body


def test_preflight_mode_is_read_only_and_does_not_claim() -> None:
    namespace = load_remote_namespace()
    namespace["validate_u4"] = lambda plan: {"baseline": True}
    result = namespace["execute"](
        {"mode": "preflight", "live_execution_authorized": False}
    )
    assert result["status"] == "PASS"
    assert result["read_only"] is True
    assert result["u5_transition_eligible"] is True
    assert result["authorization_claimed"] is False
    assert result["authorization_consumed"] is False
    assert result["transaction_mutation"] is False
    assert result["usb_mutation"] is False
    assert result["usb_transaction_metadata_mutation"] is False
    assert result["u5_transition"] is False
    assert result["u6_plus"] is False


def test_execute_fails_closed_while_manifest_is_ungranted() -> None:
    namespace = load_remote_namespace()
    namespace["validate_u4"] = lambda plan: {"baseline": True}
    stop_type = namespace["Stop"]
    try:
        namespace["execute"](
            {
                "mode": "execute",
                "live_execution_authorized": False,
                "authorization_state": {
                    "granted": False,
                    "claimed": False,
                    "consumed": False,
                    "replay_permitted": False,
                },
            }
        )
    except stop_type as error:
        assert str(error) == "u5_transition_live_execution_not_authorized"
    else:
        raise AssertionError("ungranted U5 transition must fail closed")


def test_remote_transition_is_bounded_to_install_intent_only() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert '"action": "INSTALL"' in source
    assert '"target_release_id": release_id' in source
    assert '"U4_READY_TO_INSTALL"' in source
    assert '"U5_INSTALL_REQUESTED_REVALIDATING"' in source
    assert '"INSTALL_REQUESTED_REVALIDATING"' in source
    assert "git_blob_sha1" in source
    assert "usb_transaction_metadata_view" in source
    assert "usb_transaction_phase_observed" in source
    assert "split_state_detected" in source
    assert "start_predecessor_recovery(" not in source
    assert "claim_live_authorization(" not in source
    assert 'run(["systemctl", "restart"' not in source
    assert 'run(["docker", "stop"' not in source
    assert 'run(["docker", "rm"' not in source
    assert 'run(["docker", "load"' not in source
    assert 'run(["umount"' not in source
    assert 'run(["mount"' not in source


def test_execute_claims_before_install_request_and_has_no_rollback_action() -> None:
    source = load_executor().REMOTE_SCRIPT
    claim = 'durable_json(\n        state_root / "authorization_claim.json"'
    install = "install_response = ipc_install("
    assert claim in source
    assert install in source
    assert source.index(claim) < source.index(install)
    assert 'terminal.get("rollback_required") is not False' in source
    assert source.lower().count("rollback") == 1


def test_authorized_execute_marks_usb_metadata_mutation_and_stops_at_u5(
    tmp_path: Path,
    monkeypatch,
) -> None:
    namespace = load_remote_namespace()
    baseline = {
        "containers": {
            "manager": {"container_id": "manager-id"},
        },
        "usb_transaction_metadata": {
            "manifest_sha256": "a" * 64,
            "phase_sha256": "b" * 64,
            "checksums_sha256": "c" * 64,
        },
    }
    namespace["validate_u4"] = lambda plan: baseline
    namespace["ipc_install"] = lambda manager_id, release_id: {
        "accepted": True,
        "phase": "INSTALL_REQUESTED_REVALIDATING",
    }
    namespace["validate_u5"] = lambda plan, before: {
        "transaction_phase": "U5_INSTALL_REQUESTED_REVALIDATING",
    }
    monkeypatch.setattr(namespace["os"], "chown", lambda *args: None)

    result = namespace["execute"](
        {
            "mode": "execute",
            "live_execution_authorized": True,
            "authorization_state": {
                "granted": True,
                "claimed": False,
                "consumed": False,
                "replay_permitted": False,
            },
            "authorization": GATE,
            "authorization_id": GATE,
            "confirmation": CONFIRMATION,
            "expected_confirmation": CONFIRMATION,
            "state_root": str(tmp_path / "state"),
            "transaction_id_sha256": "1" * 64,
            "usb_filesystem_uuid": "uuid",
            "target_release_id": "homeassistant-2026.10.4",
        }
    )
    assert result["status"] == "U5_INSTALL_INTENT_TRANSITION_PASS"
    assert result["authorization_claimed"] is True
    assert result["authorization_consumed"] is True
    assert result["transaction_mutation"] is True
    assert result["usb_mutation"] is True
    assert result["usb_transaction_metadata_mutation"] is True
    assert result["u5_transition"] is True
    assert result["u6_plus"] is False
    assert result["split_state_detected"] is False


def test_execute_failure_detects_usb_u5_host_u4_split(
    tmp_path: Path,
    monkeypatch,
) -> None:
    namespace = load_remote_namespace()
    namespace["validate_u4"] = lambda plan: {
        "containers": {"manager": {"container_id": "manager-id"}},
    }
    stop_type = namespace["Stop"]

    def fail_install(manager_id, release_id):
        raise stop_type("synthetic_ipc_response_loss")

    namespace["ipc_install"] = fail_install
    namespace["read_object"] = lambda path: {"phase": "U4_READY_TO_INSTALL"}
    namespace["usb_transaction_phase_observed"] = (
        lambda plan: "U5_INSTALL_REQUESTED_REVALIDATING"
    )
    monkeypatch.setattr(namespace["os"], "chown", lambda *args: None)

    result = namespace["execute"](
        {
            "mode": "execute",
            "live_execution_authorized": True,
            "authorization_state": {
                "granted": True,
                "claimed": False,
                "consumed": False,
                "replay_permitted": False,
            },
            "authorization": GATE,
            "authorization_id": GATE,
            "confirmation": CONFIRMATION,
            "expected_confirmation": CONFIRMATION,
            "state_root": str(tmp_path / "state"),
            "transaction_id_sha256": "1" * 64,
            "usb_filesystem_uuid": "uuid",
            "target_release_id": "homeassistant-2026.10.4",
        }
    )
    assert result["status"] == "STOP"
    assert result["authorization_claimed"] is True
    assert result["authorization_consumed"] is True
    assert result["transaction_mutation"] is False
    assert result["usb_mutation"] is True
    assert result["usb_transaction_metadata_mutation"] is True
    assert result["observed_transaction_phase"] == "U4_READY_TO_INSTALL"
    assert result["observed_usb_transaction_phase"] == (
        "U5_INSTALL_REQUESTED_REVALIDATING"
    )
    assert result["split_state_detected"] is True
    assert result["u6_plus"] is False


def test_local_wrapper_propagates_failure_mutation_and_split_state_evidence() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    block_start = source.index('if completed.returncode != 0 or remote.get("status") not in {')
    block_end = source.index("        else:\n            result.update(remote)", block_start)
    block = source[block_start:block_end]
    for key in (
        "authorization_claimed",
        "authorization_consumed",
        "transaction_mutation",
        "host_state_mutation",
        "host_source_mutation",
        "usb_mutation",
        "usb_transaction_metadata_mutation",
        "split_state_detected",
        "service_restart",
        "homeassistant_mutation",
        "manager_mutation",
        "broker_mutation",
        "u5_transition",
        "u6_plus",
        "board_access",
        "merge",
    ):
        assert f'"{key}"' in block


def test_target_binding_workflow_covers_transition_package() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_u4_to_u5_install_intent_transition_successor/**"
    )
    executor_path = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_u4_to_u5_install_intent_transition_successor/executor.py"
    )
    test_path = "tests/tools/test_n3w_t1_kf147_u4_to_u5_install_intent_transition_successor.py"
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor_path) == 1
    assert workflow.count(test_path) == 2
