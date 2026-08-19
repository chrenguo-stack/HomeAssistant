#pragma once

#include <array>
#include <cstdint>
#include <string>
#include <utility>

#include "n3w_esp32_simple_nvs.h"

namespace esphome::greenhouse_n3w_core {

struct PendingPairingAckV2 {
  std::string manager_host;
  uint16_t manager_port{0};
  std::string pairing_path;
  std::string session_id;
  std::array<uint8_t, 32> delivery_digest{};

  bool valid() const;
  void clear();
};

class NvsPendingPairingAckStoreV2 {
 public:
  explicit NvsPendingPairingAckStoreV2(
      std::string namespace_name = "gh_n3w_v2",
      std::string key_name = "pair_ack")
      : namespace_name_(std::move(namespace_name)), key_name_(std::move(key_name)) {}

  SimpleNvsStatus load(PendingPairingAckV2 *state);
  SimpleNvsStatus save(const PendingPairingAckV2 &state);
  SimpleNvsStatus erase();

 private:
  std::string namespace_name_;
  std::string key_name_;
};

}  // namespace esphome::greenhouse_n3w_core
