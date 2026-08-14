#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>

#include "esphome/components/greenhouse_n3w_core/n3w_radio.h"
#include "n3w_product_s5_radio_mux.h"

namespace esphome::greenhouse_n3w_product_runtime {

using greenhouse_n3w_core::ChildRelayCache;
using greenhouse_n3w_core::RelayForwardSink;
using greenhouse_n3w_core::RelayFrame;
using greenhouse_n3w_core::RelayIngressController;
using greenhouse_n3w_core::RetryPolicy;

// The bridge carries only the existing gh.relay/1 frame and the existing
// DATA_FRAGMENT/RECEIPT_ACK radio contract. It does not define a telemetry
// schema, node identity, peer identity, or key lifecycle of its own.
enum class ProductS5TelemetryRole : uint8_t {
  CHILD = 0,
  RELAY = 1,
};

enum class ProductS5TelemetryError : uint8_t {
  NONE = 0,
  INVALID_ARGUMENT,
  NOT_READY,
  STATE_REJECTED,
  RADIO_FAILED,
  FRAME_REJECTED,
  CACHE_FAILED,
};

class ProductS5TelemetryBridge final : public ProductS5TelemetrySink,
                                       public RelayForwardSink {
 public:
  ProductS5TelemetryBridge(
      ProductS5TelemetryRole role,
      std::string local_node_id,
      ProductRuntimeRadioPort *radio,
      RelayForwardSink *forward_sink = nullptr,
      std::size_t cache_capacity = 8,
      RetryPolicy retry_policy = {});
  ~ProductS5TelemetryBridge() override;

  bool set_relay_child_node_id(const std::string &node_id);
  void clear_relay_child_node_id();

  ProductS5TelemetryError send_relay_frame(const RelayFrame &frame, uint64_t now_ms);
  ProductS5TelemetryError tick(uint64_t now_ms);

  bool active_peer() const { return active_peer_mac_.has_value(); }
  bool identity_bound() const { return !active_peer_node_id_.empty(); }
  bool active_lmk_resident() const { return nonzero_key_(active_lmk_); }
  const std::string &active_peer_node_id() const { return active_peer_node_id_; }
  std::size_t pending_frames() const { return child_cache_.size(); }
  ProductS5TelemetryError last_error() const { return last_error_; }

  void on_s5_peer_installed(
      const MacAddress &peer_mac,
      const LinkKey &lmk,
      uint8_t channel) override;
  void on_s5_peer_identity_bound(
      const MacAddress &peer_mac,
      const std::string &peer_node_id) override;
  void on_s5_peer_removed(const MacAddress &peer_mac) override;
  void on_s5_telemetry_datagram(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size,
      const EspNowReceiveMetadata &metadata) override;

  bool accept_for_forwarding(const RelayFrame &frame) override;

 private:
  static bool same_mac_(const MacAddress &left, const MacAddress &right);
  static bool nonzero_key_(const LinkKey &key);
  static void zeroize_(void *data, std::size_t length);
  void clear_active_peer_();
  ProductS5TelemetryError flush_due_(uint64_t now_ms);

  ProductS5TelemetryRole role_{ProductS5TelemetryRole::CHILD};
  std::string local_node_id_;
  ProductRuntimeRadioPort *radio_{nullptr};
  RelayForwardSink *forward_sink_{nullptr};
  std::size_t cache_capacity_{8};
  RetryPolicy retry_policy_{};
  ChildRelayCache child_cache_;
  RelayIngressController relay_ingress_;
  std::optional<MacAddress> active_peer_mac_{};
  LinkKey active_lmk_{};
  uint8_t active_channel_{0};
  std::string active_peer_node_id_;
  std::string relay_child_node_id_;
  ProductS5TelemetryError last_error_{ProductS5TelemetryError::NONE};
};

}  // namespace esphome::greenhouse_n3w_product_runtime
