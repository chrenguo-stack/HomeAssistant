#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

#if __has_include("esphome/core/defines.h")
#include "esphome/core/defines.h"
#endif
#include "esphome/components/greenhouse_n3w_core/n3w_radio.h"
#include "n3w_product_s5_manager_wire.h"
#include "esphome/components/greenhouse_n3w_product_runtime/n3w_product_s5_peer_coordinator.h"

#ifdef USE_MQTT
#include "esphome/components/mqtt/custom_mqtt_device.h"
#endif

namespace esphome::greenhouse_n3w_s5_manager_transport {

using greenhouse_n3w_product_runtime::ProductPeerGrant;
using greenhouse_n3w_product_runtime::ProductPeerRequest;
using greenhouse_n3w_product_runtime::ProductPeerRole;
using greenhouse_n3w_product_runtime::ProductPeerSecurity;
using greenhouse_n3w_product_runtime::ProductRuntimeClock;
using greenhouse_n3w_product_runtime::ProductS5ManagerPort;

using greenhouse_n3w_core::RelayForwardSink;
using greenhouse_n3w_core::RelayFrame;

class ProductS5ManagerAuthorizationSink {
 public:
  virtual ~ProductS5ManagerAuthorizationSink() = default;
  virtual bool queue_s5_manager_authorization(
      const ProductPeerGrant &child_grant,
      const ProductPeerGrant &relay_grant) = 0;
};

class ProductS5MessageBusSink {
 public:
  virtual ~ProductS5MessageBusSink() = default;
  virtual void on_s5_message(
      const std::string &topic,
      const std::string &payload) = 0;
};

class ProductS5MessageBusPort {
 public:
  virtual ~ProductS5MessageBusPort() = default;
  virtual bool begin(
      const std::string &subscription,
      ProductS5MessageBusSink *sink) = 0;
  virtual bool connected() = 0;
  virtual bool publish_message(
      const std::string &topic,
      const std::string &payload,
      uint8_t qos,
      bool retain) = 0;
};

struct ProductS5ManagerTransportPolicy {
  uint32_t authority_refresh_interval_ms{10000};
  uint32_t authority_max_age_ms{30000};
  uint32_t authority_request_timeout_ms{5000};
  uint32_t direct_liveness_interval_ms{5000};

  bool valid() const {
    return authority_refresh_interval_ms >= 1000 &&
           authority_refresh_interval_ms <= authority_max_age_ms &&
           authority_max_age_ms <= 300000 &&
           authority_request_timeout_ms >= 500 &&
           authority_request_timeout_ms <= authority_max_age_ms &&
           direct_liveness_interval_ms >= 1000 &&
           direct_liveness_interval_ms <= 10000;
  }
};

// Opt-in isolated Relay transport. It carries only the existing S4 peer
// authorization request/response and the existing gh.relay/1 envelope. It
// never creates or distributes a pair LMK and never owns peer identity.
class ProductS5IsolatedManagerTransport final : public ProductS5ManagerPort,
                                                 public RelayForwardSink,
                                                 public ProductS5MessageBusSink {
 public:
  ProductS5IsolatedManagerTransport(
      std::string system_id,
      std::string relay_node_id,
      ProductRuntimeClock *clock,
      ProductS5MessageBusPort *bus,
      ProductS5ManagerAuthorizationSink *authorization_sink,
      uint64_t boot_session,
      ProductS5ManagerTransportPolicy policy = {});

  bool start();
  bool maintain_direct_liveness();
  bool authority_now_ms(uint64_t *now_ms) override;
  bool submit_peer_authorization(
      const ProductPeerRequest &request) override;

  bool accept_for_forwarding(const RelayFrame &frame) override;
  void on_s5_message(
      const std::string &topic,
      const std::string &payload) override;

  bool started() const { return started_; }
  bool authority_time_ready() const { return authority_anchor_valid_; }
  bool authorization_pending() const {
    return !pending_authorization_session_.empty();
  }
  const std::string &relay_node_id() const { return relay_node_id_; }

 private:
  bool request_authority_time_(uint64_t local_now_ms);
  void clear_authority_anchor_();
  static bool same_grant_pair_(
      const ProductPeerGrant &child,
      const ProductPeerGrant &relay);

  std::string system_id_;
  std::string relay_node_id_;
  ProductRuntimeClock *clock_{nullptr};
  ProductS5MessageBusPort *bus_{nullptr};
  ProductS5ManagerAuthorizationSink *authorization_sink_{nullptr};
  uint64_t boot_session_{0};
  ProductS5ManagerTransportPolicy policy_{};
  bool started_{false};
  std::string response_subscription_;
  std::string time_request_topic_;
  std::string time_response_topic_;
  std::string direct_liveness_topic_;
  std::string direct_liveness_boot_id_;
  uint32_t direct_liveness_sequence_{0};
  uint64_t direct_liveness_last_local_ms_{0};
  bool direct_liveness_sent_{false};
  bool direct_liveness_exhausted_{false};

  uint64_t time_request_counter_{0};
  bool time_request_pending_{false};
  uint64_t time_request_local_ms_{0};
  std::string time_request_nonce_;
  bool authority_anchor_valid_{false};
  uint64_t authority_anchor_epoch_ms_{0};
  uint64_t authority_anchor_local_ms_{0};

  std::string pending_authorization_session_;
};

#ifdef USE_MQTT
class ProductS5EspHomeMqttBus final : public mqtt::CustomMQTTDevice,
                                      public ProductS5MessageBusPort {
 public:
  bool begin(
      const std::string &subscription,
      ProductS5MessageBusSink *sink) override;
  bool connected() override;
  bool publish_message(
      const std::string &topic,
      const std::string &payload,
      uint8_t qos,
      bool retain) override;

 private:
  void on_message_(
      const std::string &topic,
      const std::string &payload);

  bool started_{false};
  ProductS5MessageBusSink *sink_{nullptr};
};
#endif

}  // namespace esphome::greenhouse_n3w_s5_manager_transport
