#include "n3w_product_s5_radio_mux.h"

namespace esphome::greenhouse_n3w_product_runtime {

bool ProductS5RadioMux::valid_unicast_mac_(const MacAddress &mac) {
  uint8_t aggregate = 0;
  for (uint8_t value : mac) aggregate |= value;
  return aggregate != 0 && (mac[0] & 0x01U) == 0;
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
  return inner_ == nullptr ? DriverError::INVALID_ARGUMENT
                           : inner_->add_encrypted_peer(peer_mac, lmk, channel);
}

DriverError ProductS5RadioMux::remove_peer(const MacAddress &peer_mac) {
  return inner_ == nullptr ? DriverError::INVALID_ARGUMENT : inner_->remove_peer(peer_mac);
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

  // The S5 sink performs strict type/state decoding. The mux only guarantees
  // a bounded non-discovery datagram from a unicast source.
  s5_sink_->on_s5_datagram(source, data, size, metadata);
}

void ProductS5RadioMux::on_espnow_send_result(
    const MacAddress &destination,
    bool success) {
  if (initialized_ && runtime_sink_ != nullptr) {
    runtime_sink_->on_espnow_send_result(destination, success);
  }
}

}  // namespace esphome::greenhouse_n3w_product_runtime
