#pragma once

#include <cstdint>
#include <string>

#include "../greenhouse_pairing_client/pairing_profile_lifecycle_integration.h"
#include "../greenhouse_profile_production_adapters/profile_production_adapters.h"

namespace esphome::greenhouse_pairing_client {

enum class ProfileLifecycleControllerPhase : uint8_t {
  IDLE = 0,
  RECOVERED = 1,
  ACTIVE_LIVE = 2,
  VALIDATING = 3,
  VERIFIED = 4,
  ACTIVATING = 5,
  ACTIVATED = 6,
  ROLLED_BACK = 7,
  FAILED = 8,
  REBOOT_REQUIRED = 9,
};

enum class StartupRecoveryDisposition : uint8_t {
  UNKNOWN = 0,
  UNPAIRED = 1,
  ACTIVE_READY = 2,
  PREPARED_FIRST_ENROLLMENT = 3,
  ACTIVE_WITH_PREPARED = 4,
  ACTIVE_WITH_MAINTENANCE_PENDING = 5,
  FAULT_REBOOT_REQUIRED = 6,
};

enum class ProfileLifecycleControllerFailure : uint8_t {
  NONE = 0,
  INVALID_CONFIGURATION = 1,
  INVALID_STATE = 2,
  RECOVERY_FAILED = 3,
  RECOVERY_CONFLICT = 4,
  ACTIVE_RUNTIME_MISMATCH = 5,
  ACTIVE_START_REQUIRED = 6,
  ACTIVE_BIND_FAILED = 7,
  NO_PREPARED_CANDIDATE = 8,
  LIFECYCLE_CONFIGURATION_FAILED = 9,
  PREPARED_RECOVERY_FAILED = 10,
  NONCE_GENERATION_FAILED = 11,
  VALIDATION_START_FAILED = 12,
  VALIDATION_FAILED = 13,
  MUTATION_NOT_AUTHORIZED = 14,
  ACTIVATION_FAILED = 15,
  PROMOTION_FAILED = 16,
  RESET_FAILED = 17,
};

enum class ProfileLifecycleMutationOperation : uint8_t {
  COMMIT_PREPARED_PROFILE = 0,
};

class ProfileLifecycleMutationAuthorizer {
 public:
  virtual ~ProfileLifecycleMutationAuthorizer() = default;

  virtual bool authorize(ProfileLifecycleMutationOperation operation,
                         uint32_t active_generation,
                         uint32_t candidate_generation) = 0;
};

struct ProfileLifecycleControllerSnapshot {
  ProfileLifecycleControllerPhase phase{ProfileLifecycleControllerPhase::IDLE};
  StartupRecoveryDisposition startup_disposition{
      StartupRecoveryDisposition::UNKNOWN};
  ProfileLifecycleControllerFailure failure{
      ProfileLifecycleControllerFailure::NONE};
  PersistentRecoveryStatus persistence_status{PersistentRecoveryStatus::EMPTY};
  ProfileLifecyclePhase lifecycle_phase{ProfileLifecyclePhase::IDLE};
  uint32_t active_generation{0};
  uint32_t candidate_generation{0};
  bool active_runtime_live{false};
  bool candidate_runtime_live{false};
  bool probe_client_live{false};
  bool prepared_present{false};
  bool maintenance_pending{false};
  bool mutation_authorized{false};
  bool persistence_committed{false};
  bool promotion_finalized{false};
  bool transaction_busy{false};
  bool reboot_required{false};
};

class ProductionProfileLifecycleController {
 public:
  bool configure(PairingPersistentStore *store,
                 ProductionCandidateMqttTransport *candidate_transport,
                 ProductionProfileLifecycleRuntime *runtime,
                 ActivationNonceSource *nonce_source,
                 uint32_t validation_timeout_ms = 15000);

  // Startup recovery is read-only. It never opens a network session, validates a
  // candidate, commits persistence, or performs maintenance cleanup.
  bool recover_startup();

  // Active startup is explicit. If the same generation is already live after a
  // prior controller transaction, this method only verifies and adopts it.
  bool start_recovered_active();

  // Candidate validation is explicit and remains independent from the active
  // runtime. No persistent mutation is performed by these methods.
  bool begin_prepared_validation();
  bool poll_validation(uint32_t elapsed_ms);

  // Persistent commit is impossible without a per-call authorizer decision.
  bool activate(ProfileLifecycleMutationAuthorizer *authorizer);

  // Reset only clears controller transaction state. A successfully promoted
  // active session may remain live and will be re-adopted on the next recovery.
  bool reset_transaction();

  // Safety closure for an external supervisor. This never writes persistence.
  void quiesce_for_reboot();

  const ProfileLifecycleControllerSnapshot &snapshot() const {
    return this->snapshot_;
  }

  static const char *phase_name(ProfileLifecycleControllerPhase phase);
  static const char *disposition_name(StartupRecoveryDisposition disposition);
  static const char *failure_name(ProfileLifecycleControllerFailure failure);

 protected:
  bool active_disposition_() const;
  bool prepared_disposition_() const;
  bool classify_recovery_(const PersistentRecoverySnapshot &recovery,
                          const RamCredentialBundle &active,
                          const RamCredentialBundle &candidate);
  bool fail_(ProfileLifecycleControllerFailure failure,
             bool reboot_required = false,
             bool quiesce_runtime = false);
  void refresh_runtime_snapshot_();
  void refresh_lifecycle_snapshot_();
  void clear_recovered_material_();
  void clear_nonce_(std::string *nonce_hex);

  PairingPersistentStore *store_{nullptr};
  ProductionCandidateMqttTransport *candidate_transport_{nullptr};
  ProductionProfileLifecycleRuntime *runtime_{nullptr};
  ActivationNonceSource *nonce_source_{nullptr};
  uint32_t validation_timeout_ms_{15000};
  bool configured_{false};

  RamCredentialBundle recovered_active_{};
  PairingProfileLifecycleIntegration lifecycle_{};
  ProfileLifecycleControllerSnapshot snapshot_{};
};

}  // namespace esphome::greenhouse_pairing_client
