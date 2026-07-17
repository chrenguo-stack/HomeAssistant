#pragma once

#include <cstdint>
#include <string>

#include "esphome/components/mqtt/mqtt_client.h"
#include "esphome/core/component.h"
#include "esphome/core/preferences.h"

namespace esphome::greenhouse_mqtt_auth {

enum class AuthProfile : uint8_t {
  ANONYMOUS = 0,
  CANDIDATE = 1,
};

enum class AuthPhase : uint8_t {
  LEGACY_ANONYMOUS = 0,
  CANDIDATE_STAGED = 1,
  CANDIDATE_CONNECTING = 2,
  AUTHENTICATED_OBSERVATION = 3,
  FALLBACK_ANONYMOUS = 4,
  COMMITTED = 5,
};

struct PersistedState {
  uint32_t magic;
  uint16_t generation;
  uint8_t desired_profile;
  uint8_t candidate_failure_count;
  uint8_t observation_success_count;
  uint8_t committed;
  uint8_t reserved[2];
};

class GreenhouseMqttAuth final : public Component {
 public:
  void set_mqtt_client(mqtt::MQTTClientComponent *mqtt_client) { this->mqtt_client_ = mqtt_client; }
  void set_candidate_username(const std::string &value) { this->candidate_username_ = value; }
  void set_candidate_password(const std::string &value) { this->candidate_password_ = value; }
  void set_candidate_client_id(const std::string &value) { this->candidate_client_id_ = value; }
  void set_anonymous_client_id(const std::string &value) { this->anonymous_client_id_ = value; }
  void set_candidate_generation(uint16_t value) { this->candidate_generation_ = value; }
  void set_candidate_secret_fingerprint(const std::string &value) {
    this->candidate_secret_fingerprint_ = value;
  }
  void set_candidate_failure_threshold(uint8_t value) { this->candidate_failure_threshold_ = value; }
  void set_observation_success_threshold(uint8_t value) {
    this->observation_success_threshold_ = value;
  }
  void set_retry_cooldown_ms(uint32_t value) { this->retry_cooldown_ms_ = value; }

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override;

  // Test-harness entry points. Production authorization and provisioning are
  // intentionally outside this component revision.
  bool request_candidate_activation(bool explicitly_authorized);
  bool request_candidate_commit(bool explicitly_authorized);
  void request_anonymous_rollback();
  void record_observation_success();
  void record_observation_failure();

  // Board-lab-only deterministic power-cut hook. This flag is RAM-only and is
  // never part of PersistedState. Production YAML must not call these methods.
  void set_test_reboot_hold(bool value) { this->test_reboot_hold_ = value; }
  bool test_reboot_hold() const { return this->test_reboot_hold_; }
  bool reboot_held_for_test() const { return this->reboot_held_for_test_; }
  void release_held_reboot_for_test();

  AuthProfile active_profile() const { return this->active_profile_; }
  AuthPhase phase() const { return this->phase_; }
  const std::string &active_client_id() const {
    return this->active_profile_ == AuthProfile::CANDIDATE ? this->candidate_client_id_ : this->anonymous_client_id_;
  }
  const char *active_profile_name() const;
  const char *phase_name() const;
  const char *last_failure_class() const {
    return this->last_failure_class_ == nullptr ? "none" : this->last_failure_class_;
  }
  uint8_t candidate_failure_count() const { return this->state_.candidate_failure_count; }
  uint8_t observation_success_count() const { return this->state_.observation_success_count; }
  bool ready_for_commit() const;
  bool mqtt_connected() const { return this->mqtt_connected_; }
  bool candidate_secret_present() const { return !this->candidate_password_.empty(); }
  const std::string &candidate_secret_fingerprint() const {
    return this->candidate_secret_fingerprint_;
  }
  uint16_t candidate_generation() const { return this->candidate_generation_; }
  uint32_t retry_remaining_ms() const;
  bool local_operation_healthy() const { return true; }
  bool anonymous_fallback_present() const { return true; }
  bool disconnect_reason_is_generic() const { return true; }

 protected:
  static constexpr uint32_t PREFERENCE_KEY = 0x47484D51UL;
  static constexpr uint32_t STATE_MAGIC = 0x47484D31UL;

  void reset_state_();
  bool load_state_();
  bool save_state_();
  bool state_valid_() const;
  void apply_boot_profile_();
  void on_mqtt_connect_(bool session_present);
  void on_mqtt_disconnect_(mqtt::MQTTClientDisconnectReason reason);
  void select_anonymous_fallback_(const char *failure_class);
  void schedule_safe_reboot_();

  mqtt::MQTTClientComponent *mqtt_client_{nullptr};
  ESPPreferenceObject preference_;
  PersistedState state_{};

  std::string candidate_username_;
  std::string candidate_password_;
  std::string candidate_client_id_;
  std::string anonymous_client_id_;
  std::string candidate_secret_fingerprint_;

  uint16_t candidate_generation_{1};
  uint8_t candidate_failure_threshold_{3};
  uint8_t observation_success_threshold_{3};
  uint32_t retry_cooldown_ms_{300000};

  AuthProfile active_profile_{AuthProfile::ANONYMOUS};
  AuthPhase phase_{AuthPhase::LEGACY_ANONYMOUS};
  uint32_t fallback_boot_millis_{0};
  bool reboot_requested_{false};
  bool ignore_disconnect_{false};
  bool mqtt_connected_{false};
  bool test_reboot_hold_{false};
  bool reboot_held_for_test_{false};
  const char *last_failure_class_{nullptr};
};

}  // namespace esphome::greenhouse_mqtt_auth
