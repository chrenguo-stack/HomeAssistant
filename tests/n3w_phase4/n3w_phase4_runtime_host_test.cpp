#include <cassert>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>

#include "n3w_simple_product_runtime.h"

using namespace esphome::greenhouse_n3w_core;

namespace {

struct FakeClock final : SimpleProductClock {
  uint64_t value{1000};
  uint64_t now_ms() const override { return value; }
};

struct FakeRandom final : SimpleProductRandom {
  uint8_t seed{1};
  bool fill(uint8_t *data, std::size_t size) override {
    if (data == nullptr || size == 0) return false;
    for (std::size_t i = 0; i < size; ++i) data[i] = seed++;
    return true;
  }
};

struct InstalledPeer {
  MacAddress mac{};
  LinkKey lmk{};
  uint8_t channel{0};
};

struct FakePort final : SimpleProductPort {
  uint8_t channel{0};
  std::vector<std::vector<uint8_t>> broadcasts;
  std::vector<std::pair<MacAddress, std::vector<uint8_t>>> encrypted;
  std::vector<InstalledPeer> installed;
  std::vector<MacAddress> removed;
  std::vector<std::pair<std::string, std::string>> direct;
  std::vector<std::pair<std::string, std::string>> relay;
  bool direct_success{true};

  bool set_radio_channel(uint8_t value) override {
    channel = value;
    return valid_radio_channel(value);
  }
  bool broadcast_control(const uint8_t *data, std::size_t size) override {
    broadcasts.emplace_back(data, data + size);
    return true;
  }
  bool install_encrypted_peer(
      const MacAddress &mac,
      const LinkKey &lmk,
      uint8_t value) override {
    installed.push_back({mac, lmk, value});
    return true;
  }
  bool remove_peer(const MacAddress &mac) override {
    removed.push_back(mac);
    return true;
  }
  bool send_encrypted_peer(
      const MacAddress &mac,
      const uint8_t *data,
      std::size_t size) override {
    encrypted.push_back({mac, std::vector<uint8_t>(data, data + size)});
    return true;
  }
  bool publish_direct(const std::string &topic, const std::string &payload) override {
    direct.push_back({topic, payload});
    return direct_success;
  }
  bool publish_relay(const std::string &topic, const std::string &payload) override {
    relay.push_back({topic, payload});
    return true;
  }
};

ProvisionedPeerStateV2 make_state(const std::string &node_id, uint8_t app_key_byte) {
  ProvisionedPeerStateV2 state;
  state.system_id = "gh-system-01";
  state.node_id = node_id;
  state.peer_trust_generation = 7;
  state.system_peer_key.fill(0xA5);
  state.n3w_key_epoch = 3;
  state.n3w_application_key.fill(app_key_byte);
  assert(state.valid());
  return state;
}

}  // namespace

int main() {
  FakeClock child_clock;
  FakeClock relay_clock;
  FakeRandom child_random;
  FakeRandom relay_random;
  FakePort child_port;
  FakePort relay_port;

  const MacAddress child_mac{0x02, 0x00, 0x00, 0x00, 0x00, 0x0B};
  const MacAddress relay_mac{0x02, 0x00, 0x00, 0x00, 0x00, 0x0A};
  const auto child_state = make_state("node_child", 0x11);
  const auto relay_state = make_state("node_relay", 0x22);

  SimpleProductRuntime child(&child_port, &child_clock, &child_random);
  SimpleProductRuntime relay(&relay_port, &relay_clock, &relay_random);
  assert(child.start(child_state, child_mac, 6) == SimpleProductError::NONE);
  assert(relay.start(relay_state, relay_mac, 6) == SimpleProductError::NONE);

  const std::string direct_json =
      R"({"schema":"gh.telemetry/1","node_id":"node_child","boot_id":"boot_0000000000000001","seq":1})";
  assert(child.send_telemetry(direct_json, "boot_0000000000000001", 1) == SimpleProductError::NONE);
  assert(child_port.direct.size() == 1);

  child_port.direct_success = false;
  for (uint32_t seq = 2; seq <= 4; ++seq) {
    const SimpleProductError result = child.send_telemetry(
        direct_json, "boot_0000000000000001", seq);
    assert(result == SimpleProductError::MQTT_FAILED || result == SimpleProductError::NONE);
  }
  assert(child.path_state() == LocalPathState::DISCOVERY);
  assert(child_port.channel == 6);

  relay_clock.value = 2000;
  assert(relay.tick() == SimpleProductError::NONE);
  assert(!relay_port.broadcasts.empty());
  const auto discovery = relay_port.broadcasts.back();
  assert(child.on_radio_receive(relay_mac, discovery.data(), discovery.size(), 6) ==
         SimpleProductError::NONE);
  assert(!child_port.broadcasts.empty());

  const auto challenge = child_port.broadcasts.back();
  assert(relay.on_radio_receive(child_mac, challenge.data(), challenge.size(), 6) ==
         SimpleProductError::NONE);
  assert(relay.relay_child_count() == 1);
  assert(!relay_port.broadcasts.empty());

  const auto accept = relay_port.broadcasts.back();
  assert(child.on_radio_receive(relay_mac, accept.data(), accept.size(), 6) ==
         SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::RELAY_ACTIVE);
  assert(child.active_relay().has_value());
  assert(!child_port.installed.empty());
  assert(!relay_port.installed.empty());
  assert(child_port.installed.back().lmk == relay_port.installed.back().lmk);

  child_port.direct_success = true;
  const std::string relay_json =
      R"({"schema":"gh.telemetry/1","node_id":"node_child","boot_id":"boot_0000000000000001","seq":5})";
  assert(child.send_telemetry(relay_json, "boot_0000000000000001", 5) ==
         SimpleProductError::NONE);
  assert(child_port.encrypted.size() == 1);
  const auto &encoded = child_port.encrypted.back().second;
  assert(relay.on_radio_receive(child_mac, encoded.data(), encoded.size(), 6) ==
         SimpleProductError::NONE);
  assert(relay_port.relay.size() == 1);
  assert(relay_port.relay.back().first ==
         "gh/v1/gh-system-01/ingress/gateway/node_relay/node_child/frame");
  assert(relay_port.relay.back().second.find("N3W2") != std::string::npos ||
         !relay_port.relay.back().second.empty());

  assert(child.note_direct_recovery_probe(true) == SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::RELAY_ACTIVE);
  assert(child.note_direct_recovery_probe(true) == SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::DIRECT);
  assert(!child.active_relay().has_value());

  return 0;
}
