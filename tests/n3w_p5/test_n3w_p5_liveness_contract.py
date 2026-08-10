from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P5_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_p5_lab/n3w_p5_lab.cpp"
P5_H = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_p5_lab/n3w_p5_lab.h"
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


def test_connected_sta_channel_is_reused_without_radio_init_thrash() -> None:
    source = P5_CPP.read_text(encoding="utf-8")
    header = P5_H.read_text(encoding="utf-8")
    body = function_body(
        source,
        "bool GreenhouseN3wP5Lab::ensure_radio_ready_()",
        "void GreenhouseN3wP5Lab::loop()",
    )

    retry_gate = body.index("now - last_radio_attempt_ms_ < kRadioRetryIntervalMs")
    attempt_record = body.index("last_radio_attempt_ms_ = now")
    current_channel = body.index("esp_wifi_get_channel")
    initialize = body.index("driver_.initialize")
    add_peer = body.index("driver_.add_encrypted_peer")

    assert retry_gate < attempt_record < current_channel < initialize < add_peer
    assert "driver_.set_channel" not in body
    assert "driver_.shutdown()" in body
    assert "ESP-NOW initialization failed error=%u" in body
    assert "ESP-NOW peer configuration failed error=%u" in body
    assert "bool radio_attempted_{false};" in header
    assert "uint64_t last_radio_attempt_ms_{0};" in header


def test_cached_resend_requires_radio_ready_and_reports_exact_outcome() -> None:
    source = P5_CPP.read_text(encoding="utf-8")
    header = P5_H.read_text(encoding="utf-8")
    body = function_body(
        source,
        "bool GreenhouseN3wP5Lab::resend_last_datagrams_(bool reverse)",
        "void GreenhouseN3wP5Lab::handle_lab_command",
    )
    handler = function_body(
        source,
        "void GreenhouseN3wP5Lab::handle_lab_command",
        "}  // namespace esphome::greenhouse_n3w_p5_lab",
    )

    empty_cache = body.index("last_datagrams_.empty()")
    radio_ready = body.index("ensure_radio_ready_()")
    send_cached = body.index("send_datagrams_(last_datagrams_, reverse)")
    assert empty_cache < radio_ready < send_cached
    assert "reason=empty_cache" in body
    assert "reason=radio_not_ready" in body
    assert "result=queued" in body
    assert "reason=driver_send" in body
    assert 'command == "RESEND"' in handler
    assert "resend_last_datagrams_(false)" in handler
    assert 'command == "REORDER"' in handler
    assert "resend_last_datagrams_(true)" in handler
    assert "bool resend_last_datagrams_(bool reverse);" in header
    assert "boot_.take_sequence" not in body
    assert "build_relay_frame" not in body
    assert "desired_path_" not in body


def test_direct_publish_commits_exact_relay_datagrams_only_after_mqtt_success() -> None:
    source = P5_CPP.read_text(encoding="utf-8")
    header = P5_H.read_text(encoding="utf-8")
    direct = function_body(
        source,
        "bool GreenhouseN3wP5Lab::publish_direct_",
        "ApplicationKeyState *GreenhouseN3wP5Lab::active_key_",
    )
    cache = function_body(
        source,
        "bool GreenhouseN3wP5Lab::build_relay_datagrams_",
        "void GreenhouseN3wP5Lab::flush_relay_cache_",
    )

    build = direct.index(
        "build_relay_datagrams_(seq, telemetry, nullptr, &pending_datagrams)"
    )
    publish = direct.index("global_mqtt_client->publish")
    publish_failure = direct.index("return false", publish)
    commit = direct.index("last_datagrams_ = std::move(pending_datagrams)")
    assert build < publish < publish_failure < commit
    assert "(void) seq" not in direct
    assert "driver_.send" not in direct
    assert "cache_.enqueue" not in direct

    assert (
        "build_relay_frame(header, *active_key_(), telemetry, &cached_frame)" in cache
    )
    assert "header.seq = seq" in cache
    assert "fragment_relay_frame(cached_frame, &pending_datagrams)" in cache
    assert "*datagrams = std::move(pending_datagrams)" in cache
    assert "last_datagrams_" not in cache
    assert "driver_.send" not in cache
    assert "cache_.enqueue" not in cache
    assert "bool build_relay_datagrams_(uint32_t seq" in header


def test_relay_publish_reuses_cache_priming_then_enqueues_for_normal_retry() -> None:
    source = P5_CPP.read_text(encoding="utf-8")
    relay = function_body(
        source,
        "bool GreenhouseN3wP5Lab::publish_relay_",
        "bool GreenhouseN3wP5Lab::build_relay_datagrams_",
    )

    build = relay.index(
        "build_relay_datagrams_(seq, telemetry, &frame, &pending_datagrams)"
    )
    enqueue = relay.index("cache_.enqueue(frame, now_ms_())")
    commit = relay.index("last_datagrams_ = std::move(pending_datagrams)")
    flush = relay.index("flush_relay_cache_()")
    assert build < enqueue < commit < flush


def test_async_espnow_delivery_failure_is_deferred_out_of_wifi_callback() -> None:
    source = P5_CPP.read_text(encoding="utf-8")
    callback = function_body(
        source,
        "void GreenhouseN3wP5Lab::on_espnow_send_result",
        "void GreenhouseN3wP5Lab::process_rx_",
    )
    processor = function_body(
        source,
        "void GreenhouseN3wP5Lab::process_tx_",
        "void GreenhouseN3wP5Lab::process_child_packet_",
    )
    header = P5_H.read_text(encoding="utf-8")

    assert "xQueueSend(tx_queue_" in callback
    assert "ESP_LOG" not in callback
    assert "++send_failures_" not in callback
    assert "xQueueReceive(tx_queue_" in processor
    assert "++send_failures_" in processor
    assert "ESP-NOW delivery callback failed total=%u" in processor
    assert "QueueHandle_t tx_queue_{nullptr};" in header


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
