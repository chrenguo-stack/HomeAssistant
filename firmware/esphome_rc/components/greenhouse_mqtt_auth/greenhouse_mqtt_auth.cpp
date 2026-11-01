#include "greenhouse_mqtt_auth.h"

#include <algorithm>
#include <cinttypes>

#include "esphome/core/application.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"

namespace esphome::greenhouse_mqtt_auth {

static const char *const TAG = "greenhouse_mqtt_auth";

void GreenhouseMqttAuth::reset_state_() {
  this->state_ = PersistedState{
      .magic = STATE_MAGIC,
      .generation = this->candidate_generation_,
      .desired_profile = static_cast<uint8_t>(AuthProfile::ANONYMOUS),
      .candidate_failure_count = 0,
      .observation_success_count = 0,
      .committed = 0,
      .reserved = {0, 0},
  };
}

bool GreenhouseMqttAuth::state_valid_() const {
  return this->state_.magic == STATE_MAGIC && this->state_.generation == this->candidate_generation_ &&
         this->state_.desired_profile <= static_cast<uint8_t>(AuthProfile::CANDIDATE) &&
         this->state_.candidate_failure_count <= this->candidate_failure_threshold_ &&
         this->state_.observation_success_count <= this->observation_success_threshold_ &&
         this->state_.committed <= 1;
}

bool GreenhouseMqttAuth::load_state_() {
  if (!this->preference_.load(&this->state_) || !this->state_valid_()) {
    this->reset_state_();
    return this->save_state_();
  }
  return true;
}

bool GreenhouseMqttAuth::save_state_() {
  if (!this->preference_.save(&this->state_)) {
    ESP_LOGE(TAG, "Unable to persist the redacted MQTT profile state");
    this->status_set_error();
    return false;
  }
  return true;
}

void GreenhouseMqttAuth::apply_boot_profile_() {
  const auto desired = static_cast<AuthProfile>(this->state_.desired_profile);
  if (desired == AuthProfile::CANDIDATE) {
    this->mqtt_client_->set_username(this->candidate_username_);
    this->mqtt_client_->set_password(this->candidate_password_);
    this->mqtt_client_->set_client_id(this->candidate_client_id_);
    this->active_profile_ = AuthProfile::CANDIDATE;
    this->phase_ = AuthPhase::CANDIDATE_CONNECTING;
    ESP_LOGI(TAG, "Applied candidate MQTT profile before MQTT initialization");
    return;
  }

  this->mqtt_client_->set_username("");
  this->mqtt_client_->set_password("");
  this->mqtt_client_->set_client_id(this->anonymous_client_id_);
  this->active_profile_ = AuthProfile::ANONYMOUS;
  this->phase_ = this->state_.candidate_failure_count > 0 ? AuthPhase::FALLBACK_ANONYMOUS
                                                          : AuthPhase::LEGACY_ANONYMOUS;
  this->fallback_boot_millis_ = millis();
  ESP_LOGI(TAG, "Applied anonymous MQTT fallback before MQTT initialization");
}

void GreenhouseMqttAuth::setup() {
  if (this->mqtt_client_ == nullptr) {
    ESP_LOGE(TAG, "MQTT client binding is missing");
    this->mark_failed();
    return;
  }

  this->preference_ = global_preferences->make_preference<PersistedState>(PREFERENCE_KEY);
  if (!this->load_state_()) {
    this->mark_failed();
    return;
  }

  this->mqtt_client_->set_on_connect(
      [this](bool session_present) { this->on_mqtt_connect_(session_present); });
  this->mqtt_client_->set_on_disconnect(
      [this](mqtt::MQTTClientDisconnectReason reason) { this->on_mqtt_disconnect_(reason); });

  // ESPHome 2026.4.3 initializes the ESP-IDF MQTT backend only once. Credentials
  // and Client ID therefore must be selected before MQTTClientComponent::setup().
  this->apply_boot_profile_();
}

void GreenhouseMqttAuth::loop() {
  if (!this->reboot_requested_)
    return;
  this->reboot_requested_ = false;
  ESP_LOGW(TAG, "Rebooting to apply the persisted MQTT boot profile");
  App.safe_reboot();
}

float GreenhouseMqttAuth::get_setup_priority() const { return setup_priority::DATA; }

const char *GreenhouseMqttAuth::active_profile_name() const {
  return this->active_profile_ == AuthProfile::CANDIDATE ? "candidate" : "anonymous";
}

const char *GreenhouseMqttAuth::phase_name() const {
  switch (this->phase_) {
    case AuthPhase::LEGACY_ANONYMOUS:
      return "legacy_anonymous";
    case AuthPhase::CANDIDATE_STAGED:
      return "candidate_staged";
    case AuthPhase::CANDIDATE_CONNECTING:
      return "candidate_connecting";
    case AuthPhase::AUTHENTICATED_OBSERVATION:
      return "authenticated_observation";
    case AuthPhase::FALLBACK_ANONYMOUS:
      return "fallback_anonymous";
    case AuthPhase::COMMITTED:
      return "committed";
  }
  return "unknown";
}

void GreenhouseMqttAuth::dump_config() {
  ESP_LOGCONFIG(TAG,
                "Greenhouse MQTT Auth Adapter:\n"
                "  Boot-selected profile: %s\n"
                "  Phase: %s\n"
                "  Candidate generation: %u\n"
                "  Candidate secret present: %s\n"
                "  Candidate secret fingerprint: %s\n"
                "  Generic candidate failures: %u/%u\n"
                "  Observation successes: %u/%u\n"
                "  Retry cooldown: %" PRIu32 " ms\n"
                "  Committed: %s\n"
                "  Anonymous fallback present: YES\n"
                "  Disconnect classification: generic\n"
                "  Board-lab reboot hold: %s\n"
                "  Board-lab reboot currently held: %s",
                this->active_profile_name(), this->phase_name(), this->candidate_generation_,
                YESNO(this->candidate_secret_present()), this->candidate_secret_fingerprint_.c_str(),
                this->state_.candidate_failure_count, this->candidate_failure_threshold_,
                this->state_.observation_success_count, this->observation_success_threshold_, this->retry_cooldown_ms_,
                YESNO(this->state_.committed != 0), YESNO(this->test_reboot_hold_),
                YESNO(this->reboot_held_for_test_));
}

void GreenhouseMqttAuth::on_mqtt_connect_(bool session_present) {
  (void) session_present;
  this->mqtt_connected_ = true;
  this->last_failure_class_ = nullptr;

  if (this->active_profile_ == AuthProfile::ANONYMOUS) {
    this->phase_ = this->state_.candidate_failure_count > 0 ? AuthPhase::FALLBACK_ANONYMOUS
                                                            : AuthPhase::LEGACY_ANONYMOUS;
    return;
  }

  if (this->state_.candidate_failure_count != 0) {
    this->state_.candidate_failure_count = 0;
    this->save_state_();
  }
  this->phase_ = this->state_.committed != 0 ? AuthPhase::COMMITTED
                                             : AuthPhase::AUTHENTICATED_OBSERVATION;
}

void GreenhouseMqttAuth::on_mqtt_disconnect_(mqtt::MQTTClientDisconnectReason reason) {
  (void) reason;
  this->mqtt_connected_ = false;
  if (this->ignore_disconnect_ || this->active_profile_ != AuthProfile::CANDIDATE)
    return;

  // ESPHome 2026.4.3's ESP-IDF backend exposes disconnects as TCP_DISCONNECTED
  // even when the underlying event was a connection refusal. Count a generic
  // candidate connection failure; never claim an authentication-specific reason.
  if (this->state_.candidate_failure_count < this->candidate_failure_threshold_)
    this->state_.candidate_failure_count++;
  this->last_failure_class_ = "generic_candidate_connection_failure";
  this->save_state_();

  if (this->state_.candidate_failure_count >= this->candidate_failure_threshold_)
    this->select_anonymous_fallback_(this->last_failure_class_);
}

void GreenhouseMqttAuth::select_anonymous_fallback_(const char *failure_class) {
  this->state_.desired_profile = static_cast<uint8_t>(AuthProfile::ANONYMOUS);
  this->state_.observation_success_count = 0;
  this->last_failure_class_ = failure_class;
  this->phase_ = AuthPhase::FALLBACK_ANONYMOUS;
  if (this->save_state_())
    this->schedule_safe_reboot_();
}

void GreenhouseMqttAuth::schedule_safe_reboot_() {
  this->ignore_disconnect_ = true;
  if (this->test_reboot_hold_) {
    this->reboot_held_for_test_ = true;
    ESP_LOGW(TAG, "Board-lab reboot hold is active after persisted profile update");
    return;
  }
  this->reboot_requested_ = true;
}

void GreenhouseMqttAuth::release_held_reboot_for_test() {
  if (!this->reboot_held_for_test_)
    return;
  this->test_reboot_hold_ = false;
  this->reboot_held_for_test_ = false;
  this->reboot_requested_ = true;
  ESP_LOGW(TAG, "Board-lab reboot hold released");
}

bool GreenhouseMqttAuth::request_candidate_activation(bool explicitly_authorized) {
  if (!explicitly_authorized || this->mqtt_client_ == nullptr || this->candidate_password_.empty())
    return false;
  if (this->active_profile_ == AuthProfile::CANDIDATE || this->reboot_requested_ ||
      this->reboot_held_for_test_)
    return false;
  if (this->phase_ == AuthPhase::FALLBACK_ANONYMOUS && this->retry_remaining_ms() != 0)
    return false;

  this->state_.desired_profile = static_cast<uint8_t>(AuthProfile::CANDIDATE);
  this->state_.candidate_failure_count = 0;
  if (this->state_.committed == 0)
    this->state_.observation_success_count = 0;
  this->phase_ = AuthPhase::CANDIDATE_STAGED;
  if (!this->save_state_())
    return false;
  this->schedule_safe_reboot_();
  return true;
}

bool GreenhouseMqttAuth::request_candidate_commit(bool explicitly_authorized) {
  if (!explicitly_authorized || this->active_profile_ != AuthProfile::CANDIDATE || !this->mqtt_connected_ ||
      this->phase_ != AuthPhase::AUTHENTICATED_OBSERVATION || !this->ready_for_commit())
    return false;

  this->state_.committed = 1;
  if (!this->save_state_())
    return false;
  this->phase_ = AuthPhase::COMMITTED;
  return true;
}

void GreenhouseMqttAuth::request_anonymous_rollback() {
  this->state_.desired_profile = static_cast<uint8_t>(AuthProfile::ANONYMOUS);
  this->state_.observation_success_count = 0;
  this->state_.committed = 0;
  this->last_failure_class_ = "operator_rollback";
  this->phase_ = AuthPhase::FALLBACK_ANONYMOUS;
  if (this->save_state_())
    this->schedule_safe_reboot_();
}

void GreenhouseMqttAuth::record_observation_success() {
  if (this->active_profile_ != AuthProfile::CANDIDATE || !this->mqtt_connected_ ||
      this->phase_ != AuthPhase::AUTHENTICATED_OBSERVATION)
    return;
  if (this->state_.observation_success_count < this->observation_success_threshold_) {
    this->state_.observation_success_count++;
    this->save_state_();
  }
}

void GreenhouseMqttAuth::record_observation_failure() {
  if (this->active_profile_ != AuthProfile::CANDIDATE || this->phase_ == AuthPhase::COMMITTED)
    return;
  this->select_anonymous_fallback_("continuity_or_acl_failure");
}

bool GreenhouseMqttAuth::ready_for_commit() const {
  return this->active_profile_ == AuthProfile::CANDIDATE && this->mqtt_connected_ &&
         this->phase_ == AuthPhase::AUTHENTICATED_OBSERVATION &&
         this->state_.observation_success_count >= this->observation_success_threshold_;
}

uint32_t GreenhouseMqttAuth::retry_remaining_ms() const {
  if (this->phase_ != AuthPhase::FALLBACK_ANONYMOUS)
    return 0;
  const uint32_t elapsed = millis() - this->fallback_boot_millis_;
  return elapsed >= this->retry_cooldown_ms_ ? 0 : this->retry_cooldown_ms_ - elapsed;
}

}  // namespace esphome::greenhouse_mqtt_auth
