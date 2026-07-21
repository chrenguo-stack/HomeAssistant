#include "pairing_profile_lifecycle_integration.h"

#include <utility>

namespace esphome::greenhouse_pairing_client {

bool PairingPersistentStoreActivationAdapter::configure(
    PairingPersistentStore *store, uint32_t active_generation,
    uint32_t candidate_generation) {
  this->store_ = store;
  this->expected_active_generation_ = active_generation;
  this->expected_candidate_generation_ = candidate_generation;
  this->prepared_matches_ = false;
  this->last_recovery_status_ = PersistentRecoveryStatus::EMPTY;
  return this->store_ != nullptr && candidate_generation != 0 &&
         candidate_generation > active_generation;
}

bool PairingPersistentStoreActivationAdapter::refresh() {
  this->prepared_matches_ = false;
  if (this->store_ == nullptr || this->expected_candidate_generation_ == 0)
    return false;

  PersistentRecoverySnapshot recovery{};
  RamCredentialBundle active;
  RamCredentialBundle candidate;
  if (!this->store_->recover(&recovery, &active, &candidate)) {
    this->last_recovery_status_ = recovery.status;
    return false;
  }
  this->last_recovery_status_ = recovery.status;

  const bool first_enrollment = this->expected_active_generation_ == 0;
  const bool status_matches =
      first_enrollment
          ? recovery.status == PersistentRecoveryStatus::NO_ACTIVE_PREPARED
          : recovery.status == PersistentRecoveryStatus::ACTIVE_WITH_PREPARED;
  const bool active_matches =
      first_enrollment
          ? recovery.active_generation == 0 &&
                !recovery.active_credentials_available
          : recovery.active_generation == this->expected_active_generation_ &&
                recovery.active_credentials_available && active.valid() &&
                active.credential_generation == this->expected_active_generation_;
  const bool candidate_matches =
      recovery.candidate_credentials_available && candidate.valid() &&
      recovery.candidate_generation == this->expected_candidate_generation_ &&
      candidate.credential_generation == this->expected_candidate_generation_;

  this->prepared_matches_ =
      status_matches && active_matches && candidate_matches;
  return this->prepared_matches_;
}

bool PairingPersistentStoreActivationAdapter::prepared_matches(
    uint32_t active_generation, uint32_t candidate_generation) const {
  return this->prepared_matches_ &&
         active_generation == this->expected_active_generation_ &&
         candidate_generation == this->expected_candidate_generation_;
}

bool PairingPersistentStoreActivationAdapter::old_authority_preserved_(
    const PersistentRecoverySnapshot &snapshot) const {
  if (this->expected_active_generation_ == 0) {
    return snapshot.active_generation == 0 &&
           !snapshot.active_credentials_available &&
           (snapshot.status == PersistentRecoveryStatus::EMPTY ||
            snapshot.status == PersistentRecoveryStatus::NO_ACTIVE_PREPARED ||
            snapshot.status ==
                PersistentRecoveryStatus::NO_ACTIVE_COMMITTED_ORPHAN);
  }

  return snapshot.active_generation == this->expected_active_generation_ &&
         snapshot.active_credentials_available &&
         (snapshot.status == PersistentRecoveryStatus::ACTIVE ||
          snapshot.status == PersistentRecoveryStatus::ACTIVE_WITH_PREPARED ||
          snapshot.status ==
              PersistentRecoveryStatus::ACTIVE_WITH_COMMITTED_ORPHAN ||
          snapshot.status ==
              PersistentRecoveryStatus::ACTIVE_WITH_INVALID_INACTIVE);
}

ProfileActivationCommitResult
PairingPersistentStoreActivationAdapter::commit_verified_candidate() {
  if (this->store_ == nullptr || !this->prepared_matches_)
    return ProfileActivationCommitResult::INDETERMINATE_REBOOT_REQUIRED;

  const bool committed = this->store_->commit_prepared();
  PersistentRecoverySnapshot recovery{};
  RamCredentialBundle active;
  RamCredentialBundle candidate;
  if (!this->store_->recover(&recovery, &active, &candidate)) {
    this->last_recovery_status_ = recovery.status;
    this->prepared_matches_ = false;
    return ProfileActivationCommitResult::INDETERMINATE_REBOOT_REQUIRED;
  }
  this->last_recovery_status_ = recovery.status;
  this->prepared_matches_ = false;

  if (committed && recovery.status == PersistentRecoveryStatus::ACTIVE &&
      recovery.active_credentials_available && active.valid() &&
      recovery.active_generation == this->expected_candidate_generation_ &&
      active.credential_generation == this->expected_candidate_generation_) {
    return ProfileActivationCommitResult::COMMITTED;
  }

  if (!committed && this->old_authority_preserved_(recovery))
    return ProfileActivationCommitResult::OLD_ACTIVE_PRESERVED;

  return ProfileActivationCommitResult::INDETERMINATE_REBOOT_REQUIRED;
}

bool PairingProfileLifecycleIntegration::configure(
    PairingPersistentStore *store, CandidateMqttTransport *candidate_transport,
    ProfileLifecycleRuntime *runtime, uint32_t validation_timeout_ms) {
  this->clear_local_material_();
  this->store_ = store;
  this->candidate_transport_ = candidate_transport;
  this->runtime_ = runtime;
  this->validation_timeout_ms_ = validation_timeout_ms;
  this->validator_ = CandidateMqttProfileValidator{};
  this->activation_ = ProfileActivationCoordinator{};
  this->persistence_adapter_ = PairingPersistentStoreActivationAdapter{};
  this->evidence_ = {};
  this->snapshot_ = {};

  if (store == nullptr || candidate_transport == nullptr || runtime == nullptr ||
      validation_timeout_ms < 1000 || validation_timeout_ms > 60000) {
    this->snapshot_.phase = ProfileLifecyclePhase::FAILED;
    this->snapshot_.failure = ProfileLifecycleFailure::INVALID_CONFIGURATION;
    return false;
  }
  return true;
}

bool PairingProfileLifecycleIntegration::recover_prepared() {
  if (this->snapshot_.phase != ProfileLifecyclePhase::IDLE ||
      this->store_ == nullptr || this->runtime_ == nullptr)
    return false;

  PersistentRecoverySnapshot recovery{};
  RamCredentialBundle active;
  RamCredentialBundle candidate;
  if (!this->store_->recover(&recovery, &active, &candidate)) {
    this->snapshot_.persistence_status = recovery.status;
    return this->fail_(ProfileLifecycleFailure::RECOVERY_FAILED);
  }
  this->snapshot_.persistence_status = recovery.status;

  const bool first_enrollment =
      recovery.status == PersistentRecoveryStatus::NO_ACTIVE_PREPARED;
  const bool rotation =
      recovery.status == PersistentRecoveryStatus::ACTIVE_WITH_PREPARED;
  if ((!first_enrollment && !rotation) ||
      !recovery.candidate_credentials_available || !candidate.valid() ||
      recovery.candidate_generation == 0 ||
      candidate.credential_generation != recovery.candidate_generation) {
    return this->fail_(ProfileLifecycleFailure::NO_PREPARED_CANDIDATE);
  }
  if (rotation &&
      (!recovery.active_credentials_available || !active.valid() ||
       active.credential_generation != recovery.active_generation)) {
    return this->fail_(ProfileLifecycleFailure::RECOVERY_FAILED);
  }

  const RamCredentialBundle *active_ptr = rotation ? &active : nullptr;
  if (!this->runtime_->stage_recovered_profiles(active_ptr, candidate) ||
      !this->runtime_->staged_generations_match(
          recovery.active_generation, recovery.candidate_generation)) {
    return this->fail_(ProfileLifecycleFailure::RUNTIME_STAGE_FAILED);
  }

  if (!this->validator_.configure(recovery.active_generation,
                                  this->validation_timeout_ms_)) {
    return this->fail_(
        ProfileLifecycleFailure::VALIDATOR_CONFIGURATION_FAILED);
  }
  if (!this->persistence_adapter_.configure(
          this->store_, recovery.active_generation,
          recovery.candidate_generation) ||
      !this->persistence_adapter_.refresh()) {
    return this->fail_(ProfileLifecycleFailure::PERSISTENCE_PREFLIGHT_FAILED);
  }

  this->candidate_credentials_ = std::move(candidate);
  active.clear();
  this->snapshot_.phase = ProfileLifecyclePhase::RECOVERED_PREPARED;
  this->snapshot_.failure = ProfileLifecycleFailure::NONE;
  this->snapshot_.active_generation = recovery.active_generation;
  this->snapshot_.candidate_generation = recovery.candidate_generation;
  this->snapshot_.active_profile_unchanged = true;
  this->snapshot_.candidate_material_present = true;
  this->refresh_nested_snapshots_();
  return true;
}

CandidateMqttProfile
PairingProfileLifecycleIntegration::profile_from_bundle_(
    const RamCredentialBundle &credentials) {
  CandidateMqttProfile profile;
  profile.system_id = credentials.system_id;
  profile.node_id = credentials.node_id;
  profile.broker_host = credentials.broker_host;
  profile.broker_port = credentials.broker_port;
  profile.broker_tls_server_name = credentials.broker_tls_server_name;
  profile.ca_pem = credentials.ca_pem;
  profile.mqtt_username = credentials.mqtt_username;
  profile.mqtt_client_id = credentials.mqtt_client_id;
  profile.credential_generation = credentials.credential_generation;
  profile.mqtt_password = credentials.mqtt_password;
  return profile;
}

bool PairingProfileLifecycleIntegration::begin_validation(
    const std::string &nonce_hex) {
  if (this->snapshot_.phase != ProfileLifecyclePhase::RECOVERED_PREPARED ||
      this->candidate_transport_ == nullptr ||
      !this->candidate_credentials_.valid())
    return false;

  CandidateMqttProfile profile =
      profile_from_bundle_(this->candidate_credentials_);
  this->candidate_credentials_.clear();
  if (!this->validator_.stage(std::move(profile), nonce_hex) ||
      !this->validator_.begin(this->candidate_transport_)) {
    return this->fail_(ProfileLifecycleFailure::VALIDATION_START_FAILED);
  }

  this->snapshot_.phase = ProfileLifecyclePhase::VALIDATING;
  this->refresh_nested_snapshots_();
  return true;
}

bool PairingProfileLifecycleIntegration::poll_validation(uint32_t elapsed_ms) {
  if (this->snapshot_.phase != ProfileLifecyclePhase::VALIDATING ||
      this->candidate_transport_ == nullptr)
    return false;

  const bool progress =
      this->validator_.poll(this->candidate_transport_, elapsed_ms);
  this->refresh_nested_snapshots_();
  const CandidateMqttProbeSnapshot &validation = this->validator_.snapshot();
  if (!progress || validation.phase == CandidateMqttProbePhase::FAILED ||
      validation.phase == CandidateMqttProbePhase::CANCELLED) {
    return this->fail_(ProfileLifecycleFailure::VALIDATION_FAILED);
  }
  if (validation.phase != CandidateMqttProbePhase::VERIFIED)
    return true;

  this->evidence_.active_generation = validation.active_generation;
  this->evidence_.candidate_generation = validation.candidate_generation;
  this->evidence_.candidate_verified = true;
  this->evidence_.candidate_probe_client_destroyed =
      !validation.candidate_client_live && !this->candidate_transport_->live();
  this->evidence_.active_profile_unchanged =
      validation.active_profile_unchanged;
  if (!this->evidence_.candidate_probe_client_destroyed ||
      !this->evidence_.active_profile_unchanged) {
    return this->fail_(ProfileLifecycleFailure::VALIDATION_FAILED);
  }

  this->snapshot_.phase = ProfileLifecyclePhase::VERIFIED;
  this->snapshot_.candidate_material_present = true;
  this->refresh_nested_snapshots_();
  return true;
}

bool PairingProfileLifecycleIntegration::activate() {
  if (this->snapshot_.phase != ProfileLifecyclePhase::VERIFIED ||
      this->runtime_ == nullptr ||
      !this->runtime_->staged_generations_match(
          this->snapshot_.active_generation,
          this->snapshot_.candidate_generation)) {
    return false;
  }
  if (!this->persistence_adapter_.refresh())
    return this->fail_(ProfileLifecycleFailure::PERSISTENCE_PREFLIGHT_FAILED);
  if (!this->activation_.configure(this->snapshot_.active_generation) ||
      !this->activation_.arm(this->evidence_)) {
    return this->fail_(ProfileLifecycleFailure::ACTIVATION_ARM_FAILED);
  }

  this->snapshot_.phase = ProfileLifecyclePhase::ACTIVATING;
  const bool activated = this->activation_.execute(
      this->runtime_, &this->persistence_adapter_);
  this->refresh_nested_snapshots_();
  const ProfileActivationSnapshot &activation = this->activation_.snapshot();
  this->snapshot_.persistence_status =
      this->persistence_adapter_.last_recovery_status();
  this->snapshot_.persistence_committed = activation.persistence_committed;
  this->snapshot_.reboot_required = activation.reboot_required;
  this->snapshot_.candidate_material_present =
      !activation.candidate_material_cleared;

  if (activated && activation.phase == ProfileActivationPhase::ACTIVATED) {
    this->snapshot_.phase = ProfileLifecyclePhase::ACTIVATED;
    this->snapshot_.failure = ProfileLifecycleFailure::NONE;
    this->snapshot_.active_generation = activation.active_generation;
    this->snapshot_.candidate_generation = 0;
    return true;
  }
  this->snapshot_.failure = ProfileLifecycleFailure::ACTIVATION_FAILED;
  if (activation.phase == ProfileActivationPhase::ROLLED_BACK) {
    this->snapshot_.phase = ProfileLifecyclePhase::ROLLED_BACK;
    return false;
  }
  if (activation.phase == ProfileActivationPhase::REBOOT_REQUIRED) {
    this->snapshot_.phase = ProfileLifecyclePhase::REBOOT_REQUIRED;
    return false;
  }
  this->snapshot_.phase = ProfileLifecyclePhase::FAILED;
  return false;
}

bool PairingProfileLifecycleIntegration::reset() {
  if (this->snapshot_.phase != ProfileLifecyclePhase::ACTIVATED &&
      this->snapshot_.phase != ProfileLifecyclePhase::ROLLED_BACK &&
      this->snapshot_.phase != ProfileLifecyclePhase::FAILED)
    return false;
  this->clear_local_material_();
  this->validator_ = CandidateMqttProfileValidator{};
  this->activation_ = ProfileActivationCoordinator{};
  this->persistence_adapter_ = PairingPersistentStoreActivationAdapter{};
  this->evidence_ = {};
  this->snapshot_ = {};
  return true;
}

bool PairingProfileLifecycleIntegration::fail_(
    ProfileLifecycleFailure failure, bool clear_runtime_candidate) {
  if (this->candidate_transport_ != nullptr &&
      this->candidate_transport_->live())
    this->candidate_transport_->destroy();
  this->clear_local_material_();
  if (clear_runtime_candidate && this->runtime_ != nullptr)
    this->runtime_->clear_candidate_material();
  this->snapshot_.phase = ProfileLifecyclePhase::FAILED;
  this->snapshot_.failure = failure;
  this->snapshot_.candidate_material_present = false;
  this->snapshot_.candidate_probe_client_live = false;
  this->refresh_nested_snapshots_();
  return false;
}

void PairingProfileLifecycleIntegration::refresh_nested_snapshots_() {
  const CandidateMqttProbeSnapshot &validation = this->validator_.snapshot();
  const ProfileActivationSnapshot &activation = this->activation_.snapshot();
  this->snapshot_.validation_phase = validation.phase;
  this->snapshot_.activation_phase = activation.phase;
  this->snapshot_.candidate_probe_client_live =
      validation.candidate_client_live;
  this->snapshot_.active_profile_unchanged =
      validation.active_profile_unchanged;
}

void PairingProfileLifecycleIntegration::clear_local_material_() {
  this->candidate_credentials_.clear();
}

const char *PairingProfileLifecycleIntegration::phase_name(
    ProfileLifecyclePhase phase) {
  switch (phase) {
    case ProfileLifecyclePhase::IDLE:
      return "idle";
    case ProfileLifecyclePhase::RECOVERED_PREPARED:
      return "recovered_prepared";
    case ProfileLifecyclePhase::VALIDATING:
      return "validating";
    case ProfileLifecyclePhase::VERIFIED:
      return "verified";
    case ProfileLifecyclePhase::ACTIVATING:
      return "activating";
    case ProfileLifecyclePhase::ACTIVATED:
      return "activated";
    case ProfileLifecyclePhase::ROLLED_BACK:
      return "rolled_back";
    case ProfileLifecyclePhase::FAILED:
      return "failed";
    case ProfileLifecyclePhase::REBOOT_REQUIRED:
      return "reboot_required";
  }
  return "unknown";
}

const char *PairingProfileLifecycleIntegration::failure_name(
    ProfileLifecycleFailure failure) {
  switch (failure) {
    case ProfileLifecycleFailure::NONE:
      return "none";
    case ProfileLifecycleFailure::INVALID_CONFIGURATION:
      return "invalid_configuration";
    case ProfileLifecycleFailure::RECOVERY_FAILED:
      return "recovery_failed";
    case ProfileLifecycleFailure::NO_PREPARED_CANDIDATE:
      return "no_prepared_candidate";
    case ProfileLifecycleFailure::RUNTIME_STAGE_FAILED:
      return "runtime_stage_failed";
    case ProfileLifecycleFailure::VALIDATOR_CONFIGURATION_FAILED:
      return "validator_configuration_failed";
    case ProfileLifecycleFailure::VALIDATION_START_FAILED:
      return "validation_start_failed";
    case ProfileLifecycleFailure::VALIDATION_FAILED:
      return "validation_failed";
    case ProfileLifecycleFailure::PERSISTENCE_PREFLIGHT_FAILED:
      return "persistence_preflight_failed";
    case ProfileLifecycleFailure::ACTIVATION_ARM_FAILED:
      return "activation_arm_failed";
    case ProfileLifecycleFailure::ACTIVATION_FAILED:
      return "activation_failed";
  }
  return "unknown";
}

}  // namespace esphome::greenhouse_pairing_client
