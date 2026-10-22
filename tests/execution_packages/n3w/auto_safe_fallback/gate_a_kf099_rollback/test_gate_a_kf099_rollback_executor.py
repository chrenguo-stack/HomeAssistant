from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = ROOT / "tools/execution_packages/n3w/auto_safe_fallback/gate_a_kf099_rollback/executor.py"

spec = importlib.util.spec_from_file_location("gate_a_kf099_rollback", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_exact_kf099_rollback_authority_is_frozen() -> None:
    assert module.ARTIFACT_ID == 10959875986
    assert module.ARTIFACT_ZIP_SHA256 == "56abb5267ee1786f77930837d6a660745ee64f320d1c6ad64aac7c852aa115cb"
    assert module.APPLICATION_SHA256 == "d0875ca692f7bd4349fd7d8bcdab69318e6c8b737b69a48f667b6e72cb89cb60"
    assert module.OTADATA_SHA256 == "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"
    assert module.EXPECTED_HARDWARE_ID_SHA256 == "3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee"
    assert module.PARTITION_TABLE_SHA256 == "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"


def test_rollback_uses_new_authorization_token() -> None:
    assert module.WRITE_CONFIRMATION == "N3W_GATE_A_KF099_ROLLBACK_WRITE_AUTHORIZED"
    assert module.WRITE_CONFIRMATION != "KF099_C578BCB_BOARD_B_WRITE_AUTHORIZED"
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "if args.confirm != WRITE_CONFIRMATION" in source
    assert '"replay_permitted": False' in source


def test_rollback_write_scope_is_only_otadata_and_application() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    region = source[source.index("def build_write_command") : source.index("def run_write")]
    assert '"0x9000", str(ota)' in region
    assert '"0x10000", str(app)' in region
    for token in ("erase-flash", "erase_flash", "0x8000", "nvs.bin"):
        assert token not in region


def test_rollback_expected_baseline_is_pairing_wait_not_direct_mqtt() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert '"KF099_PAIRING_WAIT_REPAIR_INTENT_REQUIRED"' in source
    assert "DIRECT_BASELINE" not in source


def test_rollback_executor_has_no_t1_transport_or_mutation() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8").lower()
    for token in ("ssh", "scp", "docker", "systemctl", "ip addr", "mosquitto"):
        assert token not in source
