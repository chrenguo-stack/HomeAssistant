#include <cassert>
#include <cstdint>
#include <vector>

#include "n3w_product_runtime.h"

using namespace esphome::greenhouse_n3w_core;
using namespace esphome::greenhouse_n3w_product_core;
using namespace esphome::greenhouse_n3w_product_runtime;

namespace {

class FakeClock final : public ProductRuntimeClock {
 public:
  uint64_t now_ms() const override { return now; }
  uint64_t now{1000};
};

class FakeRadio final : public ProductRuntimeRadioPort {
 public:
  DriverError initialize(EspNowEventSink *sink, const LinkKey &pmk) override {
    sink_ = sink;
    pmk_ = pmk;
    initialized = true;
    return initialize_error;
  }
  void shutdown() override { initialized = false; }
  DriverError set_channel(uint8_t channel) override {
    if (set_channel_error != DriverError::NONE) return set_channel_error;
    current_channel = channel;
    channel_history.push_back(channel);
    return DriverError::NONE;
  }
  DriverError prepare_broadcast_peer(uint8_t channel) override {
    broadcast_channel = channel;
    return broadcast_peer_error;
  }
  DriverError add_encrypted_peer(
      const MacAddress &peer_mac,
      const LinkKey &lmk,
      uint8_t channel) override {
    if (add_peer_error != DriverError::NONE) return add_peer_error;
    added_peer = peer_mac;
    added_lmk = lmk;
    added_channel = channel;
    peer_present = true;
    return DriverError::NONE;
  }
  DriverError remove_peer(const MacAddress &peer_mac) override {
    removed_peers.push_back(peer_mac);
    peer_present = false;
    return remove_peer_error;
  }
  DriverError send_peer(
      const MacAddress &peer_mac,
      const uint8_t *data,
      std::size_t size) override {
    if (!peer_present || data == nullptr || size == 0) return DriverError::SEND_FAILED;
    peer_send_destination = peer_mac;
    peer_payload.assign(data, data + size);
    return peer_send_error;
  }
  DriverError send_broadcast(const uint8_t *data, std::size_t size) override {
    if (data == nullptr || size == 0) return DriverError::SEND_FAILED;
    broadcast_payload.assign(data, data + size);
    return broadcast_send_error;
  }

  EspNowEventSink *sink_{nullptr};
  LinkKey pmk_{};
  bool initialized{false};
  bool peer_present{false};
  uint8_t current_channel{0};
  uint8_t broadcast_channel{0};
  uint8_t added_channel{0};
  MacAddress added_peer{};
  LinkKey added_lmk{};
  MacAddress peer_send_destination{};
  std::vector<uint8_t> peer_payload{};
  std::vector<uint8_t> broadcast_payload{};
  std::vector<uint8_t> channel_history{};
  std::vector<MacAddress> removed_peers{};
  DriverError initialize_error{DriverError::NONE};
  DriverError set_channel_error{DriverError::NONE};
  DriverError broadcast_peer_error{DriverError::NONE};
  DriverError add_peer_error{DriverError::NONE};
  DriverError remove_peer_error{DriverError::NONE};
  DriverError peer_send_error{DriverError::NONE};
  DriverError broadcast_send_error{DriverError::NONE};
};

class FakeEvents final : public ProductRuntimeEventSink {
 public:
  void on_candidate_observed(const RelayCandidateObservation &observation) override {
    observed.push_back(observation);
  }
  void on_authorization_needed(const RelayCandidateRecord &candidate) override {
    authorization_requests.push_back(candidate);
  }
  void on_peer_active(const DynamicPeerAuthorization &authorization) override {
    active.push_back(authorization);
  }
  void on_peer_released(const MacAddress &peer_mac) override {
    released.push_back(peer_mac);
  }
  void on_advertisement_sent(const ProductDiscoveryAdvertisement &advertisement) override {
    advertisements.push_back(advertisement);
  }

