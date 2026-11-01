#pragma once

#include <cstdint>
#include <string>

#include "pairing_candidate_mqtt_validator.h"
#include "pairing_persistent_store.h"
#include "pairing_profile_activation_coordinator.h"

namespace esphome::greenhouse_pairing_client {

enum class ProfileLifecyclePhase : uint8_t {
  IDLE = 0,
  RECOVERED_PREPARED = 1,
  VALIDATING = 2,
  VERIFIED = 3,
  ACTIVATING = 4,
  ACTIVATED = 5,
  ROLLED_BACK = 6,
  FAILED = 7,
  REBOOT_REQUIRED = 8,
};

enum class ProfileLifecycleFailure : uint8_t {
  NONE = 0,
  INVALID_CONFIGURATION = 1,
  RECOVERY_FAILED = 2,
  NO_PREPARED_CANDIDATE = 3,
  RUNTIME_STAGE_FAILED = 4,
  VALIDATOR_CONFIGURATION_FAILED = 5,
  VALIDATION_START_FAILED = 6,
  VALIDATION_FAILED = 7,
  PERSISTENCE_PREFLIGHT_FAILED = 8,
  ACTIVATION_ARM_FAILED = 9,
  ACTIVATION_FAILED = 10,
};

struct ProfileLifecycleSnapshot {
  ProfileLifecyclePhase phase{ProfileLifecyclePhase::IDLE};
  ProfileLifecycleFailure failure{ProfileLifecycleFailure::NONE};
  PersistentRecoveryStatus persistence_status{PersistentRecoveryStatus::EMPTY};
  CandidateMqttProbePhase validation_phase{CandidateMqttProbePhase::IDLE};
  ProfileActivationPhase activation_phase{ProfileActivationPhase::IDLE};
  uint32_t active_generation{0};
  uint32_t candidate_generation{0};
  bool active_profile_unchanged{true};
  bool candidate_probe_client_live{false};
  bool candidate_material_present{false};
  bool persistence_committed{false};
  bool reboot_required{false};
};

class ProfileLifecycleRuntime : public ProfileActivationRuntime {
 public:
  ~ProfileLifecycleRuntime() override = default;

  virtual bool stage_recovered_profiles(
      const RamCredentialBundle *active_credentials,
      const RamCredentialBundle &candidate_credentials) = 0;
  virtual bool staged_generations_match(uint32_t active_generation,
                                        uint32_t candidate_generation) const = 0;
};

class PairingPersistentStoreActivationAdapter final
    : public ProfileActivationPersistence {
 public:
  bool configure(PairingPersistentStore *store, uint32_t active_generation,
                 uint32_t candidate_generation);
  bool refresh();

  bool prepared_matches(uint32_t active_generation,
                        uint32_t candidate_generation) const override;
  ProfileActivationCommitResult commit_verified_candidate() override;

  PersistentRecoveryStatus last_recovery_status() const {
    return this->last_recovery_status_;
  }

 protected:
  bool old_authority_preserved_(
      const PersistentRecoverySnapshot &snapshot) const;

  PairingPersistentStore *store_{nullptr};
  uint32_t expected_active_generation_{0};
  uint32_t expected_candidate_generation_{0};
  bool prepared_matches_{false};
  PersistentRecoveryStatus last_recovery_status_{PersistentRecoveryStatus::EMPTY};
};

class PairingProfileLifecycleIntegration {
 public:
  bool configure(PairingPersistentStore *store,
                 CandidateMqttTransport *candidate_transport,
                 ProfileLifecycleRuntime *runtime,
                 uint32_t validation_timeout_ms = 15000);
  bool recover_prepared();
  bool begin_validation(const std::string &nonce_hex);
  bool poll_validation(uint32_t elapsed_ms);
  bool activate();
  bool reset();

  const ProfileLifecycleSnapshot &snapshot() const { return this->snapshot_; }
  const VerifiedCandidateEvidence &verified_evidence() const {
    return this->evidence_;
  }

  static const char *phase_name(ProfileLifecyclePhase phase);
  static const char *failure_name(ProfileLifecycleFailure failure);

 protected:
  static CandidateMqttProfile profile_from_bundle_(
      const RamCredentialBundle &credentials);
  bool fail_(ProfileLifecycleFailure failure, bool clear_runtime_candidate = true);
  void refresh_nested_snapshots_();
  void clear_local_material_();

  PairingPersistentStore *store_{nullptr};
  CandidateMqttTransport *candidate_transport_{nullptr};
  ProfileLifecycleRuntime *runtime_{nullptr};
  uint32_t validation_timeout_ms_{15000};

  RamCredentialBundle candidate_credentials_{};
  CandidateMqttProfileValidator validator_{};
  PairingPersistentStoreActivationAdapter persistence_adapter_{};
  ProfileActivationCoordinator activation_{};
  VerifiedCandidateEvidence evidence_{};
  ProfileLifecycleSnapshot snapshot_{};
};

}  // namespace esphome::greenhouse_pairing_client
