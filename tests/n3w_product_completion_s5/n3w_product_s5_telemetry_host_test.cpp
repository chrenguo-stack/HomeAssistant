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
    if (peer_sink_ == nullptr || data == nullptr || size == 0) return DriverError::SEND_FAILED;
    EspNowReceiveMetadata metadata;
    metadata.channel = channel_ == 0 ? 6 : channel_;
    metadata.rssi_dbm = -45;
    peer_sink_->on_s5_telemetry_datagram(mac_, data, size, metadata);
    return DriverError::NONE;
  }

 private:
  MacAddress mac_{};
  ProductS5TelemetrySink *peer_sink_{nullptr};
  uint8_t channel_{6};
};

LinkKey link_key() {
  LinkKey key{};
  for (std::size_t i = 0; i < key.size(); ++i) key[i] = static_cast<uint8_t>(0x31 + i);
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

}  // namespace

int main() {
  const MacAddress child_mac{0x02, 0x11, 0x22, 0x33, 0x44, 0x55};
  const MacAddress relay_mac{0x02, 0xaa, 0xbb, 0xcc, 0xdd, 0xee};
  const LinkKey lmk = link_key();

  NetworkPort child_radio(child_mac);
  NetworkPort relay_radio(relay_mac);
  CaptureForward forward;
  ProductS5TelemetryBridge child(
      ProductS5TelemetryRole::CHILD, "node_child01", &child_radio);
  ProductS5TelemetryBridge relay(
      ProductS5TelemetryRole::RELAY, "node_relay01", &relay_radio, &forward);
  child_radio.connect(&relay);
  relay_radio.connect(&child);

  child.on_s5_peer_installed(relay_mac, lmk, 6);
  relay.on_s5_peer_installed(child_mac, lmk, 6);
  assert(relay.set_relay_child_node_id("node_child01"));

  RelayHeader header;
  header.gateway_id = "node_relay01";
  header.node_id = "node_child01";
  header.key_epoch = 3;
  header.boot_id = "boot_0000000000000001";
  header.seq = 42;

  const std::string telemetry =
      R"({"schema":"gh.telemetry/1","node_id":"node_child01","boot_id":"boot_0000000000000001","seq":42,"uptime_ms":1234,"cap_hash":"cap_hash_001","measurements":{"air_temperature_c":24.5},"quality":{"air_temperature_c":"ok"},"power":{"source":"main","low":false}})";
  RelayFrame frame;
  const ApplicationKeyState key = application_key();
  assert(build_relay_frame(header, key, telemetry, &frame) == CoreError::NONE);

  assert(child.send_relay_frame(frame, 1000) == ProductS5TelemetryError::NONE);
  assert(forward.count == 1);
  assert(forward.last.header.schema == "gh.relay/1");
  assert(forward.last.header.transport == "esp_now");
  assert(forward.last.header.gateway_id == "node_relay01");
  assert(forward.last.header.node_id == "node_child01");
  assert(forward.last.header.boot_id == header.boot_id);
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

  child.on_s5_peer_removed(relay_mac);
  relay.on_s5_peer_removed(child_mac);
  assert(!child.active_peer());
  assert(!relay.active_peer());

  std::cout << "S5_RELIABLE_TELEMETRY_BRIDGE=PASS\n";
  return 0;
}
