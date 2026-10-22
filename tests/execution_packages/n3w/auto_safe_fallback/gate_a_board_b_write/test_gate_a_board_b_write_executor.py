from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = ROOT / "tools/execution_packages/n3w/auto_safe_fallback/gate_a_board_b_write/executor.py"

spec = importlib.util.spec_from_file_location("gate_a_board_b_write", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_exact_private_artifact_binding_is_frozen() -> None:
    assert module.SOURCE_HEAD == "8210cf7b53e9ec934d145f1c15e9619579c923be"
    assert module.APPLICATION_SIZE == 1140352
    assert module.APPLICATION_SHA256 == "77b0fd6a98c3e837d3543eebdd30b86354790847d0c78cdab7e96f0d7d66a8ad"
    assert module.OTADATA_SIZE == 8192
    assert module.OTADATA_SHA256 == "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"
    assert module.PARTITION_TABLE_SHA256 == "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"
    assert module.EXPECTED_HARDWARE_ID_SHA256 == "3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee"


def test_write_scope_is_only_otadata_and_application() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert '"0x9000", str(ota)' in source
    assert '"0x10000", str(app)' in source
    forbidden = (
        "erase-flash",
        "erase_flash",
        "0x0",
        "0x8000",
        "partition-table.bin",
        "nvs.bin",
    )
    write_region = source[source.index("def build_write_command") : source.index("def run_write")]
    for token in forbidden:
        assert token not in write_region


def test_write_requires_separate_explicit_confirmation() -> None:
    assert module.WRITE_CONFIRMATION == "N3W_GATE_A_BOARD_B_WRITE_AUTHORIZED"
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "if args.confirm != WRITE_CONFIRMATION" in source
    assert '"replay_permitted": False' in source


def test_rollback_is_metadata_only_and_requires_fresh_authorization() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert module.ROLLBACK_ARTIFACT_ID == 10959875986
    assert module.ROLLBACK_ARCHIVE_SHA256 == "56abb5267ee1786f77930837d6a660745ee64f320d1c6ad64aac7c852aa115cb"
    assert '"write_authorization_required": True' in source
    assert "ROLLBACK_APPLICATION_SHA256" in source
    assert "run_rollback" not in source
    assert "rollback_write" not in source


def test_executor_has_no_t1_mutation_transport() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    forbidden = (
        "ssh",
        "scp",
        "docker",
        "ip addr",
        "systemctl",
        "mosquitto",
    )
    for token in forbidden:
        assert token not in source.lower()


def test_public_output_never_prints_private_bundle_path() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    print_region = source[source.index('print("GATE_A_BOARD_B_PREFLIGHT=PASS")') :]
    assert 'print(args.bundle)' not in print_region
    assert 'print(bundle["root"])' not in print_region
