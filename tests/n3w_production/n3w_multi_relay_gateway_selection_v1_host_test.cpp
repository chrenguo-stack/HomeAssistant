#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

#include "mbedtls/md.h"

#include "n3w_simple_product_runtime.h"

namespace {
bool g_force_selection_hash_collision = false;
}

extern "C" int __real_mbedtls_md(
    const mbedtls_md_info_t *md_info,
    const unsigned char *input,
    size_t ilen,
    unsigned char *output);

extern "C" int __wrap_mbedtls_md(
    const mbedtls_md_info_t *md_info,
    const unsigned char *input,
    size_t ilen,
    unsigned char *output) {
  static constexpr char kDomain[] = "N3W-GWSEL-V1";
  if (g_force_selection_hash_collision &&
      input != nullptr &&
      output != nullptr &&
      ilen >= sizeof(kDomain) &&
      std::equal(
          kDomain,
          kDomain + sizeof(kDomain) - 1U,
          reinterpret_cast<const char *>(input)) &&
      input[sizeof(kDomain) - 1U] == 0) {
    std::fill(output, output + 32, static_cast<unsigned char>(0x5a));
    return 0;
  }
  return __real_mbedtls_md(md_info, input, ilen, output);
}

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
  bool channel_success{true};
  bool broadcast_success{true};
  bool install_success{true};
  bool remove_success{true};
  bool encrypted_success{true};
  bool direct_success{true};
  bool relay_success{true};
  bool legal_channels_success{true};
  std::vector<uint8_t> legal_channels{1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11};
  std::vector<std::vector<uint8_t>> broadcasts;
  std::vector<InstalledPeer> installed;
  std::vector<MacAddress> removed;

  bool set_radio_channel(uint8_t value) override {
    if (!channel_success || !valid_radio_channel(value)) return false;
    channel = value;
    return true;
  }
  bool current_legal_channels(std::vector<uint8_t> *channels) override {
    if (!legal_channels_success || channels == nullptr) return false;
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
  bool remove_peer(const MacAddress &mac) override {
    removed.push_back(mac);
    return remove_success;
  }
  bool send_encrypted_peer(
      const MacAddress &,
      const uint8_t *,
      std::size_t) override {
    return encrypted_success;
  }
  bool publish_direct(const std::string &, const std::string &) override {
    return direct_success;
  }
  bool publish_relay(const std::string &, const std::string &) override {
    return relay_success;
  }
};

