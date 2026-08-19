#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>

#include "esphome/components/greenhouse_n3w_core/n3w_core.h"
#include "esphome/components/greenhouse_n3w_product_runtime/n3w_product_s5_telemetry.h"

using namespace esphome::greenhouse_n3w_core;
using namespace esphome::greenhouse_n3w_product_runtime;

namespace {

class CaptureForward final : public RelayForwardSink {
 public:
  bool accept_for_forwarding(const RelayFrame &frame) override {
    ++count;
    last = frame;
    return true;
  }

  int count{0};
  RelayFrame last{};
};

class NetworkPort final : public ProductRuntimeRadioPort {
 public:
  explicit NetworkPort(MacAddress mac) : mac_(mac) {}

  void connect(ProductS5TelemetrySink *peer_sink) { peer_sink_ = peer_sink; }

  DriverError initialize(EspNowEventSink *, const LinkKey &) override {
    return DriverError::NONE;
  }
  void shutdown() override {}
  DriverError set_channel(uint8_t channel) override {
    channel_ = channel;
    return DriverError::NONE;
  }
  DriverError prepare_broadcast_peer(uint8_t channel) override {
    channel_ = channel;
    return DriverError::NONE;
  }
  DriverError add_encrypted_peer(const MacAddress &, const LinkKey &, uint8_t channel) override {
    channel_ = channel;
    return DriverError::NONE;
  }
  DriverError remove_peer(const MacAddress &) override { return DriverError::NONE; }
  DriverError send_broadcast(const uint8_t *, std::size_t) override {
    return DriverError::NONE;
  }
  DriverError send_peer(
      const MacAddress &,
      const uint8_t *data,
      std::size_t size) override {
    ++send_count;
    if (fail_send || peer_sink_ == nullptr || data == nullptr || size == 0)
      return DriverError::SEND_FAILED;
    EspNowReceiveMetadata metadata;
    metadata.channel = channel_ == 0 ? 6 : channel_;
    metadata.rssi_dbm = -45;
    peer_sink_->on_s5_telemetry_datagram(mac_, data, size, metadata);
    return DriverError::NONE;
  }

  bool fail_send{false};
  int send_count{0};

 private:
  MacAddress mac_{};
  ProductS5TelemetrySink *peer_sink_{nullptr};
  uint8_t channel_{6};
};

LinkKey link_key(uint8_t seed = 0x31) {
  LinkKey key{};
  for (std::size_t i = 0; i < key.size(); ++i) key[i] = static_cast<uint8_t>(seed + i);
  return key;
}

ApplicationKeyState application_key() {
  ApplicationKeyState state;
  state.lifecycle = KeyLifecycle::ACTIVE;
  state.key_epoch = 3;
  state.session_floor = 1;
  for (std::size_t i = 0; i < state.key.size(); ++i)
    state.key[i] = static_cast<uint8_t>(0x80 + i);
  assert(state.valid_for_encrypt());
  return state;
}

RelayFrame relay_frame(
    const std::string &gateway_id,
    uint32_t seq,
    const ApplicationKeyState &key) {
  RelayHeader header;
  header.gateway_id = gateway_id;
  header.node_id = "node_child01";
  header.key_epoch = 3;
  header.boot_id = "boot_0000000000000001";
  header.seq = seq;
  const std::string telemetry =
      std::string("{\"schema\":\"gh.telemetry/1\",\"node_id\":\"node_child01\",") +
      "\"boot_id\":\"boot_0000000000000001\",\"seq\":" + std::to_string(seq) +
      ",\"uptime_ms\":1234,\"cap_hash\":\"cap_hash_001\"," +
      "\"measurements\":{\"air_temperature_c\":24.5}," +
      "\"quality\":{\"air_temperature_c\":\"ok\"}," +
      "\"power\":{\"source\":\"main\",\"low\":false}}";
  RelayFrame frame;
  assert(build_relay_frame(header, key, telemetry, &frame) == CoreError::NONE);
  return frame;
}

}  // namespace

