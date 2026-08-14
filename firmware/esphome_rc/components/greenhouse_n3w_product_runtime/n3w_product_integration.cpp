#include "n3w_product_integration.h"

#include <cctype>

#include "esphome/core/log.h"

#ifdef USE_ESP32
#include "esp_timer.h"
#endif

namespace esphome::greenhouse_n3w_product_runtime {
namespace {
static const char *const TAG = "n3w_product_integration";
}

bool GreenhouseN3wProductIntegration::parse_hex_key_(
    const std::string &value,
    LinkKey *output) {
  if (output == nullptr || value.size() != output->size() * 2) return false;
  uint8_t aggregate = 0;
  auto nibble = [](char character) -> uint8_t {
    if (character >= '0' && character <= '9') return character - '0';
    character = static_cast<char>(std::tolower(static_cast<unsigned char>(character)));
    if (character >= 'a' && character <= 'f') return character - 'a' + 10;
    return 0xff;
  };
  for (std::size_t index = 0; index < output->size(); ++index) {
    const uint8_t high = nibble(value[index * 2]);
    const uint8_t low = nibble(value[index * 2 + 1]);
    if (high == 0xff || low == 0xff) return false;
    (*output)[index] = static_cast<uint8_t>((high << 4U) | low);
    aggregate |= (*output)[index];
  }
  return aggregate != 0;
}

float GreenhouseN3wProductIntegration::get_setup_priority() const {
  return setup_priority::AFTER_WIFI;
}

uint64_t GreenhouseN3wProductIntegration::now_ms() const {
#ifdef USE_ESP32
  return static_cast<uint64_t>(esp_timer_get_time() / 1000ULL);
#else
  return 0;
#endif
}

void GreenhouseN3wProductIntegration::setup() {
  if ((role_ != "child" && role_ != "relay") ||
      !greenhouse_n3w_core::valid_radio_channel(last_direct_channel_) ||
      !parse_hex_key_(pmk_hex_, &pmk_)) {
    ESP_LOGE(TAG, "N3-W Product integration configuration rejected");
    this->mark_failed();
    return;
  }
  ESP_LOGI(
      TAG,
      "S5 integration setup role=%s execution_enabled=%s fixed_peer=false",
      role_.c_str(),
      execution_enabled_ ? "true" : "false");
  if (!execution_enabled_) return;

  runtime_ = std::make_unique<ProductEspNowRuntime>(
      &radio_, this, nullptr, WifiDirectHealthPolicy{}, RelayCandidatePolicy{},
      AutoPathPolicy{}, ProductRuntimePolicy{});
  coordinator_ = std::make_unique<ProductRuntimeCoordinator>(runtime_.get(), this);
  runtime_->set_event_sink(coordinator_.get());
  if (runtime_->set_last_direct_channel(last_direct_channel_) != ProductRuntimeError::NONE ||
      runtime_->start(pmk_) != ProductRuntimeError::NONE) {
    ESP_LOGE(TAG, "N3-W Product integration failed to start");
    this->mark_failed();
  }
}

void GreenhouseN3wProductIntegration::loop() {
  if (!execution_enabled_ || this->is_failed() || coordinator_ == nullptr) return;
  const ProductRuntimeError result = coordinator_->tick();
  if (result != ProductRuntimeError::NONE) {
    ESP_LOGW(TAG, "N3-W Product integration tick result=%u", static_cast<unsigned>(result));
  }
}

void GreenhouseN3wProductIntegration::dump_config() {
  ESP_LOGCONFIG(TAG, "N3-W Product Completion S3/S4 board integration");
  ESP_LOGCONFIG(TAG, "  role: %s", role_.c_str());
  ESP_LOGCONFIG(TAG, "  execution enabled: %s", execution_enabled_ ? "true" : "false");
  ESP_LOGCONFIG(TAG, "  factory fixed peer: false");
  ESP_LOGCONFIG(TAG, "  PMK bytes logged: false");
}

bool GreenhouseN3wProductIntegration::request_manager_eligibility(
    const RelayCandidateRecord &candidate) {
  pending_manager_candidate_ = candidate;
  eligibility_requested_ = true;
  return true;
}

bool GreenhouseN3wProductIntegration::poll_manager_eligibility(
    ManagerEligibilityDecision *decision) {
  if (decision == nullptr || !eligibility_decision_.has_value()) return false;
  *decision = *eligibility_decision_;
  eligibility_decision_.reset();
  eligibility_requested_ = false;
  return true;
}

bool GreenhouseN3wProductIntegration::request_peer_authorization(
    const RelayCandidateRecord &candidate) {
  pending_manager_candidate_ = candidate;
  authorization_requested_ = true;
  return true;
}

bool GreenhouseN3wProductIntegration::poll_peer_authorization(
    ManagerPeerAuthorizationDecision *decision) {
  if (decision == nullptr || !authorization_decision_.has_value()) return false;
  *decision = *authorization_decision_;
  authorization_decision_.reset();
  authorization_requested_ = false;
  return true;
}

bool GreenhouseN3wProductIntegration::submit_manager_eligibility(
    const ManagerEligibilityDecision &decision) {
  if (!eligibility_requested_ || eligibility_decision_.has_value()) return false;
  eligibility_decision_ = decision;
  return true;
}

bool GreenhouseN3wProductIntegration::submit_peer_authorization(
    const ManagerPeerAuthorizationDecision &decision) {
  if (!authorization_requested_ || authorization_decision_.has_value() ||
      decision.status == ManagerPeerAuthorizationStatus::NONE) {
    return false;
  }
  authorization_decision_ = decision;
  return true;
}

ProductRuntimeError GreenhouseN3wProductIntegration::note_direct_result(bool success) {
  if (runtime_ == nullptr) return ProductRuntimeError::NOT_READY;
  return runtime_->note_direct_result(success);
}

}  // namespace esphome::greenhouse_n3w_product_runtime
