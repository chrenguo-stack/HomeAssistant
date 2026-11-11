from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT / "tools" / "execution_packages" / "n3w" / "r7a"
    / "kf147_u5_writable_mount_restoration"
)
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
WORKFLOW = ROOT / ".github" / "workflows" / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "U5_WRITABLE_MOUNT_RESTORATION_R8_20261111_01"
)


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_kf147_u5_writable_mount_restoration_test",
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
    assert document["live_execution_authorized"] is False
    assert document["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert document["state_root"].endswith(
        "kf147-u5-writable-mount-restoration-r8-20261111-01"
    )
    live = document["expected_live_entry"]
    assert live["transaction_sha256"] == (
        "dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259"
    )
    assert live["usb_public_fingerprint"] == (
        "e45fba0ad3e9997be2738c7a8f25d5c342ebba66ddbf822b1f6bf6a016c2ed93"
    )
    assert live["recovery_mount_required_options"] == [
        "ro", "nodev", "nosuid", "noexec"
    ]
    assert live["recovery_mount_forbidden_options"] == ["rw"]
    assert live["writable_mount_required_options"] == [
        "rw", "nodev", "nosuid", "noexec"
    ]
    assert live["writable_mount_forbidden_options"] == [
        "ro", "noload", "norecovery"
    ]


def test_executor_and_remote_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<kf147-u5-writable-mount-restoration>", "exec")
    assert module.GATE_ID == GATE


def test_preflight_mode_is_read_only_and_never_claims() -> None:
    namespace = load_remote_namespace()
    namespace["validate_preflight"] = lambda plan: {"baseline": True}
    result = namespace["execute"](
        {"mode": "preflight", "live_execution_authorized": False}
    )
    assert result["status"] == "PASS"
    assert result["read_only"] is True
    assert result["restoration_eligible"] is True
    assert result["authorization_claimed"] is False
    assert result["authorization_consumed"] is False
    assert result["usb_mutation"] is False
    assert result["u5_transition"] is False


def test_execute_is_fail_closed_while_manifest_is_ungranted() -> None:
    namespace = load_remote_namespace()
    namespace["validate_preflight"] = lambda plan: {"baseline": True}
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
        assert str(error) == "restoration_live_execution_not_authorized"
    else:
        raise AssertionError("ungranted execute must fail closed")


def test_mutation_sequence_is_explicit_unmount_then_fresh_rw_mount() -> None:
    source = load_executor().REMOTE_SCRIPT
    unmount = 'run(["umount", target], timeout=60)'
    writable = '"rw,nodev,nosuid,noexec"'
    rollback = '"ro,noload,nodev,nosuid,noexec"'
    assert unmount in source
    assert writable in source
    assert rollback in source
    assert "remount,rw" not in source
    assert source.index(unmount) < source.index(writable)


def test_rollback_is_bounded_and_u5_transition_is_absent() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'result["rollback_attempted"] = True' in source
    assert "automatic_retry" not in source
    assert "usb_disk_descendant_still_mounted" in source
    assert "require_service_namespace=False" in source
    assert "rollback_transaction_changed" in source
    assert "request_install(" not in source
    assert 'run(["systemctl", "restart"' not in source
    assert 'run(["docker", "stop"' not in source
    assert 'run(["docker", "rm"' not in source
    assert 'run(["docker", "load"' not in source


def test_restoration_requires_recovery_and_writable_mount_contracts() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'expected_mode == "recovery"' in source
    assert 'expected_mode == "writable"' in source
    assert '{"noload", "norecovery"} & mount_options' in source
    assert '"usb_writable_mount_contract_invalid:"' in source


def test_target_binding_workflow_covers_restoration_package() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_u5_writable_mount_restoration/**"
    )
    executor_path = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_u5_writable_mount_restoration/executor.py"
    )
    test_path = "tests/tools/test_n3w_t1_kf147_u5_writable_mount_restoration.py"
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor_path) == 1
    assert workflow.count(test_path) == 2