int main() {
  const MacAddress child_mac{0x02, 0x11, 0x22, 0x33, 0x44, 0x55};
  const MacAddress relay_mac{0x02, 0xaa, 0xbb, 0xcc, 0xdd, 0xee};
  const MacAddress relay2_mac{0x02, 0xab, 0xbc, 0xcd, 0xde, 0xef};
  const LinkKey lmk = link_key();
  const ApplicationKeyState key = application_key();

  NetworkPort child_radio(child_mac);
  NetworkPort relay_radio(relay_mac);
  CaptureForward forward;
  ProductS5TelemetryBridge child(
      ProductS5TelemetryRole::CHILD, "node_child01", &child_radio);
  ProductS5TelemetryBridge relay(
      ProductS5TelemetryRole::RELAY, "node_relay01", &relay_radio, &forward);
  child_radio.connect(&relay);
  relay_radio.connect(&child);

  // Link-layer peer installation alone is insufficient. The Manager-verified
  // node identity must be bound to the same MAC before reliable telemetry is
  // allowed in either direction.
  child.on_s5_peer_installed(relay_mac, lmk, 6);
  relay.on_s5_peer_installed(child_mac, lmk, 6);
  assert(child.active_lmk_resident());
  assert(relay.active_lmk_resident());
  assert(!child.identity_bound());
  assert(!relay.identity_bound());
  const RelayFrame frame = relay_frame("node_relay01", 42, key);
  assert(child.send_relay_frame(frame, 1000) == ProductS5TelemetryError::NOT_READY);
  child.on_s5_peer_identity_bound(relay_mac, "node_relay01");
  relay.on_s5_peer_identity_bound(child_mac, "node_child01");
  assert(child.identity_bound());
  assert(relay.identity_bound());
  assert(child.active_peer_node_id() == "node_relay01");
  assert(relay.active_peer_node_id() == "node_child01");

  // Once Manager authorization binds identity to an installed MAC, that
  // binding is immutable until peer removal. Reusing the same MAC with a
  // different NODE_ID must fail closed rather than silently changing the
  // gateway/child identity attached to the active LMK.
  child.on_s5_peer_identity_bound(relay_mac, "node_relay99");
  assert(child.last_error() == ProductS5TelemetryError::STATE_REJECTED);
  assert(child.active_peer_node_id() == "node_relay01");
  relay.on_s5_peer_identity_bound(child_mac, "node_child99");
  assert(relay.last_error() == ProductS5TelemetryError::STATE_REJECTED);
  assert(relay.active_peer_node_id() == "node_child01");

  assert(child.send_relay_frame(frame, 1000) == ProductS5TelemetryError::NONE);
  assert(forward.count == 1);
  assert(forward.last.header.schema == "gh.relay/1");
  assert(forward.last.header.transport == "esp_now");
  assert(forward.last.header.gateway_id == "node_relay01");
  assert(forward.last.header.node_id == "node_child01");
  assert(forward.last.header.boot_id == "boot_0000000000000001");
  assert(forward.last.header.seq == 42);
  assert(forward.last.header.key_epoch == 3);
  assert(forward.last.ciphertext == frame.ciphertext);
  assert(child.pending_frames() == 0);

  std::string serialized;
  assert(serialize_relay_frame_json(forward.last, &serialized) == CoreError::NONE);
  assert(serialized.find("\"schema\":\"gh.relay/1\"") != std::string::npos);
  assert(serialized.find("\"gateway_id\":\"node_relay01\"") != std::string::npos);
  assert(serialized.find("\"node_id\":\"node_child01\"") != std::string::npos);
  assert(serialized.find("\"seq\":42") != std::string::npos);

  const MacAddress stranger{0x02, 0x99, 0x88, 0x77, 0x66, 0x55};
  const uint8_t fake_fragment[] = {'G', 'H', 1, 4, 0};
  EspNowReceiveMetadata metadata;
  metadata.channel = 6;
  relay.on_s5_telemetry_datagram(
      stranger, fake_fragment, sizeof(fake_fragment), metadata);
  assert(forward.count == 1);

  // Exercise retry-cache lifecycle. A frame that failed on Relay-1 remains
  // queued only while Relay-1 is the active authorized identity. Peer removal
  // clears the cache and LMK. A later Relay-2 authorization cannot inherit or
  // resend Relay-1-bound ciphertext.
  child_radio.fail_send = true;
  const RelayFrame old_gateway_frame = relay_frame("node_relay01", 43, key);
  assert(child.send_relay_frame(old_gateway_frame, 2000) ==
         ProductS5TelemetryError::RADIO_FAILED);
  assert(child.pending_frames() == 1);
  const int sends_before_remove = child_radio.send_count;

  child.on_s5_peer_removed(relay_mac);
  relay.on_s5_peer_removed(child_mac);
  assert(!child.active_peer());
  assert(!relay.active_peer());
  assert(!child.active_lmk_resident());
  assert(!relay.active_lmk_resident());
  assert(!child.identity_bound());
  assert(!relay.identity_bound());
  assert(child.pending_frames() == 0);

  child_radio.fail_send = false;
  child.on_s5_peer_installed(relay2_mac, link_key(0x51), 6);
  child.on_s5_peer_identity_bound(relay2_mac, "node_relay02");
  assert(child.active_peer());
  assert(child.identity_bound());
  assert(child.active_peer_node_id() == "node_relay02");
  assert(child.tick(3000) == ProductS5TelemetryError::NONE);
  assert(child_radio.send_count == sends_before_remove);
  assert(child.send_relay_frame(old_gateway_frame, 3001) ==
         ProductS5TelemetryError::FRAME_REJECTED);
  assert(child.pending_frames() == 0);

  // New data must be rendered for the currently authorized gateway identity;
  // it is not a re-homed copy of the old gateway-bound RelayFrame.
  const RelayFrame relay2_frame = relay_frame("node_relay02", 44, key);
  assert(child.send_relay_frame(relay2_frame, 3002) == ProductS5TelemetryError::NONE ||
         child.last_error() == ProductS5TelemetryError::RADIO_FAILED);

  child.on_s5_peer_removed(relay2_mac);
  assert(!child.active_lmk_resident());
  assert(!child.identity_bound());
  assert(child.pending_frames() == 0);

  std::cout << "S5_RELIABLE_LINK_LIFECYCLE_GATEWAY_BINDING=PASS\n";
  return 0;
}
