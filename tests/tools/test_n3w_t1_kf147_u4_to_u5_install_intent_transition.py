from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT / "tools" / "execution_packages" / "n3w" / "r7a"
    / "kf147_u4_to_u5_install_intent_transition"
)
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
WORKFLOW = ROOT / ".github" / "workflows" / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "U4_TO_U5_INSTALL_INTENT_TRANSITION_R9_20261111_01"
)
CONFIRMATION = "EXECUTE KF147 U4 TO U5 INSTALL INTENT TRANSITION R9: YES"


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_kf147_u4_to_u5_install_intent_transition_test",
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


def test_manifest_is_ungranted_and_binds_exact_u4_state() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["gate_id"] == GATE
    assert document["authorization_id"] == GATE
    assert document["confirmation"] == CONFIRMATION
    assert document["live_execution_authorized"] is False
    assert document["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert document["state_root"].endswith(
        "kf147-u4-u5-install-intent-r9-20261111-01"
    )
    live = document["expected_live_entry"]
    assert live["transaction_sha256"] == (
        "dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259"
    )
    assert live["target_release_id"] == "homeassistant-2026.10.4"
    assert live["usb_filesystem_uuid"] == "967cf065-abe5-49ee-8499-7c3f50d2c48f"
    assert live["mount_required_options"] == ["rw", "nodev", "nosuid", "noexec"]
    assert live["mount_forbidden_options"] == ["ro", "noload", "norecovery"]
    contract = document["execution_contract"]
    assert contract["transaction_mutation_on_execute"] is True
    assert contract["u5_transition_on_execute"] is True
    assert contract["u6_plus"] is False
    assert contract["source_deployment"] is False
    assert contract["service_restart"] is False
    assert contract["usb_mutation"] is False
    assert contract["homeassistant_mutation"] is False
    assert contract["manager_mutation"] is False
    assert contract["broker_mutation"] is False
    assert contract["automatic_retry"] is False
    assert contract["rollback_permitted"] is False
    assert document["stop_boundary"] == (
        "STOP_AFTER_U5_INSTALL_INTENT_TRANSITION_BEFORE_U6_PREDECESSOR_RECOVERY"
    )


def test_executor_and_remote_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<kf147-u4-u5-install-intent-transition>", "exec")
    assert module.GATE_ID == GATE
    assert module.CONFIRMATION == CONFIRMATION


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
    assert "start_predecessor_recovery(" not in source
    assert "claim_live_authorization(" not in source
    assert 'run(["systemctl", "restart"' not in source
    assert 'run(["docker", "stop"' not in source
    assert 'run(["docker", "rm"' not in source
    assert 'run(["docker", "load"' not in source
    assert 'run(["umount"' not in source
    assert 'run(["mount"' not in source


def test_execute_claims_before_install_request_and_has_no_rollback() -> None:
    source = load_executor().REMOTE_SCRIPT
    claim = 'durable_json(\n        state_root / "authorization_claim.json"'
    install = "install_response = ipc_install("
    assert claim in source
    assert install in source
    assert source.index(claim) < source.index(install)
    assert "rollback" not in source.lower()


def test_target_binding_workflow_covers_transition_package() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_u4_to_u5_install_intent_transition/**"
    )
    executor_path = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_u4_to_u5_install_intent_transition/executor.py"
    )
    test_path = "tests/tools/test_n3w_t1_kf147_u4_to_u5_install_intent_transition.py"
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor_path) == 1
    assert workflow.count(test_path) == 2
