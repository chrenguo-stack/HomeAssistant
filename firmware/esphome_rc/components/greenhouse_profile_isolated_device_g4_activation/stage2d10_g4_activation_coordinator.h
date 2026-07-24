#pragma once

#include <cstdint>
#include <string>

#include "../greenhouse_profile_isolated_device_driver/isolated_device_driver.h"

namespace esphome::greenhouse_pairing_client {

enum class Stage2D10G4Phase : uint8_t {
  COLD = 0,
  RECOVERED_PREPARED = 1,
  VALIDATING = 2,
  VERIFIED = 3,
  ACTIVATING = 4,
  ACTIVATED = 5,
  VERIFIED_AFTER_REBOOT = 6,
  FAILED = 7,
  REBOOT_REQUIRED = 8,
};

enum class Stage2D10G4Failure : uint8_t {
  NONE = 0,
  INVALID_CONFIGURATION = 1,
  INVALID_STATE = 2,
  TEST_KEY_REQUIRED = 3,
  READ_ONLY_RECOVERY_FAILED = 4,
  RECOVERED_STATE_MISMATCH = 5,
  RECOVERED_CANDIDATE_MISMATCH = 6,
  READ_ONLY_WRITE_DRIFT = 7,
  MQTT_CONFIGURATION_FAILED = 8,
  VALIDATION_START_FAILED = 9,
  VALIDATION_FAILED = 10,
  AUTHORIZATION_INVALID = 11,
  AUTHORIZATION_NOT_ARMED = 12,
  AUTHORIZATION_MISMATCH = 13,
  AUTHORITY_AMBIGUOUS = 14,
  ACTIVATION_START_FAILED = 15,
  ACTIVATION_ROLLBACK_FAILED = 16,
  PERSISTENCE_COMMIT_FAILED = 17,
  MARKER_LAST_NOT_PROVEN = 18,
  ACTIVE_RECOVERY_MISMATCH = 19,
  PROMOTION_FAILED = 20,
  REBOOT_VERIFICATION_FAILED = 21,
};

struct Stage2D10G4Config {
  std::string partition_label;
  std::string namespace_name;
  uint32_t validation_timeout_ms{15000};
  uint32_t activation_timeout_ms{15000};
  uint32_t expected_active_generation{0};
  uint32_t expected_candidate_generation{1};

  bool valid() const;
};

struct Stage2D10G4Snapshot {
  Stage2D10G4Phase phase{Stage2D10G4Phase::COLD};
  Stage2D10G4Failure failure{Stage2D10G4Failure::NONE};
  std::string persistence_status{"unknown"};
  uint32_t active_generation{0};
  uint32_t candidate_generation{0};
  uint32_t persistent_write_count{0};
  bool read_only_observed{false};
  bool recovered_candidate_match{false};
  bool validation_complete{false};
  bool validation_success{false};
  bool active_session_live{false};
  bool candidate_session_live{false};
  bool probe_session_live{false};
  bool marker_committed{false};
  bool marker_last_observed{false};
  bool rollback_completed{false};
  bool promotion_complete{false};
  bool package_authorization_armed{false};
  bool package_authorization_consumed{false};
  bool mirrored_authorization_armed{false};
  bool reboot_required{false};
  std::string mqtt_failure_point{"none"};
  std::string rollback_result{"not_applicable"};
};

class Stage2D10G4ActivationCoordinator final {
 public:
  bool configure(
      const Stage2D10G4Config &config,
      IsolatedDevicePersistencePort *persistence,
      IsolatedDeviceMqttPort *mqtt,
      VolatileTestPersistenceKeyProvider *test_key_provider,
      OneShotGenerationAuthorization *package_authorization,
      MirroredGenerationWriteAuthorization *mirrored_authorization);

  bool recover_prepared_read_only(
      const IsolatedCandidateProfile &runtime_candidate,
      Stage2D10G4Snapshot *snapshot);
  bool begin_validation(Stage2D10G4Snapshot *snapshot);
  bool poll_validation(uint32_t elapsed_ms,
                       Stage2D10G4Snapshot *snapshot);
  bool grant_activation_authorization(
      const std::string &authorization_digest,
      Stage2D10G4Snapshot *snapshot);
  bool activate(Stage2D10G4Snapshot *snapshot);
  bool verify_active_read_only(
      const IsolatedCandidateProfile &expected_active,
      Stage2D10G4Snapshot *snapshot);
  void quiesce_for_reboot();

  Stage2D10G4Phase phase() const { return this->phase_; }
  Stage2D10G4Failure failure() const { return this->failure_; }
  bool reboot_required() const { return this->reboot_required_; }

  static const char *phase_name(Stage2D10G4Phase phase);
  static const char *failure_name(Stage2D10G4Failure failure);

 protected:
  static bool bundle_matches_candidate_(
      const RamCredentialBundle &bundle,
      const IsolatedCandidateProfile &candidate);
  static void clone_bundle_(const RamCredentialBundle &source,
                            RamCredentialBundle *target);
  bool exact_initial_state_(
      const IsolatedDevicePersistenceSnapshot &snapshot) const;
  bool exact_active_state_(
      const IsolatedDevicePersistenceSnapshot &snapshot) const;
  bool rollback_precommit_(Stage2D10G4Snapshot *snapshot);
  bool reject_(Stage2D10G4Failure failure,
               Stage2D10G4Snapshot *snapshot);
  bool fail_(Stage2D10G4Failure failure,
             Stage2D10G4Snapshot *snapshot,
             bool reboot_required = false);
  void refresh_snapshot_(Stage2D10G4Snapshot *snapshot) const;
  void clear_sensitive_material_();
  void clear_authorizations_();

  Stage2D10G4Config config_{};
  IsolatedDevicePersistencePort *persistence_{nullptr};
  IsolatedDeviceMqttPort *mqtt_{nullptr};
  VolatileTestPersistenceKeyProvider *test_key_provider_{nullptr};
  OneShotGenerationAuthorization *package_authorization_{nullptr};
  MirroredGenerationWriteAuthorization *mirrored_authorization_{nullptr};

  RamCredentialBundle recovered_candidate_{};
  RamCredentialBundle recovered_active_{};
  IsolatedCandidateProfile runtime_candidate_{};
  IsolatedDevicePersistenceSnapshot persistence_snapshot_{};
  IsolatedDeviceMqttSnapshot mqtt_snapshot_{};

  Stage2D10G4Phase phase_{Stage2D10G4Phase::COLD};
  Stage2D10G4Failure failure_{Stage2D10G4Failure::NONE};
  bool configured_{false};
  bool recovered_candidate_match_{false};
  bool activation_authorization_granted_{false};
  bool authorization_consumed_{false};
  bool reboot_required_{false};
};

}  // namespace esphome::greenhouse_pairing_client
