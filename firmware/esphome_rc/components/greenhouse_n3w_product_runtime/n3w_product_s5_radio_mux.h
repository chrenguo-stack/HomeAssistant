#pragma once

#include <cstddef>
#include <cstdint>

#include "n3w_product_runtime.h"

namespace esphome::greenhouse_n3w_product_runtime {

class ProductS5DatagramSink {
 public:
  virtual ~ProductS5DatagramSink() = default;
  virtual void on_s5_datagram(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size,
      const EspNowReceiveMetadata &metadata) = 0;
};

// S5-only adapter that multiplexes the single ESP-NOW callback without
// changing the frozen S3 runtime contract. Discovery advertisements continue
// to flow only into ProductEspNowRuntime. Non-discovery datagrams are exposed
// to the S5 peer-auth/reliable-transport coordinator.
class ProductS5RadioMux final : public ProductRuntimeRadioPort,
                                public EspNowEventSink {
 public:
  ProductS5RadioMux(
      ProductRuntimeRadioPort *inner,
      ProductS5DatagramSink *s5_sink)
      : inner_(inner), s5_sink_(s5_sink) {}

  DriverError initialize(EspNowEventSink *runtime_sink, const LinkKey &pmk) override;
  void shutdown() override;
  DriverError set_channel(uint8_t channel) override;
  DriverError prepare_broadcast_peer(uint8_t channel) override;
  DriverError add_encrypted_peer(
      const MacAddress &peer_mac,
      const LinkKey &lmk,
      uint8_t channel) override;
  DriverError remove_peer(const MacAddress &peer_mac) override;
  DriverError send_peer(
      const MacAddress &peer_mac,
      const uint8_t *data,
      std::size_t size) override;
  DriverError send_broadcast(const uint8_t *data, std::size_t size) override;

  void on_espnow_receive(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size) override;
  void on_espnow_receive_with_metadata(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size,
      const EspNowReceiveMetadata &metadata) override;
  void on_espnow_send_result(
      const MacAddress &destination,
      bool success) override;

  bool initialized() const { return initialized_; }

 private:
  static bool valid_unicast_mac_(const MacAddress &mac);

  ProductRuntimeRadioPort *inner_{nullptr};
  ProductS5DatagramSink *s5_sink_{nullptr};
  EspNowEventSink *runtime_sink_{nullptr};
  bool initialized_{false};
};

}  // namespace esphome::greenhouse_n3w_product_runtime
