from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRANSPORT_HEADER = (
    ROOT
    / "firmware"
    / "esphome_rc"
    / "components"
    / "greenhouse_n3w_s5_manager_transport"
    / "n3w_product_s5_manager_transport.h"
)
COMPONENT_CPP = (
    ROOT
    / "firmware"
    / "esphome_rc"
    / "components"
    / "greenhouse_n3w_s5_manager_transport"
    / "n3w_product_s5_manager_component.cpp"
)


def test_relay_mqtt_diagnostic_is_state_only_and_non_mutating() -> None:
    header = TRANSPORT_HEADER.read_text(encoding="utf-8")
    component = COMPONENT_CPP.read_text(encoding="utf-8")

    # The seam exposes only two booleans needed to classify the live boundary.
    assert "bool message_bus_connected()" in header
    assert "bool direct_liveness_sent() const" in header
    assert "return started_ && bus_ != nullptr && bus_->connected();" in header

    # The diagnostic must observe the existing authority tick, not create a
    # second publish path or a second protocol.
    assert component.count("transport_->authority_now_ms(&authority_now)") == 1
    assert "transport_->maintain_direct_liveness()" not in component
    assert "publish_message(" not in component
    assert "subscribe(" not in component

    required_markers = (
        "S5 MQTT diagnostic bus_connected=%s liveness_sent=%s authority_ready=%s",
        "S5 MQTT diagnostic first_direct_liveness_publish=success",
        "S5 MQTT diagnostic first_direct_liveness_publish=failed ",
        "S5 MQTT diagnostic authority_time_ready=true",
    )
    for marker in required_markers:
        assert marker in component

    # No credential, payload, peer, MAC, or node identity is emitted by the new
    # diagnostic log statements.
    diagnostic_lines = [
        line.strip()
        for line in component.splitlines()
        if "S5 MQTT diagnostic" in line
    ]
    joined = "\n".join(diagnostic_lines).lower()
    for forbidden in (
        "application_key",
        "password",
        "secret",
        "payload",
        "grant_mac",
        "peer_mac",
        "node_id",
        "system_id",
        "lmk",
        "pmk",
    ):
        assert forbidden not in joined


def test_relay_mqtt_diagnostic_preserves_existing_fail_closed_authority_flow() -> None:
    component = COMPONENT_CPP.read_text(encoding="utf-8")

    authority_call = component.index("transport_->authority_now_ms(&authority_now)")
    grant_delivery = component.index("queued_child_grant_.has_value()")
    assert authority_call < grant_delivery

    # The diagnostic does not force authority readiness or synthesize an epoch.
    assert "authority_now =" not in component[authority_call + 1 : grant_delivery]
    assert "authority_ready = true" not in component
