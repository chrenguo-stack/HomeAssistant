#include "echo_filtered_modbus.h"

#include <algorithm>
#include <cinttypes>

#include "esphome/components/uart/uart_component.h"
#include "esphome/core/helpers.h"
#include "esphome/core/log.h"

namespace esphome {
namespace echo_filtered_modbus {

static const char *const TAG = "echo_filtered_modbus";

void EchoFilteredModbus::add_filter_function_code(uint8_t function_code) {
  if (!this->function_code_is_filtered_(function_code)) {
    this->filter_function_codes_.push_back(function_code);
  }
}

bool EchoFilteredModbus::function_code_is_filtered_(uint8_t function_code) const {
  return std::find(this->filter_function_codes_.begin(), this->filter_function_codes_.end(), function_code) !=
         this->filter_function_codes_.end();
}

bool EchoFilteredModbus::should_filter_frame_(const std::vector<uint8_t> &frame) const {
  // RTU request must contain at least address, function and two CRC bytes.
  if (frame.size() < 4) {
    return false;
  }
  return this->function_code_is_filtered_(frame[1]);
}

void EchoFilteredModbus::arm_echo_filter_(const std::vector<uint8_t> &frame) {
  this->echo_candidate_.clear();
  this->expected_echo_.clear();
  this->echo_filter_active_ = false;

  if (!this->should_filter_frame_(frame)) {
    return;
  }

  this->expected_echo_ = frame;
  this->echo_candidate_.reserve(frame.size());
  this->echo_filter_started_ms_ = millis();
  this->echo_filter_active_ = true;

  ESP_LOGV(TAG, "Armed exact echo filter for %zu-byte TX frame: %s", frame.size(),
           format_hex_pretty(frame, ':', false).c_str());
}

void EchoFilteredModbus::pass_byte_to_official_parser_(uint8_t byte) {
  if (this->rx_buffer_.empty()) {
    ESP_LOGV(TAG, "Passing first response byte %" PRIu8 " (0x%02X), %" PRIu32 "ms after send", byte, byte,
             millis() - this->last_send_);
  } else {
    ESP_LOGVV(TAG, "Passing response byte %" PRIu8 " (0x%02X), %" PRIu32 "ms after send", byte, byte,
              millis() - this->last_send_);
  }

  // This is ESPHome's official parser. If it rejects the byte sequence,
  // preserve the official behavior and clear the parser buffer.
  if (!this->parse_modbus_byte_(byte)) {
    this->clear_rx_buffer_(LOG_STR("parse failed after echo filter"), true);
  }
}

void EchoFilteredModbus::flush_candidate_to_official_parser_() {
  for (const uint8_t byte : this->echo_candidate_) {
    this->pass_byte_to_official_parser_(byte);
  }
  this->echo_candidate_.clear();
}

void EchoFilteredModbus::handle_candidate_timeout_() {
  if (!this->echo_filter_active_ || this->echo_candidate_.empty()) {
    return;
  }

  // For read functions 0x01..0x04, a valid client response differs from the
  // request at byte 2 (response byte-count versus request start-address high).
  // Therefore, three or more bytes still matching the request are not a valid
  // read response prefix and can safely be treated as a partial local echo.
  if (this->echo_candidate_.size() >= 3) {
    this->partial_echo_drop_count_++;
    ESP_LOGW(TAG,
             "Dropping timed-out partial TX echo (%zu/%zu bytes, count=%" PRIu32 "): %s",
             this->echo_candidate_.size(), this->expected_echo_.size(), this->partial_echo_drop_count_,
             format_hex_pretty(this->echo_candidate_, ':', false).c_str());
    this->echo_candidate_.clear();
  } else {
    // One or two matching bytes may be the beginning of a legitimate response;
    // return them to the official parser rather than discarding them.
    ESP_LOGV(TAG, "Echo candidate timed out after %zu byte(s); returning candidate to official parser",
             this->echo_candidate_.size());
    this->flush_candidate_to_official_parser_();
  }

  this->expected_echo_.clear();
  this->echo_filter_active_ = false;
}

void EchoFilteredModbus::process_received_byte_(uint8_t byte) {
  if (!this->echo_filter_active_ || this->expected_echo_.empty()) {
    this->pass_byte_to_official_parser_(byte);
    return;
  }

  if (millis() - this->echo_filter_started_ms_ > this->echo_timeout_ms_) {
    this->handle_candidate_timeout_();
    this->pass_byte_to_official_parser_(byte);
    return;
  }

  const size_t index = this->echo_candidate_.size();
  if (index < this->expected_echo_.size() && byte == this->expected_echo_[index]) {
    this->echo_candidate_.push_back(byte);

    if (this->echo_candidate_.size() == this->expected_echo_.size()) {
      this->filtered_echo_count_++;
      if (this->log_filtered_echo_) {
        ESP_LOGI(TAG, "Discarded exact TX echo #%" PRIu32 " (%zu bytes): %s", this->filtered_echo_count_,
                 this->echo_candidate_.size(),
                 format_hex_pretty(this->echo_candidate_, ':', false).c_str());
      } else {
        ESP_LOGV(TAG, "Discarded exact TX echo #%" PRIu32 " (%zu bytes)", this->filtered_echo_count_,
                 this->echo_candidate_.size());
      }

      this->echo_candidate_.clear();
      this->expected_echo_.clear();
      this->echo_filter_active_ = false;
    }
    return;
  }

  // No exact echo: this can be a normal response (for example 01 03 06 ...).
  // Return every held prefix byte, then the current mismatching byte, to the
  // official parser in original order without modifying any data.
  this->candidate_mismatch_count_++;
  ESP_LOGV(TAG,
           "Echo candidate mismatch at byte %zu (expected 0x%02X, got 0x%02X); passing data to official parser",
           index, index < this->expected_echo_.size() ? this->expected_echo_[index] : 0, byte);

  this->flush_candidate_to_official_parser_();
  this->expected_echo_.clear();
  this->echo_filter_active_ = false;
  this->pass_byte_to_official_parser_(byte);
}

void EchoFilteredModbus::receive_and_parse_filtered_bytes_() {
  size_t available_bytes = this->available();
  uint8_t buffer[64];

  while (available_bytes > 0) {
    const size_t to_read = std::min(available_bytes, sizeof(buffer));
    if (!this->read_array(buffer, to_read)) {
      break;
    }
    available_bytes -= to_read;

    for (size_t i = 0; i < to_read; i++) {
      this->process_received_byte_(buffer[i]);
      // Keep ESPHome's timing behavior: all physical UART bytes, including a
      // discarded local echo, update the last-received-byte timestamp.
      this->last_modbus_byte_ = millis();
    }
  }
}

void EchoFilteredModbus::loop() {
  // 1. Receive UART bytes, discard only an exact copy of the just-sent frame,
  //    and forward all other bytes to ESPHome's official Modbus parser.
  this->receive_and_parse_filtered_bytes_();

  // A partial candidate may remain when the line stops before a complete echo.
  if (this->echo_filter_active_ && !this->echo_candidate_.empty() &&
      millis() - this->echo_filter_started_ms_ > this->echo_timeout_ms_) {
    this->handle_candidate_timeout_();
  }

  // 2. Preserve the official Modbus partial-response timeout behavior.
  const uint16_t timeout = std::max(
      static_cast<uint16_t>(this->frame_delay_ms_),
      static_cast<uint16_t>(
          this->rx_buffer_.size() >= this->parent_->get_rx_full_threshold() ? this->long_rx_buffer_delay_ms_ : 0));

  if (millis() - this->last_modbus_byte_ > timeout) {
    this->clear_rx_buffer_(LOG_STR("timeout after partial response"), true);
  }

  // 3. Preserve the official response wait timeout behavior.
  if (this->waiting_for_response_ != 0 &&
      millis() - this->last_send_ > this->last_send_tx_offset_ + this->send_wait_time_ &&
      (this->rx_buffer_.empty() || this->rx_buffer_[0] != this->waiting_for_response_)) {
    ESP_LOGW(TAG, "Stop waiting for response from %" PRIu8 " %" PRIu32 "ms after last send",
             this->waiting_for_response_, millis() - this->last_send_);
    this->waiting_for_response_ = 0;
  }

  // 4. Let ESPHome's official Modbus implementation send the next queued frame.
  //    Snapshot the exact RTU bytes before send_next_frame_() pops the queue.
  const size_t queued_before = this->tx_buffer_.size();
  std::vector<uint8_t> frame_about_to_send;
  if (queued_before > 0) {
    const auto &frame = this->tx_buffer_.front();
    frame_about_to_send.assign(frame.data.get(), frame.data.get() + frame.size);
  }

  this->send_next_frame_();

  // Queue size decreases only when the official sender actually transmitted
  // and popped a frame. Arm the filter for that exact transmitted frame.
  if (this->tx_buffer_.size() < queued_before && !frame_about_to_send.empty()) {
    this->arm_echo_filter_(frame_about_to_send);
  }
}

void EchoFilteredModbus::dump_config() {
  modbus::Modbus::dump_config();

  ESP_LOGCONFIG(TAG, "TX Echo Filter:");
  ESP_LOGCONFIG(TAG, "  Echo timeout: %" PRIu32 " ms", this->echo_timeout_ms_);
  ESP_LOGCONFIG(TAG, "  Log discarded echo at INFO: %s", YESNO(this->log_filtered_echo_));

  if (this->filter_function_codes_.empty()) {
    ESP_LOGCONFIG(TAG, "  Filtered function codes: none");
  } else {
    ESP_LOGCONFIG(TAG, "  Filtered function codes: %s",
                  format_hex_pretty(this->filter_function_codes_, ',', false).c_str());
  }
}

}  // namespace echo_filtered_modbus
}  // namespace esphome
