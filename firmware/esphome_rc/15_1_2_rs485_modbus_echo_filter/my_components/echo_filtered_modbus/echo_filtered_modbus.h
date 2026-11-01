#pragma once

#include <cstdint>
#include <vector>

#include "esphome/components/modbus/modbus.h"

namespace esphome {
namespace echo_filtered_modbus {

/**
 * Modbus RTU client with an exact TX-echo filter in front of ESPHome's
 * official Modbus parser.
 *
 * Only the local echo is custom-handled. CRC checking, frame parsing,
 * command queueing, retries, device online/offline handling and register
 * decoding remain in ESPHome's official modbus/modbus_controller components.
 */
class EchoFilteredModbus : public modbus::Modbus {
 public:
  void loop() override;
  void dump_config() override;

  void set_echo_timeout(uint32_t timeout_ms) { this->echo_timeout_ms_ = timeout_ms; }
  void set_log_filtered_echo(bool enabled) { this->log_filtered_echo_ = enabled; }
  void add_filter_function_code(uint8_t function_code);

 protected:
  void receive_and_parse_filtered_bytes_();
  void process_received_byte_(uint8_t byte);
  void pass_byte_to_official_parser_(uint8_t byte);
  void flush_candidate_to_official_parser_();
  void handle_candidate_timeout_();
  void arm_echo_filter_(const std::vector<uint8_t> &frame);
  bool should_filter_frame_(const std::vector<uint8_t> &frame) const;
  bool function_code_is_filtered_(uint8_t function_code) const;

  std::vector<uint8_t> expected_echo_;
  std::vector<uint8_t> echo_candidate_;
  std::vector<uint8_t> filter_function_codes_;

  bool echo_filter_active_{false};
  bool log_filtered_echo_{true};
  uint32_t echo_filter_started_ms_{0};
  uint32_t echo_timeout_ms_{100};
  uint32_t filtered_echo_count_{0};
  uint32_t candidate_mismatch_count_{0};
  uint32_t partial_echo_drop_count_{0};
};

}  // namespace echo_filtered_modbus
}  // namespace esphome
