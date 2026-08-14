#pragma once

#include <memory>
#include <optional>

#include "esphome/components/greenhouse_n3w_product_runtime/n3w_product_integration.h"
#include "esphome/core/component.h"
#include "n3w_product_s5_manager_transport.h"

namespace esphome::greenhouse_n3w_s5_manager_transport {

using greenhouse_n3w_product_runtime::GreenhouseN3wProductIntegration;
using greenhouse_n3w_product_runtime::ProductS5NodeCredentials;
using greenhouse_n3w_product_runtime::ProductS5RelayHealthProvider;
using greenhouse_n3w_product_runtime::ProductS5SelfCredentialProvider;

class GreenhouseN3wS5ManagerTransportComponent final
    : public Component,
      public ProductS5ManagerAuthorizationSink {
 public:
  void set_product_integration(
      GreenhouseN3wProductIntegration *integration) {
    integration_ = integration;
  }
  void set_execution_enabled(bool value) {
    execution_enabled_ = value;
  }

  // Private lab composition supplies only this Relay's own post-registration
  // credential provider and live health provider. Public YAML never calls this.
  bool configure_private(
      ProductS5SelfCredentialProvider *self_credentials,
      ProductS5RelayHealthProvider *relay_health);

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override;

  bool queue_s5_manager_authorization(
      const ProductPeerGrant &child_grant,
      const ProductPeerGrant &relay_grant) override;

 private:
  static void zeroize_(void *data, std::size_t length);

  bool execution_enabled_{false};
  bool private_configured_{false};
  bool active_{false};
  GreenhouseN3wProductIntegration *integration_{nullptr};
  ProductS5SelfCredentialProvider *self_credentials_{nullptr};
  ProductS5RelayHealthProvider *relay_health_{nullptr};
  std::unique_ptr<ProductS5EspHomeMqttBus> bus_{};
  std::unique_ptr<ProductS5IsolatedManagerTransport> transport_{};
  std::optional<ProductPeerGrant> queued_child_grant_{};
  std::optional<ProductPeerGrant> queued_relay_grant_{};
};

}  // namespace esphome::greenhouse_n3w_s5_manager_transport
