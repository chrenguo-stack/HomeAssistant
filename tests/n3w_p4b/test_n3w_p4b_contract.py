from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "docs/decisions/n3w-esp32c6-espnow-radio-runtime-stage-entry.json"
LINK = ROOT / "protocols/transport/gh-n3w-espnow-link-v1.md"
RADIO_H = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_radio.h"
RADIO_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_radio.cpp"
DRIVER_CPP = (
    ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_espnow_driver.cpp"
)
INIT_PY = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/__init__.py"
COMPONENT_H = (
    ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/greenhouse_n3w_core.h"
)


def test_stage_entry_binds_exact_authorization_and_main() -> None:
    doc = json.loads(STAGE.read_text(encoding="utf-8"))
    assert doc["authorization_gate"] == (
        "D1-N3W-ESP32C6-SINGLEHOP-ESP-NOW-RADIO-RUNTIME-"
        "HOSTONLY-AND-COMPILE-DEVELOPMENT-20260807-01"
    )
    assert doc["base_ref"] == "main"
    assert doc["base_sha"] == "4f9242efc8c1b4776e4cc46c66ebc85b6e4ffe57"
    assert doc["preserved_pr"] == 276
    assert doc["preserved_pr_head"] == ("239ea594c643d4990d449187f8b0cabae619e3d7")
    assert doc["mode"] == "HOST_ONLY_AND_COMPILE_ONLY"
    assert doc["force_push"] is False
    assert doc["p4a_dependency"]["merged_pr"] == 290
    assert doc["p4a_dependency"]["merge_commit_sha"] == doc["base_sha"]
    assert all(value is False for value in doc["safety_boundary"].values())


def test_p4b_contract_is_single_hop_and_keeps_application_key_off_relay() -> None:
    doc = json.loads(STAGE.read_text(encoding="utf-8"))["p4b_contract"]
    assert doc["topology"] == "child_to_single_wifi_relay"
    assert doc["mesh"] is False
    assert doc["multihop"] is False
    assert doc["second_node_id"] is False
    assert doc["relay_holds_child_application_key"] is False
    assert doc["manager_remains_canonical_publisher"] is True
    assert doc["espnow_unicast_encryption"] is True
    assert doc["discovery_advertisement_trusted"] is False
    assert doc["discovery_requires_exact_gateway_mac_binding"] is True
    assert doc["authenticated_probe_required_before_relay_active"] is True
    assert doc["max_datagram_bytes"] == 240
    assert doc["fragment_payload_bytes"] == 180
    assert doc["max_application_ciphertext_bytes"] == 1024
    assert doc["max_fragments"] == 6
    assert doc["production_mqtt_forwarding_wired"] is False
    assert doc["product_firmware_runtime_activated"] is False


def test_radio_core_freezes_fragment_receipt_and_path_semantics() -> None:
    header = RADIO_H.read_text(encoding="utf-8")
    source = RADIO_CPP.read_text(encoding="utf-8")
    combined = header + "\n" + source
    required = (
        "kEspNowDatagramLimit = 240",
        "kDataFragmentPayloadBytes = 180",
        "RelayPeerBinding",
        "ChildPeerBinding",
        "DiscoveryAdvertisement",
        "RelayReassembler",
        "RelayIngressController",
        "RelayForwardSink",
        "ChildRelayCache",
        "ChannelScanPlan",
        "LocalPathController",
        "ACCEPTED_FOR_FORWARDING",
        '"gh.n3w-control-v1"',
    )
    for token in required:
        assert token in combined
    assert "RelayForwardSink" in combined
    assert "aes256gcm_decrypt" not in combined
    assert "ApplicationKeyState" not in DRIVER_CPP.read_text(encoding="utf-8")


def test_esp_idf_driver_has_real_compile_time_radio_calls_but_no_product_activation() -> (
    None
):
    driver = DRIVER_CPP.read_text(encoding="utf-8")
    for token in (
        "esp_netif_init()",
        "esp_event_loop_create_default()",
        "esp_wifi_init(&config)",
        "esp_wifi_set_storage(WIFI_STORAGE_RAM)",
        "esp_wifi_set_mode(WIFI_MODE_STA)",
        "esp_wifi_start()",
        "esp_now_init()",
        "esp_now_set_pmk(",
        "esp_now_register_recv_cb(",
        "esp_now_register_send_cb(",
        "esp_now_add_peer(",
        "esp_now_mod_peer(",
        "esp_now_del_peer(",
        "esp_now_send(",
        "esp_wifi_set_channel(",
        "peer.encrypt = true",
        "esp_now_send_info_t",
    ):
        assert token in driver

    init_source = INIT_PY.read_text(encoding="utf-8")
    assert 'include_builtin_idf_component("esp_event")' in init_source
    assert 'include_builtin_idf_component("esp_netif")' in init_source
    assert 'include_builtin_idf_component("esp_wifi")' in init_source
    component = COMPONENT_H.read_text(encoding="utf-8")
    assert "void setup() override {}" in component
    assert "void loop() override {}" in component

    combined = driver + "\n" + init_source + "\n" + component
    for forbidden in (
        "GH_N3W_RUNTIME_ENABLED=true",
        "esphome run",
        "esptool",
        "homeassistant/#",
        "gh/v1/+/state/#",
        "mqtt_password",
        "esp_wifi_connect(",
    ):
        assert forbidden not in combined


def test_espnow_driver_owns_an_isolated_wifi_lifecycle() -> None:
    driver = DRIVER_CPP.read_text(encoding="utf-8")
    ordered_start = (
        "esp_netif_init()",
        "esp_event_loop_create_default()",
        "esp_wifi_init(&config)",
        "esp_wifi_set_storage(WIFI_STORAGE_RAM)",
        "esp_wifi_set_mode(WIFI_MODE_STA)",
        "esp_wifi_start()",
        "esp_now_init()",
    )
    positions = [driver.index(token) for token in ordered_start]
    assert positions == sorted(positions)
    assert "wifi_owned_ = true" in driver
    assert "stop_owned_wifi_();" in driver
    assert "esp_wifi_connect(" not in driver
    shutdown = driver[driver.index("void EspNowDriver::shutdown()") :]
    assert shutdown.index("esp_now_deinit()") < shutdown.index("stop_owned_wifi_()")


def test_link_contract_states_ack_is_local_not_manager_acceptance() -> None:
    text = LINK.read_text(encoding="utf-8")
    assert "single-hop" in text
    assert "Mesh" in text
    assert "untrusted hint" in text
    assert "gateway_id" in text
    assert "source MAC" in text
    assert "HMAC-SHA-256" in text
    assert "<= 240" in text
    assert "180" in text
    assert "1024" in text
    assert "6" in text
    assert "accepted the frame for forwarding" in text
    assert "not a Manager canonical-acceptance acknowledgment" in text
    assert "same already-encrypted fragments" in text
    assert "distinct from Manager path lease arbitration" in text
