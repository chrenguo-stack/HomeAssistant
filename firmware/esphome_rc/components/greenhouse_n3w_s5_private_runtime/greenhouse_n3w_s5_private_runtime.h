#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>

#include "esphome/components/greenhouse_n3w_product_runtime/n3w_product_integration.h"
#include "esphome/core/component.h"
#include "n3w_product_s5_private_telemetry_stimulus.h"

namespace esphome::greenhouse_n3w_s5_private_runtime {

using greenhouse_n3w_product_runtime::GreenhouseN3wProductIntegration;
using greenhouse_n3w_product_runtime::ProductRelayHealth;
using greenhouse_n3w_product_runtime::ProductS5NodeCredentials;
using greenhouse_n3w_product_runtime::ProductS5RelayHealthProvider;
using greenhouse_n3w_product_runtime::ProductS5SelfCredentialProvider;
using greenhouse_n3w_product_runtime::MacAddress;

class GreenhouseN3wS5PrivateRuntimeMaterial final
    : public Component,
      public ProductS5SelfCredentialProvider,
      public ProductS5RelayHealthProvider {
 public:
  ~GreenhouseN3wS5PrivateRuntimeMaterial() override;

  void set_role(const std::string &value) { role_ = value; }
  void set_system_id(const std::string &value) { system_id_ = value; }
  void set_node_id(const std::string &value) { node_id_ = value; }
  void set_credential_generation(uint32_t value) { credential_generation_ = value; }
  void set_key_epoch(uint32_t value) { key_epoch_ = value; }
  void set_application_key_hex(const std::string &value) { application_key_hex_ = value; }
  void set_local_mac(const std::string &value) { local_mac_text_ = value; }
  void set_relay_capable(bool value) { relay_capable_ = value; }
  void set_low_battery(bool value) { low_battery_ = value; }
  void set_overloaded(bool value) { overloaded_ = value; }
  void set_telemetry_stimulus_enabled(bool value) { telemetry_stimulus_enabled_ = value; }
  void set_telemetry_stimulus_boot_session(uint64_t value) {
    telemetry_stimulus_boot_session_ = value;
  }
  void set_telemetry_stimulus_seq(uint32_t value) { telemetry_stimulus_seq_ = value; }

  // Child has no direct Manager transport. The private provider binds only the
  // child's own post-registration material into the already-reviewed S5 path.
  bool configure_child(GreenhouseN3wProductIntegration *integration);

  bool load_self(ProductS5NodeCredentials *credentials, MacAddress *local_mac) override;
  bool read_health(uint64_t authority_now_ms, ProductRelayHealth *health) override;

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override;

  bool material_ready() const { return material_ready_; }
  bool application_key_resident() const;
  uint8_t remaining_credential_loads() const { return remaining_credential_loads_; }
  bool telemetry_stimulus_submitted() const { return telemetry_stimulus_.submitted(); }

 private:
  static bool parse_hex_key_(const std::string &value, std::array<uint8_t, 32> *output);
  static bool parse_mac_(const std::string &value, MacAddress *output);
  static void zeroize_(void *data, std::size_t length);

  std::string role_{"child"};
  std::string system_id_{};
  std::string node_id_{};
  uint32_t credential_generation_{0};
  uint32_t key_epoch_{0};
  std::string application_key_hex_{};
  std::string local_mac_text_{};
  std::array<uint8_t, 32> application_key_{};
  MacAddress local_mac_{};
  bool relay_capable_{true};
  bool low_battery_{false};
  bool overloaded_{false};
  bool child_bound_{false};
  bool material_ready_{false};
  uint8_t remaining_credential_loads_{0};
  GreenhouseN3wProductIntegration *child_integration_{nullptr};

  bool telemetry_stimulus_enabled_{false};
  uint64_t telemetry_stimulus_boot_session_{0};
  uint32_t telemetry_stimulus_seq_{0};
  ProductS5PrivateTelemetryStimulus telemetry_stimulus_{};
};

}  // namespace esphome::greenhouse_n3w_s5_private_runtime
