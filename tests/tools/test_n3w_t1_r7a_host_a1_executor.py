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


def test_manifest_retires_consumed_successor_after_a1_pass() -> None:
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert document["schema"] == "gh.n3w-t1-r7a-host-a1-live-activation-package/1"
    assert document["live_execution_authorized"] is False
    contract = document["execution_contract"]
    assert contract["host_daemon_install"] is True
    assert contract["host_release_policy_install"] is True
    assert contract["host_release_policy_exact_hash_verify"] is True
    assert contract["compose_overlay_install"] is True
    assert contract["services_owner_restart_maximum"] == 1
    assert contract["broker_restart"] is False
    assert contract["usb_mutation"] is False
    assert contract["prepare_intent"] is False
    assert contract["confirm_usb_erase"] is False
    assert contract["u2_plus"] is False
    assert contract["manager_image_rollback"] is False
    assert contract["second_activation"] is False
    assert contract["legacy_recovery_gate"] is True
    assert contract["manager_ipc_status_probe"] is True
    assert contract["structured_ssh_start_stop"] is True
    assert contract["symlink_nonregular_fail_closed"] is True
    assert contract["rollback_backup_hash_verified"] is True
    assert contract["post_restart_container_settle_wait"] is True
    assert contract["rollback_restart_container_settle_wait"] is True


def test_a1_binds_and_installs_exact_host_release_policy_v2() -> None:
    executor = load_executor()
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    policy_path = (
        "infra/n3w-t1/upgrades/homeassistant-2026.10.4-host-release-policy.json"
    )
    capacity_path = "tools/n3w_t1_core_updater_ha_capacity.py"

    assert policy_path in document["source_authority"]
    assert capacity_path in document["source_authority"]
    assert executor.SOURCE_DESTINATIONS[policy_path] == (
        "/etc/n3w-t1-ota/homeassistant-release-source.json"
    )
    assert executor.SOURCE_DESTINATIONS[capacity_path] == (
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_capacity.py"
    )

    policy = json.loads((ROOT / policy_path).read_text(encoding="utf-8"))
    assert policy["schema"] == "gh.n3w-t1-ha-ota-host-release-policy/2"
    assert policy["predecessor_recovery_budget_bytes"] == 1_342_177_280

    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    post = source[
        source.index("def validate_post_activation("):
        source.index("def restore_targets(")
    ]
    assert 'require_file_metadata(transport, HOST_RELEASE_POLICY, "0:0:644:regular file")' in post
    assert "require_source_hashes(transport, source_hashes)" in post


def test_successor_authorization_contract_remains_bound_but_retired() -> None:
    executor = load_executor()
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    successor = "N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_LIVE_ACTIVATION_20261108_02"
    consumed = "N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_LIVE_ACTIVATION_20261107_01"
    assert executor.AUTHORIZATION == successor
    assert document["proposed_authorization_id"] == successor
    assert document["live_execution_authorized"] is False
    assert executor.AUTHORIZATION != consumed


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


def test_live_gate_rejects_consumed_successor_replay() -> None:
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


def test_post_activation_requires_stable_same_containers_after_hold_window() -> None:
    executor = load_executor()
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    assert executor.POST_ACTIVATION_STABILITY_SECONDS == 15.0
    stability = source[
        source.index("def require_post_activation_stability("):
        source.index("def env_map(")
    ]
    assert '["sleep", str(POST_ACTIVATION_STABILITY_SECONDS)]' in stability
    assert '"services_owner_unstable_post"' in stability
    assert 'document.get("Id") != expected_id' in stability
    post = source[
        source.index("def validate_post_activation("):source.index("def restore_targets(")
    ]
    assert "require_post_activation_stability(" in post


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


def test_legacy_nonterminal_transaction_blocks_a1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = load_executor()
    monkeypatch.setattr(
        executor,
        "remote_exists",
        lambda _transport, path, kind="-e": path == executor.LEGACY_TRANSACTION,
    )
    monkeypatch.setattr(
        executor,
        "remote_private_json",
        lambda *_args, **_kwargs: {
            "schema": "gh.n3w-t1-core-updater-transaction/1",
            "status": "APPLYING",
        },
    )
    with pytest.raises(
        executor.StopExecution,
        match="legacy_manager_recovery_required",
    ):
        executor.require_recovery_clear(object())