  std::vector<RelayCandidateObservation> observed{};
  std::vector<RelayCandidateRecord> authorization_requests{};
  std::vector<DynamicPeerAuthorization> active{};
  std::vector<MacAddress> released{};
  std::vector<ProductDiscoveryAdvertisement> advertisements{};
};

RelayCandidateEligibility eligible(uint64_t now_ms, uint32_t credential_generation) {
  RelayCandidateEligibility value;
  value.manager_verified = true;
  value.registered = true;
  value.same_system = true;
  value.wifi_up = true;
  value.uplink_available = true;
  value.direct_uplink = true;
  value.relay_capable = true;
  value.low_battery = false;
  value.overloaded = false;
  value.retired = false;
  value.revoked = false;
  value.uplink_quality_pct = 90;
  value.load_pct = 10;
  value.battery_pct = 80;
  value.credential_generation = credential_generation;
  value.verified_at_ms = now_ms - 1;
  value.valid_until_ms = now_ms + 10000;
  return value;
}

DynamicPeerAuthorization authorization_for(
    const RelayCandidateRecord &candidate,
    uint64_t now_ms) {
  DynamicPeerAuthorization value;
  value.authorization_id = "auth_runtime_1";
  value.gateway_id = candidate.observation.gateway_id;
  value.peer_mac = candidate.observation.source_mac;
  value.channel = candidate.observation.channel;
  value.relay_credential_generation = candidate.eligibility.credential_generation;
  value.issued_at_ms = now_ms;
  value.expires_at_ms = now_ms + 5000;
  value.manager_authorized = true;
  value.same_system = true;
  return value;
}

LinkKey nonzero_key(uint8_t seed) {
  LinkKey key{};
  for (std::size_t i = 0; i < key.size(); ++i) key[i] = static_cast<uint8_t>(seed + i);
  return key;
}

ProductEspNowRuntime make_runtime(FakeRadio *radio, FakeClock *clock, FakeEvents *events) {
  WifiDirectHealthPolicy direct_policy{1, 3, 3};
  RelayCandidatePolicy candidate_policy{8, 15000, -92, 12, 30000};
  AutoPathPolicy path_policy{2};
  ProductRuntimePolicy runtime_policy{{1, 6, 11}, 250, 10, 1000};
  return ProductEspNowRuntime(
      radio, clock, events, direct_policy, candidate_policy, path_policy, runtime_policy);
}

void enter_discovery(ProductEspNowRuntime *runtime) {
  assert(runtime->note_direct_result(false) == ProductRuntimeError::NONE);
  assert(runtime->note_direct_result(false) == ProductRuntimeError::NONE);
  assert(runtime->note_direct_result(false) == ProductRuntimeError::NONE);
  assert(runtime->path_state() == AutoPathState::DISCOVERY);
  assert(runtime->scan_active());
}

void deliver_advertisement(
    ProductEspNowRuntime *runtime,
    FakeClock *clock,
    const MacAddress &source,
    const std::string &gateway_id,
    uint32_t generation,
    int16_t rssi_dbm) {
  ProductDiscoveryAdvertisement advertisement;
  advertisement.gateway_id = gateway_id;
  advertisement.channel = runtime->scan_channel();
  advertisement.advertisement_generation = generation;
  std::vector<uint8_t> encoded;
  assert(encode_product_discovery_advertisement(advertisement, &encoded));
  EspNowReceiveMetadata metadata;
  metadata.channel = advertisement.channel;
  metadata.rssi_dbm = rssi_dbm;
  clock->now += 1;
  runtime->on_espnow_receive_with_metadata(
      source, encoded.data(), encoded.size(), metadata);
}

}  // namespace

