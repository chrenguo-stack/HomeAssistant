#include "n3w_product_integration.h"

#include <algorithm>
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

void GreenhouseN3wProductIntegration::zeroize_(void *data, std::size_t length) {
  if (data == nullptr) return;
  volatile uint8_t *cursor = static_cast<volatile uint8_t *>(data);
  while (length-- > 0) *cursor++ = 0;
}

GreenhouseN3wProductIntegration::~GreenhouseN3wProductIntegration() {
  // Member destruction would otherwise destroy the telemetry sink before the
  // S5 coordinator. Tear down peers while the mux and telemetry sink are both
  // alive, then stop the runtime/radio before unique_ptr destruction begins.
  if (s5_coordinator_ != nullptr) s5_coordinator_->reset();
  if (runtime_ != nullptr) runtime_->stop();
  zeroize_(pmk_.data(), pmk_.size());
}

void GreenhouseN3wProductIntegration::configure_s5_isolated(
    ProductS5SelfCredentialProvider *self_credentials,
    ProductS5RelayHealthProvider *relay_health,
    ProductS5ManagerPort *manager,
    RelayForwardSink *relay_forward_sink) {
  s5_self_credentials_ = self_credentials;
  s5_relay_health_ = relay_health;
  s5_manager_ = manager;
  s5_relay_forward_sink_ = relay_forward_sink;
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

bool GreenhouseN3wProductIntegration::setup_s5_isolated_() {
  ProductS5NodeCredentials credentials;
  MacAddress local_mac{};
  if (s5_self_credentials_ == nullptr ||
      !s5_self_credentials_->load_self(&credentials, &local_mac) || !credentials.valid()) {
    zeroize_(credentials.application_key.data(), credentials.application_key.size());
    return false;
  }

  const bool relay_role = role_ == "relay";
  if (relay_role &&
      (s5_relay_health_ == nullptr || s5_manager_ == nullptr || s5_relay_forward_sink_ == nullptr)) {
    zeroize_(credentials.application_key.data(), credentials.application_key.size());
    return false;
  }

  const ProductS5Role peer_role = relay_role ? ProductS5Role::RELAY : ProductS5Role::CHILD;
  const ProductS5TelemetryRole telemetry_role =
      relay_role ? ProductS5TelemetryRole::RELAY : ProductS5TelemetryRole::CHILD;

  s5_coordinator_ = std::make_unique<ProductS5PeerCoordinator>(
      peer_role,
      local_mac,
      credentials,
      this,
      &s5_random_,
      relay_role ? s5_relay_health_ : nullptr,
      relay_role ? s5_manager_ : nullptr);
  s5_radio_mux_ = std::make_unique<ProductS5RadioMux>(&radio_, s5_coordinator_.get());
  s5_telemetry_ = std::make_unique<ProductS5TelemetryBridge>(
      telemetry_role,
      credentials.node_id,
      s5_radio_mux_.get(),
      relay_role ? s5_relay_forward_sink_ : nullptr);
  if (!s5_radio_mux_->set_telemetry_sink(s5_telemetry_.get()) ||
      !s5_coordinator_->set_telemetry_sink(s5_telemetry_.get())) {
    zeroize_(credentials.application_key.data(), credentials.application_key.size());
    return false;
  }

  // The isolated S5 Child composition intentionally has no Wi-Fi Direct
  // transport. Treat its first explicit Direct failure as terminal so the
  // runtime enters Relay discovery instead of remaining idle in DIRECT.
  const WifiDirectHealthPolicy direct_health =
      relay_role ? WifiDirectHealthPolicy{} : WifiDirectHealthPolicy{1, 1, 3};
  runtime_ = std::make_unique<ProductEspNowRuntime>(
      s5_radio_mux_.get(), this, s5_coordinator_.get(), direct_health,
      RelayCandidatePolicy{}, AutoPathPolicy{}, ProductRuntimePolicy{});
  if (s5_coordinator_->attach(runtime_.get(), s5_radio_mux_.get()) != ProductS5CoordinatorError::NONE) {
    zeroize_(credentials.application_key.data(), credentials.application_key.size());
    return false;
  }

  // The endpoint relay-auth key has already been derived. Do not retain the
  // registered node application key in either this temporary copy or the
  // long-lived S5 coordinator.
  s5_coordinator_->scrub_application_key();
  zeroize_(credentials.application_key.data(), credentials.application_key.size());
  if (s5_coordinator_->application_key_resident()) return false;

  if (runtime_->set_last_direct_channel(last_direct_channel_) != ProductRuntimeError::NONE ||
      runtime_->start(pmk_) != ProductRuntimeError::NONE) {
    return false;
  }

  if (!relay_role && runtime_->note_direct_result(false) != ProductRuntimeError::NONE) {
    return false;
  }

  if (relay_role) {
    LocalRelayAdvertisement advertisement;
    advertisement.enabled = true;
    advertisement.gateway_id = credentials.node_id;
    advertisement.channel = last_direct_channel_;
    advertisement.advertisement_generation = credentials.credential_generation;
    if (runtime_->set_local_relay_advertisement(advertisement) != ProductRuntimeError::NONE) {
      return false;
    }
  }
  return true;
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

  if (s5_self_credentials_ != nullptr) {
    if (!setup_s5_isolated_()) {
      ESP_LOGE(TAG, "N3-W isolated S5 integration failed to start");
      this->mark_failed();
    }
    return;
  }

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
  if (!execution_enabled_ || this->is_failed()) return;
  if (s5_coordinator_ != nullptr) {
    const ProductS5CoordinatorError peer = s5_coordinator_->tick();
    const ProductS5TelemetryError telemetry =
        s5_telemetry_ == nullptr ? ProductS5TelemetryError::NOT_READY
                                 : s5_telemetry_->tick(now_ms());
    if (peer != ProductS5CoordinatorError::NONE) {
      ESP_LOGW(TAG, "N3-W S5 peer tick result=%u", static_cast<unsigned>(peer));
    }
    if (telemetry != ProductS5TelemetryError::NONE &&
        telemetry != ProductS5TelemetryError::NOT_READY) {
      ESP_LOGW(TAG, "N3-W S5 telemetry tick result=%u", static_cast<unsigned>(telemetry));
    }
    return;
  }
  if (coordinator_ == nullptr) return;
  const ProductRuntimeError result = coordinator_->tick();
  if (result != ProductRuntimeError::NONE) {
    ESP_LOGW(TAG, "N3-W Product integration tick result=%u", static_cast<unsigned>(result));
  }
}

void GreenhouseN3wProductIntegration::dump_config() {
  ESP_LOGCONFIG(TAG, "N3-W Product Completion S3/S4/S5 board integration");
  ESP_LOGCONFIG(TAG, "  role: %s", role_.c_str());
  ESP_LOGCONFIG(TAG, "  execution enabled: %s", execution_enabled_ ? "true" : "false");
  ESP_LOGCONFIG(TAG, "  isolated S5 ports configured: %s", s5_isolated_configured() ? "true" : "false");
  ESP_LOGCONFIG(TAG, "  factory fixed peer: false");
  ESP_LOGCONFIG(TAG, "  PMK bytes logged: false");
  ESP_LOGCONFIG(TAG, "  node application key logged: false");
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

ProductS5CoordinatorError GreenhouseN3wProductIntegration::submit_s5_manager_authorization(
    const ProductPeerGrant &child_grant,
    const ProductPeerGrant &relay_grant) {
  if (s5_coordinator_ == nullptr || role_ != "relay") {
    return ProductS5CoordinatorError::NOT_READY;
  }
  return s5_coordinator_->accept_manager_authorization(child_grant, relay_grant);
}

ProductS5CoordinatorError GreenhouseN3wProductIntegration::revoke_s5_authorization(
    const std::string &authorization_id) {
  if (s5_coordinator_ == nullptr) return ProductS5CoordinatorError::NOT_READY;
  return s5_coordinator_->revoke_active_authorization(authorization_id);
}

ProductS5TelemetryError GreenhouseN3wProductIntegration::send_s5_relay_frame(
    const RelayFrame &frame,
    uint64_t now_ms) {
  if (s5_telemetry_ == nullptr) return ProductS5TelemetryError::NOT_READY;
  return s5_telemetry_->send_relay_frame(frame, now_ms);
}

}  // namespace esphome::greenhouse_n3w_product_runtime
