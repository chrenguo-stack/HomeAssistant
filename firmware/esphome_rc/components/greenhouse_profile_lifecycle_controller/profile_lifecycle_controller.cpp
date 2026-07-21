#include "profile_lifecycle_controller.h"

#include <algorithm>
#include <utility>

namespace esphome::greenhouse_pairing_client {
namespace {

void clone_bundle(const RamCredentialBundle &source, RamCredentialBundle *target) {
  if (target == nullptr)
    return;
  target->clear();
  target->schema = source.schema;
  target->system_id = source.system_id;
  target->node_id = source.node_id;
  target->broker_host = source.broker_host;
  target->broker_port = source.broker_port;
  target->broker_tls_server_name = source.broker_tls_server_name;
  target->ca_pem = source.ca_pem;
  target->mqtt_username = source.mqtt_username;
  target->mqtt_client_id = source.mqtt_client_id;
  target->credential_generation = source.credential_generation;
  target->mqtt_password = source.mqtt_password;
}

bool lifecycle_terminal(ProfileLifecyclePhase phase) {
  return phase == ProfileLifecyclePhase::ACTIVATED ||
         phase == ProfileLifecyclePhase::ROLLED_BACK ||
         phase == ProfileLifecyclePhase::FAILED;
}

}  // namespace

bool ProductionProfileLifecycleController::configure(
    PairingPersistentStore *store,
    ProductionCandidateMqttTransport *candidate_transport,
    ProductionProfileLifecycleRuntime *runtime,
    ActivationNonceSource *nonce_source, uint32_t validation_timeout_ms) {
  this->clear_recovered_material_();
  this->store_ = store;
  this->candidate_transport_ = candidate_transport;
  this->runtime_ = runtime;
  this->nonce_source_ = nonce_source;
  this->validation_timeout_ms_ = validation_timeout_ms;
  this->lifecycle_ = PairingProfileLifecycleIntegration{};
  this->snapshot_ = {};
  this->configured_ = false;

  if (store == nullptr || candidate_transport == nullptr || runtime == nullptr ||
      nonce_source == nullptr || candidate_transport->live() ||
      runtime->candidate_active_live() || validation_timeout_ms < 1000 ||
      validation_timeout_ms > 60000) {
    this->snapshot_.phase = ProfileLifecycleControllerPhase::FAILED;
    this->snapshot_.failure =
        ProfileLifecycleControllerFailure::INVALID_CONFIGURATION;
    return false;
  }

  this->configured_ = true;
  this->refresh_runtime_snapshot_();
  return true;
}

bool ProductionProfileLifecycleController::recover_startup() {
  if (!this->configured_ || this->store_ == nullptr || this->runtime_ == nullptr ||
      this->snapshot_.phase != ProfileLifecycleControllerPhase::IDLE) {
    return false;
  }

  this->clear_recovered_material_();
  this->snapshot_ = {};
  PersistentRecoverySnapshot recovery{};
  RamCredentialBundle active;
  RamCredentialBundle candidate;
  if (!this->store_->recover(&recovery, &active, &candidate)) {
    this->snapshot_.persistence_status = recovery.status;
    this->snapshot_.startup_disposition =
        StartupRecoveryDisposition::FAULT_REBOOT_REQUIRED;
    active.clear();
    candidate.clear();
    return this->fail_(ProfileLifecycleControllerFailure::RECOVERY_FAILED, true,
                       true);
  }

  this->snapshot_.persistence_status = recovery.status;
  this->snapshot_.active_generation = recovery.active_generation;
  this->snapshot_.candidate_generation = recovery.candidate_generation;
  if (!this->classify_recovery_(recovery, active, candidate)) {
    this->snapshot_.startup_disposition =
        StartupRecoveryDisposition::FAULT_REBOOT_REQUIRED;
    active.clear();
    candidate.clear();
    return this->fail_(ProfileLifecycleControllerFailure::RECOVERY_CONFLICT,
                       true, true);
  }
  active.clear();
  candidate.clear();

  this->refresh_runtime_snapshot_();
  if (this->snapshot_.candidate_runtime_live ||
      this->snapshot_.probe_client_live) {
    return this->fail_(
        ProfileLifecycleControllerFailure::ACTIVE_RUNTIME_MISMATCH, true, true);
  }

  if (this->active_disposition_()) {
    if (this->snapshot_.active_runtime_live) {
      if (this->runtime_->active_generation() !=
          this->snapshot_.active_generation) {
        return this->fail_(
            ProfileLifecycleControllerFailure::ACTIVE_RUNTIME_MISMATCH, true,
            true);
      }
      this->recovered_active_.clear();
      this->snapshot_.phase = ProfileLifecycleControllerPhase::ACTIVE_LIVE;
    } else {
      this->snapshot_.phase = ProfileLifecycleControllerPhase::RECOVERED;
    }
  } else {
    if (this->snapshot_.active_runtime_live) {
      return this->fail_(
          ProfileLifecycleControllerFailure::ACTIVE_RUNTIME_MISMATCH, true,
          true);
    }
    this->snapshot_.phase = ProfileLifecycleControllerPhase::RECOVERED;
  }

  this->snapshot_.failure = ProfileLifecycleControllerFailure::NONE;
  this->snapshot_.reboot_required = false;
  this->snapshot_.transaction_busy = false;
  return true;
}

bool ProductionProfileLifecycleController::start_recovered_active() {
  if (!this->configured_ || this->runtime_ == nullptr ||
      !this->active_disposition_()) {
    return false;
  }

  this->refresh_runtime_snapshot_();
  if (this->snapshot_.phase == ProfileLifecycleControllerPhase::ACTIVE_LIVE) {
    return this->snapshot_.active_runtime_live &&
           this->runtime_->active_generation() ==
               this->snapshot_.active_generation;
  }
  if (this->snapshot_.phase != ProfileLifecycleControllerPhase::RECOVERED)
    return false;

  if (this->snapshot_.active_runtime_live) {
    if (this->runtime_->active_generation() !=
        this->snapshot_.active_generation) {
      return this->fail_(
          ProfileLifecycleControllerFailure::ACTIVE_RUNTIME_MISMATCH, true,
          true);
    }
  } else if (!this->recovered_active_.valid() ||
             this->recovered_active_.credential_generation !=
                 this->snapshot_.active_generation ||
             !this->runtime_->bind_active_profile(this->recovered_active_)) {
    this->recovered_active_.clear();
    return this->fail_(ProfileLifecycleControllerFailure::ACTIVE_BIND_FAILED);
  }

  this->recovered_active_.clear();
  this->refresh_runtime_snapshot_();
  if (!this->snapshot_.active_runtime_live ||
      this->runtime_->active_generation() != this->snapshot_.active_generation) {
    return this->fail_(
        ProfileLifecycleControllerFailure::ACTIVE_RUNTIME_MISMATCH, true, true);
  }
  this->snapshot_.phase = ProfileLifecycleControllerPhase::ACTIVE_LIVE;
  this->snapshot_.failure = ProfileLifecycleControllerFailure::NONE;
  return true;
}

bool ProductionProfileLifecycleController::begin_prepared_validation() {
  if (!this->configured_ || this->store_ == nullptr ||
      this->candidate_transport_ == nullptr || this->runtime_ == nullptr ||
      this->nonce_source_ == nullptr || !this->prepared_disposition_()) {
    return false;
  }

  const bool rotation = this->snapshot_.startup_disposition ==
                        StartupRecoveryDisposition::ACTIVE_WITH_PREPARED;
  const bool phase_ok =
      rotation ? this->snapshot_.phase ==
                     ProfileLifecycleControllerPhase::ACTIVE_LIVE
               : this->snapshot_.phase ==
                     ProfileLifecycleControllerPhase::RECOVERED;
  if (!phase_ok) {
    this->snapshot_.failure = rotation
                                  ? ProfileLifecycleControllerFailure::
                                        ACTIVE_START_REQUIRED
                                  : ProfileLifecycleControllerFailure::INVALID_STATE;
    return false;
  }

  if (rotation &&
      (!this->runtime_->old_active_live() ||
       this->runtime_->active_generation() !=
           this->snapshot_.active_generation)) {
    return this->fail_(
        ProfileLifecycleControllerFailure::ACTIVE_RUNTIME_MISMATCH, true, true);
  }
  if (!rotation && this->runtime_->old_active_live()) {
    return this->fail_(
        ProfileLifecycleControllerFailure::ACTIVE_RUNTIME_MISMATCH, true, true);
  }

  if (!this->lifecycle_.configure(this->store_, this->candidate_transport_,
                                  this->runtime_,
                                  this->validation_timeout_ms_)) {
    return this->fail_(
        ProfileLifecycleControllerFailure::LIFECYCLE_CONFIGURATION_FAILED);
  }
  if (!this->lifecycle_.recover_prepared()) {
    this->refresh_lifecycle_snapshot_();
    return this->fail_(
        ProfileLifecycleControllerFailure::PREPARED_RECOVERY_FAILED);
  }

  std::string nonce_hex;
  if (!this->nonce_source_->next_nonce_hex(&nonce_hex)) {
    this->clear_nonce_(&nonce_hex);
    return this->fail_(
        ProfileLifecycleControllerFailure::NONCE_GENERATION_FAILED);
  }
  const bool started = this->lifecycle_.begin_validation(nonce_hex);
  this->clear_nonce_(&nonce_hex);
  if (!started) {
    this->refresh_lifecycle_snapshot_();
    return this->fail_(
        ProfileLifecycleControllerFailure::VALIDATION_START_FAILED);
  }

  this->snapshot_.phase = ProfileLifecycleControllerPhase::VALIDATING;
  this->snapshot_.failure = ProfileLifecycleControllerFailure::NONE;
  this->snapshot_.transaction_busy = true;
  this->refresh_lifecycle_snapshot_();
  return true;
}

bool ProductionProfileLifecycleController::poll_validation(uint32_t elapsed_ms) {
  if (!this->configured_ || this->snapshot_.phase !=
                                ProfileLifecycleControllerPhase::VALIDATING)
    return false;

  const bool progress = this->lifecycle_.poll_validation(elapsed_ms);
  this->refresh_lifecycle_snapshot_();
  const ProfileLifecyclePhase lifecycle_phase =
      this->lifecycle_.snapshot().phase;
  if (progress && lifecycle_phase == ProfileLifecyclePhase::VERIFIED) {
    this->snapshot_.phase = ProfileLifecycleControllerPhase::VERIFIED;
    this->snapshot_.failure = ProfileLifecycleControllerFailure::NONE;
    this->snapshot_.transaction_busy = false;
    return true;
  }
  if (!progress || lifecycle_phase == ProfileLifecyclePhase::FAILED ||
      lifecycle_phase == ProfileLifecyclePhase::ROLLED_BACK ||
      lifecycle_phase == ProfileLifecyclePhase::REBOOT_REQUIRED) {
    const bool reboot = lifecycle_phase == ProfileLifecyclePhase::REBOOT_REQUIRED;
    return this->fail_(ProfileLifecycleControllerFailure::VALIDATION_FAILED,
                       reboot, reboot);
  }
  return true;
}

bool ProductionProfileLifecycleController::activate(
    ProfileLifecycleMutationAuthorizer *authorizer) {
  if (!this->configured_ || this->runtime_ == nullptr ||
      this->snapshot_.phase != ProfileLifecycleControllerPhase::VERIFIED)
    return false;

  const uint32_t active_generation =
      this->lifecycle_.snapshot().active_generation;
  const uint32_t candidate_generation =
      this->lifecycle_.snapshot().candidate_generation;
  if (authorizer == nullptr ||
      !authorizer->authorize(
          ProfileLifecycleMutationOperation::COMMIT_PREPARED_PROFILE,
          active_generation, candidate_generation)) {
    this->snapshot_.failure =
        ProfileLifecycleControllerFailure::MUTATION_NOT_AUTHORIZED;
    this->snapshot_.mutation_authorized = false;
    return false;
  }

  this->snapshot_.mutation_authorized = true;
  this->snapshot_.failure = ProfileLifecycleControllerFailure::NONE;
  this->snapshot_.phase = ProfileLifecycleControllerPhase::ACTIVATING;
  this->snapshot_.transaction_busy = true;
  const bool activated = this->lifecycle_.activate();
  this->refresh_lifecycle_snapshot_();
  const ProfileLifecycleSnapshot &lifecycle = this->lifecycle_.snapshot();

  if (activated && lifecycle.phase == ProfileLifecyclePhase::ACTIVATED) {
    if (!this->runtime_->finalize_activation_promotion()) {
      return this->fail_(ProfileLifecycleControllerFailure::PROMOTION_FAILED,
                         true, true);
    }
    this->snapshot_.phase = ProfileLifecycleControllerPhase::ACTIVATED;
    this->snapshot_.failure = ProfileLifecycleControllerFailure::NONE;
    this->snapshot_.active_generation = this->runtime_->active_generation();
    this->snapshot_.candidate_generation = 0;
    this->snapshot_.persistence_committed = true;
    this->snapshot_.promotion_finalized = true;
    this->snapshot_.transaction_busy = false;
    this->refresh_runtime_snapshot_();
    return this->snapshot_.active_runtime_live &&
           !this->snapshot_.candidate_runtime_live;
  }

  this->snapshot_.failure =
      ProfileLifecycleControllerFailure::ACTIVATION_FAILED;
  this->snapshot_.transaction_busy = false;
  if (lifecycle.phase == ProfileLifecyclePhase::ROLLED_BACK) {
    this->snapshot_.phase = ProfileLifecycleControllerPhase::ROLLED_BACK;
    return false;
  }
  if (lifecycle.phase == ProfileLifecyclePhase::REBOOT_REQUIRED) {
    this->snapshot_.phase = ProfileLifecycleControllerPhase::REBOOT_REQUIRED;
    this->snapshot_.reboot_required = true;
    this->runtime_->quiesce_all();
    this->refresh_runtime_snapshot_();
    return false;
  }
  this->snapshot_.phase = ProfileLifecycleControllerPhase::FAILED;
  return false;
}

bool ProductionProfileLifecycleController::reset_transaction() {
  if (!this->configured_ ||
      (this->snapshot_.phase != ProfileLifecycleControllerPhase::ACTIVATED &&
       this->snapshot_.phase != ProfileLifecycleControllerPhase::ROLLED_BACK &&
       this->snapshot_.phase != ProfileLifecycleControllerPhase::FAILED)) {
    return false;
  }

  if (lifecycle_terminal(this->lifecycle_.snapshot().phase) &&
      !this->lifecycle_.reset()) {
    return this->fail_(ProfileLifecycleControllerFailure::RESET_FAILED, true,
                       true);
  }

  this->clear_recovered_material_();
  this->snapshot_ = {};
  this->snapshot_.phase = ProfileLifecycleControllerPhase::IDLE;
  this->refresh_runtime_snapshot_();
  return true;
}

void ProductionProfileLifecycleController::quiesce_for_reboot() {
  if (this->candidate_transport_ != nullptr &&
      this->candidate_transport_->live())
    this->candidate_transport_->destroy();
  if (this->runtime_ != nullptr)
    this->runtime_->quiesce_all();
  this->clear_recovered_material_();
  this->snapshot_.phase = ProfileLifecycleControllerPhase::REBOOT_REQUIRED;
  this->snapshot_.reboot_required = true;
  this->snapshot_.transaction_busy = false;
  this->refresh_runtime_snapshot_();
}

bool ProductionProfileLifecycleController::active_disposition_() const {
  return this->snapshot_.startup_disposition ==
             StartupRecoveryDisposition::ACTIVE_READY ||
         this->snapshot_.startup_disposition ==
             StartupRecoveryDisposition::ACTIVE_WITH_PREPARED ||
         this->snapshot_.startup_disposition ==
             StartupRecoveryDisposition::ACTIVE_WITH_MAINTENANCE_PENDING;
}

bool ProductionProfileLifecycleController::prepared_disposition_() const {
  return this->snapshot_.startup_disposition ==
             StartupRecoveryDisposition::PREPARED_FIRST_ENROLLMENT ||
         this->snapshot_.startup_disposition ==
             StartupRecoveryDisposition::ACTIVE_WITH_PREPARED;
}

bool ProductionProfileLifecycleController::classify_recovery_(
    const PersistentRecoverySnapshot &recovery,
    const RamCredentialBundle &active,
    const RamCredentialBundle &candidate) {
  this->snapshot_.prepared_present = false;
  this->snapshot_.maintenance_pending = false;
  this->snapshot_.startup_disposition = StartupRecoveryDisposition::UNKNOWN;

  switch (recovery.status) {
    case PersistentRecoveryStatus::EMPTY:
      if (recovery.active_generation != 0 || recovery.candidate_generation != 0)
        return false;
      this->snapshot_.startup_disposition =
          StartupRecoveryDisposition::UNPAIRED;
      return true;

    case PersistentRecoveryStatus::ACTIVE:
      if (!recovery.active_credentials_available || !active.valid() ||
          active.credential_generation != recovery.active_generation ||
          recovery.active_generation == 0)
        return false;
      clone_bundle(active, &this->recovered_active_);
      if (recovery.stale_committed_slot_present) {
        this->snapshot_.startup_disposition =
            StartupRecoveryDisposition::ACTIVE_WITH_MAINTENANCE_PENDING;
        this->snapshot_.maintenance_pending = true;
      } else {
        this->snapshot_.startup_disposition =
            StartupRecoveryDisposition::ACTIVE_READY;
      }
      return true;

    case PersistentRecoveryStatus::ACTIVE_WITH_PREPARED:
      if (!recovery.active_credentials_available ||
          !recovery.candidate_credentials_available || !active.valid() ||
          !candidate.valid() || recovery.active_generation == 0 ||
          recovery.candidate_generation <= recovery.active_generation ||
          active.credential_generation != recovery.active_generation ||
          candidate.credential_generation != recovery.candidate_generation)
        return false;
      clone_bundle(active, &this->recovered_active_);
      this->snapshot_.startup_disposition =
          StartupRecoveryDisposition::ACTIVE_WITH_PREPARED;
      this->snapshot_.prepared_present = true;
      return true;

    case PersistentRecoveryStatus::NO_ACTIVE_PREPARED:
      if (recovery.active_generation != 0 ||
          !recovery.candidate_credentials_available || !candidate.valid() ||
          recovery.candidate_generation == 0 ||
          candidate.credential_generation != recovery.candidate_generation)
        return false;
      this->snapshot_.startup_disposition =
          StartupRecoveryDisposition::PREPARED_FIRST_ENROLLMENT;
      this->snapshot_.prepared_present = true;
      return true;

    case PersistentRecoveryStatus::ACTIVE_WITH_COMMITTED_ORPHAN:
    case PersistentRecoveryStatus::ACTIVE_WITH_INVALID_INACTIVE:
      if (!recovery.active_credentials_available || !active.valid() ||
          recovery.active_generation == 0 ||
          active.credential_generation != recovery.active_generation)
        return false;
      clone_bundle(active, &this->recovered_active_);
      this->snapshot_.startup_disposition =
          StartupRecoveryDisposition::ACTIVE_WITH_MAINTENANCE_PENDING;
      this->snapshot_.maintenance_pending = true;
      return true;

    case PersistentRecoveryStatus::NO_ACTIVE_COMMITTED_ORPHAN:
    case PersistentRecoveryStatus::INVALID_RECORD:
    case PersistentRecoveryStatus::CONFLICT:
    case PersistentRecoveryStatus::STORAGE_ERROR:
      this->snapshot_.startup_disposition =
          StartupRecoveryDisposition::FAULT_REBOOT_REQUIRED;
      return false;
  }
  return false;
}

bool ProductionProfileLifecycleController::fail_(
    ProfileLifecycleControllerFailure failure, bool reboot_required,
    bool quiesce_runtime) {
  if (this->candidate_transport_ != nullptr &&
      this->candidate_transport_->live())
    this->candidate_transport_->destroy();
  if (quiesce_runtime && this->runtime_ != nullptr)
    this->runtime_->quiesce_all();
  this->recovered_active_.clear();
  this->snapshot_.failure = failure;
  this->snapshot_.phase = reboot_required
                              ? ProfileLifecycleControllerPhase::REBOOT_REQUIRED
                              : ProfileLifecycleControllerPhase::FAILED;
  this->snapshot_.reboot_required = reboot_required;
  this->snapshot_.transaction_busy = false;
  this->refresh_runtime_snapshot_();
  this->refresh_lifecycle_snapshot_();
  return false;
}

void ProductionProfileLifecycleController::refresh_runtime_snapshot_() {
  this->snapshot_.probe_client_live =
      this->candidate_transport_ != nullptr && this->candidate_transport_->live();
  this->snapshot_.active_runtime_live =
      this->runtime_ != nullptr && this->runtime_->old_active_live();
  this->snapshot_.candidate_runtime_live =
      this->runtime_ != nullptr && this->runtime_->candidate_active_live();
}

void ProductionProfileLifecycleController::refresh_lifecycle_snapshot_() {
  const ProfileLifecycleSnapshot &lifecycle = this->lifecycle_.snapshot();
  this->snapshot_.lifecycle_phase = lifecycle.phase;
  if (lifecycle.phase != ProfileLifecyclePhase::IDLE) {
    this->snapshot_.active_generation = lifecycle.active_generation;
    this->snapshot_.candidate_generation = lifecycle.candidate_generation;
    this->snapshot_.persistence_status = lifecycle.persistence_status;
    this->snapshot_.persistence_committed = lifecycle.persistence_committed;
    this->snapshot_.reboot_required =
        this->snapshot_.reboot_required || lifecycle.reboot_required;
  }
  this->refresh_runtime_snapshot_();
}

void ProductionProfileLifecycleController::clear_recovered_material_() {
  this->recovered_active_.clear();
}

void ProductionProfileLifecycleController::clear_nonce_(
    std::string *nonce_hex) {
  if (nonce_hex == nullptr)
    return;
  std::fill(nonce_hex->begin(), nonce_hex->end(), '\0');
  nonce_hex->clear();
  nonce_hex->shrink_to_fit();
}

const char *ProductionProfileLifecycleController::phase_name(
    ProfileLifecycleControllerPhase phase) {
  switch (phase) {
    case ProfileLifecycleControllerPhase::IDLE:
      return "idle";
    case ProfileLifecycleControllerPhase::RECOVERED:
      return "recovered";
    case ProfileLifecycleControllerPhase::ACTIVE_LIVE:
      return "active_live";
    case ProfileLifecycleControllerPhase::VALIDATING:
      return "validating";
    case ProfileLifecycleControllerPhase::VERIFIED:
      return "verified";
    case ProfileLifecycleControllerPhase::ACTIVATING:
      return "activating";
    case ProfileLifecycleControllerPhase::ACTIVATED:
      return "activated";
    case ProfileLifecycleControllerPhase::ROLLED_BACK:
      return "rolled_back";
    case ProfileLifecycleControllerPhase::FAILED:
      return "failed";
    case ProfileLifecycleControllerPhase::REBOOT_REQUIRED:
      return "reboot_required";
  }
  return "unknown";
}

const char *ProductionProfileLifecycleController::disposition_name(
    StartupRecoveryDisposition disposition) {
  switch (disposition) {
    case StartupRecoveryDisposition::UNKNOWN:
      return "unknown";
    case StartupRecoveryDisposition::UNPAIRED:
      return "unpaired";
    case StartupRecoveryDisposition::ACTIVE_READY:
      return "active_ready";
    case StartupRecoveryDisposition::PREPARED_FIRST_ENROLLMENT:
      return "prepared_first_enrollment";
    case StartupRecoveryDisposition::ACTIVE_WITH_PREPARED:
      return "active_with_prepared";
    case StartupRecoveryDisposition::ACTIVE_WITH_MAINTENANCE_PENDING:
      return "active_with_maintenance_pending";
    case StartupRecoveryDisposition::FAULT_REBOOT_REQUIRED:
      return "fault_reboot_required";
  }
  return "unknown";
}

const char *ProductionProfileLifecycleController::failure_name(
    ProfileLifecycleControllerFailure failure) {
  switch (failure) {
    case ProfileLifecycleControllerFailure::NONE:
      return "none";
    case ProfileLifecycleControllerFailure::INVALID_CONFIGURATION:
      return "invalid_configuration";
    case ProfileLifecycleControllerFailure::INVALID_STATE:
      return "invalid_state";
    case ProfileLifecycleControllerFailure::RECOVERY_FAILED:
      return "recovery_failed";
    case ProfileLifecycleControllerFailure::RECOVERY_CONFLICT:
      return "recovery_conflict";
    case ProfileLifecycleControllerFailure::ACTIVE_RUNTIME_MISMATCH:
      return "active_runtime_mismatch";
    case ProfileLifecycleControllerFailure::ACTIVE_START_REQUIRED:
      return "active_start_required";
    case ProfileLifecycleControllerFailure::ACTIVE_BIND_FAILED:
      return "active_bind_failed";
    case ProfileLifecycleControllerFailure::NO_PREPARED_CANDIDATE:
      return "no_prepared_candidate";
    case ProfileLifecycleControllerFailure::LIFECYCLE_CONFIGURATION_FAILED:
      return "lifecycle_configuration_failed";
    case ProfileLifecycleControllerFailure::PREPARED_RECOVERY_FAILED:
      return "prepared_recovery_failed";
    case ProfileLifecycleControllerFailure::NONCE_GENERATION_FAILED:
      return "nonce_generation_failed";
    case ProfileLifecycleControllerFailure::VALIDATION_START_FAILED:
      return "validation_start_failed";
    case ProfileLifecycleControllerFailure::VALIDATION_FAILED:
      return "validation_failed";
    case ProfileLifecycleControllerFailure::MUTATION_NOT_AUTHORIZED:
      return "mutation_not_authorized";
    case ProfileLifecycleControllerFailure::ACTIVATION_FAILED:
      return "activation_failed";
    case ProfileLifecycleControllerFailure::PROMOTION_FAILED:
      return "promotion_failed";
    case ProfileLifecycleControllerFailure::RESET_FAILED:
      return "reset_failed";
  }
  return "unknown";
}

}  // namespace esphome::greenhouse_pairing_client