int main() {
  // Wire contract: discovery carries only non-secret candidate metadata.
  ProductDiscoveryAdvertisement wire{"gw_dynamic_A", 6, 9};
  std::vector<uint8_t> encoded;
  assert(encode_product_discovery_advertisement(wire, &encoded));
  ProductDiscoveryAdvertisement decoded;
  assert(decode_product_discovery_advertisement(encoded.data(), encoded.size(), &decoded));
  assert(decoded.gateway_id == wire.gateway_id);
  assert(decoded.channel == wire.channel);
  assert(decoded.advertisement_generation == wire.advertisement_generation);

  FakeRadio radio;
  FakeClock clock;
  FakeEvents events;
  auto runtime = make_runtime(&radio, &clock, &events);
  assert(runtime.start(nonzero_key(0x10)) == ProductRuntimeError::NONE);
  assert(runtime.set_last_direct_channel(6) == ProductRuntimeError::NONE);
  enter_discovery(&runtime);

  // Disconnected scan begins automatically after the frozen failure threshold.
  const uint8_t first_scan_channel = runtime.scan_channel();
  assert(first_scan_channel >= 1 && first_scan_channel <= 14);
  clock.now += 300;
  assert(runtime.tick() == ProductRuntimeError::NONE);
  assert(runtime.scan_channel() != 0);
  assert(radio.channel_history.size() >= 2);

  // Advertisement alone is untrusted: it creates a candidate but cannot enter Relay.
  const MacAddress mac_a{0x02, 0x11, 0x22, 0x33, 0x44, 0x55};
  deliver_advertisement(&runtime, &clock, mac_a, "gw_dynamic_A", 1, -55);
  assert(events.observed.size() == 1);
  assert(events.authorization_requests.empty());
  assert(runtime.path_state() == AutoPathState::DISCOVERY);

  // Manager-verified eligibility unlocks selection and requests authorization.
  const RelayCandidateEligibility eligibility_a = eligible(clock.now, 7);
  assert(runtime.apply_manager_eligibility(mac_a, "gw_dynamic_A", eligibility_a) ==
         ProductRuntimeError::NONE);
  assert(runtime.path_state() == AutoPathState::RELAY_AUTH);
  assert(events.authorization_requests.size() == 1);
  assert(runtime.pending_authorization_mac().has_value());

  // Runtime peer establishment uses fresh Manager authorization + pairwise LMK.
  RuntimePeerMaterial material;
  material.authorization = authorization_for(events.authorization_requests.back(), clock.now);
  material.lmk = nonzero_key(0x40);
  assert(runtime.install_authorized_peer(material) == ProductRuntimeError::NONE);
  assert(runtime.path_state() == AutoPathState::RELAY_ACTIVE);
  assert(runtime.relay_telemetry_ready());
  assert(radio.peer_present);
  assert(radio.added_peer == mac_a);
  assert(radio.added_lmk == material.lmk);
  assert(events.active.size() == 1);

  const uint8_t payload[]{1, 2, 3, 4};
  assert(runtime.send_active_peer(payload, sizeof(payload)) == ProductRuntimeError::NONE);
  assert(radio.peer_payload.size() == sizeof(payload));

  // Relay loss releases the runtime peer and returns to automatic rediscovery.
  assert(runtime.note_relay_result(false) == ProductRuntimeError::NONE);
  assert(runtime.note_relay_result(false) == ProductRuntimeError::NONE);
  assert(runtime.scan_active());
  assert(!runtime.active_peer_mac().has_value());
  assert(!events.released.empty());

  // A late-added node is discoverable without any old-node peer configuration.
  const MacAddress mac_c{0x02, 0xaa, 0xbb, 0xcc, 0xdd, 0xee};
  deliver_advertisement(&runtime, &clock, mac_c, "gw_late_C", 1, -50);
  assert(events.observed.back().source_mac == mac_c);
  const RelayCandidateEligibility eligibility_c = eligible(clock.now, 11);
  assert(runtime.apply_manager_eligibility(mac_c, "gw_late_C", eligibility_c) ==
         ProductRuntimeError::NONE);
  assert(runtime.path_state() == AutoPathState::RELAY_AUTH);
  assert(events.authorization_requests.back().observation.source_mac == mac_c);

  // Manager denial fails closed and resumes scanning; no peer is installed.
  assert(runtime.reject_peer_authorization() == ProductRuntimeError::NONE);
  assert(runtime.scan_active());
  assert(!radio.peer_present);

  // Direct, eligible nodes emit non-secret dynamic advertisements on their real Wi-Fi channel.
  FakeRadio relay_radio;
  FakeClock relay_clock;
  FakeEvents relay_events;
  auto relay_runtime = make_runtime(&relay_radio, &relay_clock, &relay_events);
  assert(relay_runtime.start(nonzero_key(0x20)) == ProductRuntimeError::NONE);
  assert(relay_runtime.set_last_direct_channel(11) == ProductRuntimeError::NONE);
  LocalRelayAdvertisement local;
  local.enabled = true;
  local.gateway_id = "gw_runtime_relay";
  local.channel = 11;
  local.advertisement_generation = 3;
  assert(relay_runtime.set_local_relay_advertisement(local) == ProductRuntimeError::NONE);
  assert(relay_runtime.tick() == ProductRuntimeError::NONE);
  assert(relay_radio.broadcast_channel == 11);
  assert(!relay_radio.broadcast_payload.empty());
  ProductDiscoveryAdvertisement broadcast_decoded;
  assert(decode_product_discovery_advertisement(
      relay_radio.broadcast_payload.data(),
      relay_radio.broadcast_payload.size(),
      &broadcast_decoded));
  assert(broadcast_decoded.gateway_id == local.gateway_id);
  assert(broadcast_decoded.advertisement_generation == local.advertisement_generation);
  assert(relay_events.advertisements.size() == 1);

  runtime.stop();
  relay_runtime.stop();
  return 0;
}
