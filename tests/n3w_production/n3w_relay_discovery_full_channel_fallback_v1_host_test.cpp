#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <string>
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
  bool channel_success{true};
  bool legal_success{true};
  bool broadcast_success{true};
  bool install_success{true};
  FakeClock *clock{nullptr};
  uint32_t channel_delay_ms{0};
  uint8_t channel{0};
  std::vector<uint8_t> legal_channels{1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11};
  std::vector<uint8_t> channel_history;
  std::vector<std::vector<uint8_t>> broadcasts;
  std::vector<InstalledPeer> installed;

  bool set_radio_channel(uint8_t value) override {
    if (!channel_success || !valid_radio_channel(value)) return false;
    if (std::find(legal_channels.begin(), legal_channels.end(), value) ==
        legal_channels.end()) {
      return false;
    }
    channel = value;
    channel_history.push_back(value);
    if (clock != nullptr) {
      clock->value += channel_delay_ms;
    }
    return true;
  }

  bool current_legal_channels(std::vector<uint8_t> *channels) override {
    if (!legal_success || channels == nullptr || legal_channels.empty()) {
      return false;
    }
    *channels = legal_channels;
    return true;
  }

  bool broadcast_control(const uint8_t *data, std::size_t size) override {
    if (broadcast_success) broadcasts.emplace_back(data, data + size);
    return broadcast_success;
  }

  bool install_encrypted_peer(
      const MacAddress &mac,
      const LinkKey &lmk,
      uint8_t value) override {
    if (!install_success) return false;
    installed.push_back({mac, lmk, value});
    return true;
  }

  bool remove_peer(const MacAddress &) override { return true; }

  bool send_encrypted_peer(
      const MacAddress &,
      const uint8_t *,
      std::size_t) override {
    return true;
  }

  bool publish_direct(const std::string &, const std::string &) override {
    return true;
  }

  bool publish_relay(const std::string &, const std::string &) override {
    return true;
  }
};

ProvisionedPeerStateV2 make_state(const std::string &node_id) {
  ProvisionedPeerStateV2 state;
  state.system_id = "gh-system-01";
  state.node_id = node_id;
  state.peer_trust_generation = 7;
  state.system_peer_key.fill(0xA5);
  state.n3w_key_epoch = 3;
  state.n3w_application_key.fill(0x44);
  assert(state.valid());
  return state;
}

std::vector<uint8_t> discovery_bytes(
    const std::string &relay_node_id,
    uint8_t channel) {
  SimpleRelayDiscovery discovery;
  discovery.peer_trust_generation = 7;
  discovery.channel = channel;
  discovery.relay_node_id = relay_node_id;
  std::vector<uint8_t> encoded;
  assert(
      encode_simple_relay_discovery(discovery, &encoded) ==
      SimpleRuntimeError::NONE);
  return encoded;
}

SimpleProductError feed_discovery(
    SimpleProductRuntime &runtime,
    const MacAddress &mac,
    const std::string &relay_node_id,
    uint8_t channel,
    int16_t rssi_dbm) {
  const auto encoded = discovery_bytes(relay_node_id, channel);
  return runtime.on_radio_receive(
      mac, encoded.data(), encoded.size(), channel, rssi_dbm);
}

SimplePeerChallenge last_challenge(const FakePort &port) {
  assert(!port.broadcasts.empty());
  SimplePeerChallenge challenge;
  const auto &encoded = port.broadcasts.back();
  assert(
      decode_simple_peer_challenge(
          encoded.data(), encoded.size(), &challenge) ==
      SimpleRuntimeError::NONE);
  return challenge;
}

bool cyclic_scan_hears(
    uint32_t cycle_ms,
    uint32_t channel_start_ms,
    uint32_t channel_end_ms,
    uint32_t advertisement_phase_ms) {
  for (uint32_t k = 0; k < 20; ++k) {
    const uint32_t t = advertisement_phase_ms + k * 2000U;
    const uint32_t phase = t % cycle_ms;
    if (phase >= channel_start_ms && phase < channel_end_ms) return true;
  }
  return false;
}

}

