from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[5]
EXECUTOR = ROOT / "tools/execution_packages/n3w/kf089/id16_board_a_only/executor.py"
MANIFEST = ROOT / "tools/execution_packages/n3w/kf089/id16_board_a_only/manifest.json"

spec = importlib.util.spec_from_file_location("id16_executor", EXECUTOR)
assert spec and spec.loader
executor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(executor)


def test_manifest_freezes_board_a_only_scope() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["gate_id"] == "id16_board_a_only"
    assert manifest["target_contract"]["physical_target"] == "BOARD_A_ONLY"
    assert manifest["target_contract"]["board_b_physical_access_forbidden"] is True
    assert manifest["forbidden"]["board_b_physical_access"] is True
    assert manifest["forbidden"]["second_rf_capture"] is True
    assert manifest["forbidden"]["t1_access"] is True
    assert manifest["forbidden"]["flash_write"] is True
    assert manifest["forbidden"]["nvs_write"] is True
    assert manifest["manual_physical_preparation"]["occurs_only_after_explicit_id16_authorization"] is True


def test_parser_and_predecessor_evidence_are_exactly_bound() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert executor.EXPECTED_DIAG_PARSER_BLOB == "af78ed4cb14c38579f56e6ba3019e2debdb21d9e"
    assert manifest["tool_bindings"]["diag_parser_git_blob"] == executor.EXPECTED_DIAG_PARSER_BLOB
    assert manifest["tool_bindings"]["diag_parser_input_mode"] == "--nvs-image"
    assert manifest["predecessor_evidence"]["board_b_nvs_sha256"] == executor.EXPECTED_BOARD_B_NVS_SHA256
    assert manifest["predecessor_evidence"]["board_b_unicast_completion_count"] == 44
    assert manifest["predecessor_evidence"]["board_b_unicast_completion_success"] == 41
    assert manifest["predecessor_evidence"]["board_b_unicast_completion_failure"] == 3
    assert manifest["predecessor_evidence"]["next_unproven_stage"] == "A_COMPACT_RX"


def test_esptool_commands_are_rom_read_only() -> None:
    read_mac = executor.build_read_mac_command("/dev/example")
    read_nvs = executor.build_read_nvs_command("/dev/example", Path("/tmp/nvs.bin"))
    for argv in (read_mac, read_nvs):
        assert "--before" in argv and "no-reset" in argv
        assert "--after" in argv
        assert "--no-stub" in argv
        executor.assert_read_only_argv(argv)
    assert read_mac[-1] == "read-mac"
    assert "read-flash" in read_nvs
    assert hex(executor.NVS_OFFSET) in read_nvs
    assert hex(executor.NVS_SIZE) in read_nvs


def test_decoder_uses_full_nvs_image_mode() -> None:
    argv = executor.build_decode_command(Path("/repo"), Path("/private/nvs.bin"))
    assert "--nvs-image" in argv
    assert "--blob" not in argv


def test_board_a_identity_suffix_parser_is_canonical_base_mac_only() -> None:
    mac = ":".join(["98", "a3", "16", "a9", "f3", "50"])
    generic_mac = ":".join(["00"] * 6)
    output = "MAC: " + generic_mac + "\nBASE MAC: " + mac + "\n"
    parsed = executor.parse_base_mac(output)
    assert executor.mac_suffix(parsed) == "f3:50"


def test_required_schema_v5_counters_are_selected() -> None:
    board_a = {field: 0 for field in executor.BOARD_A_REQUIRED_FIELDS}
    board_a["schema_version"] = 5
    selected_a = executor.validate_snapshot(board_a, executor.BOARD_A_REQUIRED_FIELDS, "board_a")
    assert tuple(selected_a) == executor.BOARD_A_REQUIRED_FIELDS

    board_b = {field: 0 for field in executor.BOARD_B_REQUIRED_FIELDS}
    board_b["schema_version"] = 5
    selected_b = executor.validate_snapshot(board_b, executor.BOARD_B_REQUIRED_FIELDS, "board_b")
    assert tuple(selected_b) == executor.BOARD_B_REQUIRED_FIELDS


def test_executor_has_no_board_b_port_or_board_b_target_command() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "--board-b-port" not in source
    assert "board_b_read_mac" not in source
    assert "board_b_read_nvs" not in source
    assert "BOARD_B_EXISTING_EVIDENCE_DECODE" in source
