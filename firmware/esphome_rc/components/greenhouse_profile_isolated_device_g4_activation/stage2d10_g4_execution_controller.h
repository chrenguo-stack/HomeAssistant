#pragma once

#include <cstdint>
#include <string>

#include "stage2d10_g4_activation_coordinator.h"
#include "stage2d10_g4_command_codec.h"

namespace esphome::greenhouse_pairing_client {

enum class Stage2D10G4WifiFailure : uint8_t {
  NONE = 0,
  INVALID_CONFIGURATION = 1,
  START_FAILED = 2,
  AUTHENTICATION_FAILED = 3,
  TIMEOUT = 4,
  DISCONNECTED = 5,
  INTERNAL = 6,
};

struct Stage2D10G4WifiSnapshot {
  bool configured{false};
  bool start_attempted{false};
  bool connected{false};
  bool terminal{false};
  bool credentials_destroyed{false};
  uint32_t elapsed_ms{0};
  Stage2D10G4WifiFailure failure{Stage2D10G4WifiFailure::NONE};
};

class Stage2D10G4WifiPort {
 public:
  virtual ~Stage2D10G4WifiPort() = default;
  virtual bool configure_private(const std::string &ssid,
                                 const std::string &password,
                                 const std::string &profile_digest,
                                 uint32_t timeout_ms,
                                 Stage2D10G4WifiSnapshot *snapshot) = 0;
  virtual bool begin(Stage2D10G4WifiSnapshot *snapshot) = 0;
  virtual bool poll(uint32_t elapsed_ms,
                    Stage2D10G4WifiSnapshot *snapshot) = 0;
  virtual void quiesce_and_destroy() = 0;
};

enum class Stage2D10G4ExecutionPhase : uint8_t {
  LOCKED = 0,
  COMMAND_BOUND = 1,
  WIFI_CONNECTING = 2,
  VALIDATING = 3,
  ACTIVATING = 4,
  ACTIVATED_RESTART_REQUIRED = 5,
  VERIFYING_READ_ONLY = 6,
  VERIFIED_AFTER_RESTART = 7,
  FAILED = 8,
  REBOOT_REQUIRED = 9,
};

enum class Stage2D10G4ExecutionFailure : uint8_t {
  NONE = 0,
  INVALID_CONFIGURATION = 1,
  INVALID_STATE = 2,
  ACTION_MISMATCH = 3,
  CANDIDATE_DIGEST_MISMATCH = 4,
  BROKER_DIGEST_MISMATCH = 5,
  WIFI_CONFIGURATION_FAILED = 6,
  WIFI_START_FAILED = 7,
  WIFI_FAILED = 8,
  RECOVER_PREPARED_FAILED = 9,
  VALIDATION_START_FAILED = 10,
  VALIDATION_FAILED = 11,
  ACTIVATION_AUTHORIZATION_FAILED = 12,
  ACTIVATION_FAILED = 13,
  ACTIVE_DIGEST_MISMATCH = 14,
  READ_ONLY_VERIFY_FAILED = 15,
};

struct Stage2D10G4ExecutionSnapshot {
  Stage2D10G4ExecutionPhase phase{Stage2D10G4ExecutionPhase::LOCKED};
  Stage2D10G4ExecutionFailure failure{Stage2D10G4ExecutionFailure::NONE};
  Stage2D10G4WifiSnapshot wifi{};
  Stage2D10G4Snapshot coordinator{};
  bool command_bound{false};
  bool command_consumed{false};
  bool candidate_digest_match{false};
  bool broker_digest_match{false};
  bool wifi_operation_attempted{false};
  bool mqtt_operation_attempted{false};
  bool activation_attempted{false};
  bool activation_succeeded{false};
  bool read_only_verify_attempted{false};
  bool read_only_verify_succeeded{false};
  bool automatic_restart_required{false};
  bool cleanup_operation_attempted{false};
};

struct Stage2D10G4ExecutionConfig {
  IsolatedCandidateProfile expected_candidate{};
  std::string expected_candidate_digest{};
  std::string expected_broker_configuration_digest{};
  uint32_t wifi_timeout_ms{20000};

  bool valid() const;
  void clear();
};

class Stage2D10G4ExecutionController final {
 public:
  bool configure(const Stage2D10G4ExecutionConfig &config,
                 Stage2D10G4ActivationCoordinator *coordinator,
                 Stage2D10G4WifiPort *wifi_port);
  bool bind_command(Stage2D10G4CommandEnvelope *command,
                    Stage2D10G4ExecutionSnapshot *snapshot);
  bool begin_activate(Stage2D10G4ExecutionSnapshot *snapshot);
  bool poll(uint32_t elapsed_ms,
            Stage2D10G4ExecutionSnapshot *snapshot);
  bool verify_active_read_only(Stage2D10G4ExecutionSnapshot *snapshot);
  void quiesce();

  Stage2D10G4ExecutionPhase phase() const { return this->phase_; }
  Stage2D10G4ExecutionFailure failure() const { return this->failure_; }

  static bool candidate_digest(const IsolatedCandidateProfile &candidate,
                               std::string *digest);
  static const char *phase_name(Stage2D10G4ExecutionPhase phase);
  static const char *failure_name(Stage2D10G4ExecutionFailure failure);

 protected:
  bool fail_(Stage2D10G4ExecutionFailure failure,
             Stage2D10G4ExecutionSnapshot *snapshot,
             bool reboot_required = false);
  void refresh_(Stage2D10G4ExecutionSnapshot *snapshot) const;
  void clear_command_();
  static bool constant_equal_(const std::string &left,
                              const std::string &right);

  Stage2D10G4ExecutionConfig config_{};
  Stage2D10G4ActivationCoordinator *coordinator_{nullptr};
  Stage2D10G4WifiPort *wifi_port_{nullptr};
  Stage2D10G4CommandEnvelope command_{};
  Stage2D10G4WifiSnapshot wifi_snapshot_{};
  Stage2D10G4Snapshot coordinator_snapshot_{};
  Stage2D10G4ExecutionPhase phase_{Stage2D10G4ExecutionPhase::LOCKED};
  Stage2D10G4ExecutionFailure failure_{Stage2D10G4ExecutionFailure::NONE};
  bool configured_{false};
  bool command_bound_{false};
  bool command_consumed_{false};
  bool candidate_digest_match_{false};
  bool broker_digest_match_{false};
  bool wifi_operation_attempted_{false};
  bool mqtt_operation_attempted_{false};
  bool activation_attempted_{false};
  bool activation_succeeded_{false};
  bool read_only_verify_attempted_{false};
  bool read_only_verify_succeeded_{false};
  bool automatic_restart_required_{false};
};

}  // namespace esphome::greenhouse_pairing_client
