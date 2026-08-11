from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P5_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_p5_lab/n3w_p5_lab.cpp"
P5_H = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_p5_lab/n3w_p5_lab.h"


def function_body(text: str, signature: str, next_signature: str) -> str:
    start = text.index(signature)
    end = text.index(next_signature, start)
    return text[start:end]


def test_relay_requires_fresh_authenticated_probe_before_reassembly() -> None:
    source = P5_CPP.read_text(encoding="utf-8")
    header = P5_H.read_text(encoding="utf-8")
    body = function_body(
        source,
        "void GreenhouseN3wP5Lab::process_relay_packet_",
        "bool GreenhouseN3wP5Lab::accept_for_forwarding",
    )

    probe_decode = body.index("decode_authenticated_probe")
    reset = body.index("relay_ingress_.reset()", probe_decode)
    establish = body.index("relay_probe_established_since_boot_ = true", reset)
    probe_ack = body.index("encode_authenticated_probe_ack", establish)
    gate = body.index("if (!relay_probe_established_since_boot_)")
    reassembly = body.index("relay_ingress_.accept_fragment")

    assert probe_decode < reset < establish < probe_ack < gate < reassembly
    assert "Fresh authenticated Child probe established for current Relay boot" in body
    assert "Relay fragment ignored until fresh authenticated Child probe" in body
    assert "bool relay_probe_established_since_boot_{false};" in header


def test_retry_exhaustion_invalidates_child_relay_authentication() -> None:
    source = P5_CPP.read_text(encoding="utf-8")
    header = P5_H.read_text(encoding="utf-8")
    flush = function_body(
        source,
        "void GreenhouseN3wP5Lab::flush_relay_cache_()",
        "bool GreenhouseN3wP5Lab::send_datagrams_",
    )
    invalidate = function_body(
        source,
        "void GreenhouseN3wP5Lab::invalidate_relay_auth_",
        "void GreenhouseN3wP5Lab::maybe_probe_",
    )

    attempt = flush.index("cache_.note_attempt(session, seq, now)")
    exhausted = flush.index("RadioError::RETRY_EXHAUSTED")
    discard = flush.index("cache_.discard(session, seq)")
    invalidate_call = flush.index(
        'invalidate_relay_auth_("receipt_ack_retry_exhausted")'
    )

    assert attempt < exhausted < discard < invalidate_call
    assert "relay_authenticated_ = false;" in invalidate
    assert "++probe_challenge_;" in invalidate
    assert "if (probe_challenge_ == 0) ++probe_challenge_;" in invalidate
    assert "last_probe_ms_ = 0;" in invalidate
    assert "void invalidate_relay_auth_(const char *reason);" in header


def test_path_relay_reuses_the_same_fresh_probe_invalidation_boundary() -> None:
    source = P5_CPP.read_text(encoding="utf-8")
    handler = function_body(
        source,
        "void GreenhouseN3wP5Lab::handle_lab_command",
        "}  // namespace esphome::greenhouse_n3w_p5_lab",
    )

    path_relay = handler.index('command == "PATH RELAY"')
    desired_relay = handler.index("desired_path_ = DesiredPath::RELAY", path_relay)
    invalidate = handler.index('invalidate_relay_auth_("path_relay")', desired_relay)

    assert path_relay < desired_relay < invalidate
    assert "++probe_challenge_;" not in handler[desired_relay:invalidate]
    assert "last_probe_ms_ = 0;" not in handler[desired_relay:invalidate]


def test_child_accepts_probe_ack_only_for_the_current_challenge() -> None:
    source = P5_CPP.read_text(encoding="utf-8")
    body = function_body(
        source,
        "void GreenhouseN3wP5Lab::process_child_packet_",
        "void GreenhouseN3wP5Lab::process_relay_packet_",
    )

    decode = body.index("decode_authenticated_probe_ack")
    challenge = body.index("probe.challenge == probe_challenge_", decode)
    authenticated = body.index("relay_authenticated_ = true", challenge)

    assert decode < challenge < authenticated


def test_relay_restart_command_remains_a_plain_device_restart() -> None:
    source = P5_CPP.read_text(encoding="utf-8")
    handler = function_body(
        source,
        "void GreenhouseN3wP5Lab::handle_lab_command",
        "}  // namespace esphome::greenhouse_n3w_p5_lab",
    )

    restart = handler.index('command == "RESTART"')
    esp_restart = handler.index("esp_restart()", restart)

    assert restart < esp_restart
    restart_branch = handler[restart:]
    assert "PATH RELAY" not in restart_branch
    assert "invalidate_relay_auth_" not in restart_branch


def test_m08_repair_remains_host_only_and_adds_no_execution_tokens() -> None:
    checked = [P5_CPP, P5_H]
    forbidden = (
        "esphome run",
        "esptool",
        "pio run --target upload",
        "espota",
        "/dev/cu.",
        "/dev/tty",
        "192.168.68.",
    )

    for path in checked:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text