ProvisionedPeerStateV2 make_state(
    const std::string &node_id,
    uint8_t app_key_byte = 0x33) {
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

std::array<uint8_t, 32> selection_digest(
    const std::string &child,
    const std::string &relay) {
  static constexpr char domain[] = "N3W-GWSEL-V1";
  std::vector<uint8_t> input;
  input.insert(input.end(), domain, domain + sizeof(domain) - 1U);
  input.push_back(0);
  const auto append_u16be = [&input](std::size_t size) {
    const uint16_t value = static_cast<uint16_t>(size);
    input.push_back(static_cast<uint8_t>(value >> 8U));
    input.push_back(static_cast<uint8_t>(value & 0xffU));
  };
  append_u16be(child.size());
  input.insert(input.end(), child.begin(), child.end());
  append_u16be(relay.size());
  input.insert(input.end(), relay.begin(), relay.end());

  std::array<uint8_t, 32> digest{};
  const mbedtls_md_info_t *info =
      mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  assert(info != nullptr);
  assert(mbedtls_md(info, input.data(), input.size(), digest.data()) == 0);
  return digest;
}

std::string expected_hash_winner(
    const std::string &child,
    const std::string &left,
    const std::string &right) {
  const auto left_digest = selection_digest(child, left);
  const auto right_digest = selection_digest(child, right);
  if (left_digest == right_digest) return std::min(left, right);
  return std::lexicographical_compare(
             left_digest.begin(), left_digest.end(),
             right_digest.begin(), right_digest.end())
             ? left
             : right;
}

struct Sample {
  MacAddress mac{};
  std::string node_id;
  uint8_t channel{1};
  int16_t rssi_dbm{-70};
};

std::string select_after_window(const std::vector<Sample> &samples) {
  assert(!samples.empty());
  FakeClock clock;
  FakeRandom random;
  FakePort port;
  SimpleProductRuntime runtime(&port, &clock, &random);
  const MacAddress child_mac{0x02, 0x00, 0x00, 0x00, 0x00, 0xC1};
  assert(
      runtime.start(
          make_state("node_child"),
          child_mac,
          0,
          SimpleProductStartMode::DISCOVERY) ==
      SimpleProductError::NONE);
  for (const auto &sample : samples) {
    assert(
        feed_discovery(
            runtime,
            sample.mac,
            sample.node_id,
            sample.channel,
            sample.rssi_dbm) == SimpleProductError::NONE);
  }
  assert(runtime.gateway_selection_busy());
  assert(port.broadcasts.empty());
  clock.value = 7500;
  assert(runtime.tick() == SimpleProductError::NONE);
  assert(runtime.challenge_pending());
  return last_challenge(port).relay_node_id;
}

struct AcceptTimingOutcome {
  SimpleProductError receive_result{SimpleProductError::NONE};
  LocalPathState path{LocalPathState::DIRECT};
  bool challenge_pending{false};
  bool selection_busy{false};
};

AcceptTimingOutcome run_valid_accept_at(
    uint64_t accept_time_ms,
    bool tick_before_receive) {
  FakeClock child_clock;
  FakeClock relay_clock;
  FakeRandom child_random;
  FakeRandom relay_random;
  FakePort child_port;
  FakePort relay_port;
  SimpleProductRuntime child(&child_port, &child_clock, &child_random);
  SimpleProductRuntime relay(&relay_port, &relay_clock, &relay_random);
  const MacAddress child_mac{0x02, 0x00, 0x00, 0x00, 0x02, 0xC1};
  const MacAddress relay_mac{0x02, 0x00, 0x00, 0x00, 0x02, 0xA1};

  assert(
      child.start(
          make_state("node_child", 0x52),
          child_mac,
          0,
          SimpleProductStartMode::DISCOVERY) ==
      SimpleProductError::NONE);
  assert(
      relay.start(
          make_state("node_relay_a", 0x52),
          relay_mac,
          1,
          SimpleProductStartMode::DIRECT) ==
      SimpleProductError::NONE);
  relay.set_relay_capable(true);
  assert(relay.tick() == SimpleProductError::NONE);
  const auto discovery = relay_port.broadcasts.back();
  assert(
      child.on_radio_receive(
          relay_mac, discovery.data(), discovery.size(), 1, -60) ==
      SimpleProductError::NONE);

  child_clock.value = 7500;
  assert(child.tick() == SimpleProductError::NONE);
  const auto challenge = child_port.broadcasts.back();
  assert(
      relay.on_radio_receive(
          child_mac, challenge.data(), challenge.size(), 1, -55) ==
      SimpleProductError::NONE);
  const auto accept = relay_port.broadcasts.back();

  child_clock.value = accept_time_ms;
  if (tick_before_receive) {
    assert(child.tick() == SimpleProductError::NONE);
  }
  const SimpleProductError receive_result =
      child.on_radio_receive(
          relay_mac, accept.data(), accept.size(), 1, -60);
  if (!tick_before_receive &&
      receive_result != SimpleProductError::NONE) {
    assert(child.tick() == SimpleProductError::NONE);
  }

  return AcceptTimingOutcome{
      receive_result,
      child.path_state(),
      child.challenge_pending(),
      child.gateway_selection_busy(),
  };
}

bool worst_phase_candidate_is_collectible(
    uint16_t advertisement_phase_ms,
    uint8_t relay_channel) {
  static constexpr std::array<uint8_t, 3> channels{1, 6, 11};
  static constexpr uint32_t dwell_ms = 250;
  static constexpr uint32_t advertisement_period_ms = 2000;
  static constexpr uint32_t candidate_window_ms = 6500;

  for (uint32_t advertisement_ms = advertisement_phase_ms;
       advertisement_ms < candidate_window_ms;
       advertisement_ms += advertisement_period_ms) {
    const std::size_t channel_index =
        (advertisement_ms / dwell_ms) % channels.size();
    if (channels[channel_index] == relay_channel) return true;
  }
  return false;
}

bool role_pair_works(
    const std::string &child_id,
    const std::string &relay_id,
    const MacAddress &child_mac,
    const MacAddress &relay_mac) {
  FakeClock child_clock;
  FakeClock relay_clock;
  FakeRandom child_random;
  FakeRandom relay_random;
  FakePort child_port;
  FakePort relay_port;
  SimpleProductRuntime child(&child_port, &child_clock, &child_random);
  SimpleProductRuntime relay(&relay_port, &relay_clock, &relay_random);

  assert(
      child.start(
          make_state(child_id, 0x41),
          child_mac,
          0,
          SimpleProductStartMode::DISCOVERY) ==
      SimpleProductError::NONE);
  assert(
      relay.start(
          make_state(relay_id, 0x41),
          relay_mac,
          1,
          SimpleProductStartMode::DIRECT) ==
      SimpleProductError::NONE);
  relay.set_relay_capable(true);

  assert(relay.tick() == SimpleProductError::NONE);
  assert(!relay_port.broadcasts.empty());
  const auto discovery = relay_port.broadcasts.back();
  assert(
      child.on_radio_receive(
          relay_mac, discovery.data(), discovery.size(), 1, -60) ==
      SimpleProductError::NONE);

  child_clock.value = 7500;
  assert(child.tick() == SimpleProductError::NONE);
  const auto challenge = child_port.broadcasts.back();
  assert(
      relay.on_radio_receive(
          child_mac, challenge.data(), challenge.size(), 1, -55) ==
      SimpleProductError::NONE);
  const auto accept = relay_port.broadcasts.back();
  assert(
      child.on_radio_receive(
          relay_mac, accept.data(), accept.size(), 1, -60) ==
      SimpleProductError::NONE);
  return child.path_state() == LocalPathState::RELAY_ACTIVE &&
         child.active_relay().has_value() &&
         child.active_relay()->node_id == relay_id;
}

}  // namespace