@pytest.mark.parametrize("status", ["COMMITTED", "ROLLED_BACK"])
def test_legacy_terminal_transaction_keeps_recovery_clear(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    executor = load_executor()
    monkeypatch.setattr(
        executor,
        "remote_exists",
        lambda _transport, path, kind="-e": path == executor.LEGACY_TRANSACTION,
    )
    monkeypatch.setattr(
        executor,
        "remote_private_json",
        lambda *_args, **_kwargs: {
            "schema": "gh.n3w-t1-core-updater-transaction/1",
            "status": status,
        },
    )
    result = executor.require_recovery_clear(object())
    assert result["legacy_manager_status"] == status
    assert result["recovery_required"] is False


def test_manager_ipc_probe_uses_actual_manager_uid_and_readonly_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = load_executor()
    captured = {}

    def fake_remote(_transport, argv, **_kwargs):
        captured["argv"] = argv
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps(
                {
                    "phase": "DISCOVERED",
                    "progress_percent": None,
                    "error_code": None,
                    "usb_confirmation_required": False,
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(executor, "remote", fake_remote)
    manager_id = "a" * 64
    result = executor.manager_ipc_status_probe(object(), manager_id)
    assert result["phase"] == "DISCOVERED"
    assert captured["argv"][:5] == [
        "docker",
        "exec",
        "--user",
        "999:999",
        manager_id,
    ]
    command = captured["argv"][-1]
    assert "UnixSocketOtaBridge" in command
    assert "get_homeassistant_ota_runtime_state" in command
    assert "submit_homeassistant_ota_intent" not in command


def test_ssh_epoch_start_failure_is_structured_stop() -> None:
    executor = load_executor()

    class BrokenTransport:
        def __init__(self, **_kwargs):
            pass

        def start_epoch(self):
            raise RuntimeError("synthetic")

        def close_epoch(self):
            return {"status": "PASS", "session_closed": True}

    with pytest.raises(
        executor.StopExecution,
        match="ssh_epoch_start_failed:RuntimeError",
    ):
        executor.start_ssh_epoch(
            BrokenTransport,
            target="root@example.invalid",
            known_hosts=Path("/tmp/known_hosts"),
            expected_host_key_sha256="0" * 64,
        )


def test_activation_residue_rejects_dangling_symlink(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = load_executor()

    def fake_exists(_transport, path, kind="-e"):
        return (
            path == executor.HOST_UNIT_PATH
            and kind == "-L"
        )

    monkeypatch.setattr(executor, "remote_exists", fake_exists)
    with pytest.raises(
        executor.StopExecution,
        match="a1_activation_residue_present",
    ):
        executor.require_activation_residue_absent(object())


def test_rollback_snapshot_rejects_nonregular_existing_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = load_executor()

    def fake_exists(_transport, path, kind="-e"):
        first = executor.LIVE_TARGETS[0]
        if path == first and kind == "-L":
            return False
        if path == first and kind == "-e":
            return True
        if path == first and kind == "-f":
            return False
        return False

    monkeypatch.setattr(executor, "remote_exists", fake_exists)
    monkeypatch.setattr(
        executor,
        "remote",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )
    with pytest.raises(
        executor.StopExecution,
        match="activation_target_not_regular",
    ):
        executor.snapshot_rollback(object(), "/var/tmp/a1")


def test_docker_container_waits_for_single_running_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = load_executor()
    responses = iter(["", "abc123\n"])
    calls = []

    def fake_remote(_transport, argv, **_kwargs):
        calls.append(argv)
        if argv[:2] == ["docker", "ps"]:
            return subprocess.CompletedProcess(argv, 0, next(responses), "")
        if argv[:2] == ["docker", "inspect"]:
            return subprocess.CompletedProcess(
                argv,
                0,
                json.dumps([{"Id": "abc123", "State": {"Status": "running"}}]),
                "",
            )
        raise AssertionError(argv)

    monkeypatch.setattr(executor, "remote", fake_remote)
    monkeypatch.setattr(executor.time, "sleep", lambda _seconds: None)
    ticks = iter([0.0, 0.0, 1.0])
    monkeypatch.setattr(executor.time, "monotonic", lambda: next(ticks))
    result = executor.docker_container(
        object(),
        executor.EXPECTED_MANAGER,
        settle_timeout_s=120.0,
    )
    assert result["Id"] == "abc123"
    assert sum(argv[:2] == ["docker", "ps"] for argv in calls) == 2


def test_post_and_rollback_use_bounded_container_settle_wait() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    post = source[
        source.index("def validate_post_activation("):
        source.index("def restore_targets(")
    ]
    rollback = source[
        source.index("def rollback_activation("):
        source.index("def execute(")
    ]
    assert post.count("settle_timeout_s=120.0") >= 2
    assert rollback.count("settle_timeout_s=120.0") >= 2


def test_preflight_does_not_wait_for_container_convergence() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    preflight = source[
        source.index("def collect_preflight("):
        source.index("def remote_staging_root(")
    ]
    assert "settle_timeout_s=120.0" not in preflight


def test_post_activation_waits_for_container_convergence() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    post = source[
        source.index("def validate_post_activation("):
        source.index("def restore_targets(")
    ]
    assert post.count("settle_timeout_s=120.0") >= 2
