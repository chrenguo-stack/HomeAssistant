from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
EXECUTOR_PATH = (
    ROOT
    / "tools/execution_packages/n3w/r7a/host_a1_live_activation/executor.py"
)
MANIFEST_PATH = EXECUTOR_PATH.with_name("manifest.json")


def load_executor():
    spec = importlib.util.spec_from_file_location("r7a_a1_executor", EXECUTOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_is_source_only_and_stops_before_live_a1() -> None:
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert document["schema"] == "gh.n3w-t1-r7a-host-a1-live-activation-package/1"
    assert document["live_execution_authorized"] is False
    contract = document["execution_contract"]
    assert contract["host_daemon_install"] is True
    assert contract["compose_overlay_install"] is True
    assert contract["services_owner_restart_maximum"] == 1
    assert contract["broker_restart"] is False
    assert contract["usb_mutation"] is False
    assert contract["prepare_intent"] is False
    assert contract["confirm_usb_erase"] is False
    assert contract["u2_plus"] is False
    assert contract["manager_image_rollback"] is False
    assert contract["second_activation"] is False


def test_source_authority_matches_exact_git_blobs() -> None:
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for path, expected in document["source_authority"].items():
        observed = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", f"HEAD:{path}"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        assert observed == expected


def test_live_gate_rejects_until_separate_a1_authorization() -> None:
    executor = load_executor()
    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    with pytest.raises(executor.StopExecution, match="live_execution_not_authorized"):
        executor.validate_local_source(head, require_live=True)


@pytest.mark.parametrize(
    ("image", "expected"),
    [
        ("local/n3w-homeassistant:2026.10.0-0c73235a", "2026.10.0"),
        ("local/n3w-homeassistant:2026.10.4-5881590f", "2026.10.4"),
    ],
)
def test_activation_env_version_is_derived_from_host_image(
    image: str,
    expected: str,
) -> None:
    executor = load_executor()
    assert executor.installed_version_from_ha_image(image) == expected


def test_a1_executor_has_no_usb_destructive_or_prepare_intent_path() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    forbidden = (
        '"wipefs"',
        '"sfdisk"',
        '"mkfs.ext4"',
        '"mount"',
        '"umount"',
        "CONFIRM_USB_ERASE",
        "request_prepare(",
        "confirm_and_prepare(",
    )
    for token in forbidden:
        assert token not in source


def test_execution_order_preflight_stage_backup_claim_activate_verify() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    execute_source = source[source.index("def execute("):source.index("def parser(")]
    assert execute_source.index("collect_preflight(transport)") < execute_source.index(
        "stage_bundle("
    )
    assert execute_source.index("stage_bundle(") < execute_source.index(
        "snapshot_rollback("
    )
    assert execute_source.index('"authorization_claim.json"') < execute_source.index(
        "activate(transport, staging_root)"
    )
    assert execute_source.index("activate(transport, staging_root)") < execute_source.index(
        "validate_post_activation("
    )


def test_activation_restarts_services_owner_once_and_never_restarts_broker() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    activate_source = source[
        source.index("def activate("):source.index("def require_file_metadata(")
    ]
    assert activate_source.count('["systemctl", "restart", SERVICES_UNIT]') == 1
    assert '["systemctl", "restart", BROKER_UNIT]' not in activate_source


def test_post_activation_requires_nonprivileged_manager_and_readonly_mount() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    post = source[
        source.index("def validate_post_activation("):source.index("def restore_targets(")
    ]
    assert 'manager.get("Config", {}).get("User") != MANAGER_USER' in post
    assert 'runtime_mounts[0].get("RW") is not False' in post
    assert "manager_docker_socket_present" in post
    assert "manager_block_device_access_present" in post
    assert "prepare_transaction_created_during_a1" in post


def test_failure_after_claim_rolls_back_a1_wiring_not_manager_image() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    rollback = source[
        source.index("def rollback_activation("):source.index("def execute(")
    ]
    assert '["systemctl", "stop", HOST_UNIT]' in rollback
    assert '["systemctl", "disable", HOST_UNIT]' in rollback
    assert '["systemctl", "restart", SERVICES_UNIT]' in rollback
    assert "EXPECTED_MANAGER" in rollback
    assert "T1_CORE_UPDATER_APPLY" not in rollback
    assert "greenhouse-manager-arm64.tar" not in rollback