int main() {
  const MacAddress child_mac{0x02, 0x00, 0x00, 0x00, 0x10, 0xC1};
  const MacAddress relay_a{0x02, 0x00, 0x00, 0x00, 0x10, 0xA1};
  const MacAddress relay_b{0x02, 0x00, 0x00, 0x00, 0x10, 0xB1};

  {
    assert(!cyclic_scan_hears(2000, 250, 500, 600));
    assert(!cyclic_scan_hears(1000, 250, 500, 600));
    for (uint32_t phase = 0; phase < 2000; ++phase) {
      assert(phase < 2250);
    }
  }

  {
    FakeClock clock;
    FakeRandom random;
    FakePort port;
    SimpleProductRuntime runtime(&port, &clock, &random);
    assert(
        runtime.start(
            make_state("node_child"),
            child_mac,
            0,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);
    assert(runtime.discovery_scan_stage() == DiscoveryScanStage::FAST);
    assert(runtime.working_channel() == 1);

    clock.value = 7500;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(runtime.discovery_scan_stage() == DiscoveryScanStage::FULL);
    assert(runtime.gateway_selection_busy());
    assert(runtime.working_channel() == 1);

    clock.value = 9750;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(runtime.working_channel() == 2);
    assert(
        feed_discovery(runtime, relay_a, "relay_a", 2, -75) ==
        SimpleProductError::NONE);

    const std::array<uint64_t, 6> to_channel_8{
        12000, 14250, 16500, 18750, 21000, 23250};
    for (uint64_t at : to_channel_8) {
      clock.value = at;
      assert(runtime.tick() == SimpleProductError::NONE);
    }
    assert(runtime.working_channel() == 8);
    assert(
        feed_discovery(runtime, relay_b, "relay_b", 8, -45) ==
        SimpleProductError::NONE);
    assert(port.broadcasts.empty());

    for (uint64_t at : {25500ULL, 27750ULL, 30000ULL}) {
      clock.value = at;
      assert(runtime.tick() == SimpleProductError::NONE);
    }
    assert(runtime.working_channel() == 11);
    clock.value = 32250;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(runtime.challenge_pending());
    assert(last_challenge(port).relay_node_id == "relay_b");

    const std::vector<uint8_t> expected{
        1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 8};
    assert(port.channel_history == expected);
  }

  {
    FakeClock clock;
    FakeRandom random;
    FakePort port;
    SimpleProductRuntime runtime(&port, &clock, &random);
    assert(
        runtime.start(
            make_state("node_child"),
            child_mac,
            2,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);
    assert(runtime.discovery_scan_stage() == DiscoveryScanStage::HINT);
    assert(runtime.working_channel() == 2);
    assert(
        feed_discovery(runtime, relay_a, "relay_a", 2, -60) ==
        SimpleProductError::NONE);
    assert(runtime.discovery_scan_stage() == DiscoveryScanStage::FULL);
    assert(runtime.gateway_selection_busy());
    assert(runtime.working_channel() == 1);
  }

  {
    FakeClock clock;
    FakeRandom random;
    FakePort port;
    port.legal_channels = {1, 2, 3, 4, 5, 6};
    SimpleProductRuntime runtime(&port, &clock, &random);
    assert(
        runtime.start(
            make_state("node_child"),
            child_mac,
            13,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);
    assert(runtime.discovery_scan_stage() == DiscoveryScanStage::FAST);
    assert(runtime.working_channel() == 1);
    clock.value = 7500;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(runtime.discovery_scan_stage() == DiscoveryScanStage::FULL);
    for (uint8_t channel : port.channel_history) {
      assert(channel <= 6);
    }
  }

  {
    FakeClock clock;
    FakeRandom random;
    FakePort port;
    port.legal_success = false;
    SimpleProductRuntime runtime(&port, &clock, &random);
    assert(
        runtime.start(
            make_state("node_child"),
            child_mac,
            0,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::RADIO_FAILED);
    assert(port.channel_history.empty());
  }

  {
    FakeClock clock;
    FakeRandom random;
    FakePort port;
    SimpleProductRuntime runtime(&port, &clock, &random);
    assert(
        runtime.start(
            make_state("node_child"),
            child_mac,
            0,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);
    clock.value = 7500;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(runtime.discovery_scan_stage() == DiscoveryScanStage::FULL);
    clock.value = 40000;
    assert(runtime.tick() == SimpleProductError::RADIO_FAILED);
    assert(!runtime.gateway_selection_busy());
    assert(!runtime.discovery_radio_ready());

    assert(
        runtime.restart_discovery_after_radio_fault() ==
        SimpleProductError::NONE);
    assert(runtime.discovery_scan_stage() == DiscoveryScanStage::FAST);
    assert(runtime.discovery_radio_ready());
    const std::size_t restart_history = port.channel_history.size();
    clock.value += 250;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(port.channel_history.size() == restart_history + 1U);

    port.legal_success = false;
    assert(
        runtime.restart_discovery_after_radio_fault() ==
        SimpleProductError::RADIO_FAILED);
    assert(!runtime.discovery_radio_ready());
    port.legal_success = true;
    assert(
        runtime.restart_discovery_after_radio_fault() ==
        SimpleProductError::NONE);
    assert(runtime.discovery_radio_ready());
  }

  {
    FakeClock clock;
    FakeRandom random;
    FakePort port;
    port.clock = &clock;
    SimpleProductRuntime runtime(&port, &clock, &random);
    assert(
        runtime.start(
            make_state("node_child"),
            child_mac,
            0,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);

    clock.value = 7500;
    port.channel_delay_ms = 300;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(clock.value == 7800);
    assert(runtime.discovery_scan_stage() == DiscoveryScanStage::FULL);
    assert(runtime.working_channel() == 1);

    clock.value = 10049;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(runtime.working_channel() == 1);

    clock.value = 10050;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(clock.value == 10350);
    assert(runtime.working_channel() == 2);

    for (uint64_t at : {
             12600ULL,
             15150ULL,
             17700ULL,
             20250ULL,
             22800ULL,
             25350ULL,
             27900ULL,
             30450ULL,
             33000ULL}) {
      clock.value = at;
      assert(runtime.tick() == SimpleProductError::NONE);
    }
    assert(runtime.working_channel() == 11);
    clock.value = 34250;
    assert(runtime.tick() == SimpleProductError::RADIO_FAILED);
    assert(!runtime.gateway_selection_busy());
    assert(!runtime.discovery_radio_ready());
  }

  {
    FakeClock clock;
    FakeRandom random;
    FakePort port;
    SimpleProductRuntime runtime(&port, &clock, &random);
    assert(
        runtime.start(
            make_state("node_child"),
            child_mac,
            0,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);
    clock.value = 7500;
    assert(runtime.tick() == SimpleProductError::NONE);
    clock.value = 9750;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(
        feed_discovery(runtime, relay_a, "relay_a", 2, -50) ==
        SimpleProductError::NONE);
    for (uint64_t at : {
             12000ULL,
             14250ULL,
             16500ULL,
             18750ULL,
             21000ULL,
             23250ULL,
             25500ULL,
             27750ULL,
             30000ULL}) {
      clock.value = at;
      assert(runtime.tick() == SimpleProductError::NONE);
    }
    port.broadcast_success = false;
    clock.value = 32250;
    assert(runtime.tick() == SimpleProductError::RADIO_FAILED);
    assert(!runtime.gateway_selection_busy());

    port.broadcast_success = true;
    assert(
        runtime.restart_discovery_after_radio_fault() ==
        SimpleProductError::NONE);
    assert(runtime.discovery_scan_stage() == DiscoveryScanStage::FAST);
    assert(runtime.discovery_radio_ready());
    const std::size_t restart_history = port.channel_history.size();
    clock.value += 250;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(port.channel_history.size() == restart_history + 1U);
  }

  {
    const SimpleProductPolicy policy{};
    assert(policy.scan_dwell_ms == 250U);
    assert(policy.fast_search_budget_ms == 6500U);
    assert(policy.candidate_window_ms == 6500U);
    assert(policy.gateway_selection_transaction_max_ms == 30000U);
    assert(policy.full_scan_dwell_ms == 2250U);
    assert(policy.full_scan_schedule_margin_ms == 2000U);
    assert(policy.full_handshake_max_ms == 26000U);
    assert(
        14ULL * policy.full_scan_dwell_ms +
            policy.full_scan_schedule_margin_ms +
            policy.full_handshake_max_ms <=
        policy.full_scan_total_max_ms);
    assert(policy.full_scan_total_max_ms == 60000U);
  }

  return 0;
}
