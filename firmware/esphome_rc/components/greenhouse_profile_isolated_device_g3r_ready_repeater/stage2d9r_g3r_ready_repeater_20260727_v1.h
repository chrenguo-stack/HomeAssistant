#pragma once

#include <cstdint>
#include <string>

#include "esphome/core/component.h"

namespace esphome::greenhouse_pairing_client {

// Read-only companion for the frozen V1 executor. It does not parse commands,
// grant authorization, touch credentials, or write NVS. It only projects the
// boot-time PREPARE/VERIFY readiness state as a repeated serial marker so a host
// cannot permanently miss the executor's one-shot setup log line.
class Stage2D9RG3RReadyRepeaterV1 final : public Component {
 public:
  void set_partition_label(const std::string &value) {
    this->partition_label_ = value;
  }
  void set_namespace_name(const std::string &value) {
    this->namespace_name_ = value;
  }
  void set_repeat_interval_ms(uint32_t value) {
    this->repeat_interval_ms_ = value;
  }
  void set_repeat_window_ms(uint32_t value) {
    this->repeat_window_ms_ = value;
  }

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override;

 protected:
  enum class ReadyMode : uint8_t {
    NONE = 0,
    PREPARE = 1,
    VERIFY = 2,
  };

  bool inspect_read_only_();
  void emit_ready_marker_() const;

  std::string partition_label_{};
  std::string namespace_name_{};
  uint32_t repeat_interval_ms_{1000};
  uint32_t repeat_window_ms_{180000};
  uint32_t started_ms_{0};
  uint32_t last_emit_ms_{0};
  ReadyMode ready_mode_{ReadyMode::NONE};
  bool enabled_{false};
};

}  // namespace esphome::greenhouse_pairing_client
