#pragma once

#include <cstdint>
#include <string>
#include <utility>

#include "n3w_esp32_simple_nvs.h"

namespace esphome::greenhouse_n3w_core {

struct ProvisionedBrokerStateV2 {
  std::string system_id;
  std::string node_id;
  std::string broker_host;
  uint16_t broker_port{0};
  std::string broker_tls_server_name;
  std::string ca_pem;
  std::string mqtt_username;
  std::string mqtt_password;
  std::string mqtt_client_id;
  uint32_t credential_generation{0};

  bool valid() const;
  void clear();
};

class NvsProvisionedBrokerStoreV2 {
 public:
  explicit NvsProvisionedBrokerStoreV2(
      std::string namespace_name = "gh_n3w_v2",
      std::string key_name = "broker")
      : namespace_name_(std::move(namespace_name)), key_name_(std::move(key_name)) {}

  SimpleNvsStatus load(ProvisionedBrokerStateV2 *state);
  SimpleNvsStatus save(const ProvisionedBrokerStateV2 &state);
  SimpleNvsStatus erase();

 private:
  std::string namespace_name_;
  std::string key_name_;
};

}  // namespace esphome::greenhouse_n3w_core
