#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>

#include "esphome/components/greenhouse_n3w_product_runtime/n3w_product_s5_radio_mux.h"

using namespace esphome::greenhouse_n3w_core;
using namespace esphome::greenhouse_n3w_product_runtime;

namespace {

class FakeInner final : public ProductRuntimeRadioPort {
 public:
  DriverError initialize(EspNowEventSink *sink, const LinkKey &pmk) override {
    sink_ = sink;
    pmk_ = pmk;
    initialized = true;
    return DriverError::NONE;
  }
  void shutdown() override { initialized = false; }
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
  DriverError send_peer(const MacAddress &, const uint8_t *, std::size_t) override {
    return DriverError::NONE;
  }
  DriverError send_broadcast(const uint8_t *, std::size_t) override {
    return DriverError::NONE;
  }

  EspNowEventSink *sink_{nullptr};
  LinkKey pmk_{};
  uint8_t channel_{0};
  bool initialized{false};
};

class RuntimeSink final : public EspNowEventSink {
 public:
  void on_espnow_receive_with_metadata(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size,
      const EspNowReceiveMetadata &metadata) override {
    ++receive_count;
    last_source = source;
    last_payload.assign(data, data + size);
    last_metadata = metadata;
  }
  void on_espnow_send_result(const MacAddress &destination, bool success) override {
    ++send_result_count;
    last_destination = destination;
    last_send_success = success;
  }

  int receive_count{0};
  int send_result_count{0};
  MacAddress last_source{};
  MacAddress last_destination{};
  EspNowReceiveMetadata last_metadata{};
  std::vector<uint8_t> last_payload{};
  bool last_send_success{false};
};

class S5Sink final : public ProductS5DatagramSink {
 public:
  void on_s5_datagram(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size,
      const EspNowReceiveMetadata &metadata) override {
    ++receive_count;
    last_source = source;
    last_payload.assign(data, data + size);
    last_metadata = metadata;
  }

  int receive_count{0};
  MacAddress last_source{};
  EspNowReceiveMetadata last_metadata{};
  std::vector<uint8_t> last_payload{};
};

LinkKey key() {
  LinkKey result{};
  for (std::size_t index = 0; index < result.size(); ++index)
    result[index] = static_cast<uint8_t>(0x10 + index);
  return result;
}

}  // namespace

int main() {
  FakeInner inner;
  RuntimeSink runtime;
  S5Sink s5;
  ProductS5RadioMux mux(&inner, &s5);
  assert(mux.initialize(&runtime, key()) == DriverError::NONE);
  assert(mux.initialized());
  assert(inner.sink_ == &mux);

  const MacAddress source{0x02, 0x11, 0x22, 0x33, 0x44, 0x55};
  EspNowReceiveMetadata metadata;
  metadata.channel = 6;
  metadata.rssi_dbm = -52;

  ProductDiscoveryAdvertisement advertisement{"node_relay01", 6, 7};
  std::vector<uint8_t> discovery;
  assert(encode_product_discovery_advertisement(advertisement, &discovery));
  mux.on_espnow_receive_with_metadata(
      source, discovery.data(), discovery.size(), metadata);
  assert(runtime.receive_count == 1);
  assert(s5.receive_count == 0);
  assert(runtime.last_source == source);

  const std::vector<uint8_t> preauth{'G', 'P', 1, 2, 0x01, 0x02, 0x03};
  mux.on_espnow_receive_with_metadata(source, preauth.data(), preauth.size(), metadata);
  assert(runtime.receive_count == 1);
  assert(s5.receive_count == 1);
  assert(s5.last_source == source);
  assert(s5.last_payload == preauth);
  assert(s5.last_metadata.channel == 6);
  assert(s5.last_metadata.rssi_dbm == -52);

  const MacAddress multicast{0x01, 0x11, 0x22, 0x33, 0x44, 0x55};
  mux.on_espnow_receive_with_metadata(
      multicast, preauth.data(), preauth.size(), metadata);
  assert(runtime.receive_count == 1);
  assert(s5.receive_count == 1);

  std::vector<uint8_t> oversized(kEspNowDatagramLimit + 1, 0x5a);
  mux.on_espnow_receive_with_metadata(
      source, oversized.data(), oversized.size(), metadata);
  assert(runtime.receive_count == 1);
  assert(s5.receive_count == 1);

  mux.on_espnow_send_result(source, true);
  assert(runtime.send_result_count == 1);
  assert(runtime.last_destination == source);
  assert(runtime.last_send_success);

  mux.shutdown();
  assert(!mux.initialized());
  assert(!inner.initialized);

  std::cout << "S5_PRODUCT_RADIO_MUX=PASS\n";
  return 0;
}
