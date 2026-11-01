#include "n3w_product_s5_private_telemetry_stimulus.h"

#include <algorithm>
#include <utility>

namespace esphome::greenhouse_n3w_s5_private_runtime {

using greenhouse_n3w_core::ApplicationKeyState;
using greenhouse_n3w_core::CoreError;
using greenhouse_n3w_core::KeyLifecycle;
using greenhouse_n3w_core::RelayHeader;

ProductS5PrivateTelemetryStimulus::~ProductS5PrivateTelemetryStimulus() {
  zeroize_(application_key_.data(), application_key_.size());
}

bool ProductS5PrivateTelemetryStimulus::nonzero_(
    const std::array<uint8_t, greenhouse_n3w_core::kApplicationKeyBytes> &value) {
  uint8_t aggregate = 0;
  for (uint8_t byte : value) aggregate |= byte;
  return aggregate != 0;
}

void ProductS5PrivateTelemetryStimulus::zeroize_(
    void *data,
    std::size_t length) {
  if (data == nullptr) return;
  volatile uint8_t *cursor = static_cast<volatile uint8_t *>(data);
  while (length-- > 0) *cursor++ = 0;
}

bool ProductS5PrivateTelemetryStimulus::configure(
    const std::string &node_id,
    uint32_t key_epoch,
    const std::array<uint8_t, greenhouse_n3w_core::kApplicationKeyBytes> &application_key,
    uint64_t boot_session,
    uint32_t seq) {
  if (configured_ || submitted_ || node_id.size() < 8 ||
      !greenhouse_n3w_core::valid_identity(node_id) || key_epoch == 0 ||
      boot_session == 0 || !nonzero_(application_key)) {
    return false;
  }
  node_id_ = node_id;
  key_epoch_ = key_epoch;
  boot_session_ = boot_session;
  seq_ = seq;
  application_key_ = application_key;
  configured_ = true;
  return true;
}

ProductS5PrivateTelemetryStimulusError
ProductS5PrivateTelemetryStimulus::prepare(
    const std::string &gateway_id,
    uint64_t uptime_ms) {
  if (!configured_) return ProductS5PrivateTelemetryStimulusError::NOT_CONFIGURED;
  if (submitted_) return ProductS5PrivateTelemetryStimulusError::ALREADY_SUBMITTED;
  if (prepared_) return ProductS5PrivateTelemetryStimulusError::ALREADY_PREPARED;
  if (!greenhouse_n3w_core::valid_identity(gateway_id) || gateway_id == node_id_ ||
      !application_key_resident()) {
    return ProductS5PrivateTelemetryStimulusError::INVALID_ARGUMENT;
  }

  const std::string boot_id = greenhouse_n3w_core::format_boot_id(boot_session_);
  if (boot_id.empty()) {
    zeroize_(application_key_.data(), application_key_.size());
    return ProductS5PrivateTelemetryStimulusError::BUILD_FAILED;
  }

  RelayHeader header;
  header.gateway_id = gateway_id;
  header.node_id = node_id_;
  header.key_epoch = key_epoch_;
  header.boot_id = boot_id;
  header.seq = seq_;

  const std::string telemetry =
      "{\"schema\":\"gh.telemetry/1\",\"node_id\":\"" + node_id_ +
      "\",\"boot_id\":\"" + boot_id +
      "\",\"seq\":" + std::to_string(seq_) +
      ",\"uptime_ms\":" + std::to_string(uptime_ms) +
      ",\"cap_hash\":\"s5_r7_private_stimulus_v1\""
      ",\"fw_version\":\"s5-r7-private-stimulus\""
      ",\"measurements\":{\"air_temperature_c\":24.5}"
      ",\"quality\":{\"air_temperature_c\":\"ok\"}"
      ",\"power\":{\"source\":\"main\",\"low\":false}"
      ",\"test_only\":{\"source\":\"private_physical_e2e\",\"exactly_once\":true}}";

  ApplicationKeyState key_state;
  key_state.lifecycle = KeyLifecycle::ACTIVE;
  key_state.key_epoch = key_epoch_;
  key_state.key = application_key_;

  greenhouse_n3w_core::RelayFrame candidate;
  const CoreError built =
      greenhouse_n3w_core::build_relay_frame(header, key_state, telemetry, &candidate);

  key_state.clear();
  zeroize_(application_key_.data(), application_key_.size());

  if (built != CoreError::NONE) {
    return ProductS5PrivateTelemetryStimulusError::BUILD_FAILED;
  }

  gateway_id_ = gateway_id;
  frame_ = std::move(candidate);
  prepared_ = true;
  return ProductS5PrivateTelemetryStimulusError::NONE;
}

bool ProductS5PrivateTelemetryStimulus::mark_submitted() {
  if (!prepared_ || submitted_) return false;
  frame_ = greenhouse_n3w_core::RelayFrame{};
  gateway_id_.clear();
  prepared_ = false;
  submitted_ = true;
  return true;
}

bool ProductS5PrivateTelemetryStimulus::application_key_resident() const {
  return nonzero_(application_key_);
}

}  // namespace esphome::greenhouse_n3w_s5_private_runtime
