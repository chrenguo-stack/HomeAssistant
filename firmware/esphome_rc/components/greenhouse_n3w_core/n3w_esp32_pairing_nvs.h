#pragma once

#include <array>
#include <cstdint>
#include <string>
#include <utility>

#include "n3w_esp32_simple_nvs.h"

namespace esphome::greenhouse_n3w_core {

inline constexpr uint16_t kPendingPairingAckLegacyVersion = 1U;
inline constexpr uint16_t kPendingPairingAckCurrentVersion = 2U;

enum class PendingPairingAckState : uint8_t {
  ACK_PENDING = 1,
  TERMINAL_CLEANUP = 2,
};

struct PendingPairingAckV2 {
  uint16_t format_version{kPendingPairingAckCurrentVersion};
  PendingPairingAckState state{PendingPairingAckState::ACK_PENDING};

  // Exact 47112 final-ACK locator.
  std::string manager_host;
  uint16_t manager_port{0};
  std::string pairing_path;
  std::string session_id;
  std::array<uint8_t, 32> delivery_digest{};

  // R6 recovery identity. Legacy version-1 records do not contain these.
  std::string pairing_id;
  std::string manager_id;
  std::string system_id;
  std::string bootstrap_host;
  uint16_t bootstrap_port{0};
  std::string bootstrap_tls_sha256;

  bool valid() const;
  bool legacy() const {
    return format_version == kPendingPairingAckLegacyVersion;
  }
  bool recovery_capable() const;
  void clear();
};

class NvsPendingPairingAckStoreV2 {
 public:
  explicit NvsPendingPairingAckStoreV2(
      std::string namespace_name = "gh_n3w_v2",
      std::string key_name = "pair_ack")
      : namespace_name_(std::move(namespace_name)), key_name_(std::move(key_name)) {}

  // load() recognizes both the legacy version-1 blob and the R6 version-2 blob.
  // R6 writes version 2; the legacy writer remains only for the predecessor
  // non-selected pairing path so source compatibility is not silently broken.
  SimpleNvsStatus load(PendingPairingAckV2 *state);
  SimpleNvsStatus save(const PendingPairingAckV2 &state);
  SimpleNvsStatus erase();

 private:
  std::string namespace_name_;
  std::string key_name_;
};

}  // namespace esphome::greenhouse_n3w_core