int main() {
  const MacAddress mac_a{0x02, 0x00, 0x00, 0x00, 0x00, 0xA1};
  const MacAddress mac_b{0x02, 0x00, 0x00, 0x00, 0x00, 0xB1};
  const MacAddress mac_c{0x02, 0x00, 0x00, 0x00, 0x00, 0xD1};

  // 1. The first admissible Relay starts a bounded collection window; it does
  // not immediately win by arrival order.
  {
    FakeClock clock;
    FakeRandom random;
    FakePort port;
    SimpleProductRuntime runtime(&port, &clock, &random);
    const MacAddress child_mac{0x02, 0x00, 0x00, 0x00, 0x00, 0xC1};
    assert(
        runtime.start(
            make_state("node_child"),
            child_mac,
            0,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);
    assert(
        feed_discovery(runtime, mac_a, "node_relay_a", 1, -60) ==
        SimpleProductError::NONE);
    assert(runtime.gateway_selection_busy());
    assert(!runtime.challenge_pending());
    assert(port.broadcasts.empty());

    clock.value = 7499;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(port.broadcasts.empty());

    clock.value = 7500;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(runtime.challenge_pending());
    assert(last_challenge(port).relay_node_id == "node_relay_a");
  }

  // 2. Clear RSSI winner beats arrival order.
  assert(
      select_after_window({
          {mac_b, "node_relay_b", 1, -72},
          {mac_a, "node_relay_a", 1, -60},
      }) == "node_relay_a");

  // 3/4. Within the 3 dB equivalent band, including an exact mean tie, the
  // stable child+Relay SHA-256 decides.
  const std::string hash_winner =
      expected_hash_winner("node_child", "node_relay_a", "node_relay_b");
  assert(
      select_after_window({
          {mac_a, "node_relay_a", 1, -60},
          {mac_b, "node_relay_b", 1, -62},
      }) == hash_winner);
  assert(
      select_after_window({
          {mac_a, "node_relay_a", 1, -61},
          {mac_b, "node_relay_b", 1, -61},
      }) == hash_winner);

  // Exact 3 dB remains inside the equivalent-quality band.
  assert(
      select_after_window({
          {mac_a, "node_relay_a", 1, -60},
          {mac_b, "node_relay_b", 1, -63},
      }) == hash_winner);

  // Independent known vector for the frozen byte encoding:
  // "N3W-GWSEL-V1" NUL u16be(10) "node_child"
  // u16be(12) "node_relay_a".
  const std::array<uint8_t, 32> known_selection_digest{
      0x7b, 0xa1, 0x21, 0xf8, 0x33, 0xbc, 0x62, 0xce,
      0x59, 0x64, 0x6e, 0x80, 0x09, 0xdd, 0xd4, 0x4d,
      0xd0, 0xa1, 0x3e, 0x04, 0x0a, 0x81, 0x84, 0x79,
      0xa0, 0x79, 0x48, 0x50, 0x72, 0xea, 0xa9, 0xe2,
  };
  assert(selection_digest("node_child", "node_relay_a") ==
         known_selection_digest);

  // 5. An exact SHA-256 digest collision falls back to Relay NODE_ID lexical
  // order, as required by the frozen deterministic tie contract.
  g_force_selection_hash_collision = true;
  assert(
      select_after_window({
          {mac_b, "node_relay_b", 1, -61},
          {mac_a, "node_relay_a", 1, -61},
      }) == "node_relay_a");
  g_force_selection_hash_collision = false;

  // 6. The quality band is anchored to the strongest candidate, so -64 dBm is
  // not pulled into a transitive tie with -60/-62.
  const std::string anchored_winner =
      expected_hash_winner("node_child", "node_relay_a", "node_relay_b");
  assert(
      select_after_window({
          {mac_a, "node_relay_a", 1, -60},
          {mac_b, "node_relay_b", 1, -62},
          {mac_c, "node_relay_c", 1, -64},
      }) == anchored_winner);

  // 7. Advertisement order does not change the result.
  const std::string order_one =
      select_after_window({
          {mac_a, "node_relay_a", 1, -60},
          {mac_b, "node_relay_b", 1, -62},
      });
  const std::string order_two =
      select_after_window({
          {mac_b, "node_relay_b", 1, -62},
          {mac_a, "node_relay_a", 1, -60},
      });
  assert(order_one == order_two);

  // 8. Repeated same-channel samples use the arithmetic mean, not first/last
  // advertisement wins.
  assert(
      select_after_window({
          {mac_a, "node_relay_a", 1, -90},
          {mac_a, "node_relay_a", 1, -50},
          {mac_b, "node_relay_b", 1, -65},
      }) == "node_relay_b");

  // 9. A channel refresh resets the old-channel RSSI aggregate.
  assert(
      select_after_window({
          {mac_a, "node_relay_a", 1, -40},
          {mac_a, "node_relay_a", 6, -80},
          {mac_b, "node_relay_b", 6, -70},
      }) == "node_relay_b");

  // 10. Logical identity conflicts are rejected and cannot create a second
  // candidate.
  {
    FakeClock clock;
    FakeRandom random;
    FakePort port;
    SimpleProductRuntime runtime(&port, &clock, &random);
    const MacAddress child_mac{0x02, 0x00, 0x00, 0x00, 0x00, 0xC1};
    assert(
        runtime.start(
            make_state("node_child"),
            child_mac,
            0,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);
    assert(
        feed_discovery(runtime, mac_a, "node_relay_a", 1, -60) ==
        SimpleProductError::NONE);
    assert(
        feed_discovery(runtime, mac_b, "node_relay_a", 1, -50) ==
        SimpleProductError::PACKET_REJECTED);
    assert(
        feed_discovery(runtime, mac_a, "node_relay_b", 1, -50) ==
        SimpleProductError::PACKET_REJECTED);
    clock.value = 7500;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(last_challenge(port).relay_node_id == "node_relay_a");
  }

  // 11. A submitted Challenge that times out falls through to the next
  // already-collected candidate without opening another 6500 ms window.
  {
    FakeClock clock;
    FakeRandom random;
    FakePort port;
    SimpleProductRuntime runtime(&port, &clock, &random);
    const MacAddress child_mac{0x02, 0x00, 0x00, 0x00, 0x00, 0xC1};
    assert(
        runtime.start(
            make_state("node_child"),
            child_mac,
            0,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);
    assert(
        feed_discovery(runtime, mac_a, "node_relay_a", 1, -50) ==
        SimpleProductError::NONE);
    assert(
        feed_discovery(runtime, mac_b, "node_relay_b", 1, -70) ==
        SimpleProductError::NONE);
    clock.value = 7500;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(last_challenge(port).relay_node_id == "node_relay_a");
    const std::size_t first_count = port.broadcasts.size();

    clock.value = 10500;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(port.broadcasts.size() == first_count + 1);
    assert(last_challenge(port).relay_node_id == "node_relay_b");
    assert(runtime.gateway_selection_busy());
  }

  // 12. A local Challenge submit failure aborts the transaction instead of
  // falsely blaming that candidate and blindly trying another Relay.
  {
    FakeClock clock;
    FakeRandom random;
    FakePort port;
    SimpleProductRuntime runtime(&port, &clock, &random);
    const MacAddress child_mac{0x02, 0x00, 0x00, 0x00, 0x00, 0xC1};
    assert(
        runtime.start(
            make_state("node_child"),
            child_mac,
            0,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);
    assert(
        feed_discovery(runtime, mac_a, "node_relay_a", 1, -50) ==
        SimpleProductError::NONE);
    assert(
        feed_discovery(runtime, mac_b, "node_relay_b", 1, -70) ==
        SimpleProductError::NONE);
    port.broadcast_success = false;
    clock.value = 7500;
    assert(runtime.tick() == SimpleProductError::RADIO_FAILED);
    assert(!runtime.gateway_selection_busy());
    assert(port.broadcasts.empty());
  }

  // R2 local-fault classification is narrow: only an error that aborts an
  // active selection transaction requests component-level Relay restore.
  assert(gateway_selection_local_fault_requires_restore(
      SimpleProductError::RADIO_FAILED, true, false));
  assert(gateway_selection_local_fault_requires_restore(
      SimpleProductError::CRYPTO_FAILED, true, false));
  assert(gateway_selection_local_fault_requires_restore(
      SimpleProductError::STATE_REJECTED, true, false));
  assert(!gateway_selection_local_fault_requires_restore(
      SimpleProductError::STATE_REJECTED, true, true));
  assert(!gateway_selection_local_fault_requires_restore(
      SimpleProductError::PACKET_REJECTED, true, false));
  assert(!gateway_selection_local_fault_requires_restore(
      SimpleProductError::RADIO_FAILED, false, false));

  // A scan-channel failure during an active candidate window now aborts the
  // transaction, so the component can consume it as a local selection fault.
  {
    FakeClock clock;
    FakeRandom random;
    FakePort port;
    SimpleProductRuntime runtime(&port, &clock, &random);
    const MacAddress child_mac{0x02, 0x00, 0x00, 0x00, 0x03, 0xC1};
    assert(
        runtime.start(
            make_state("node_child"),
            child_mac,
            0,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);
    assert(
        feed_discovery(runtime, mac_a, "node_relay_a", 1, -60) ==
        SimpleProductError::NONE);
    assert(runtime.gateway_selection_busy());
    port.channel_success = false;
    clock.value = 1250;
    const bool busy_before = runtime.gateway_selection_busy();
    const SimpleProductError result = runtime.tick();
    assert(result == SimpleProductError::RADIO_FAILED);
    assert(!runtime.gateway_selection_busy());
    assert(gateway_selection_local_fault_requires_restore(
        result, busy_before, runtime.gateway_selection_busy()));
  }

  // 13/14. An invalid Accept does not force fallback. A valid authenticated
  // Accept followed by a local channel failure aborts the epoch without trying
  // the next candidate.
  {
    FakeClock child_clock;
    FakeClock relay_clock;
    FakeRandom child_random;
    FakeRandom relay_random;
    FakePort child_port;
    FakePort relay_port;
    SimpleProductRuntime child(&child_port, &child_clock, &child_random);
    SimpleProductRuntime relay(&relay_port, &relay_clock, &relay_random);
    const MacAddress child_mac{0x02, 0x00, 0x00, 0x00, 0x00, 0xC1};

    assert(
        child.start(
            make_state("node_child", 0x44),
            child_mac,
            0,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);
    assert(
        relay.start(
            make_state("node_relay_a", 0x44),
            mac_a,
            1,
            SimpleProductStartMode::DIRECT) ==
        SimpleProductError::NONE);
    relay.set_relay_capable(true);
    assert(relay.tick() == SimpleProductError::NONE);
    const auto discovery = relay_port.broadcasts.back();
    assert(
        child.on_radio_receive(
            mac_a, discovery.data(), discovery.size(), 1, -60) ==
        SimpleProductError::NONE);
    child_clock.value = 7500;
    assert(child.tick() == SimpleProductError::NONE);
    const auto challenge = child_port.broadcasts.back();
    assert(
        relay.on_radio_receive(
            child_mac, challenge.data(), challenge.size(), 1, -55) ==
        SimpleProductError::NONE);
    const auto accept = relay_port.broadcasts.back();

    assert(
        child.on_radio_receive(
            mac_b, accept.data(), accept.size(), 1, -50) ==
        SimpleProductError::PACKET_REJECTED);
    assert(child.challenge_pending());
    assert(child.gateway_selection_busy());

    child_port.channel_success = false;
    assert(
        child.on_radio_receive(
            mac_a, accept.data(), accept.size(), 1, -60) ==
        SimpleProductError::RADIO_FAILED);
    assert(!child.challenge_pending());
    assert(!child.gateway_selection_busy());
    assert(!child.active_relay().has_value());
  }

  // 15/16. A healthy active Relay is sticky even if a stronger Relay appears.
  // Only the existing two-failure path returns to Discovery, where a fresh
  // selection epoch may choose another Relay.
  {
    FakeClock child_clock;
    FakeClock relay_clock;
    FakeRandom child_random;
    FakeRandom relay_random;
    FakePort child_port;
    FakePort relay_port;
    SimpleProductRuntime child(&child_port, &child_clock, &child_random);
    SimpleProductRuntime relay(&relay_port, &relay_clock, &relay_random);
    const MacAddress child_mac{0x02, 0x00, 0x00, 0x00, 0x00, 0xC1};

    assert(
        child.start(
            make_state("node_child", 0x45),
            child_mac,
            0,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);
    assert(
        relay.start(
            make_state("node_relay_a", 0x45),
            mac_a,
            1,
            SimpleProductStartMode::DIRECT) ==
        SimpleProductError::NONE);
    relay.set_relay_capable(true);
    assert(relay.tick() == SimpleProductError::NONE);
    const auto discovery = relay_port.broadcasts.back();
    assert(
        child.on_radio_receive(
            mac_a, discovery.data(), discovery.size(), 1, -65) ==
        SimpleProductError::NONE);
    child_clock.value = 7500;
    assert(child.tick() == SimpleProductError::NONE);
    const auto challenge = child_port.broadcasts.back();
    assert(
        relay.on_radio_receive(
            child_mac, challenge.data(), challenge.size(), 1, -55) ==
        SimpleProductError::NONE);
    const auto accept = relay_port.broadcasts.back();
    assert(
        child.on_radio_receive(
            mac_a, accept.data(), accept.size(), 1, -65) ==
        SimpleProductError::NONE);
    assert(child.path_state() == LocalPathState::RELAY_ACTIVE);
    assert(child.active_relay()->node_id == "node_relay_a");

    assert(
        feed_discovery(child, mac_b, "node_relay_b", 1, -30) ==
        SimpleProductError::STATE_REJECTED);
    assert(child.active_relay()->node_id == "node_relay_a");
    assert(!child.gateway_selection_busy());

    assert(
        child.note_relay_delivery_result(mac_a, false) ==
        SimpleProductError::NONE);
    assert(child.path_state() == LocalPathState::RELAY_ACTIVE);
    assert(
        child.note_relay_delivery_result(mac_a, false) ==
        SimpleProductError::NONE);
    assert(child.path_state() == LocalPathState::DISCOVERY);
    assert(!child.active_relay().has_value());

    child_clock.value = 8000;
    assert(
        feed_discovery(child, mac_b, "node_relay_b", 1, -55) ==
        SimpleProductError::NONE);
    child_clock.value = 14500;
    assert(child.tick() == SimpleProductError::NONE);
    assert(last_challenge(child_port).relay_node_id == "node_relay_b");
  }

  // 17. The same production runtime remains role-neutral: either board can be
  // Child or Relay with no node-specific source behavior.
  const MacAddress role_a{0x02, 0x00, 0x00, 0x00, 0x01, 0xA1};
  const MacAddress role_b{0x02, 0x00, 0x00, 0x00, 0x01, 0xB1};
  assert(role_pair_works("node_a", "node_b", role_a, role_b));
  assert(role_pair_works("node_b", "node_a", role_b, role_a));

  // 18. Worst-edge timing: a second Relay arriving 1 ms before the 6500 ms
  // deadline still participates and may win.
  {
    FakeClock clock;
    FakeRandom random;
    FakePort port;
    SimpleProductRuntime runtime(&port, &clock, &random);
    const MacAddress child_mac{0x02, 0x00, 0x00, 0x00, 0x00, 0xC1};
    assert(
        runtime.start(
            make_state("node_child"),
            child_mac,
            0,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);
    assert(
        feed_discovery(runtime, mac_a, "node_relay_a", 1, -80) ==
        SimpleProductError::NONE);
    clock.value = 7499;
    assert(
        feed_discovery(runtime, mac_b, "node_relay_b", 1, -50) ==
        SimpleProductError::NONE);
    clock.value = 7500;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(last_challenge(port).relay_node_id == "node_relay_b");
  }

  // 19. The receive path enforces the deadline itself because the component
  // drains queued radio frames before runtime.tick(). A Relay first observed
  // at the exact deadline must not slip into the frozen candidate set.
  {
    FakeClock clock;
    FakeRandom random;
    FakePort port;
    SimpleProductRuntime runtime(&port, &clock, &random);
    const MacAddress child_mac{0x02, 0x00, 0x00, 0x00, 0x00, 0xC1};
    assert(
        runtime.start(
            make_state("node_child"),
            child_mac,
            0,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);
    assert(
        feed_discovery(runtime, mac_a, "node_relay_a", 1, -80) ==
        SimpleProductError::NONE);
    clock.value = 7500;
    assert(
        feed_discovery(runtime, mac_b, "node_relay_b", 1, -20) ==
        SimpleProductError::STATE_REJECTED);
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(last_challenge(port).relay_node_id == "node_relay_a");
  }

  // R2 frozen production bounds.
  {
    const SimpleProductPolicy policy{};
    assert(policy.max_gateway_candidates == 8U);
    assert(policy.gateway_selection_transaction_max_ms == 30000U);
  }

  // Candidate memory is bounded at eight distinct Relay identities. Existing
  // retained candidates still update while a ninth distinct identity is
  // rejected.
  {
    FakeClock clock;
    FakeRandom random;
    FakePort port;
    SimpleProductRuntime runtime(&port, &clock, &random);
    const MacAddress child_mac{0x02, 0x00, 0x00, 0x00, 0x04, 0xC1};
    assert(
        runtime.start(
            make_state("node_child"),
            child_mac,
            0,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);

    std::array<MacAddress, 8> candidate_macs{};
    for (std::size_t i = 0; i < candidate_macs.size(); ++i) {
      candidate_macs[i] =
          MacAddress{0x02, 0x00, 0x00, 0x00, 0x04,
                     static_cast<uint8_t>(0x10U + i)};
      assert(
          feed_discovery(
              runtime,
              candidate_macs[i],
              "node_relay_" + std::to_string(i),
              1,
              static_cast<int16_t>(-80 - static_cast<int>(i))) ==
          SimpleProductError::NONE);
    }

    // Existing retained candidate may still improve its mean at capacity.
    assert(
        feed_discovery(
            runtime,
            candidate_macs[0],
            "node_relay_0",
            1,
            -10) == SimpleProductError::NONE);

    const MacAddress ninth_mac{0x02, 0x00, 0x00, 0x00, 0x04, 0x30};
    assert(
        feed_discovery(
            runtime,
            ninth_mac,
            "node_relay_8",
            1,
            -5) == SimpleProductError::PACKET_REJECTED);

    clock.value = 7500;
    assert(runtime.tick() == SimpleProductError::NONE);
    assert(last_challenge(port).relay_node_id == "node_relay_0");
  }

  // Eight non-responsive candidates cannot suppress Direct recovery beyond
  // the 30 s absolute selection budget. The last pending Challenge is cut
  // short at the transaction deadline and ordinary Discovery is re-aligned.
  {
    FakeClock clock;
    FakeRandom random;
    FakePort port;
    SimpleProductRuntime runtime(&port, &clock, &random);
    const MacAddress child_mac{0x02, 0x00, 0x00, 0x00, 0x05, 0xC1};
    assert(
        runtime.start(
            make_state("node_child", 0x61),
            child_mac,
            0,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);

    std::array<MacAddress, 8> candidate_macs{};
    for (std::size_t i = 0; i < candidate_macs.size(); ++i) {
      candidate_macs[i] =
          MacAddress{0x02, 0x00, 0x00, 0x00, 0x05,
                     static_cast<uint8_t>(0x10U + i)};
      assert(
          feed_discovery(
              runtime,
              candidate_macs[i],
              "budget_relay_" + std::to_string(i),
              1,
              static_cast<int16_t>(-40 - 10 * static_cast<int>(i))) ==
          SimpleProductError::NONE);
    }

    const std::array<uint64_t, 8> challenge_times{
        7500, 10500, 13500, 16500,
        19500, 22500, 25500, 28500,
    };
    for (std::size_t i = 0; i < challenge_times.size(); ++i) {
      clock.value = challenge_times[i];
      assert(runtime.tick() == SimpleProductError::NONE);
      assert(runtime.challenge_pending());
      assert(
          last_challenge(port).relay_node_id ==
          "budget_relay_" + std::to_string(i));
    }
    assert(port.broadcasts.size() == 8U);
    assert(runtime.gateway_selection_busy());

    // Produce a valid Accept for the final candidate. It is still inside that
    // candidate's 3000 ms timeout at 31000 ms, but the absolute transaction
    // deadline wins and must reject it before any peer/channel side effect.
    FakeClock relay_clock;
    FakeRandom relay_random;
    FakePort relay_port;
    SimpleProductRuntime last_relay(
        &relay_port, &relay_clock, &relay_random);
    assert(
        last_relay.start(
            make_state("budget_relay_7", 0x61),
            candidate_macs[7],
            1,
            SimpleProductStartMode::DIRECT) ==
        SimpleProductError::NONE);
    last_relay.set_relay_capable(true);
    const auto final_challenge = port.broadcasts.back();
    assert(
        last_relay.on_radio_receive(
            child_mac,
            final_challenge.data(),
            final_challenge.size(),
            1,
            -55) == SimpleProductError::NONE);
    const auto final_accept = relay_port.broadcasts.back();

    clock.value = 31000;
    assert(
        runtime.on_radio_receive(
            candidate_macs[7],
            final_accept.data(),
            final_accept.size(),
            1,
            -60) == SimpleProductError::PACKET_REJECTED);
    assert(runtime.challenge_pending());
    assert(runtime.active_relay().has_value() == false);

    assert(runtime.tick() == SimpleProductError::NONE);
    assert(!runtime.challenge_pending());
    assert(runtime.gateway_selection_busy());
    assert(runtime.path_state() == LocalPathState::DISCOVERY);
    assert(runtime.discovery_scan_stage() == DiscoveryScanStage::FULL);
    assert(port.channel == runtime.working_channel());
  }

  // Pending Accept expiry is order invariant. Equality is expired.
  {
    const AcceptTimingOutcome before =
        run_valid_accept_at(10499, false);
    assert(before.receive_result == SimpleProductError::NONE);
    assert(before.path == LocalPathState::RELAY_ACTIVE);
    assert(!before.challenge_pending);
    assert(!before.selection_busy);

    const AcceptTimingOutcome exact_rx_first =
        run_valid_accept_at(10500, false);
    assert(
        exact_rx_first.receive_result ==
        SimpleProductError::PACKET_REJECTED);
    assert(exact_rx_first.path == LocalPathState::DISCOVERY);
    assert(!exact_rx_first.challenge_pending);
    assert(!exact_rx_first.selection_busy);

    const AcceptTimingOutcome exact_tick_first =
        run_valid_accept_at(10500, true);
    assert(
        exact_tick_first.receive_result ==
        SimpleProductError::STATE_REJECTED);
    assert(exact_tick_first.path == exact_rx_first.path);
    assert(
        exact_tick_first.challenge_pending ==
        exact_rx_first.challenge_pending);
    assert(
        exact_tick_first.selection_busy ==
        exact_rx_first.selection_busy);

    const AcceptTimingOutcome after =
        run_valid_accept_at(10501, false);
    assert(
        after.receive_result ==
        SimpleProductError::PACKET_REJECTED);
    assert(after.path == LocalPathState::DISCOVERY);
    assert(!after.challenge_pending);
    assert(!after.selection_busy);
  }

  // Peer-install failure remains a local fault even when best-effort cleanup
  // itself cannot be confirmed. Component-level bounded restore is therefore
  // still required.
  {
    FakeClock child_clock;
    FakeClock relay_clock;
    FakeRandom child_random;
    FakeRandom relay_random;
    FakePort child_port;
    FakePort relay_port;
    SimpleProductRuntime child(&child_port, &child_clock, &child_random);
    SimpleProductRuntime relay(&relay_port, &relay_clock, &relay_random);
    const MacAddress child_mac{0x02, 0x00, 0x00, 0x00, 0x06, 0xC1};
    const MacAddress relay_mac{0x02, 0x00, 0x00, 0x00, 0x06, 0xA1};

    assert(
        child.start(
            make_state("node_child", 0x62),
            child_mac,
            0,
            SimpleProductStartMode::DISCOVERY) ==
        SimpleProductError::NONE);
    assert(
        relay.start(
            make_state("cleanup_relay", 0x62),
            relay_mac,
            1,
            SimpleProductStartMode::DIRECT) ==
        SimpleProductError::NONE);
    relay.set_relay_capable(true);
    assert(relay.tick() == SimpleProductError::NONE);
    const auto discovery = relay_port.broadcasts.back();
    assert(
        child.on_radio_receive(
            relay_mac, discovery.data(), discovery.size(), 1, -60) ==
        SimpleProductError::NONE);
    child_clock.value = 7500;
    assert(child.tick() == SimpleProductError::NONE);
    const auto challenge = child_port.broadcasts.back();
    assert(
        relay.on_radio_receive(
            child_mac, challenge.data(), challenge.size(), 1, -55) ==
        SimpleProductError::NONE);
    const auto accept = relay_port.broadcasts.back();

    child_port.install_success = false;
    child_port.remove_success = false;
    const bool busy_before = child.gateway_selection_busy();
    const SimpleProductError result =
        child.on_radio_receive(
            relay_mac, accept.data(), accept.size(), 1, -60);
    assert(result == SimpleProductError::RADIO_FAILED);
    assert(!child.gateway_selection_busy());
    assert(!child_port.removed.empty());
    assert(gateway_selection_local_fault_requires_restore(
        result, busy_before, child.gateway_selection_busy()));
  }

  // Host timing model for SOURCE_DESIGN case 23. Across all advertisement
  // phases in one 2000 ms period and each of the three 250 ms scan dwells, a
  // second Relay has at least one collectible advertisement inside 6500 ms.
  for (uint16_t phase_ms = 0; phase_ms < 2000; ++phase_ms) {
    assert(worst_phase_candidate_is_collectible(phase_ms, 1));
    assert(worst_phase_candidate_is_collectible(phase_ms, 6));
    assert(worst_phase_candidate_is_collectible(phase_ms, 11));
  }

  return 0;
}
