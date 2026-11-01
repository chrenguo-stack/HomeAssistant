#include "pairing_profile_activation_coordinator.h"

namespace esphome::greenhouse_pairing_client {

bool ProfileActivationCoordinator::configure(uint32_t active_generation) {
  this->snapshot_ = {};
  this->snapshot_.active_generation = active_generation;
  return true;
}

bool ProfileActivationCoordinator::arm(
    const VerifiedCandidateEvidence &evidence) {
  if (this->snapshot_.phase != ProfileActivationPhase::IDLE)
    return false;
  if (!evidence.candidate_verified ||
      !evidence.candidate_probe_client_destroyed ||
      !evidence.active_profile_unchanged || evidence.candidate_generation == 0 ||
      evidence.candidate_generation <= evidence.active_generation ||
      evidence.active_generation != this->snapshot_.active_generation) {
    this->snapshot_.phase = ProfileActivationPhase::FAILED;
    this->snapshot_.failure = ProfileActivationFailure::INVALID_EVIDENCE;
    return false;
  }

  this->snapshot_.phase = ProfileActivationPhase::ARMED;
  this->snapshot_.failure = ProfileActivationFailure::NONE;
  this->snapshot_.candidate_generation = evidence.candidate_generation;
  this->snapshot_.old_active_live = evidence.active_generation != 0;
  this->snapshot_.candidate_active_live = false;
  this->snapshot_.persistence_committed = false;
  this->snapshot_.candidate_material_cleared = false;
  this->snapshot_.reboot_required = false;
  return true;
}

bool ProfileActivationCoordinator::execute(
    ProfileActivationRuntime *runtime,
    ProfileActivationPersistence *persistence) {
  if (runtime == nullptr || persistence == nullptr ||
      this->snapshot_.phase != ProfileActivationPhase::ARMED)
    return false;

  this->capture_runtime_(runtime);
  const bool expect_old_active = this->snapshot_.active_generation != 0;
  if (runtime->old_active_live() != expect_old_active ||
      runtime->candidate_active_live()) {
    return this->require_reboot_(runtime,
                                 ProfileActivationFailure::OLD_ACTIVE_INVARIANT);
  }

  if (!persistence->prepared_matches(this->snapshot_.active_generation,
                                     this->snapshot_.candidate_generation)) {
    return this->fail_without_runtime_change_(
        runtime, ProfileActivationFailure::PREPARED_MISMATCH);
  }

  if (expect_old_active) {
    this->snapshot_.phase = ProfileActivationPhase::STOPPING_OLD;
    if (!runtime->stop_old_active()) {
      this->capture_runtime_(runtime);
      if (!runtime->old_active_live()) {
        return this->require_reboot_(runtime,
                                     ProfileActivationFailure::STOP_OLD_FAILED);
      }
      return this->fail_without_runtime_change_(
          runtime, ProfileActivationFailure::STOP_OLD_FAILED);
    }
    if (runtime->old_active_live()) {
      return this->require_reboot_(runtime,
                                   ProfileActivationFailure::RUNTIME_INVARIANT);
    }
  }

  this->snapshot_.phase = ProfileActivationPhase::STARTING_CANDIDATE;
  if (!runtime->start_candidate()) {
    return this->rollback_(runtime,
                           ProfileActivationFailure::START_CANDIDATE_FAILED);
  }
  if (!runtime->candidate_active_live() || runtime->old_active_live()) {
    return this->require_reboot_(runtime,
                                 ProfileActivationFailure::RUNTIME_INVARIANT);
  }

  this->snapshot_.phase = ProfileActivationPhase::CONFIRMING_CANDIDATE;
  if (!runtime->confirm_candidate_round_trip()) {
    return this->rollback_(
        runtime, ProfileActivationFailure::CONFIRM_CANDIDATE_FAILED);
  }
  if (!runtime->candidate_active_live() || runtime->old_active_live()) {
    return this->require_reboot_(runtime,
                                 ProfileActivationFailure::RUNTIME_INVARIANT);
  }

  this->snapshot_.phase = ProfileActivationPhase::COMMITTING_PERSISTENCE;
  const ProfileActivationCommitResult commit =
      persistence->commit_verified_candidate();
  if (commit == ProfileActivationCommitResult::COMMITTED) {
    if (!runtime->candidate_active_live() || runtime->old_active_live()) {
      return this->require_reboot_(runtime,
                                   ProfileActivationFailure::RUNTIME_INVARIANT);
    }
    this->snapshot_.active_generation = this->snapshot_.candidate_generation;
    this->snapshot_.candidate_generation = 0;
    this->snapshot_.persistence_committed = true;
    this->snapshot_.phase = ProfileActivationPhase::ACTIVATED;
    this->snapshot_.failure = ProfileActivationFailure::NONE;
    this->clear_candidate_material_(runtime);
    this->capture_runtime_(runtime);
    return true;
  }

  if (commit == ProfileActivationCommitResult::OLD_ACTIVE_PRESERVED) {
    return this->rollback_(runtime,
                           ProfileActivationFailure::PERSISTENCE_REJECTED);
  }

  return this->require_reboot_(
      runtime, ProfileActivationFailure::PERSISTENCE_INDETERMINATE);
}

bool ProfileActivationCoordinator::reset() {
  if (this->snapshot_.phase != ProfileActivationPhase::ACTIVATED &&
      this->snapshot_.phase != ProfileActivationPhase::ROLLED_BACK &&
      this->snapshot_.phase != ProfileActivationPhase::FAILED)
    return false;
  const uint32_t active_generation = this->snapshot_.active_generation;
  this->snapshot_ = {};
  this->snapshot_.active_generation = active_generation;
  return true;
}

bool ProfileActivationCoordinator::rollback_(
    ProfileActivationRuntime *runtime, ProfileActivationFailure failure) {
  if (runtime == nullptr)
    return false;

  bool stop_ok = true;
  if (runtime->candidate_active_live())
    stop_ok = runtime->stop_candidate();
  if (!stop_ok || runtime->candidate_active_live()) {
    return this->require_reboot_(
        runtime, ProfileActivationFailure::STOP_CANDIDATE_FAILED);
  }

  const bool has_old_active = this->snapshot_.active_generation != 0;
  if (has_old_active && !runtime->old_active_live()) {
    if (!runtime->restore_old_active() || !runtime->old_active_live()) {
      return this->require_reboot_(runtime,
                                   ProfileActivationFailure::RESTORE_OLD_FAILED);
    }
  }
  if (!has_old_active && runtime->old_active_live()) {
    return this->require_reboot_(runtime,
                                 ProfileActivationFailure::RUNTIME_INVARIANT);
  }

  this->snapshot_.phase = has_old_active ? ProfileActivationPhase::ROLLED_BACK
                                         : ProfileActivationPhase::FAILED;
  this->snapshot_.failure = failure;
  this->snapshot_.persistence_committed = false;
  this->snapshot_.reboot_required = false;
  this->clear_candidate_material_(runtime);
  this->capture_runtime_(runtime);
  return false;
}

bool ProfileActivationCoordinator::fail_without_runtime_change_(
    ProfileActivationRuntime *runtime, ProfileActivationFailure failure) {
  if (runtime == nullptr)
    return false;
  this->snapshot_.phase = ProfileActivationPhase::FAILED;
  this->snapshot_.failure = failure;
  this->snapshot_.persistence_committed = false;
  this->snapshot_.reboot_required = false;
  this->clear_candidate_material_(runtime);
  this->capture_runtime_(runtime);
  return false;
}

bool ProfileActivationCoordinator::require_reboot_(
    ProfileActivationRuntime *runtime, ProfileActivationFailure failure) {
  if (runtime != nullptr) {
    runtime->quiesce_all();
    this->clear_candidate_material_(runtime);
    this->capture_runtime_(runtime);
  }
  this->snapshot_.phase = ProfileActivationPhase::REBOOT_REQUIRED;
  this->snapshot_.failure = failure;
  this->snapshot_.persistence_committed = false;
  this->snapshot_.reboot_required = true;
  return false;
}

void ProfileActivationCoordinator::capture_runtime_(
    const ProfileActivationRuntime *runtime) {
  if (runtime == nullptr)
    return;
  this->snapshot_.old_active_live = runtime->old_active_live();
  this->snapshot_.candidate_active_live = runtime->candidate_active_live();
}

void ProfileActivationCoordinator::clear_candidate_material_(
    ProfileActivationRuntime *runtime) {
  if (runtime == nullptr || this->snapshot_.candidate_material_cleared)
    return;
  runtime->clear_candidate_material();
  this->snapshot_.candidate_material_cleared = true;
}

const char *ProfileActivationCoordinator::phase_name(
    ProfileActivationPhase phase) {
  switch (phase) {
    case ProfileActivationPhase::IDLE:
      return "idle";
    case ProfileActivationPhase::ARMED:
      return "armed";
    case ProfileActivationPhase::STOPPING_OLD:
      return "stopping_old";
    case ProfileActivationPhase::STARTING_CANDIDATE:
      return "starting_candidate";
    case ProfileActivationPhase::CONFIRMING_CANDIDATE:
      return "confirming_candidate";
    case ProfileActivationPhase::COMMITTING_PERSISTENCE:
      return "committing_persistence";
    case ProfileActivationPhase::ACTIVATED:
      return "activated";
    case ProfileActivationPhase::ROLLED_BACK:
      return "rolled_back";
    case ProfileActivationPhase::FAILED:
      return "failed";
    case ProfileActivationPhase::REBOOT_REQUIRED:
      return "reboot_required";
  }
  return "unknown";
}

const char *ProfileActivationCoordinator::failure_name(
    ProfileActivationFailure failure) {
  switch (failure) {
    case ProfileActivationFailure::NONE:
      return "none";
    case ProfileActivationFailure::INVALID_EVIDENCE:
      return "invalid_evidence";
    case ProfileActivationFailure::PREPARED_MISMATCH:
      return "prepared_mismatch";
    case ProfileActivationFailure::OLD_ACTIVE_INVARIANT:
      return "old_active_invariant";
    case ProfileActivationFailure::STOP_OLD_FAILED:
      return "stop_old_failed";
    case ProfileActivationFailure::START_CANDIDATE_FAILED:
      return "start_candidate_failed";
    case ProfileActivationFailure::CONFIRM_CANDIDATE_FAILED:
      return "confirm_candidate_failed";
    case ProfileActivationFailure::PERSISTENCE_REJECTED:
      return "persistence_rejected";
    case ProfileActivationFailure::PERSISTENCE_INDETERMINATE:
      return "persistence_indeterminate";
    case ProfileActivationFailure::STOP_CANDIDATE_FAILED:
      return "stop_candidate_failed";
    case ProfileActivationFailure::RESTORE_OLD_FAILED:
      return "restore_old_failed";
    case ProfileActivationFailure::RUNTIME_INVARIANT:
      return "runtime_invariant";
  }
  return "unknown";
}

}  // namespace esphome::greenhouse_pairing_client
