from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/greenhouse_n3w_core.h"
PRODUCT = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.cpp"
RUNTIME_H = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_runtime.h"
RUNTIME_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_runtime.cpp"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_boardb_diagnostic_observability_markers_present():
    core = text(CORE)
    for marker in (
        "N3W_DIAG_BOOT",
        "N3W_DIAG_STATE",
        "N3W_DIAG_CHANNEL",
        "N3W_DIAG_ESPNOW_TX_SUBMIT",
        "N3W_DIAG_ESPNOW_TX_DONE",
        "N3W_DIAG_ESPNOW_RX",
        "N3W_DIAG_DIRECT_PUBLISH",
        "esp_reset_reason()",
        "esp_get_idf_version()",
        "decode_simple_relay_discovery",
        "decode_simple_peer_challenge",
        "decode_simple_peer_accept",
        "decode_compact_telemetry_frame_v2",
    ):
        assert marker in core


def test_diagnostic_branch_does_not_change_known_transport_policy():
    product = text(PRODUCT)
    runtime_h = text(RUNTIME_H)
    runtime_cpp = text(RUNTIME_CPP)

    assert "std::vector<uint8_t> allowed_channels{1, 6, 11};" in runtime_h
    assert "uint32_t scan_dwell_ms{250};" in runtime_h
    assert "(void) runtime_.tick();" in product
    assert "return radio_.set_channel(channel) == DriverError::NONE;" in product
    assert "next_scan_switch_ms_ = now_ms + policy_.scan_dwell_ms;" in runtime_cpp


def test_diagnostic_logging_does_not_emit_payload_or_topic():
    core = text(CORE)
    start = core.index("bool publish_direct(")
    end = core.index("protected:", start)
    body = core[start:end]
    assert "topic.c_str()" not in body
    assert "payload.c_str()" not in body
