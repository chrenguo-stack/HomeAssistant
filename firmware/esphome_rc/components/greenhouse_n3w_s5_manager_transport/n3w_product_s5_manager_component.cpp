#include "n3w_product_s5_manager_component.h"

#include "esphome/core/log.h"

#ifdef USE_ESP32
#include "esp_system.h"
#endif

namespace esphome::greenhouse_n3w_s5_manager_transport {
namespace {
static const char *const TAG = "n3w_s5_manager_transport";
}

void GreenhouseN3wS5ManagerTransportComponent::zeroize_(
    void *data,
    std::size_t length) {
  if (data == nullptr) return;
  volatile uint8_t *cursor = static_cast<volatile uint8_t *>(data);
  while (length-- > 0) *cursor++ = 0;
}

bool GreenhouseN3wS5ManagerTransportComponent::configure_private(
    ProductS5SelfCredentialProvider *self_credentials,
    ProductS5RelayHealthProvider *relay_health) {
  if (private_configured_ || self_credentials == nullptr ||
      relay_health == nullptr) {
    return false;
  }
  self_credentials_ = self_credentials;
  relay_health_ = relay_health;
  private_configured_ = true;
  return true;
}

float GreenhouseN3wS5ManagerTransportComponent::get_setup_priority() const {
  // The existing Product integration starts at AFTER_WIFI (200). Configure its
  // concrete isolated ports just before that setup without starting Wi-Fi.
  return setup_priority::AFTER_WIFI + 1.0f;
}

void GreenhouseN3wS5ManagerTransportComponent::setup() {
  ESP_LOGI(
      TAG,
      "S5 isolated Manager transport execution_enabled=%s private_configured=%s",
      execution_enabled_ ? "true" : "false",
      private_configured_ ? "true" : "false");
  if (!execution_enabled_) return;
  if (integration_ == nullptr || self_credentials_ == nullptr ||
      relay_health_ == nullptr) {
    ESP_LOGE(TAG, "S5 isolated Manager transport missing private composition");
    this->mark_failed();
    return;
  }

  ProductS5NodeCredentials credentials;
  esphome::greenhouse_n3w_core::MacAddress local_mac{};
  if (!self_credentials_->load_self(&credentials, &local_mac) ||
      !credentials.valid()) {
    zeroize_(
        credentials.application_key.data(),
        credentials.application_key.size());
    ESP_LOGE(TAG, "S5 isolated Manager transport self credentials rejected");
    this->mark_failed();
    return;
  }

  bus_ = std::make_unique<ProductS5EspHomeMqttBus>();
  uint64_t boot_session = 1;
#ifdef USE_ESP32
  boot_session =
      (static_cast<uint64_t>(esp_random()) << 32U) |
      static_cast<uint64_t>(esp_random());
  if (boot_session == 0) boot_session = 1;
#endif
  transport_ = std::make_unique<ProductS5IsolatedManagerTransport>(
      credentials.system_id,
      credentials.node_id,
      integration_,
      bus_.get(),
      this,
      boot_session);
  zeroize_(
      credentials.application_key.data(),
      credentials.application_key.size());

  if (!transport_->start()) {
    ESP_LOGE(TAG, "S5 isolated Manager transport subscription setup failed");
    this->mark_failed();
    return;
  }

  integration_->configure_s5_isolated(
      self_credentials_,
      relay_health_,
      transport_.get(),
      transport_.get());
  active_ = true;
}

void GreenhouseN3wS5ManagerTransportComponent::loop() {
  if (!active_ || this->is_failed() || transport_ == nullptr ||
      integration_ == nullptr) {
    return;
  }

  // Warm/refresh Manager epoch without ever substituting endpoint monotonic
  // uptime. Missing/stale authority time remains fail-closed.
  uint64_t authority_now = 0;
  (void) transport_->authority_now_ms(&authority_now);

  if (queued_child_grant_.has_value() &&
      queued_relay_grant_.has_value()) {
    const auto result = integration_->submit_s5_manager_authorization(
        *queued_child_grant_,
        *queued_relay_grant_);
    queued_child_grant_.reset();
    queued_relay_grant_.reset();
    if (result !=
        greenhouse_n3w_product_runtime::ProductS5CoordinatorError::NONE) {
      ESP_LOGW(
          TAG,
          "S5 isolated Manager grant delivery result=%u",
          static_cast<unsigned>(result));
    }
  }
}

void GreenhouseN3wS5ManagerTransportComponent::dump_config() {
  ESP_LOGCONFIG(TAG, "N3-W S5 isolated Manager transport");
  ESP_LOGCONFIG(
      TAG,
      "  execution enabled: %s",
      execution_enabled_ ? "true" : "false");
  ESP_LOGCONFIG(
      TAG,
      "  private composition present: %s",
      private_configured_ ? "true" : "false");
  ESP_LOGCONFIG(TAG, "  static peer identity: false");
  ESP_LOGCONFIG(TAG, "  pair LMK distribution: false");
  ESP_LOGCONFIG(TAG, "  credentials logged: false");
}

bool GreenhouseN3wS5ManagerTransportComponent::queue_s5_manager_authorization(
    const ProductPeerGrant &child_grant,
    const ProductPeerGrant &relay_grant) {
  if (!active_ || !child_grant.valid_shape() ||
      !relay_grant.valid_shape() ||
      queued_child_grant_.has_value() ||
      queued_relay_grant_.has_value()) {
    return false;
  }
  queued_child_grant_ = child_grant;
  queued_relay_grant_ = relay_grant;
  return true;
}

}  // namespace esphome::greenhouse_n3w_s5_manager_transport
