from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[5]
PACKAGE = ROOT / "tools/execution_packages/n3w/kf089/id13_readonly_recovery"
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
SCHEMA = PACKAGE / "evidence_schema.json"


def load_executor():
    spec = importlib.util.spec_from_file_location("id13_executor", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_package_files_parse_and_bind_expected_gate():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert manifest["package_schema_version"] == 1
    assert manifest["project"] == "n3w"
    assert manifest["stage"] == "kf089"
    assert manifest["gate_id"] == "id13_readonly_recovery"
    assert schema["$schema"].endswith("2020-12/schema")
    assert schema["title"] == "N3W KF-089 ID13 read-only recovery closure"


def test_esptool_commands_are_explicit_python_module_read_only():
    mod = load_executor()
    read_mac = mod.build_read_mac_command("/dev/cu.example-b")
    read_nvs = mod.build_read_nvs_command(
        "/dev/cu.example-b", Path("/private/tmp/id13-b-nvs.bin")
    )

    for argv in (read_mac, read_nvs):
        assert argv[:3] == [sys.executable, "-m", "esptool"]
        assert "--chip" in argv and "esp32c6" in argv
        assert "--before" in argv and "no-reset" in argv
        assert "--after" in argv and "no-reset" in argv
        assert "--no-stub" in argv
        lowered = {item.lower() for item in argv}
        assert not (lowered & mod.WRITE_LIKE_TOKENS)

    assert read_mac[-1] == "read-mac"
    assert "read-flash" in read_nvs
    assert "--flash-size" in read_nvs
    assert "8MB" in read_nvs
    assert hex(mod.NVS_OFFSET) in read_nvs
    assert hex(mod.NVS_SIZE) in read_nvs


def test_base_mac_parser_uses_only_complete_base_mac_lines():
    mod = load_executor()
    stdout = "\n".join(
        [
            "MAC: aa:bb:cc:dd:ee:ff",
            "BASE MAC: 98:a3:16:a9:f4:5c",
            "EUI64: 9a:a3:16:ff:fe:a9:f4:5c",
            "BASE MAC: 98:a3:16:a9:f4:5c",
        ]
    )
    assert mod.parse_base_mac(stdout) == "98:a3:16:a9:f4:5c"
    assert mod.mac_suffix(mod.parse_base_mac(stdout)) == "f4:5c"

    with pytest.raises(mod.StopExecution, match="no complete BASE MAC"):
        mod.parse_base_mac("MAC: 98:a3:16:a9:f4:5c\n")

    with pytest.raises(mod.StopExecution, match="multiple distinct BASE MAC"):
        mod.parse_base_mac(
            "BASE MAC: 98:a3:16:a9:f4:5c\n"
            "BASE MAC: 98:a3:16:a9:f3:50\n"
        )


def test_schema_v5_selected_counter_contract():
    mod = load_executor()

    board_b = {
        "schema_version": 5,
        "boot_session": 11,
        "snapshot_uptime_ms": 90000,
        "path_state": 4,
        "relay_active_count": 1,
        "relay_telemetry_attempts": 4,
        "relay_telemetry_success": 4,
        "unicast_completion_count": 4,
        "unicast_completion_success": 3,
        "unicast_completion_failure": 1,
    }
    selected_b = mod.validate_snapshot("board_b", board_b)
    assert tuple(selected_b) == mod.BOARD_REQUIRED_FIELDS["board_b"]

    board_a = {
        "schema_version": 5,
        "boot_session": 22,
        "snapshot_uptime_ms": 120000,
        "path_state": 1,
        "compact_rx_count": 4,
        "compact_state_reject_count": 0,
        "compact_child_binding_failure": 0,
        "compact_decode_success": 4,
        "compact_decode_failure": 0,
        "compact_wrap_failure": 0,
        "compact_forward_attempts": 4,
        "compact_forward_submit_success": 4,
        "compact_forward_submit_failure": 0,
    }
    selected_a = mod.validate_snapshot("board_a", board_a)
    assert tuple(selected_a) == mod.BOARD_REQUIRED_FIELDS["board_a"]

    bad = dict(board_b)
    bad["schema_version"] = 4
    with pytest.raises(mod.StopExecution, match="diagnostic schema mismatch"):
        mod.validate_snapshot("board_b", bad)


def test_command_json_survives_process_launch_failure(tmp_path: Path, monkeypatch):
    mod = load_executor()
    evidence = tmp_path / "evidence"
    mod.ensure_private_dir(evidence)

    def fail_run(*args, **kwargs):
        raise PermissionError("synthetic launch denial")

    monkeypatch.setattr(mod.subprocess, "run", fail_run)

    with pytest.raises(mod.StopExecution, match="process launch failed"):
        mod.run_recorded(
            evidence_root=evidence,
            index=1,
            label="synthetic",
            argv=[sys.executable, "-c", "print('never')"],
            cwd=tmp_path,
            target_operation=True,
        )

    op = evidence / "op_01_synthetic"
    command = json.loads((op / "command.json").read_text(encoding="utf-8"))
    result = json.loads((op / "result.json").read_text(encoding="utf-8"))
    assert command["argv"] == [sys.executable, "-c", "print('never')"]
    assert result["command_started"] is False
    assert result["target_access_occurred"] is False
    assert (op / "stderr.txt").read_text(encoding="utf-8").startswith(
        "PermissionError:"
    )


def test_authorization_state_transitions_are_explicit(tmp_path: Path):
    mod = load_executor()
    evidence = tmp_path / "evidence"
    mod.ensure_private_dir(evidence)

    mod.initial_authorization(evidence, "AUTH-ID13", "EXEC-ID13")
    initial = json.loads(
        (evidence / "authorization.json").read_text(encoding="utf-8")
    )
    assert initial["claimed"] is False
    assert initial["consumed"] is False
    assert initial["replay_permitted"] is False

    mod.claim_authorization(evidence, "AUTH-ID13", "EXEC-ID13")
    claimed = json.loads(
        (evidence / "authorization.json").read_text(encoding="utf-8")
    )
    assert claimed["claimed"] is True
    assert claimed["consumed"] is True
    assert claimed["replay_permitted"] is False
    assert claimed["claim_boundary"] == (
        "immediately_before_first_board_target_command"
    )


def test_self_check_is_host_only_and_uses_bound_parser():
    mod = load_executor()
    result = mod.self_check(PACKAGE)
    assert result["gate_id"] == "id13_readonly_recovery"
    assert result["expected_esptool_version"] == "5.3.1"
    assert result["expected_diag_parser_blob"] == (
        "de6951daf6cfd20035243b85c32957eb6108308a"
    )
    assert result["read_mac_uses_no_stub"] is True
    assert result["read_nvs_uses_no_stub"] is True
    assert result["write_like_tokens_present"] is False


def test_evidence_files_are_private_by_default(tmp_path: Path):
    mod = load_executor()
    path = tmp_path / "private"
    mod.ensure_private_dir(path)
    file_path = path / "value.json"
    mod.write_json(file_path, {"ok": True})
    assert os.stat(path).st_mode & 0o777 == 0o700
    assert os.stat(file_path).st_mode & 0o777 == 0o600
