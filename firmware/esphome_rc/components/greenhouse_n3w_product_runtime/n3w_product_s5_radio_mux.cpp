#include "n3w_product_s5_radio_mux.h"

namespace esphome::greenhouse_n3w_product_runtime {

namespace {
constexpr uint8_t kHandshakeMagic0 = 'G';
constexpr uint8_t kHandshakeMagic1 = 'P';
constexpr uint8_t kHandshakeVersion = 1;
constexpr uint8_t kHandshakeFirstType = 2;
constexpr uint8_t kHandshakeLastType = 5;
constexpr uint8_t kLinkMagic0 = 'G';
constexpr uint8_t kLinkMagic1 = 'H';
constexpr uint8_t kLinkVersion = 1;
}

bool ProductS5RadioMux::valid_unicast_mac_(const MacAddress &mac) {
  uint8_t aggregate = 0;
  for (uint8_t value : mac) aggregate |= value;
  return aggregate != 0 && (mac[0] & 0x01U) == 0;
}

bool ProductS5RadioMux::is_handshake_datagram_(const uint8_t *data, std::size_t size) {
  return data != nullptr && size >= 4 && data[0] == kHandshakeMagic0 &&
         data[1] == kHandshakeMagic1 && data[2] == kHandshakeVersion &&
         data[3] >= kHandshakeFirstType && data[3] <= kHandshakeLastType;
}

bool ProductS5RadioMux::is_telemetry_datagram_(const uint8_t *data, std::size_t size) {
  if (data == nullptr || size < 4 || data[0] != kLinkMagic0 || data[1] != kLinkMagic1 ||
      data[2] != kLinkVersion) {
    return false;
  }
  const auto type = static_cast<greenhouse_n3w_core::LinkPacketType>(data[3]);
  return type == greenhouse_n3w_core::LinkPacketType::DATA_FRAGMENT ||
         type == greenhouse_n3w_core::LinkPacketType::RECEIPT_ACK;
}

DriverError ProductS5RadioMux::initialize(
    EspNowEventSink *runtime_sink,
    const LinkKey &pmk) {
  if (initialized_ || inner_ == nullptr || runtime_sink == nullptr || s5_sink_ == nullptr) {
    return DriverError::INVALID_ARGUMENT;
  }
  runtime_sink_ = runtime_sink;
  const DriverError result = inner_->initialize(this, pmk);
  if (result != DriverError::NONE) {
    runtime_sink_ = nullptr;
    return result;
  }
  initialized_ = true;
  return DriverError::NONE;
}

void ProductS5RadioMux::shutdown() {
  if (inner_ != nullptr && initialized_) inner_->shutdown();
  initialized_ = false;
  runtime_sink_ = nullptr;
}

DriverError ProductS5RadioMux::set_channel(uint8_t channel) {
  return inner_ == nullptr ? DriverError::INVALID_ARGUMENT : inner_->set_channel(channel);
}

DriverError ProductS5RadioMux::prepare_broadcast_peer(uint8_t channel) {
  return inner_ == nullptr ? DriverError::INVALID_ARGUMENT
                           : inner_->prepare_broadcast_peer(channel);
}

DriverError ProductS5RadioMux::add_encrypted_peer(
    const MacAddress &peer_mac,
    const LinkKey &lmk,
    uint8_t channel) {
  if (inner_ == nullptr) return DriverError::INVALID_ARGUMENT;
  const DriverError result = inner_->add_encrypted_peer(peer_mac, lmk, channel);
  if (result == DriverError::NONE && telemetry_sink_ != nullptr) {
    telemetry_sink_->on_s5_peer_installed(peer_mac, lmk, channel);
  }
  return result;
}

DriverError ProductS5RadioMux::remove_peer(const MacAddress &peer_mac) {
  if (inner_ == nullptr) return DriverError::INVALID_ARGUMENT;
  const DriverError result = inner_->remove_peer(peer_mac);
  if (result == DriverError::NONE && telemetry_sink_ != nullptr) {
    telemetry_sink_->on_s5_peer_removed(peer_mac);
  }
  return result;
}

DriverError ProductS5RadioMux::send_peer(
    const MacAddress &peer_mac,
    const uint8_t *data,
    std::size_t size) {
  return inner_ == nullptr ? DriverError::INVALID_ARGUMENT : inner_->send_peer(peer_mac, data, size);
}

DriverError ProductS5RadioMux::send_broadcast(const uint8_t *data, std::size_t size) {
  return inner_ == nullptr ? DriverError::INVALID_ARGUMENT : inner_->send_broadcast(data, size);
}

void ProductS5RadioMux::on_espnow_receive(
    const MacAddress &source,
    const uint8_t *data,
    std::size_t size) {
  EspNowReceiveMetadata metadata;
  on_espnow_receive_with_metadata(source, data, size, metadata);
}

void ProductS5RadioMux::on_espnow_receive_with_metadata(
    const MacAddress &source,
    const uint8_t *data,
    std::size_t size,
    const EspNowReceiveMetadata &metadata) {
  if (!initialized_ || runtime_sink_ == nullptr || s5_sink_ == nullptr ||
      !valid_unicast_mac_(source) || data == nullptr || size == 0 ||
      size > greenhouse_n3w_core::kEspNowDatagramLimit) {
    return;
  }

  ProductDiscoveryAdvertisement advertisement;
  if (decode_product_discovery_advertisement(data, size, &advertisement)) {
    runtime_sink_->on_espnow_receive_with_metadata(source, data, size, metadata);
    return;
  }
  if (is_handshake_datagram_(data, size)) {
    s5_sink_->on_s5_datagram(source, data, size, metadata);
    return;
  }
  if (telemetry_sink_ != nullptr && is_telemetry_datagram_(data, size)) {
    telemetry_sink_->on_s5_telemetry_datagram(source, data, size, metadata);
  }
}

void ProductS5RadioMux::on_espnow_send_result(
    const MacAddress &destination,
    bool success) {
  if (initialized_ && runtime_sink_ != nullptr) {
    runtime_sink_->on_espnow_send_result(destination, success);
  }
}

}  // namespace esphome::greenhouse_n3w_product_runtime
