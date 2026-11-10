from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "tools/execution_packages/n3w/r7a/kf147_manager_v3_live_apply"
MANIFEST = PACKAGE / "manifest.json"
LOCAL = PACKAGE / "executor.py"
REMOTE = PACKAGE / "remote_apply.py"
WORKFLOW = ROOT / ".github/workflows/n3w-kf147-manager-v3-live-package-ci.yml"

PACKAGE_GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "MANAGER_IPC_V3_IMAGE_ONLY_LIVE_APPLY_20261110_01"
)
GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "MANAGER_IPC_V3_IMAGE_ONLY_LIVE_APPLY_R2_20261110_01"
)


def load_local():
    spec = importlib.util.spec_from_file_location("kf147_manager_v3_live_executor_test", LOCAL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["kf147_manager_v3_live_executor_test"] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_fresh_artifact_bound_and_authorization_state_is_valid() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert doc["schema"] == "gh.n3w-t1-kf147-manager-v3-live-executor/1"
    assert doc["gate_id"] == GATE
    assert doc["authorization_id"] == GATE
    assert doc["binding_state"] == "FRESH_ARTIFACT_BOUND"
    assert doc["package_authority"] == {
        "workflow_run_id": 42761736604,
        "artifact_id": 13738561063,
        "artifact_name": "n3w-kf147-manager-v3-live-44e7d7472714-20261110",
        "artifact_digest": "sha256:69af4054e993398c25bd7788773c76cc80f54524787d1f5972a894adef22bcfc",
    }
    assert doc["predecessor_authorization"] == {
        "authorization_id": PACKAGE_GATE,
        "granted": True,
        "claimed": True,
        "consumed": True,
        "replay_permitted": False,
        "result": "STOP_PRE_SERVICE_MUTATION_LOADED_TARGET_IDENTITY_INVALID",
    }
    assert doc["repair"] == {
        "class": "KF-106_CROSS_STORE_IMAGE_IDENTITY_RECURRENCE",
        "portable_identity_authority": "tools/n3w_t1_portable_image_identity.py",
        "fresh_readonly_preflight_required": True,
        "new_live_authorization_required": True,
    }
    authorization = doc["authorization_state"]
    assert authorization["replay_permitted"] is False
    state = (
        doc["live_execution_authorized"],
        authorization["granted"],
        authorization["claimed"],
        authorization["consumed"],
    )
    assert state in {
        (False, False, False, False),
        (True, True, False, False),
        (False, True, True, True),
    }
    assert doc["target"]["predecessor_image_id"] == "sha256:7e3f09ed47010a18de215faa426113b7faba4e220b41bb9dcafd8ee1d4acf20b"
    assert doc["target"]["homeassistant_image_id"] == "sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306"
    assert doc["target"]["broker_image_id"] == "sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563"


def test_execution_contract_preserves_u1_and_forbids_usb_mutation() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contract = doc["execution_contract"]
    assert contract["manager_image_mutation"] is True
    assert contract["application_owner_restart_required"] is True
    assert contract["homeassistant_image_mutation"] is False
    assert contract["homeassistant_container_recreate"] is False
    assert contract["broker_mutation"] is False
    assert contract["host_policy_mutation"] is False
    assert contract["host_source_mutation"] is False
    assert contract["u1_transaction_reset"] is False
    assert contract["prepare_replay"] is False
    assert contract["confirm_usb_erase"] is False
    assert contract["usb_mutation"] is False
    assert contract["u2_plus"] is False
    assert contract["automatic_retry"] is False
    assert contract["remote_local_rollback"] is True
    assert contract["merge"] is False


def test_remote_executor_has_no_destructive_usb_commands_or_prepare_submission() -> None:
    source = REMOTE.read_text(encoding="utf-8")
    for forbidden in (
        '"wipefs"',
        '"mkfs',
        '"fdisk"',
        '"sfdisk"',
        '"parted"',
        "CONFIRM_USB_ERASE",
        'action="PREPARE"',
        '"PREPARE"',
    ):
        assert forbidden not in source
    assert '"lsblk"' in source
    assert "U1_PREPARE_REQUESTED" in source
    assert "confirmation_consumed" in source
    assert "capacity_snapshot_present" in source


def test_remote_preflight_accepts_running_or_degraded_but_still_requires_core_units() -> None:
    source = REMOTE.read_text(encoding="utf-8")
    assert 'system_state = run(["systemctl", "is-system-running"], check=False).stdout.strip()' in source
    assert 'if system_state not in {"running", "degraded"}:' in source
    assert 'if not service_active(SERVICES_UNIT) or not service_active(OTA_UNIT):' in source


def test_remote_executor_uses_portable_target_identity_before_claim_and_after_load() -> None:
    source = REMOTE.read_text(encoding="utf-8")
    assert "parse_image_archive" in source
    assert "verify_runtime_document" in source
    assert "target_portable_identity(tar, allow_absent=True)" in source
    assert "target_portable_identity(tar, allow_absent=False)" in source
    assert 'image[0].get("Id") != TARGET_IMAGE_ID' not in source
    assert '"target_image_prestate": "PRESENT_AND_EXACT"' in source
    assert '"target_runtime_image_id": runtime_id' in source
    assert "manager.get(\"Image\") != target_runtime_id" in source


def test_remote_executor_rolls_back_from_owner_quiesce_boundary() -> None:
    source = REMOTE.read_text(encoding="utf-8")
    assert "rollback_needed = True" in source
    assert 'run(["systemctl", "stop", SERVICES_UNIT]' in source
    assert "if rollback_needed:" in source
    assert "rollback(pre, snapshot_env)" in source
    assert 'run(["systemctl", "start", SERVICES_UNIT]' in source


def test_remote_executor_binds_exact_predecessor_and_target() -> None:
    source = REMOTE.read_text(encoding="utf-8")
    assert "local/greenhouse-manager:fresh-7807271e4c48" in source
    assert "sha256:7e3f09ed47010a18de215faa426113b7faba4e220b41bb9dcafd8ee1d4acf20b" in source
    assert "local/greenhouse-manager:fresh-44e7d7472714" in source
    assert "sha256:fd5104d610645347fe47137dbb24121851fa8a48530df3e3c905704607c5e3d4" in source
    assert "sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306" in source
    assert "sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563" in source
    assert "9316817590c4fe74498629d0451a4897c2e11bef7bc4b423b66e47bb846099c5" in source
    assert "32017047552" in source
    assert "835309535" in source
    assert "eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973" in source
    assert "6e1f0b5d262e346674b62ac79bf2ffbc1c63a8dd22379a0a82c952f0e3626b49" in source
    assert "e45fba0ad3e9997be2738c7a8f25d5c342ebba66ddbf822b1f6bf6a016c2ed93" in source
    assert "u1_transaction_sha256_drift" in source


def test_local_launcher_uses_single_password_controlmaster_streaming_transport() -> None:
    source = LOCAL.read_text(encoding="utf-8")
    assert "n3w_t1_ssh_transport.py" in source
    assert "n3w_t1_portable_image_identity.py" in source
    assert "PORTABLE_IDENTITY_BLOB" in source
    assert "transport.start_epoch()" in source
    assert "transport.scp_to(" not in source
    assert "stream_file_over_ssh(" in source
    assert "ControlPath=" in source
    assert "BatchMode=yes" in source
    assert "PasswordAuthentication=no" in source
    assert "ProxyCommand=/usr/bin/false" in source
    assert "os.O_EXCL" in source
    assert "O_NOFOLLOW" in source
    assert "os.fsync(output.fileno())" in source
    assert "stream_remote_path_invalid" in source
    assert "transport.close_epoch()" in source
    assert "5bc28b30e696bd3d0f5ae4c98fd81b8f8679aaa7" in source


def test_streaming_transport_keeps_stdin_open_and_reuses_bound_master(tmp_path, monkeypatch) -> None:
    local = load_local()
    payload = b"kf147-stream-test"
    source = tmp_path / "payload.bin"
    source.write_bytes(payload)

    class FakeTransport:
        target = "root@t1.local"
        known_hosts = tmp_path / "known_hosts"
        control_path = tmp_path / "ctl"

        def assert_master(self) -> None:
            return None

    observed = {}

    def fake_run(argv, *, stdin, stdout, stderr, timeout, check):
        observed["argv"] = tuple(argv)
        observed["payload"] = stdin.read()
        observed["timeout"] = timeout
        return subprocess.CompletedProcess(tuple(argv), 0, b"", b"")

    monkeypatch.setattr(local.subprocess, "run", fake_run)
    local.stream_file_over_ssh(
        source,
        FakeTransport(),
        f"{local.REMOTE_DIR}/remote_apply.py",
        timeout=120,
    )

    argv = observed["argv"]
    assert argv[0] == "ssh"
    assert "-n" not in argv
    assert f"ControlPath={FakeTransport.control_path}" in argv
    assert "BatchMode=yes" in argv
    assert "PasswordAuthentication=no" in argv
    assert "KbdInteractiveAuthentication=no" in argv
    assert "PubkeyAuthentication=no" in argv
    assert "ProxyCommand=/usr/bin/false" in argv
    assert observed["payload"] == payload
    assert observed["timeout"] == 120


def test_remote_capacity_report_fails_closed_before_staging() -> None:
    local = load_local()
    binding = {
        "manager_image_size_bytes": 96 * 1024 * 1024,
        "capacity_required_free_bytes": (
            2 * local.EXPECTED_MANAGER_SIZE + 96 * 1024 * 1024
        ),
    }

    class FakeTransport:
        def run_remote(self, argv, *, timeout):
            assert argv[:2] == ["python3", "-c"]
            assert timeout == 90
            return subprocess.CompletedProcess(
                argv,
                0,
                json.dumps({
                    "staging_root": "/var/tmp",
                    "docker_root": "/var/lib/docker",
                    "staging_device": 7,
                    "docker_device": 7,
                    "staging_free_bytes": binding["capacity_required_free_bytes"] - 1,
                    "docker_free_bytes": binding["capacity_required_free_bytes"] - 1,
                    "staging_fstype": "ext4",
                    "docker_fstype": "ext4",
                }),
                "",
            )

    with pytest.raises(local.Stop, match="remote_capacity_insufficient"):
        local.remote_capacity_report(FakeTransport(), binding)


def test_remote_capacity_report_accepts_same_ext4_device_with_exact_bound() -> None:
    local = load_local()
    image_size = 96 * 1024 * 1024
    required = 2 * local.EXPECTED_MANAGER_SIZE + image_size
    binding = {
        "manager_image_size_bytes": image_size,
        "capacity_required_free_bytes": required,
    }

    class FakeTransport:
        def run_remote(self, argv, *, timeout):
            return subprocess.CompletedProcess(
                argv,
                0,
                json.dumps({
                    "staging_root": "/var/tmp",
                    "docker_root": "/var/lib/docker",
                    "staging_device": 7,
                    "docker_device": 7,
                    "staging_free_bytes": required,
                    "docker_free_bytes": required,
                    "staging_fstype": "ext4",
                    "docker_fstype": "ext4",
                }),
                "",
            )

    report = local.remote_capacity_report(FakeTransport(), binding)
    assert report["capacity_pass"] is True
    assert report["required_free_bytes"] == required
    assert report["available_free_bytes"] == required


def test_streaming_transport_rejects_non_owned_remote_path(tmp_path) -> None:
    local = load_local()
    source = tmp_path / "payload.bin"
    source.write_bytes(b"x")

    class FakeTransport:
        target = "root@t1.local"
        known_hosts = tmp_path / "known_hosts"
        control_path = tmp_path / "ctl"

        def assert_master(self) -> None:
            return None

    with pytest.raises(local.Stop, match="stream_remote_path_invalid"):
        local.stream_file_over_ssh(
            source,
            FakeTransport(),
            "/var/tmp/not-owned/payload.bin",
            timeout=120,
        )


def test_workflow_builds_manager_only_slice_from_frozen_exact_artifact() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "UPSTREAM_ARTIFACT_ID: \"13673322402\"" in source
    assert "SOURCE_HEAD: 44e7d74727147975de88e85c4b18ba3f7493fd76" in source
    assert "MANAGER_TAR_SHA256: 9316817590c4fe74498629d0451a4897c2e11bef7bc4b423b66e47bb846099c5" in source
    assert "MANAGER_IMAGE_SIZE_BYTES" in source
    assert '"manager_image_size_bytes"' in source
    assert '"capacity_required_free_bytes"' in source
    assert "greenhouse-manager-arm64.tar" in source
    assert f"GATE_ID: {PACKAGE_GATE}" in source
    assert "n3w-kf147-manager-v3-live-44e7d7472714-20261110" in source
    assert "tools/n3w_t1_core_updater_*.py" not in source
    assert "homeassistant-arm64.tar" not in "\n".join(
        line for line in source.splitlines()
        if "cp " in line and "$RUNNER_TEMP/package" in line
    )
