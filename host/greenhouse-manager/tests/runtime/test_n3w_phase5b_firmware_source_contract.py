from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"
P5_LAB = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_p5_lab"
S5_BOARD = ROOT / "firmware/esphome_rc/board_lab/n3w_product_completion_s5"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_active_radio_surface_drops_reliable_fragmentation_stack() -> None:
    header = _text(CORE / "n3w_radio.h")
    source = _text(CORE / "n3w_radio.cpp")
    legacy_include_gate = (
        '\n#ifdef GREENHOUSE_N3W_ENABLE_LEGACY_RADIO\n'
        '#include "n3w_radio_legacy.h"\n'
        "#endif"
    )
    assert legacy_include_gate in header
    active_header = header.replace(legacy_include_gate, "", 1)

    for marker in (
        "struct DataFragment",
        "struct ReceiptAckPacket",
        "class RelayReassembler",
        "class RelayIngressController",
        "struct RetryPolicy",
        "struct CachedRelayFrame",
        "class ChildRelayCache",
        "fragment_relay_frame(",
        "encode_authenticated_receipt_ack(",
        "decode_authenticated_receipt_ack(",
        "encode_data_fragment(",
        "decode_data_fragment(",
    ):
        assert marker not in active_header
        assert marker not in source

    for preserved in (
        "using MacAddress",
        "using LinkKey",
        "class ChannelScanPlan",
        "class LocalPathController",
        "valid_radio_channel",
        "same_mac",
    ):
        assert preserved in active_header


def test_legacy_radio_exists_only_behind_explicit_regression_gates() -> None:
    legacy_header = _text(CORE / "n3w_radio_legacy.h")
    legacy_wrapper = _text(CORE / "n3w_radio_legacy.cpp")
    legacy_impl = CORE / "n3w_radio_legacy_impl.h"
    lab_component = _text(P5_LAB / "__init__.py")

    for marker in (
        "DataFragment",
        "ReceiptAckPacket",
        "RelayReassembler",
        "RetryPolicy",
        "ChildRelayCache",
    ):
        assert marker in legacy_header

    gate = "GREENHOUSE_N3W_ENABLE_LEGACY_RADIO"
    assert gate in legacy_wrapper
    assert '#include "n3w_radio_legacy_impl.h"' in legacy_wrapper
    assert legacy_impl.is_file()
    assert not (CORE / "n3w_radio_legacy_impl.inc").exists()
    assert f'cg.add_build_flag("-D{gate}=1")' in lab_component
    for role in ("child", "relay"):
        target = _text(S5_BOARD / f"{role}.yml")
        assert "platformio_options:" in target
        assert "build_flags:" in target
        assert f'-D{gate}=1' in target
    assert "regression reference" in legacy_header
    assert "release/runtime code must not" in legacy_header.lower()


def test_single_frame_product_budget_remains_physical_driver_contract() -> None:
    driver = _text(CORE / "n3w_espnow_driver.h")
    compact = _text(CORE / "n3w_compact_telemetry.h")
    simple_runtime = _text(CORE / "n3w_simple_product_runtime.h")

    assert "kEspNowPhysicalDatagramLimit = 1470" in driver
    assert "kEspNowV2PayloadLimit = 1470" in compact
    assert "kCompactTelemetryMaxWireBytes" in compact
    for preserved in (
        "MacAddress",
        "LinkKey",
        "ChannelScanPlan",
        "LocalPathController",
    ):
        assert preserved in simple_runtime
