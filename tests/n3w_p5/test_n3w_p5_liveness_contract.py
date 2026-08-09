from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P5_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_p5_lab/n3w_p5_lab.cpp"
RADIO_H = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_radio.h"


def function_body(text: str, signature: str, next_signature: str) -> str:
    start = text.index(signature)
    end = text.index(next_signature, start)
    return text[start:end]


def test_sequence_allocation_is_gated_by_transport_liveness_and_cache_capacity() -> (
    None
):
    text = P5_CPP.read_text(encoding="utf-8")
    body = function_body(
        text,
        "void GreenhouseN3wP5Lab::maybe_publish_()",
        "std::string GreenhouseN3wP5Lab::build_telemetry_",
    )

    take = body.index("boot_.take_sequence(&seq)")
    assert body.index("cache_.full()") < take
    assert body.index("!relay_authenticated_") < take
    assert body.index("!radio_ready_") < take
    assert body.index("mqtt::global_mqtt_client == nullptr") < take
    assert body.index("!mqtt::global_mqtt_client->is_connected()") < take


def test_consumed_sequence_is_rate_limited_even_if_publish_fails() -> None:
    text = P5_CPP.read_text(encoding="utf-8")
    body = function_body(
        text,
        "void GreenhouseN3wP5Lab::maybe_publish_()",
        "std::string GreenhouseN3wP5Lab::build_telemetry_",
    )

    take = body.index("boot_.take_sequence(&seq)")
    rate_limit = body.index("last_publish_ms_ = now;")
    build = body.index("build_telemetry_(seq)")
    direct = body.index("publish_direct_(seq, telemetry)")
    relay = body.index("publish_relay_(seq, telemetry)")

    assert take < rate_limit < build < direct
    assert rate_limit < relay
    assert "if (accepted) last_publish_ms_ = now" not in body


def test_retry_exhaustion_discards_exact_cache_entry() -> None:
    text = P5_CPP.read_text(encoding="utf-8")
    body = function_body(
        text,
        "void GreenhouseN3wP5Lab::flush_relay_cache_()",
        "bool GreenhouseN3wP5Lab::send_datagrams_",
    )

    attempt = body.index("cache_.note_attempt(session, seq, now)")
    exhausted = body.index("RadioError::RETRY_EXHAUSTED")
    discard = body.index("cache_.discard(session, seq)")
    assert attempt < exhausted < discard


def test_relay_sends_explicit_rejected_receipt_without_false_positive_acceptance() -> (
    None
):
    text = P5_CPP.read_text(encoding="utf-8")
    body = function_body(
        text,
        "void GreenhouseN3wP5Lab::process_relay_packet_",
        "bool GreenhouseN3wP5Lab::accept_for_forwarding",
    )

    assert "receipt_ready ||" in body
    assert "error == greenhouse_n3w_core::RadioError::NONE" in body
    assert "receipt.boot_session != 0" in body
    assert "encode_authenticated_receipt_ack" in body
    assert "receipt.status" in body


def test_cache_exports_exact_backpressure_and_discard_primitives() -> None:
    text = RADIO_H.read_text(encoding="utf-8")
    cache = function_body(text, "class ChildRelayCache", "enum class LocalPathState")

    assert "bool full() const" in cache
    assert "entries_.size() >= capacity_" in cache
    assert "bool discard(uint64_t boot_session, uint32_t seq)" in cache
    assert "entries_.erase(it)" in cache


def test_hostonly_repair_does_not_add_physical_execution_tokens() -> None:
    checked = [P5_CPP, RADIO_H]
    forbidden = (
        "esphome run",
        "esptool",
        "pio run --target upload",
        "/dev/cu.",
        "/dev/tty",
        "192.168.68.",
    )
    for path in checked:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text
