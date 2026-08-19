#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>

#include "esphome/components/greenhouse_n3w_core/n3w_core.h"

namespace esphome::greenhouse_n3w_s5_private_runtime {

enum class ProductS5PrivateTelemetryStimulusError : uint8_t {
  NONE = 0,
  INVALID_ARGUMENT,
  NOT_CONFIGURED,
  ALREADY_PREPARED,
  ALREADY_SUBMITTED,
  BUILD_FAILED,
};

class ProductS5PrivateTelemetryStimulus final {
 public:
  ProductS5PrivateTelemetryStimulus() = default;
  ~ProductS5PrivateTelemetryStimulus();

  bool configure(
      const std::string &node_id,
      uint32_t key_epoch,
      const std::array<uint8_t, greenhouse_n3w_core::kApplicationKeyBytes> &application_key,
      uint64_t boot_session,
      uint32_t seq);

  ProductS5PrivateTelemetryStimulusError prepare(
      const std::string &gateway_id,
      uint64_t uptime_ms);

  const greenhouse_n3w_core::RelayFrame *prepared_frame() const {
    return prepared_ ? &frame_ : nullptr;
  }
  const std::string &prepared_gateway_id() const { return gateway_id_; }

  bool mark_submitted();

  bool configured() const { return configured_; }
  bool prepared() const { return prepared_; }
  bool submitted() const { return submitted_; }
  bool application_key_resident() const;

 private:
  static bool nonzero_(
      const std::array<uint8_t, greenhouse_n3w_core::kApplicationKeyBytes> &value);
  static void zeroize_(void *data, std::size_t length);

  bool configured_{false};
  bool prepared_{false};
  bool submitted_{false};
  std::string node_id_{};
  uint32_t key_epoch_{0};
  uint64_t boot_session_{0};
  uint32_t seq_{0};
  std::array<uint8_t, greenhouse_n3w_core::kApplicationKeyBytes> application_key_{};
  std::string gateway_id_{};
  greenhouse_n3w_core::RelayFrame frame_{};
};

}  // namespace esphome::greenhouse_n3w_s5_private_runtime
