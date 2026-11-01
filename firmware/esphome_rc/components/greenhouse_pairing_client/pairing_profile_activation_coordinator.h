#pragma once

#include <cstdint>

namespace esphome::greenhouse_pairing_client {

enum class ProfileActivationPhase : uint8_t {
  IDLE = 0,
  ARMED = 1,
  STOPPING_OLD = 2,
  STARTING_CANDIDATE = 3,
  CONFIRMING_CANDIDATE = 4,
  COMMITTING_PERSISTENCE = 5,
  ACTIVATED = 6,
  ROLLED_BACK = 7,
  FAILED = 8,
  REBOOT_REQUIRED = 9,
};

enum class ProfileActivationFailure : uint8_t {
  NONE = 0,
  INVALID_EVIDENCE = 1,
  PREPARED_MISMATCH = 2,
  OLD_ACTIVE_INVARIANT = 3,
  STOP_OLD_FAILED = 4,
  START_CANDIDATE_FAILED = 5,
  CONFIRM_CANDIDATE_FAILED = 6,
  PERSISTENCE_REJECTED = 7,
  PERSISTENCE_INDETERMINATE = 8,
  STOP_CANDIDATE_FAILED = 9,
  RESTORE_OLD_FAILED = 10,
  RUNTIME_INVARIANT = 11,
};

enum class ProfileActivationCommitResult : uint8_t {
  COMMITTED = 0,
  OLD_ACTIVE_PRESERVED = 1,
  INDETERMINATE_REBOOT_REQUIRED = 2,
};

struct VerifiedCandidateEvidence {
  uint32_t active_generation{0};
  uint32_t candidate_generation{0};
  bool candidate_verified{false};
  bool candidate_probe_client_destroyed{false};
  bool active_profile_unchanged{false};
};

struct ProfileActivationSnapshot {
  ProfileActivationPhase phase{ProfileActivationPhase::IDLE};
  ProfileActivationFailure failure{ProfileActivationFailure::NONE};
  uint32_t active_generation{0};
  uint32_t candidate_generation{0};
  bool old_active_live{false};
  bool candidate_active_live{false};
  bool persistence_committed{false};
  bool candidate_material_cleared{false};
  bool reboot_required{false};
};

class ProfileActivationRuntime {
 public:
  virtual ~ProfileActivationRuntime() = default;

  virtual bool stop_old_active() = 0;
  virtual bool start_candidate() = 0;
  virtual bool confirm_candidate_round_trip() = 0;
  virtual bool stop_candidate() = 0;
  virtual bool restore_old_active() = 0;
  virtual void quiesce_all() = 0;
  virtual void clear_candidate_material() = 0;
  virtual bool old_active_live() const = 0;
  virtual bool candidate_active_live() const = 0;
};

class ProfileActivationPersistence {
 public:
  virtual ~ProfileActivationPersistence() = default;

  virtual bool prepared_matches(uint32_t active_generation,
                                uint32_t candidate_generation) const = 0;
  virtual ProfileActivationCommitResult commit_verified_candidate() = 0;
};

class ProfileActivationCoordinator {
 public:
  bool configure(uint32_t active_generation);
  bool arm(const VerifiedCandidateEvidence &evidence);
  bool execute(ProfileActivationRuntime *runtime,
               ProfileActivationPersistence *persistence);
  bool reset();

  const ProfileActivationSnapshot &snapshot() const { return this->snapshot_; }
  static const char *phase_name(ProfileActivationPhase phase);
  static const char *failure_name(ProfileActivationFailure failure);

 protected:
  bool rollback_(ProfileActivationRuntime *runtime,
                 ProfileActivationFailure failure);
  bool fail_without_runtime_change_(ProfileActivationRuntime *runtime,
                                    ProfileActivationFailure failure);
  bool require_reboot_(ProfileActivationRuntime *runtime,
                       ProfileActivationFailure failure);
  void capture_runtime_(const ProfileActivationRuntime *runtime);
  void clear_candidate_material_(ProfileActivationRuntime *runtime);

  ProfileActivationSnapshot snapshot_{};
};

}  // namespace esphome::greenhouse_pairing_client
