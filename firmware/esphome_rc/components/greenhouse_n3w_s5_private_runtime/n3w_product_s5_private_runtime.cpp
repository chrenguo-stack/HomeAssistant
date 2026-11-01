#include "greenhouse_n3w_s5_private_runtime.h"

#include <algorithm>
#include <cctype>

#include "esphome/core/log.h"

namespace esphome::greenhouse_n3w_s5_private_runtime {
namespace {
static const char *const TAG = "n3w_s5_private_runtime";

uint8_t hex_nibble(char character) {
  if (character >= '0' && character <= '9') {
    return static_cast<uint8_t>(character - '0');
  }
  character = static_cast<char>(
      std::tolower(static_cast<unsigned char>(character)));
  if (character >= 'a' && character <= 'f') {
    return static_cast<uint8_t>(character - 'a' + 10);
  }
  return 0xff;
}
}  // namespace

GreenhouseN3wS5PrivateRuntimeMaterial::~GreenhouseN3wS5PrivateRuntimeMaterial() {
  zeroize_(application_key_.data(), application_key_.size());
  if (!application_key_hex_.empty()) {
    zeroize_(application_key_hex_.data(), application_key_hex_.size());
  }
}

void GreenhouseN3wS5PrivateRuntimeMaterial::zeroize_(
    void *data,
    std::size_t length) {
  if (data == nullptr) return;
  volatile uint8_t *cursor = static_cast<volatile uint8_t *>(data);
  while (length-- > 0) *cursor++ = 0;
}

bool GreenhouseN3wS5PrivateRuntimeMaterial::parse_hex_key_(
    const std::string &value,
    std::array<uint8_t, 32> *output) {
  if (output == nullptr || value.size() != output->size() * 2) return false;
  uint8_t aggregate = 0;
  for (std::size_t index = 0; index < output->size(); ++index) {
    const uint8_t high = hex_nibble(value[index * 2]);
    const uint8_t low = hex_nibble(value[index * 2 + 1]);
    if (high == 0xff || low == 0xff) return false;
    (*output)[index] = static_cast<uint8_t>((high << 4U) | low);
    aggregate |= (*output)[index];
  }
  return aggregate != 0;
}

bool GreenhouseN3wS5PrivateRuntimeMaterial::parse_mac_(
    const std::string &value,
    MacAddress *output) {
  if (output == nullptr || value.size() != output->size() * 2) return false;
  uint8_t aggregate = 0;
  for (std::size_t index = 0; index < output->size(); ++index) {
    const std::size_t offset = index * 2;
    const uint8_t high = hex_nibble(value[offset]);
    const uint8_t low = hex_nibble(value[offset + 1]);
    if (high == 0xff || low == 0xff) return false;
    (*output)[index] = static_cast<uint8_t>((high << 4U) | low);
    aggregate |= (*output)[index];
  }
  return aggregate != 0 && (((*output)[0] & 0x01U) == 0);
}

bool GreenhouseN3wS5PrivateRuntimeMaterial::configure_child(
    GreenhouseN3wProductIntegration *integration) {
  if (integration == nullptr || role_ != "child" || child_bound_) return false;
  integration->configure_s5_isolated(this, nullptr, nullptr, nullptr);
  child_integration_ = integration;
  child_bound_ = true;
  return true;
}

float GreenhouseN3wS5PrivateRuntimeMaterial::get_setup_priority() const {
  // Prepare the private endpoint material before the Relay Manager transport
  // (AFTER_WIFI+1) and the existing S5 integration (AFTER_WIFI).
  return setup_priority::AFTER_WIFI + 2.0f;
}

void GreenhouseN3wS5PrivateRuntimeMaterial::setup() {
  ProductS5NodeCredentials validation;
  validation.system_id = system_id_;
  validation.node_id = node_id_;
  validation.credential_generation = credential_generation_;
  validation.key_epoch = key_epoch_;

  if ((role_ != "child" && role_ != "relay") ||
      !parse_hex_key_(application_key_hex_, &application_key_) ||
      !parse_mac_(local_mac_text_, &local_mac_)) {
    ESP_LOGE(TAG, "S5 private runtime material rejected");
    zeroize_(application_key_.data(), application_key_.size());
    this->mark_failed();
    return;
  }
  validation.application_key = application_key_;
  if (!validation.valid()) {
    ESP_LOGE(TAG, "S5 private runtime identity rejected");
    zeroize_(application_key_.data(), application_key_.size());
    this->mark_failed();
    return;
  }

  if (telemetry_stimulus_enabled_) {
    if (role_ != "child" || child_integration_ == nullptr ||
        telemetry_stimulus_boot_session_ == 0 ||
        !telemetry_stimulus_.configure(
            node_id_,
            key_epoch_,
            application_key_,
            telemetry_stimulus_boot_session_,
            telemetry_stimulus_seq_)) {
      ESP_LOGE(TAG, "S5 R7 private telemetry stimulus configuration rejected");
      zeroize_(application_key_.data(), application_key_.size());
      this->mark_failed();
      return;
    }
  }

  // The Relay transport reads identity once before the Product integration
  // consumes the same endpoint credential. Child needs only the latter load.
  remaining_credential_loads_ = role_ == "relay" ? 2 : 1;
  material_ready_ = true;
  if (!application_key_hex_.empty()) {
    zeroize_(application_key_hex_.data(), application_key_hex_.size());
    application_key_hex_.clear();
    application_key_hex_.shrink_to_fit();
  }
}

void GreenhouseN3wS5PrivateRuntimeMaterial::loop() {
  if (!telemetry_stimulus_enabled_ || this->is_failed() ||
      telemetry_stimulus_.submitted()) {
    return;
  }
  if (role_ != "child" || child_integration_ == nullptr) {
    ESP_LOGE(TAG, "S5 R7 private telemetry stimulus lost Child binding");
    this->mark_failed();
    return;
  }

  std::string gateway_id;
  if (!child_integration_->s5_child_active_gateway_id(&gateway_id)) return;

  if (!telemetry_stimulus_.prepared()) {
    const auto prepared =
        telemetry_stimulus_.prepare(gateway_id, child_integration_->now_ms());
    if (prepared != ProductS5PrivateTelemetryStimulusError::NONE) {
      ESP_LOGE(
          TAG,
          "S5 R7 private telemetry stimulus prepare failed result=%u",
          static_cast<unsigned>(prepared));
      this->mark_failed();
      return;
    }
  } else if (telemetry_stimulus_.prepared_gateway_id() != gateway_id) {
    // Never re-home one already encrypted RelayFrame to a different Relay.
    ESP_LOGE(TAG, "S5 R7 private telemetry stimulus gateway binding changed");
    this->mark_failed();
    return;
  }

  const auto *frame = telemetry_stimulus_.prepared_frame();
  if (frame == nullptr) {
    ESP_LOGE(TAG, "S5 R7 private telemetry stimulus frame unavailable");
    this->mark_failed();
    return;
  }

  const auto result =
      child_integration_->send_s5_relay_frame(*frame, child_integration_->now_ms());
  if (result == greenhouse_n3w_product_runtime::ProductS5TelemetryError::NOT_READY) {
    return;
  }

  if (result == greenhouse_n3w_product_runtime::ProductS5TelemetryError::NONE ||
      result == greenhouse_n3w_product_runtime::ProductS5TelemetryError::RADIO_FAILED) {
    // RADIO_FAILED means the already-enqueued frame remains in the existing
    // ChildRelayCache and is retried by the existing reliable-link tick. Do
    // not create or enqueue a second application telemetry record.
    if (!telemetry_stimulus_.mark_submitted()) {
      ESP_LOGE(TAG, "S5 R7 private telemetry stimulus submit state rejected");
      this->mark_failed();
      return;
    }
    ESP_LOGI(
        TAG,
        "S5 R7 private telemetry stimulus submitted exactly_once=true initial_radio_ok=%s",
        result == greenhouse_n3w_product_runtime::ProductS5TelemetryError::NONE
            ? "true"
            : "false");
    return;
  }

  ESP_LOGE(
      TAG,
      "S5 R7 private telemetry stimulus enqueue failed result=%u",
      static_cast<unsigned>(result));
  this->mark_failed();
}

bool GreenhouseN3wS5PrivateRuntimeMaterial::load_self(
    ProductS5NodeCredentials *credentials,
    MacAddress *local_mac) {
  if (!material_ready_ || this->is_failed() || credentials == nullptr ||
      local_mac == nullptr || remaining_credential_loads_ == 0 ||
      !application_key_resident()) {
    return false;
  }
  credentials->system_id = system_id_;
  credentials->node_id = node_id_;
  credentials->credential_generation = credential_generation_;
  credentials->key_epoch = key_epoch_;
  credentials->application_key = application_key_;
  *local_mac = local_mac_;

  --remaining_credential_loads_;
  if (remaining_credential_loads_ == 0) {
    zeroize_(application_key_.data(), application_key_.size());
  }
  return credentials->valid();
}

bool GreenhouseN3wS5PrivateRuntimeMaterial::read_health(
    uint64_t authority_now_ms,
    ProductRelayHealth *health) {
  if (!material_ready_ || this->is_failed() || role_ != "relay" ||
      health == nullptr || authority_now_ms == 0) {
    return false;
  }
  health->observed_at_ms = authority_now_ms;
  health->relay_capable = relay_capable_;
  health->low_battery = low_battery_;
  health->overloaded = overloaded_;
  return true;
}

bool GreenhouseN3wS5PrivateRuntimeMaterial::application_key_resident() const {
  return std::any_of(
      application_key_.begin(),
      application_key_.end(),
      [](uint8_t value) { return value != 0; });
}

void GreenhouseN3wS5PrivateRuntimeMaterial::dump_config() {
  ESP_LOGCONFIG(TAG, "N3-W S5 private-package runtime material");
  ESP_LOGCONFIG(TAG, "  role: %s", role_.c_str());
  ESP_LOGCONFIG(TAG, "  material ready: %s", material_ready_ ? "true" : "false");
  ESP_LOGCONFIG(TAG, "  factory peer identity: false");
  ESP_LOGCONFIG(TAG, "  pair LMK supplied: false");
  ESP_LOGCONFIG(TAG, "  application key logged: false");
  ESP_LOGCONFIG(
      TAG,
      "  R7 telemetry stimulus enabled: %s",
      telemetry_stimulus_enabled_ ? "true" : "false");
  ESP_LOGCONFIG(
      TAG,
      "  R7 telemetry stimulus submitted: %s",
      telemetry_stimulus_.submitted() ? "true" : "false");
}

}  // namespace esphome::greenhouse_n3w_s5_private_runtime
