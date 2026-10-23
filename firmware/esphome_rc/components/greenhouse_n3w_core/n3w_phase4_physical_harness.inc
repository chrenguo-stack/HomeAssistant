#include "n3w_phase4_physical_harness.h"

namespace esphome::greenhouse_n3w_core {

static_assert(kCompactTelemetryMaxWireBytes <= kEspNowPhysicalDatagramLimit,
              "Phase 4 compact telemetry must fit the concrete ESP-NOW driver");
static_assert(kSimplePeerControlMaxBytes <= kEspNowDatagramLimit,
              "Phase 4 peer-control packets must stay within the legacy-safe control budget");

bool Phase4PhysicalHarness::prepare_source_only() {
  source_only_prepared_ = source_contract_ready();
  return source_only_prepared_;
}

bool Phase4PhysicalHarness::source_contract_ready() const {
  return kEspNowPhysicalDatagramLimit == kEspNowV2PayloadLimit &&
         kCompactTelemetryMaxWireBytes == 1072 &&
         kSimplePeerControlMaxBytes <= kEspNowDatagramLimit;
}

SimpleNvsStatus Phase4PhysicalHarness::load_or_create_setup_secret(SetupSecret *secret) {
  return setup_secret_store_.load_or_create(secret);
}

SimpleNvsStatus Phase4PhysicalHarness::load_provisioned_state(
    ProvisionedPeerStateV2 *state) {
  return peer_store_.load(state);
}

SimpleNvsStatus Phase4PhysicalHarness::save_provisioned_state(
    const ProvisionedPeerStateV2 &state) {
  return peer_store_.save(state);
}

SimpleNvsStatus Phase4PhysicalHarness::erase_setup_secret() {
  return setup_secret_store_.erase();
}

DriverError Phase4PhysicalHarness::activate_radio(
    const LinkKey &pmk,
    uint8_t channel) {
  if (!source_only_prepared_ || !valid_radio_channel(channel)) {
    return DriverError::INVALID_ARGUMENT;
  }
  DriverError result = radio_.initialize(this, pmk);
  if (result != DriverError::NONE) {
    return result;
  }
  result = radio_.set_channel(channel);
  if (result != DriverError::NONE) {
    radio_.shutdown();
    return result;
  }
  result = radio_.prepare_broadcast_peer(channel);
  if (result != DriverError::NONE) {
    radio_.shutdown();
  }
  return result;
}

void Phase4PhysicalHarness::shutdown_radio() {
  radio_.shutdown();
}

DriverError Phase4PhysicalHarness::install_authenticated_peer(
    const MacAddress &peer_mac,
    const LinkKey &pair_lmk,
    uint8_t channel) {
  return radio_.add_encrypted_peer(peer_mac, pair_lmk, channel);
}

DriverError Phase4PhysicalHarness::send_peer_control_broadcast(
    const uint8_t *data,
    std::size_t size) {
  if (data == nullptr || size == 0 || size > kSimplePeerControlMaxBytes) {
    return DriverError::INVALID_ARGUMENT;
  }
  return radio_.send_broadcast(data, size);
}

DriverError Phase4PhysicalHarness::send_compact_unicast(
    const MacAddress &peer_mac,
    const uint8_t *data,
    std::size_t size) {
  if (data == nullptr || size <= kCompactTelemetryHeaderBytes ||
      size > kCompactTelemetryMaxWireBytes) {
    return DriverError::INVALID_ARGUMENT;
  }
  CompactTelemetryFrameV2 decoded;
  if (decode_compact_telemetry_frame_v2(data, size, &decoded) !=
      CompactTelemetryError::NONE) {
    return DriverError::INVALID_ARGUMENT;
  }
  return radio_.send(peer_mac, data, size);
}

void Phase4PhysicalHarness::on_espnow_receive(
    const MacAddress &source,
    const uint8_t *data,
    std::size_t size) {
  EspNowReceiveMetadata metadata{};
  on_espnow_receive_with_metadata(source, data, size, metadata);
}

void Phase4PhysicalHarness::on_espnow_receive_with_metadata(
    const MacAddress &source,
    const uint8_t *data,
    std::size_t size,
    const EspNowReceiveMetadata &metadata) {
  if (data == nullptr || size == 0 || size > kEspNowPhysicalDatagramLimit) {
    return;
  }
  ++receive_count_;
  last_source_ = source;
  last_receive_size_ = size;
  last_receive_metadata_ = metadata;
}

void Phase4PhysicalHarness::on_espnow_send_result(
    const MacAddress &destination,
    bool success) {
  ++send_completion_count_;
  last_destination_ = destination;
  last_send_success_ = success;
}

}  // namespace esphome::greenhouse_n3w_core
