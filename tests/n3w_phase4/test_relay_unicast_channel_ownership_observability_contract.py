import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"
LAB = ROOT / "firmware/esphome_rc/board_lab/n3w_phase4_physical"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def function_body(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


def test_driver_captures_raw_unicast_error_and_channel_context_without_mutation() -> None:
    header = text(CORE / "n3w_espnow_driver.h")
    source = text(CORE / "n3w_espnow_driver.cpp")
    send = function_body(
        source,
        "DriverError EspNowDriver::send(\n",
        "DriverError EspNowDriver::send_broadcast(\n",
    )

    assert "bool observe_context = false" in header
    assert "last_unicast_send_error_raw()" in header
    assert "last_unicast_current_channel()" in header
    assert "last_unicast_peer_channel()" in header

    assert "if (observe_context)" in send
    assert "esp_now_get_peer(peer_mac.data(), &peer)" in send
    assert "esp_wifi_get_channel(&current_channel, &secondary)" in send
    assert "const esp_err_t send_result = esp_now_send(peer_mac.data(), data, size);" in send
    assert "last_unicast_send_error_raw_ = static_cast<int32_t>(send_result);" in send

    # This preparation is observability-only: it must not introduce a second
    # send, channel switch, or controlled-channel transmission into data-plane TX.
    assert send.count("esp_now_send(peer_mac.data(), data, size)") == 1
    assert "esp_wifi_set_channel" not in send
    assert "esp_now_switch_channel_tx" not in send


def test_product_component_enables_context_reads_only_for_lab_diagnostics() -> None:
    component = text(CORE / "n3w_simple_product_component.cpp")
    send = function_body(
        component,
        "bool SimpleProductComponent::send_encrypted_peer(\n",
        "bool SimpleProductComponent::publish_direct(\n",
    )

    assert "radio_.send(peer_mac, data, size, diagnostics_.enabled())" in send
    assert "diagnostics_.note_unicast_submit(" in send
    assert "radio_.last_unicast_send_error_raw()" in send
    assert "radio_.last_unicast_current_channel()" in send
    assert "radio_.last_unicast_peer_channel()" in send


def test_unicast_submit_evidence_is_ram_only_and_resets_with_latency_snapshot() -> None:
    header = text(CORE / "n3w_lab_diagnostics.h")

    snapshot = function_body(header, "  struct Snapshot {\n", "  struct LatencySnapshot {\n")
    latency = function_body(
        header,
        "  struct LatencySnapshot {\n",
        "  void set_enabled(bool enabled)",
    )

    fields = (
        "unicast_submit_success_count",
        "unicast_submit_failure_count",
        "unicast_submit_first_failure_driver_error",
        "unicast_submit_first_failure_error_raw",
        "unicast_submit_first_failure_current_channel",
        "unicast_submit_first_failure_peer_channel",
        "unicast_submit_first_success_current_channel",
        "unicast_submit_first_success_peer_channel",
    )
    for field in fields:
        assert field in latency
        assert field not in snapshot

    assert "static constexpr uint16_t kSchemaVersion = 5U;" in header
    assert "void note_unicast_submit(" in header
    assert "latency_.unicast_submit_first_failure_error_raw = raw_error;" in header
    assert "latency_.unicast_submit_first_failure_current_channel = current_channel;" in header
    assert "latency_.unicast_submit_first_failure_peer_channel = peer_channel;" in header


def test_physical_lab_telemetry_exports_bounded_compact_unicast_evidence() -> None:
    config = text(LAB / "generic.yml")
    core = text(CORE / "n3w_core.h")

    assert "kMaxCiphertextBytes = 1024" in core
    assert "n3w_u is intentionally compact" in config
    assert "\\\"n3w_u\\\":{" in config

    for alias in ("ok", "f", "fe", "fr", "fc", "fp", "sc", "sp"):
        assert f"\\\"{alias}\\\"" in config

    # Keep the diagnostic extension itself bounded to roughly one tenth of the
    # 1024-byte encrypted telemetry plaintext budget.
    worst_case = (
        ',"n3w_u":{"ok":4294967295,"f":4294967295,"fe":255,'
        '"fr":-2147483648,"fc":14,"fp":14,"sc":14,"sp":14}'
    )
    assert len(worst_case.encode("utf-8")) <= 104


def test_phase4_lab_full_envelope_preserves_relay_plaintext_margin() -> None:
    config = text(LAB / "generic.yml")

    assert '\\"n3w_l\\":[1,' in config
    assert '\\"n3w_r\\":[1,' in config
    assert '\\"n3w_latency\\":{' not in config
    assert '\\"stage_name\\"' in config
    assert "previous_rtc_breadcrumb_stage_name()" in config
    assert '\\"reset_reason\\"' not in config
    assert "PHASE4_LAB_TELEMETRY_OVERSIZE" in config
    assert "telemetry_bytes" in config

    # Mirror the lab-only compact layout with conservative maxima. NODE_ID is
    # allowed up to 64 characters; millis()-derived times fit in 32 bits, while
    # scheduled due times may extend by the 480 s recovery backoff.
    u32 = 4294967295
    due_max = u32 + 480000
    payload = {
        "schema": "gh.telemetry/1",
        "node_id": "n" * 64,
        "boot_id": "boot_ffffffffffffffff",
        "seq": u32,
        "uptime_ms": u32,
        "cap_hash": "phase4lab",
        "fw_version": "phase4-simple",
        "reset_reason_raw": -2147483648,
        "wdt_breadcrumb": {
            "valid": True,
            "stage": u32,
            # Longest current breadcrumb name: RADIO_CHANNEL_SET_BEGIN (23).
            "stage_name": "RADIO_CHANNEL_SET_BEGIN",
            "arg0": u32,
            "arg1": u32,
            "uptime_ms": u32,
            "marker_sequence": u32,
        },
        "n3w_l": [
            1,
            u32, u32, u32, u32, u32, u32, u32, u32, u32,
            255, 255, -2147483648, -2147483648, u32, u32, u32,
        ],
        "n3w_u": {
            "ok": u32,
            "f": u32,
            "fe": 255,
            "fr": -2147483648,
            "fc": 14,
            "fp": 14,
            "sc": 14,
            "sp": 14,
        },
        "n3w_r": [
            1,
            u32, u32, 255, u32, u32, u32, u32, 255, 255, 255,
            255, 255, u32, u32, u32, u32, u32, u32, 255,
            due_max, due_max,
        ],
        "measurements": {},
        "quality": {},
        "power": {"source": "unknown", "low": False},
        "phase4_lab": True,
    }
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    assert len(encoded) <= 1024
    # Current conservative worst case is 998 bytes, leaving 26 bytes.
    # Keep a non-trivial guard band while preserving the hard 1024-byte limit.
    assert 1024 - len(encoded) >= 16
