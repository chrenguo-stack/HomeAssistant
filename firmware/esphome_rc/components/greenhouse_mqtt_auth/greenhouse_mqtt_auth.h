#pragma once

#include <cstdint>
#include <string>

#include "esphome/components/mqtt/mqtt_client.h"
#include "esphome/core/component.h"

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

class GreenhouseMqttAuth final : public Component {
 public:
  void set_mqtt_client(mqtt::MQTTClientComponent *mqtt_client);
  void set_candidate_username(const std::string &value) { this->candidate_username_ = value; }
  void set_candidate_password(const std::string &value) { this->candidate_password_ = value; }
  void set_candidate_client_id(const std::string &value) { this->candidate_client_id_ = value; }
  void set_anonymous_client_id(const std::string &value) { this->anonymous_client_id_ = value; }
  void set_candidate_generation(uint16_t value) { this->candidate_generation_ = value; }
  void set_candidate_secret_fingerprint(const std::string &value) {
    this->candidate_secret_fingerprint_ = value;
  }
  void set_auth_failure_threshold(uint8_t value) { this->auth_failure_threshold_ = value; }
  void set_observation_success_threshold(uint8_t value) {
    this->observation_success_threshold_ = value;
  }
  void set_retry_cooldown_ms(uint32_t value) { this->retry_cooldown_ms_ = value; }

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override;

  // These methods are intentionally inert until an isolated test harness calls them.
  // Production authorization/provisioning is not implemented in this component revision.
  bool request_candidate_activation(bool explicitly_authorized);
  bool request_candidate_commit(bool explicitly_authorized);
  void request_anonymous_rollback();
  void record_observation_success();
  void record_observation_failure();

  AuthProfile active_profile() const { return this->active_profile_; }
  AuthPhase phase() const { return this->phase_; }
  uint8_t auth_failure_count() const { return this->auth_failure_count_; }
  uint8_t observation_success_count() const { return this->observation_success_count_; }
  bool ready_for_commit() const;
  bool candidate_secret_present() const { return !this->candidate_password_.empty(); }
  const std::string &candidate_secret_fingerprint() const {
    return this->candidate_secret_fingerprint_;
  }
  uint16_t candidate_generation() const { return this->candidate_generation_; }
  uint32_t retry_remaining_ms() const;
  bool local_operation_healthy() const { return true; }
  bool anonymous_fallback_present() const { return true; }

 protected:
  void on_mqtt_connect_(bool session_present);
  void on_mqtt_disconnect_(mqtt::MQTTClientDisconnectReason reason);
  void switch_to_candidate_();
  void switch_to_anonymous_();
  void schedule_fallback_(mqtt::MQTTClientDisconnectReason reason);
  bool is_authentication_failure_(mqtt::MQTTClientDisconnectReason reason) const;

  mqtt::MQTTClientComponent *mqtt_client_{nullptr};

  std::string candidate_username_;
  std::string candidate_password_;
  std::string candidate_client_id_;
  std::string anonymous_client_id_;
  std::string candidate_secret_fingerprint_;

  uint16_t candidate_generation_{1};
  uint8_t auth_failure_threshold_{3};
  uint8_t observation_success_threshold_{3};
  uint32_t retry_cooldown_ms_{300000};

  AuthProfile active_profile_{AuthProfile::ANONYMOUS};
  AuthPhase phase_{AuthPhase::LEGACY_ANONYMOUS};
  uint8_t auth_failure_count_{0};
  uint8_t observation_success_count_{0};
  uint32_t retry_deadline_ms_{0};
  bool pending_candidate_switch_{false};
  bool pending_fallback_{false};
  mqtt::MQTTClientDisconnectReason last_disconnect_reason_{
      mqtt::MQTTClientDisconnectReason::TCP_DISCONNECTED};
};

}  // namespace esphome::greenhouse_mqtt_auth
