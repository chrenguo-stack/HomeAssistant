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

class ProductS5TelemetrySink {
 public:
  virtual ~ProductS5TelemetrySink() = default;
  virtual void on_s5_peer_installed(
      const MacAddress &peer_mac,
      const LinkKey &lmk,
      uint8_t channel) = 0;
  virtual void on_s5_peer_removed(const MacAddress &peer_mac) = 0;
  virtual void on_s5_telemetry_datagram(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size,
      const EspNowReceiveMetadata &metadata) = 0;
};

// S5-only adapter that multiplexes the single ESP-NOW callback without
// changing the frozen S3 runtime contract. Product discovery goes only to S3,
// GP/v1 pre-authorization packets go only to the S5 peer coordinator, and the
// existing GH/v1 DATA_FRAGMENT/RECEIPT_ACK packets go only to the reliable
// telemetry sink. Unknown datagrams are dropped fail-closed.
class ProductS5RadioMux final : public ProductRuntimeRadioPort,
                                public EspNowEventSink {
 public:
  ProductS5RadioMux(
      ProductRuntimeRadioPort *inner,
      ProductS5DatagramSink *s5_sink,
      ProductS5TelemetrySink *telemetry_sink = nullptr)
      : inner_(inner), s5_sink_(s5_sink), telemetry_sink_(telemetry_sink) {}

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
  static bool is_handshake_datagram_(const uint8_t *data, std::size_t size);
  static bool is_telemetry_datagram_(const uint8_t *data, std::size_t size);

  ProductRuntimeRadioPort *inner_{nullptr};
  ProductS5DatagramSink *s5_sink_{nullptr};
  ProductS5TelemetrySink *telemetry_sink_{nullptr};
  EspNowEventSink *runtime_sink_{nullptr};
  bool initialized_{false};
};

}  // namespace esphome::greenhouse_n3w_product_runtime
