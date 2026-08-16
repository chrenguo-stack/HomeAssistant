#include "stage2d10_g4_activation_coordinator.h"

#include <utility>

namespace esphome::greenhouse_pairing_client {

bool Stage2D10G4Config::valid() const {
  IsolatedDeviceDriverConfig driver_config;
  driver_config.partition_label = this->partition_label;
  driver_config.namespace_name = this->namespace_name;
  driver_config.validation_timeout_ms = this->validation_timeout_ms;
  driver_config.activation_timeout_ms = this->activation_timeout_ms;
  return driver_config.valid() && this->expected_active_generation == 0 &&
         this->expected_candidate_generation == 1;
}

bool Stage2D10G4ActivationCoordinator::configure(
    const Stage2D10G4Config &config,
    IsolatedDevicePersistencePort *persistence,
    IsolatedDeviceMqttPort *mqtt,
    VolatileTestPersistenceKeyProvider *test_key_provider,
    OneShotGenerationAuthorization *package_authorization,
    MirroredGenerationWriteAuthorization *mirrored_authorization) {
  this->quiesce_for_reboot();
  this->config_ = config;
  this->persistence_ = persistence;
  this->mqtt_ = mqtt;
  this->test_key_provider_ = test_key_provider;
  this->package_authorization_ = package_authorization;
  this->mirrored_authorization_ = mirrored_authorization;
  this->persistence_snapshot_ = {};
  this->mqtt_snapshot_ = {};
  this->phase_ = Stage2D10G4Phase::COLD;
  this->failure_ = Stage2D10G4Failure::NONE;
  this->configured_ = false;
  this->recovered_candidate_match_ = false;
  this->activation_authorization_granted_ = false;
  this->authorization_consumed_ = false;
  this->reboot_required_ = false;

  if (!config.valid() || persistence == nullptr || mqtt == nullptr ||
      test_key_provider == nullptr || package_authorization == nullptr ||
      mirrored_authorization == nullptr) {
    this->failure_ = Stage2D10G4Failure::INVALID_CONFIGURATION;
    this->phase_ = Stage2D10G4Phase::FAILED;
    return false;
  }

  IsolatedDeviceDriverConfig driver_config;
  driver_config.partition_label = config.partition_label;
  driver_config.namespace_name = config.namespace_name;
  driver_config.validation_timeout_ms = config.validation_timeout_ms;
  driver_config.activation_timeout_ms = config.activation_timeout_ms;
  if (!persistence->configure(driver_config, test_key_provider)) {
    this->failure_ = Stage2D10G4Failure::INVALID_CONFIGURATION;
    this->phase_ = Stage2D10G4Phase::FAILED;
    return false;
  }

  this->clear_authorizations_();
  this->configured_ = true;
  return true;
}

bool Stage2D10G4ActivationCoordinator::recover_prepared_read_only(
    const IsolatedCandidateProfile &runtime_candidate,
    Stage2D10G4Snapshot *snapshot) {
  if (!this->configured_ || this->phase_ != Stage2D10G4Phase::COLD ||
      snapshot == nullptr || !runtime_candidate.valid()) {
    return this->reject_(Stage2D10G4Failure::INVALID_STATE, snapshot);
  }
  if (this->test_key_provider_ == nullptr ||
      !this->test_key_provider_->loaded()) {
    return this->reject_(Stage2D10G4Failure::TEST_KEY_REQUIRED, snapshot);
  }
  if (runtime_candidate.credential_generation !=
      this->config_.expected_candidate_generation) {
    return this->reject_(Stage2D10G4Failure::RECOVERED_STATE_MISMATCH,
                         snapshot);
  }

  this->clear_sensitive_material_();
  const uint32_t writes_before =
      this->persistence_snapshot_.persistent_write_count;
  IsolatedDevicePersistenceSnapshot observed{};
  if (!this->persistence_->inspect_read_only(
          &observed, &this->recovered_active_,
          &this->recovered_candidate_) ||
      !observed.read_only_opened || !observed.recovery_valid) {
    this->persistence_snapshot_ = observed;
    return this->fail_(Stage2D10G4Failure::READ_ONLY_RECOVERY_FAILED,
                       snapshot, observed.reboot_required);
  }
  this->persistence_snapshot_ = observed;

  if (observed.persistent_write_count != writes_before) {
    return this->fail_(Stage2D10G4Failure::READ_ONLY_WRITE_DRIFT, snapshot);
  }
  if (!this->exact_initial_state_(observed) ||
      this->recovered_active_.valid() ||
      !this->recovered_candidate_.valid()) {
    return this->fail_(Stage2D10G4Failure::RECOVERED_STATE_MISMATCH,
                       snapshot, observed.reboot_required);
  }
  if (!bundle_matches_candidate_(this->recovered_candidate_,
                                 runtime_candidate)) {
    return this->fail_(Stage2D10G4Failure::RECOVERED_CANDIDATE_MISMATCH,
                       snapshot);
  }

  this->runtime_candidate_ = runtime_candidate;
  if (!this->mqtt_->configure(nullptr, this->runtime_candidate_,
                              this->config_.validation_timeout_ms,
                              this->config_.activation_timeout_ms)) {
    return this->fail_(Stage2D10G4Failure::MQTT_CONFIGURATION_FAILED,
                       snapshot);
  }
  this->mqtt_snapshot_ = {};
  this->mqtt_snapshot_.configured = true;
  this->recovered_candidate_match_ = true;
  this->failure_ = Stage2D10G4Failure::NONE;
  this->phase_ = Stage2D10G4Phase::RECOVERED_PREPARED;
  this->refresh_snapshot_(snapshot);
  return true;
}

bool Stage2D10G4ActivationCoordinator::begin_validation(
    Stage2D10G4Snapshot *snapshot) {
  if (!this->configured_ ||
      this->phase_ != Stage2D10G4Phase::RECOVERED_PREPARED ||
      snapshot == nullptr || !this->recovered_candidate_match_) {
    return this->reject_(Stage2D10G4Failure::INVALID_STATE, snapshot);
  }

  IsolatedDeviceMqttSnapshot observed{};
  if (!this->mqtt_->begin_validation(&observed)) {
    this->mqtt_snapshot_ = observed;
    return this->fail_(Stage2D10G4Failure::VALIDATION_START_FAILED,
                       snapshot, observed.reboot_required);
  }
  this->mqtt_snapshot_ = observed;
  this->failure_ = Stage2D10G4Failure::NONE;
  this->phase_ = Stage2D10G4Phase::VALIDATING;
  this->refresh_snapshot_(snapshot);
  return true;
}

bool Stage2D10G4ActivationCoordinator::poll_validation(
    uint32_t elapsed_ms, Stage2D10G4Snapshot *snapshot) {
  if (!this->configured_ ||
      this->phase_ != Stage2D10G4Phase::VALIDATING || elapsed_ms == 0 ||
      snapshot == nullptr) {
    return this->reject_(Stage2D10G4Failure::INVALID_STATE, snapshot);
  }

  IsolatedDeviceMqttSnapshot observed{};
  if (!this->mqtt_->poll_validation(elapsed_ms, &observed)) {
    this->mqtt_snapshot_ = observed;
    return this->fail_(Stage2D10G4Failure::VALIDATION_FAILED, snapshot,
                       observed.reboot_required);
  }
  this->mqtt_snapshot_ = observed;
  if (observed.validation_complete && !observed.validation_success) {
    return this->fail_(Stage2D10G4Failure::VALIDATION_FAILED, snapshot,
                       observed.reboot_required);
  }
  if (observed.validation_complete && observed.validation_success) {
    if (observed.probe_session_live || observed.candidate_session_live ||
        observed.active_session_live) {
      return this->fail_(Stage2D10G4Failure::VALIDATION_FAILED, snapshot,
                         observed.reboot_required);
    }
    this->phase_ = Stage2D10G4Phase::VERIFIED;
  }
  this->failure_ = Stage2D10G4Failure::NONE;
  this->refresh_snapshot_(snapshot);
  return true;
}

bool Stage2D10G4ActivationCoordinator::grant_activation_authorization(
    const std::string &authorization_digest,
    Stage2D10G4Snapshot *snapshot) {
  if (!this->configured_ || this->phase_ != Stage2D10G4Phase::VERIFIED ||
      snapshot == nullptr || this->activation_authorization_granted_ ||
      this->package_authorization_ == nullptr ||
      this->mirrored_authorization_ == nullptr) {
    return this->reject_(Stage2D10G4Failure::INVALID_STATE, snapshot);
  }
  if (!IsolatedAcceptancePackage::valid_hex_(authorization_digest, 64)) {
    return this->reject_(Stage2D10G4Failure::AUTHORIZATION_INVALID,
                         snapshot);
  }

  if (!this->package_authorization_->arm(
          IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE,
          this->config_.expected_active_generation,
          this->config_.expected_candidate_generation,
          authorization_digest)) {
    return this->reject_(Stage2D10G4Failure::AUTHORIZATION_INVALID,
                         snapshot);
  }
  if (!this->mirrored_authorization_->arm(
          IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE,
          this->config_.expected_active_generation,
          this->config_.expected_candidate_generation,
          authorization_digest)) {
    this->package_authorization_->clear();
    return this->reject_(Stage2D10G4Failure::AUTHORIZATION_INVALID,
                         snapshot);
  }

  this->activation_authorization_granted_ = true;
  this->authorization_consumed_ = false;
  this->failure_ = Stage2D10G4Failure::NONE;
  this->refresh_snapshot_(snapshot);
  return true;
}

bool Stage2D10G4ActivationCoordinator::activate(
    Stage2D10G4Snapshot *snapshot) {
  if (!this->configured_ || this->phase_ != Stage2D10G4Phase::VERIFIED ||
      snapshot == nullptr) {
    return this->reject_(Stage2D10G4Failure::INVALID_STATE, snapshot);
  }
  if (!this->activation_authorization_granted_ ||
      this->package_authorization_ == nullptr ||
      this->mirrored_authorization_ == nullptr ||
      !this->package_authorization_->armed() ||
      !this->mirrored_authorization_->armed()) {
    return this->reject_(Stage2D10G4Failure::AUTHORIZATION_NOT_ARMED,
                         snapshot);
  }

  if (!this->package_authorization_->authorize(
          ProfileLifecycleMutationOperation::COMMIT_PREPARED_PROFILE,
          this->config_.expected_active_generation,
          this->config_.expected_candidate_generation)) {
    this->clear_authorizations_();
    return this->reject_(Stage2D10G4Failure::AUTHORIZATION_MISMATCH,
                         snapshot);
  }
  this->authorization_consumed_ = true;
  this->activation_authorization_granted_ = false;
  if (!this->mirrored_authorization_->consume(
          IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE,
          this->config_.expected_active_generation,
          this->config_.expected_candidate_generation)) {
    return this->fail_(Stage2D10G4Failure::AUTHORITY_AMBIGUOUS, snapshot,
                       true);
  }

  this->phase_ = Stage2D10G4Phase::ACTIVATING;
  IsolatedDeviceMqttSnapshot mqtt_observed{};
  if (!this->mqtt_->begin_activation(&mqtt_observed)) {
    this->mqtt_snapshot_ = mqtt_observed;
    if (!this->rollback_precommit_(snapshot)) {
      return this->fail_(Stage2D10G4Failure::ACTIVATION_ROLLBACK_FAILED,
                         snapshot, true);
    }
    return this->fail_(Stage2D10G4Failure::ACTIVATION_START_FAILED,
                       snapshot, mqtt_observed.reboot_required);
  }
  this->mqtt_snapshot_ = mqtt_observed;
  if (!mqtt_observed.candidate_session_live ||
      mqtt_observed.probe_session_live ||
      mqtt_observed.active_session_live) {
    if (!this->rollback_precommit_(snapshot)) {
      return this->fail_(Stage2D10G4Failure::ACTIVATION_ROLLBACK_FAILED,
                         snapshot, true);
    }
    return this->fail_(Stage2D10G4Failure::ACTIVATION_START_FAILED,
                       snapshot);
  }

  IsolatedDevicePersistenceSnapshot persistence_observed{};
  RamCredentialBundle new_active;
  if (!this->persistence_->commit_prepared(&persistence_observed,
                                            &new_active)) {
    this->persistence_snapshot_ = persistence_observed;
    new_active.clear();
    const bool authority_ambiguous =
        persistence_observed.marker_committed ||
        persistence_observed.active_generation ==
            this->config_.expected_candidate_generation ||
        persistence_observed.reboot_required;
    if (authority_ambiguous) {
      return this->fail_(Stage2D10G4Failure::AUTHORITY_AMBIGUOUS,
                         snapshot, true);
    }
    if (!this->rollback_precommit_(snapshot)) {
      return this->fail_(Stage2D10G4Failure::ACTIVATION_ROLLBACK_FAILED,
                         snapshot, true);
    }
    return this->fail_(Stage2D10G4Failure::PERSISTENCE_COMMIT_FAILED,
                       snapshot);
  }
  this->persistence_snapshot_ = persistence_observed;

  if (!persistence_observed.marker_last_observed ||
      !persistence_observed.marker_committed) {
    new_active.clear();
    return this->fail_(Stage2D10G4Failure::MARKER_LAST_NOT_PROVEN,
                       snapshot, true);
  }
  if (!this->exact_active_state_(persistence_observed) ||
      !new_active.valid() ||
      !bundle_matches_candidate_(new_active, this->runtime_candidate_)) {
    new_active.clear();
    return this->fail_(Stage2D10G4Failure::ACTIVE_RECOVERY_MISMATCH,
                       snapshot, true);
  }

  if (!this->mqtt_->promote_candidate(&mqtt_observed) ||
      !mqtt_observed.promotion_complete ||
      !mqtt_observed.active_session_live ||
      mqtt_observed.candidate_session_live ||
      mqtt_observed.probe_session_live) {
    this->mqtt_snapshot_ = mqtt_observed;
    new_active.clear();
    return this->fail_(Stage2D10G4Failure::PROMOTION_FAILED, snapshot,
                       true);
  }

  this->mqtt_snapshot_ = mqtt_observed;
  this->recovered_active_.clear();
  this->recovered_active_ = std::move(new_active);
  this->recovered_candidate_.clear();
  this->runtime_candidate_.clear();
  this->failure_ = Stage2D10G4Failure::NONE;
  this->phase_ = Stage2D10G4Phase::ACTIVATED;
  this->refresh_snapshot_(snapshot);
  return true;
}

bool Stage2D10G4ActivationCoordinator::verify_active_read_only(
    const IsolatedCandidateProfile &expected_active,
    Stage2D10G4Snapshot *snapshot) {
  if (!this->configured_ || this->phase_ != Stage2D10G4Phase::COLD ||
      snapshot == nullptr || !expected_active.valid() ||
      expected_active.credential_generation !=
          this->config_.expected_candidate_generation) {
    return this->reject_(Stage2D10G4Failure::INVALID_STATE, snapshot);
  }
  if (this->test_key_provider_ == nullptr ||
      !this->test_key_provider_->loaded()) {
    return this->reject_(Stage2D10G4Failure::TEST_KEY_REQUIRED, snapshot);
  }

  this->clear_sensitive_material_();
  const uint32_t writes_before =
      this->persistence_snapshot_.persistent_write_count;
  IsolatedDevicePersistenceSnapshot observed{};
  if (!this->persistence_->inspect_read_only(
          &observed, &this->recovered_active_,
          &this->recovered_candidate_) ||
      !observed.read_only_opened || !observed.recovery_valid) {
    this->persistence_snapshot_ = observed;
    return this->fail_(Stage2D10G4Failure::REBOOT_VERIFICATION_FAILED,
                       snapshot, observed.reboot_required);
  }
  this->persistence_snapshot_ = observed;

  if (observed.persistent_write_count != writes_before) {
    return this->fail_(Stage2D10G4Failure::READ_ONLY_WRITE_DRIFT, snapshot);
  }
  if (!this->exact_active_state_(observed) ||
      !this->recovered_active_.valid() ||
      this->recovered_candidate_.valid() ||
      !bundle_matches_candidate_(this->recovered_active_, expected_active)) {
    return this->fail_(Stage2D10G4Failure::REBOOT_VERIFICATION_FAILED,
                       snapshot, observed.reboot_required);
  }
  if (this->package_authorization_->armed() ||
      this->package_authorization_->consumed() ||
      this->mirrored_authorization_->armed()) {
    return this->fail_(Stage2D10G4Failure::AUTHORITY_AMBIGUOUS, snapshot,
                       true);
  }

  this->recovered_candidate_match_ = true;
  this->failure_ = Stage2D10G4Failure::NONE;
  this->phase_ = Stage2D10G4Phase::VERIFIED_AFTER_REBOOT;
  this->refresh_snapshot_(snapshot);
  return true;
}

void Stage2D10G4ActivationCoordinator::quiesce_for_reboot() {
  if (this->mqtt_ != nullptr)
    this->mqtt_->quiesce();
  if (this->persistence_ != nullptr)
    this->persistence_->quiesce();
  this->clear_sensitive_material_();
  this->clear_authorizations_();
  if (this->test_key_provider_ != nullptr)
    this->test_key_provider_->destroy();
  this->persistence_snapshot_ = {};
  this->mqtt_snapshot_ = {};
  this->configured_ = false;
  this->recovered_candidate_match_ = false;
  this->activation_authorization_granted_ = false;
  this->authorization_consumed_ = false;
  this->reboot_required_ = false;
  this->phase_ = Stage2D10G4Phase::COLD;
  this->failure_ = Stage2D10G4Failure::NONE;
}

const char *Stage2D10G4ActivationCoordinator::phase_name(
    Stage2D10G4Phase phase) {
  switch (phase) {
    case Stage2D10G4Phase::COLD:
      return "cold";
    case Stage2D10G4Phase::RECOVERED_PREPARED:
      return "recovered_prepared";
    case Stage2D10G4Phase::VALIDATING:
      return "validating";
    case Stage2D10G4Phase::VERIFIED:
      return "verified";
    case Stage2D10G4Phase::ACTIVATING:
      return "activating";
    case Stage2D10G4Phase::ACTIVATED:
      return "activated";
    case Stage2D10G4Phase::VERIFIED_AFTER_REBOOT:
      return "verified_after_reboot";
    case Stage2D10G4Phase::FAILED:
      return "failed";
    case Stage2D10G4Phase::REBOOT_REQUIRED:
      return "reboot_required";
  }
  return "unknown";
}

const char *Stage2D10G4ActivationCoordinator::failure_name(
    Stage2D10G4Failure failure) {
  switch (failure) {
    case Stage2D10G4Failure::NONE:
      return "none";
    case Stage2D10G4Failure::INVALID_CONFIGURATION:
      return "invalid_configuration";
    case Stage2D10G4Failure::INVALID_STATE:
      return "invalid_state";
    case Stage2D10G4Failure::TEST_KEY_REQUIRED:
      return "test_key_required";
    case Stage2D10G4Failure::READ_ONLY_RECOVERY_FAILED:
      return "read_only_recovery_failed";
    case Stage2D10G4Failure::RECOVERED_STATE_MISMATCH:
      return "recovered_state_mismatch";
    case Stage2D10G4Failure::RECOVERED_CANDIDATE_MISMATCH:
      return "recovered_candidate_mismatch";
    case Stage2D10G4Failure::READ_ONLY_WRITE_DRIFT:
      return "read_only_write_drift";
    case Stage2D10G4Failure::MQTT_CONFIGURATION_FAILED:
      return "mqtt_configuration_failed";
    case Stage2D10G4Failure::VALIDATION_START_FAILED:
      return "validation_start_failed";
    case Stage2D10G4Failure::VALIDATION_FAILED:
      return "validation_failed";
    case Stage2D10G4Failure::AUTHORIZATION_INVALID:
      return "authorization_invalid";
    case Stage2D10G4Failure::AUTHORIZATION_NOT_ARMED:
      return "authorization_not_armed";
    case Stage2D10G4Failure::AUTHORIZATION_MISMATCH:
      return "authorization_mismatch";
    case Stage2D10G4Failure::AUTHORITY_AMBIGUOUS:
      return "authority_ambiguous";
    case Stage2D10G4Failure::ACTIVATION_START_FAILED:
      return "activation_start_failed";
    case Stage2D10G4Failure::ACTIVATION_ROLLBACK_FAILED:
      return "activation_rollback_failed";
    case Stage2D10G4Failure::PERSISTENCE_COMMIT_FAILED:
      return "persistence_commit_failed";
    case Stage2D10G4Failure::MARKER_LAST_NOT_PROVEN:
      return "marker_last_not_proven";
    case Stage2D10G4Failure::ACTIVE_RECOVERY_MISMATCH:
      return "active_recovery_mismatch";
    case Stage2D10G4Failure::PROMOTION_FAILED:
      return "promotion_failed";
    case Stage2D10G4Failure::REBOOT_VERIFICATION_FAILED:
      return "reboot_verification_failed";
  }
  return "unknown";
}

bool Stage2D10G4ActivationCoordinator::bundle_matches_candidate_(
    const RamCredentialBundle &bundle,
    const IsolatedCandidateProfile &candidate) {
  return bundle.valid() && candidate.valid() &&
         bundle.system_id == candidate.system_id &&
         bundle.node_id == candidate.node_id &&
         bundle.broker_host == candidate.broker_host &&
         bundle.broker_port == candidate.broker_port &&
         bundle.broker_tls_server_name == candidate.broker_tls_server_name &&
         bundle.ca_pem == candidate.ca_pem &&
         bundle.mqtt_username == candidate.mqtt_username &&
         bundle.mqtt_client_id == candidate.mqtt_client_id &&
         bundle.mqtt_password == candidate.mqtt_password &&
         bundle.credential_generation == candidate.credential_generation;
}

void Stage2D10G4ActivationCoordinator::clone_bundle_(
    const RamCredentialBundle &source, RamCredentialBundle *target) {
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

bool Stage2D10G4ActivationCoordinator::exact_initial_state_(
    const IsolatedDevicePersistenceSnapshot &snapshot) const {
  return snapshot.read_only_opened && snapshot.recovery_valid &&
         snapshot.recovery_status == "no_active_prepared" &&
         snapshot.active_generation == this->config_.expected_active_generation &&
         snapshot.candidate_generation ==
             this->config_.expected_candidate_generation &&
         !snapshot.marker_committed && !snapshot.reboot_required;
}

bool Stage2D10G4ActivationCoordinator::exact_active_state_(
    const IsolatedDevicePersistenceSnapshot &snapshot) const {
  return snapshot.read_only_opened && snapshot.recovery_valid &&
         snapshot.recovery_status == "active" &&
         snapshot.active_generation ==
             this->config_.expected_candidate_generation &&
         snapshot.candidate_generation == 0 && !snapshot.reboot_required;
}

bool Stage2D10G4ActivationCoordinator::rollback_precommit_(
    Stage2D10G4Snapshot *snapshot) {
  IsolatedDeviceMqttSnapshot observed{};
  const bool rolled_back = this->mqtt_->rollback_activation(&observed);
  this->mqtt_snapshot_ = observed;
  if (!rolled_back || !observed.rollback_completed ||
      observed.active_session_live || observed.candidate_session_live ||
      observed.probe_session_live) {
    this->refresh_snapshot_(snapshot);
    return false;
  }
  this->refresh_snapshot_(snapshot);
  return true;
}

bool Stage2D10G4ActivationCoordinator::reject_(
    Stage2D10G4Failure failure, Stage2D10G4Snapshot *snapshot) {
  this->failure_ = failure;
  this->refresh_snapshot_(snapshot);
  return false;
}

bool Stage2D10G4ActivationCoordinator::fail_(
    Stage2D10G4Failure failure, Stage2D10G4Snapshot *snapshot,
    bool reboot_required) {
  this->failure_ = failure;
  this->reboot_required_ = reboot_required;
  this->phase_ = reboot_required ? Stage2D10G4Phase::REBOOT_REQUIRED
                                 : Stage2D10G4Phase::FAILED;
  if (this->mqtt_ != nullptr)
    this->mqtt_->quiesce();
  if (this->persistence_ != nullptr)
    this->persistence_->quiesce();
  this->clear_authorizations_();
  this->clear_sensitive_material_();
  if (this->test_key_provider_ != nullptr)
    this->test_key_provider_->destroy();
  this->refresh_snapshot_(snapshot);
  return false;
}

void Stage2D10G4ActivationCoordinator::refresh_snapshot_(
    Stage2D10G4Snapshot *snapshot) const {
  if (snapshot == nullptr)
    return;
  snapshot->phase = this->phase_;
  snapshot->failure = this->failure_;
  snapshot->persistence_status = this->persistence_snapshot_.recovery_status;
  snapshot->active_generation = this->persistence_snapshot_.active_generation;
  snapshot->candidate_generation =
      this->persistence_snapshot_.candidate_generation;
  snapshot->persistent_write_count =
      this->persistence_snapshot_.persistent_write_count;
  snapshot->read_only_observed =
      this->persistence_snapshot_.read_only_opened;
  snapshot->recovered_candidate_match = this->recovered_candidate_match_;
  snapshot->validation_complete = this->mqtt_snapshot_.validation_complete;
  snapshot->validation_success = this->mqtt_snapshot_.validation_success;
  snapshot->active_session_live = this->mqtt_snapshot_.active_session_live;
  snapshot->candidate_session_live =
      this->mqtt_snapshot_.candidate_session_live;
  snapshot->probe_session_live = this->mqtt_snapshot_.probe_session_live;
  snapshot->marker_committed = this->persistence_snapshot_.marker_committed;
  snapshot->marker_last_observed =
      this->persistence_snapshot_.marker_last_observed;
  snapshot->rollback_completed = this->mqtt_snapshot_.rollback_completed;
  snapshot->promotion_complete = this->mqtt_snapshot_.promotion_complete;
  snapshot->package_authorization_armed =
      this->package_authorization_ != nullptr &&
      this->package_authorization_->armed();
  snapshot->package_authorization_consumed =
      this->authorization_consumed_ ||
      (this->package_authorization_ != nullptr &&
       this->package_authorization_->consumed());
  snapshot->mirrored_authorization_armed =
      this->mirrored_authorization_ != nullptr &&
      this->mirrored_authorization_->armed();
  snapshot->reboot_required =
      this->reboot_required_ || this->persistence_snapshot_.reboot_required ||
      this->mqtt_snapshot_.reboot_required;
  snapshot->mqtt_failure_point = this->mqtt_snapshot_.failure_point;
  snapshot->rollback_result = this->mqtt_snapshot_.rollback_result;
}

void Stage2D10G4ActivationCoordinator::clear_sensitive_material_() {
  this->recovered_candidate_.clear();
  this->recovered_active_.clear();
  this->runtime_candidate_.clear();
}

void Stage2D10G4ActivationCoordinator::clear_authorizations_() {
  if (this->package_authorization_ != nullptr)
    this->package_authorization_->clear();
  if (this->mirrored_authorization_ != nullptr)
    this->mirrored_authorization_->clear();
  this->activation_authorization_granted_ = false;
}

}  // namespace esphome::greenhouse_pairing_client
