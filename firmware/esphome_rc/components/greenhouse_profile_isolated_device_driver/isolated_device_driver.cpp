#include "isolated_device_driver.h"

#include <algorithm>
#include <cctype>
#include <utility>

#include "../greenhouse_pairing_client/secure_pairing_channel.h"

namespace esphome::greenhouse_pairing_client {
namespace {

void wipe_string(std::string *value) {
  if (value == nullptr)
    return;
  std::fill(value->begin(), value->end(), '\0');
  value->clear();
  value->shrink_to_fit();
}

bool safe_test_storage_name(const std::string &value, const char *prefix) {
  if (prefix == nullptr || value.rfind(prefix, 0) != 0 || value.size() > 15)
    return false;
  return std::all_of(value.begin(), value.end(), [](unsigned char character) {
    return std::isalnum(character) != 0 || character == '_';
  });
}

}  // namespace

bool IsolatedDeviceDriverConfig::valid() const {
  return safe_test_storage_name(this->partition_label, "gh2d8_") &&
         safe_test_storage_name(this->namespace_name, "gh2d8_") &&
         this->partition_label != this->namespace_name &&
         this->validation_timeout_ms >= 1000 &&
         this->validation_timeout_ms <= 60000 &&
         this->activation_timeout_ms >= 1000 &&
         this->activation_timeout_ms <= 60000;
}

bool MirroredGenerationWriteAuthorization::arm(
    IsolatedAcceptanceWriteOperation operation, uint32_t active_generation,
    uint32_t candidate_generation, const std::string &authorization_digest) {
  this->clear();
  const bool candidate_required =
      operation != IsolatedAcceptanceWriteOperation::CLEANUP_TEST_STATE;
  if ((candidate_required && candidate_generation == 0) ||
      !IsolatedAcceptancePackage::valid_hex_(authorization_digest, 64)) {
    return false;
  }
  this->operation_ = operation;
  this->active_generation_ = active_generation;
  this->candidate_generation_ = candidate_generation;
  this->authorization_digest_ = authorization_digest;
  this->armed_ = true;
  return true;
}

bool MirroredGenerationWriteAuthorization::consume(
    IsolatedAcceptanceWriteOperation operation, uint32_t active_generation,
    uint32_t candidate_generation) {
  if (!this->armed_ || this->operation_ != operation ||
      this->active_generation_ != active_generation ||
      this->candidate_generation_ != candidate_generation) {
    return false;
  }
  this->clear();
  return true;
}

void MirroredGenerationWriteAuthorization::clear() {
  this->operation_ = IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE;
  this->active_generation_ = 0;
  this->candidate_generation_ = 0;
  wipe_string(&this->authorization_digest_);
  this->armed_ = false;
}

bool IsolatedDeviceDriver::configure(
    const IsolatedDeviceDriverConfig &config,
    IsolatedDevicePersistencePort *persistence, IsolatedDeviceMqttPort *mqtt,
    VolatileTestPersistenceKeyProvider *test_key_provider) {
  this->quiesce_for_reboot();
  this->config_ = config;
  this->persistence_ = persistence;
  this->mqtt_ = mqtt;
  this->test_key_provider_ = test_key_provider;
  this->write_authorization_.clear();
  this->persistence_snapshot_ = {};
  this->mqtt_snapshot_ = {};
  this->failure_ = IsolatedDeviceDriverFailure::NONE;
  this->configured_ = false;
  this->inspected_ = false;
  this->candidate_prepared_ = false;
  this->validation_started_ = false;
  this->validation_verified_ = false;
  this->activated_ = false;
  this->cleaned_ = false;
  this->reboot_required_ = false;

  if (!config.valid() || persistence == nullptr || mqtt == nullptr ||
      test_key_provider == nullptr ||
      !persistence->configure(config, test_key_provider)) {
    this->failure_ = IsolatedDeviceDriverFailure::INVALID_CONFIGURATION;
    return false;
  }
  this->configured_ = true;
  return true;
}

bool IsolatedDeviceDriver::arm_write_authorization(
    IsolatedAcceptanceWriteOperation operation, uint32_t active_generation,
    uint32_t candidate_generation,
    const std::string &authorization_digest) {
  if (!this->configured_ || this->reboot_required_ ||
      !this->write_authorization_.arm(operation, active_generation,
                                      candidate_generation,
                                      authorization_digest)) {
    this->failure_ =
        IsolatedDeviceDriverFailure::WRITE_AUTHORIZATION_MISMATCH;
    return false;
  }
  this->failure_ = IsolatedDeviceDriverFailure::NONE;
  return true;
}

void IsolatedDeviceDriver::clear_write_authorization() {
  this->write_authorization_.clear();
}

bool IsolatedDeviceDriver::inspect_read_only(
    IsolatedAcceptanceDriverSnapshot *snapshot) {
  if (!this->configured_ || snapshot == nullptr || this->reboot_required_ ||
      (this->inspected_ && !this->cleaned_)) {
    return this->fail_(IsolatedDeviceDriverFailure::INVALID_STATE, snapshot);
  }

  this->clear_sensitive_material_();
  const uint32_t writes_before = this->persistence_snapshot_.persistent_write_count;
  IsolatedDevicePersistenceSnapshot observed{};
  if (!this->persistence_->inspect_read_only(
          &observed, &this->recovered_active_, &this->recovered_candidate_) ||
      !observed.read_only_opened || !observed.recovery_valid ||
      observed.persistent_write_count != writes_before) {
    this->persistence_snapshot_ = observed;
    return this->fail_(
        observed.reboot_required
            ? IsolatedDeviceDriverFailure::READ_ONLY_RECOVERY_FAILED
            : IsolatedDeviceDriverFailure::READ_ONLY_OPEN_FAILED,
        snapshot, observed.reboot_required);
  }

  this->persistence_snapshot_ = observed;
  this->mqtt_snapshot_ = {};
  this->inspected_ = true;
  this->cleaned_ = false;
  this->failure_ = IsolatedDeviceDriverFailure::NONE;
  this->update_snapshot_(snapshot);
  return !snapshot->active_session_live && !snapshot->candidate_session_live &&
         !snapshot->probe_session_live;
}

bool IsolatedDeviceDriver::prepare_candidate(
    const IsolatedCandidateProfile &candidate,
    IsolatedAcceptanceDriverSnapshot *snapshot) {
  if (!this->configured_ || !this->inspected_ || this->candidate_prepared_ ||
      this->reboot_required_ || snapshot == nullptr || !candidate.valid() ||
      this->test_key_provider_ == nullptr ||
      !this->test_key_provider_->loaded()) {
    return this->fail_(
        this->test_key_provider_ == nullptr ||
                !this->test_key_provider_->loaded()
            ? IsolatedDeviceDriverFailure::TEST_KEY_REQUIRED
            : IsolatedDeviceDriverFailure::INVALID_STATE,
        snapshot);
  }
  if (candidate.credential_generation <=
      this->persistence_snapshot_.active_generation) {
    return this->fail_(
        IsolatedDeviceDriverFailure::WRITE_AUTHORIZATION_MISMATCH, snapshot);
  }
  if (!this->consume_mirrored_authorization_(
          IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE,
          this->persistence_snapshot_.active_generation,
          candidate.credential_generation)) {
    return this->fail_(
        IsolatedDeviceDriverFailure::WRITE_AUTHORIZATION_NOT_ARMED, snapshot);
  }

  RamCredentialBundle bundle = bundle_from_candidate_(candidate);
  if (!bundle.valid()) {
    bundle.clear();
    return this->fail_(IsolatedDeviceDriverFailure::INVALID_CONFIGURATION,
                       snapshot);
  }

  IsolatedDevicePersistenceSnapshot observed{};
  if (!this->persistence_->prepare_candidate(bundle, &observed)) {
    bundle.clear();
    this->persistence_snapshot_ = observed;
    return this->fail_(IsolatedDeviceDriverFailure::PREPARE_WRITE_FAILED,
                       snapshot, observed.reboot_required);
  }
  if (!observed.recovery_valid ||
      observed.candidate_generation != candidate.credential_generation ||
      (observed.recovery_status != "no_active_prepared" &&
       observed.recovery_status != "active_with_prepared")) {
    bundle.clear();
    this->persistence_snapshot_ = observed;
    return this->fail_(IsolatedDeviceDriverFailure::PREPARE_VERIFY_FAILED,
                       snapshot, observed.reboot_required);
  }

  this->persistence_snapshot_ = observed;
  clone_bundle_(bundle, &this->recovered_candidate_);
  bundle.clear();
  this->candidate_profile_ = candidate;
  this->candidate_prepared_ = true;
  this->failure_ = IsolatedDeviceDriverFailure::NONE;
  this->update_snapshot_(snapshot);
  return true;
}

bool IsolatedDeviceDriver::begin_validation(
    IsolatedAcceptanceDriverSnapshot *snapshot) {
  if (!this->configured_ || !this->candidate_prepared_ ||
      this->validation_started_ || this->reboot_required_ ||
      snapshot == nullptr || !this->candidate_profile_.valid() ||
      !this->recovered_candidate_.valid()) {
    return this->fail_(IsolatedDeviceDriverFailure::INVALID_STATE, snapshot);
  }

  const RamCredentialBundle *active =
      this->recovered_active_.valid() ? &this->recovered_active_ : nullptr;
  if (!this->mqtt_->configure(active, this->candidate_profile_,
                              this->config_.validation_timeout_ms,
                              this->config_.activation_timeout_ms)) {
    return this->fail_(
        IsolatedDeviceDriverFailure::MQTT_CONFIGURATION_FAILED, snapshot);
  }
  IsolatedDeviceMqttSnapshot observed{};
  if (!this->mqtt_->begin_validation(&observed)) {
    this->mqtt_snapshot_ = observed;
    return this->fail_(IsolatedDeviceDriverFailure::VALIDATION_START_FAILED,
                       snapshot, observed.reboot_required);
  }

  this->mqtt_snapshot_ = observed;
  this->validation_started_ = true;
  this->failure_ = IsolatedDeviceDriverFailure::NONE;
  this->update_snapshot_(snapshot);
  return true;
}

bool IsolatedDeviceDriver::poll_validation(
    uint32_t elapsed_ms, IsolatedAcceptanceDriverSnapshot *snapshot) {
  if (!this->configured_ || !this->validation_started_ ||
      this->validation_verified_ || this->reboot_required_ ||
      elapsed_ms == 0 || snapshot == nullptr) {
    return this->fail_(IsolatedDeviceDriverFailure::INVALID_STATE, snapshot);
  }

  IsolatedDeviceMqttSnapshot observed{};
  if (!this->mqtt_->poll_validation(elapsed_ms, &observed)) {
    this->mqtt_snapshot_ = observed;
    return this->fail_(IsolatedDeviceDriverFailure::VALIDATION_FAILED,
                       snapshot, observed.reboot_required);
  }
  this->mqtt_snapshot_ = observed;
  if (observed.validation_complete && !observed.validation_success) {
    return this->fail_(IsolatedDeviceDriverFailure::VALIDATION_FAILED,
                       snapshot, observed.reboot_required);
  }
  if (observed.validation_complete && observed.validation_success)
    this->validation_verified_ = true;

  this->failure_ = IsolatedDeviceDriverFailure::NONE;
  this->update_snapshot_(snapshot);
  return true;
}

bool IsolatedDeviceDriver::activate(
    ProfileLifecycleMutationAuthorizer *authorizer,
    IsolatedAcceptanceDriverSnapshot *snapshot) {
  if (!this->configured_ || !this->validation_verified_ || this->activated_ ||
      this->reboot_required_ || authorizer == nullptr || snapshot == nullptr) {
    return this->fail_(IsolatedDeviceDriverFailure::INVALID_STATE, snapshot);
  }

  const uint32_t active_generation =
      this->persistence_snapshot_.active_generation;
  const uint32_t candidate_generation =
      this->persistence_snapshot_.candidate_generation;
  if (!authorizer->authorize(
          ProfileLifecycleMutationOperation::COMMIT_PREPARED_PROFILE,
          active_generation, candidate_generation)) {
    return this->fail_(
        IsolatedDeviceDriverFailure::ACTIVATION_AUTHORIZATION_REJECTED,
        snapshot);
  }
  if (!this->consume_mirrored_authorization_(
          IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE,
          active_generation, candidate_generation)) {
    return this->fail_(IsolatedDeviceDriverFailure::AUTHORITY_AMBIGUOUS,
                       snapshot, true);
  }

  IsolatedDeviceMqttSnapshot mqtt_observed{};
  if (!this->mqtt_->begin_activation(&mqtt_observed)) {
    this->mqtt_snapshot_ = mqtt_observed;
    return this->fail_(IsolatedDeviceDriverFailure::ACTIVATION_START_FAILED,
                       snapshot, mqtt_observed.reboot_required);
  }
  this->mqtt_snapshot_ = mqtt_observed;

  IsolatedDevicePersistenceSnapshot persistence_observed{};
  RamCredentialBundle new_active;
  if (!this->persistence_->commit_prepared(&persistence_observed,
                                            &new_active)) {
    this->persistence_snapshot_ = persistence_observed;
    const bool rollback_ok = this->rollback_after_activation_failure_(
        &mqtt_observed, &persistence_observed);
    new_active.clear();
    const bool authority_ambiguous =
        persistence_observed.marker_committed ||
        persistence_observed.active_generation == candidate_generation ||
        persistence_observed.reboot_required || !rollback_ok;
    return this->fail_(
        authority_ambiguous
            ? IsolatedDeviceDriverFailure::AUTHORITY_AMBIGUOUS
            : IsolatedDeviceDriverFailure::PERSISTENCE_COMMIT_FAILED,
        snapshot, authority_ambiguous);
  }
  this->persistence_snapshot_ = persistence_observed;
  if (!persistence_observed.marker_last_observed ||
      persistence_observed.active_generation != candidate_generation ||
      !new_active.valid() ||
      new_active.credential_generation != candidate_generation) {
    new_active.clear();
    return this->fail_(
        IsolatedDeviceDriverFailure::MARKER_LAST_NOT_PROVEN, snapshot, true);
  }

  if (!this->mqtt_->promote_candidate(&mqtt_observed) ||
      !mqtt_observed.promotion_complete ||
      !mqtt_observed.active_session_live ||
      mqtt_observed.candidate_session_live || mqtt_observed.probe_session_live) {
    this->mqtt_snapshot_ = mqtt_observed;
    new_active.clear();
    return this->fail_(IsolatedDeviceDriverFailure::PROMOTION_FAILED, snapshot,
                       true);
  }

  this->mqtt_snapshot_ = mqtt_observed;
  this->recovered_active_.clear();
  this->recovered_active_ = std::move(new_active);
  this->recovered_candidate_.clear();
  this->candidate_profile_.clear();
  this->activated_ = true;
  this->failure_ = IsolatedDeviceDriverFailure::NONE;
  this->update_snapshot_(snapshot);
  return true;
}

bool IsolatedDeviceDriver::cleanup_test_state(
    IsolatedAcceptanceDriverSnapshot *snapshot) {
  if (!this->configured_ || !this->inspected_ || this->cleaned_ ||
      this->reboot_required_ || snapshot == nullptr) {
    return this->fail_(IsolatedDeviceDriverFailure::INVALID_STATE, snapshot);
  }
  if (!this->consume_mirrored_authorization_(
          IsolatedAcceptanceWriteOperation::CLEANUP_TEST_STATE,
          this->persistence_snapshot_.active_generation,
          this->persistence_snapshot_.candidate_generation)) {
    return this->fail_(
        IsolatedDeviceDriverFailure::WRITE_AUTHORIZATION_NOT_ARMED, snapshot);
  }

  this->mqtt_->quiesce();
  this->mqtt_snapshot_ = {};
  IsolatedDevicePersistenceSnapshot observed{};
  if (!this->persistence_->cleanup_test_namespace(&observed) ||
      !observed.cleanup_confirmed || !observed.recovery_valid ||
      observed.recovery_status != "empty" || observed.active_generation != 0 ||
      observed.candidate_generation != 0 || observed.reboot_required) {
    this->persistence_snapshot_ = observed;
    return this->fail_(IsolatedDeviceDriverFailure::CLEANUP_FAILED, snapshot,
                       observed.reboot_required);
  }

  this->persistence_snapshot_ = observed;
  this->clear_sensitive_material_();
  this->candidate_prepared_ = false;
  this->validation_started_ = false;
  this->validation_verified_ = false;
  this->activated_ = false;
  this->cleaned_ = true;
  this->failure_ = IsolatedDeviceDriverFailure::NONE;
  this->update_snapshot_(snapshot);
  return true;
}

void IsolatedDeviceDriver::quiesce_for_reboot() {
  if (this->mqtt_ != nullptr)
    this->mqtt_->quiesce();
  if (this->persistence_ != nullptr)
    this->persistence_->quiesce();
  this->write_authorization_.clear();
  this->clear_sensitive_material_();
  this->mqtt_snapshot_.active_session_live = false;
  this->mqtt_snapshot_.candidate_session_live = false;
  this->mqtt_snapshot_.probe_session_live = false;
  this->mqtt_snapshot_.reboot_required = true;
  this->reboot_required_ = true;
}

RamCredentialBundle IsolatedDeviceDriver::bundle_from_candidate_(
    const IsolatedCandidateProfile &candidate) {
  RamCredentialBundle bundle;
  bundle.schema = CREDENTIALS_CONTENT_TYPE;
  bundle.system_id = candidate.system_id;
  bundle.node_id = candidate.node_id;
  bundle.broker_host = candidate.broker_host;
  bundle.broker_port = candidate.broker_port;
  bundle.broker_tls_server_name = candidate.broker_tls_server_name;
  bundle.ca_pem = candidate.ca_pem;
  bundle.mqtt_username = candidate.mqtt_username;
  bundle.mqtt_client_id = candidate.mqtt_client_id;
  bundle.credential_generation = candidate.credential_generation;
  bundle.mqtt_password = candidate.mqtt_password;
  return bundle;
}

void IsolatedDeviceDriver::clone_bundle_(const RamCredentialBundle &source,
                                         RamCredentialBundle *target) {
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

bool IsolatedDeviceDriver::consume_mirrored_authorization_(
    IsolatedAcceptanceWriteOperation operation, uint32_t active_generation,
    uint32_t candidate_generation) {
  return this->write_authorization_.consume(operation, active_generation,
                                            candidate_generation);
}

bool IsolatedDeviceDriver::recover_persistence_(
    IsolatedDevicePersistenceSnapshot *snapshot) {
  if (snapshot == nullptr)
    return false;
  this->recovered_active_.clear();
  this->recovered_candidate_.clear();
  return this->persistence_->inspect_read_only(
      snapshot, &this->recovered_active_, &this->recovered_candidate_);
}

bool IsolatedDeviceDriver::rollback_after_activation_failure_(
    IsolatedDeviceMqttSnapshot *mqtt_snapshot,
    IsolatedDevicePersistenceSnapshot *persistence_snapshot) {
  if (mqtt_snapshot == nullptr || persistence_snapshot == nullptr)
    return false;
  const bool mqtt_rollback = this->mqtt_->rollback_activation(mqtt_snapshot);
  IsolatedDevicePersistenceSnapshot recovered{};
  const bool persistence_recovered = this->recover_persistence_(&recovered);
  if (persistence_recovered)
    *persistence_snapshot = recovered;
  this->mqtt_snapshot_ = *mqtt_snapshot;
  this->persistence_snapshot_ = *persistence_snapshot;
  return mqtt_rollback && persistence_recovered &&
         !persistence_snapshot->reboot_required;
}

bool IsolatedDeviceDriver::fail_(
    IsolatedDeviceDriverFailure failure,
    IsolatedAcceptanceDriverSnapshot *snapshot, bool reboot_required) {
  this->failure_ = failure;
  this->reboot_required_ = this->reboot_required_ || reboot_required;
  if (this->reboot_required_) {
    if (this->mqtt_ != nullptr)
      this->mqtt_->quiesce();
    if (this->persistence_ != nullptr)
      this->persistence_->quiesce();
    this->write_authorization_.clear();
    this->clear_sensitive_material_();
    this->mqtt_snapshot_.active_session_live = false;
    this->mqtt_snapshot_.candidate_session_live = false;
    this->mqtt_snapshot_.probe_session_live = false;
    this->mqtt_snapshot_.reboot_required = true;
  }
  this->update_snapshot_(snapshot);
  return false;
}

void IsolatedDeviceDriver::update_snapshot_(
    IsolatedAcceptanceDriverSnapshot *snapshot) const {
  if (snapshot == nullptr)
    return;
  *snapshot = {};
  snapshot->read_only_observed = this->inspected_;
  snapshot->active_generation =
      this->persistence_snapshot_.active_generation;
  snapshot->candidate_generation =
      this->persistence_snapshot_.candidate_generation;
  snapshot->persistence_status =
      this->persistence_snapshot_.recovery_status;
  snapshot->controller_phase = failure_name(this->failure_);
  snapshot->active_session_live = this->mqtt_snapshot_.active_session_live;
  snapshot->candidate_session_live =
      this->mqtt_snapshot_.candidate_session_live;
  snapshot->probe_session_live = this->mqtt_snapshot_.probe_session_live;
  snapshot->validation_complete =
      this->mqtt_snapshot_.validation_complete;
  snapshot->validation_success = this->mqtt_snapshot_.validation_success;
  snapshot->activation_complete = this->activated_;
  snapshot->activation_success = this->activated_;
  snapshot->marker_last_observed =
      this->persistence_snapshot_.marker_last_observed;
  snapshot->rollback_completed = this->mqtt_snapshot_.rollback_completed;
  snapshot->cleanup_confirmed =
      this->persistence_snapshot_.cleanup_confirmed;
  snapshot->reboot_required = this->reboot_required_;
  snapshot->persistent_write_count =
      this->persistence_snapshot_.persistent_write_count;
  snapshot->failure_injection_point = this->mqtt_snapshot_.failure_point;
  snapshot->rollback_result = this->mqtt_snapshot_.rollback_result;
}

void IsolatedDeviceDriver::clear_sensitive_material_() {
  this->recovered_active_.clear();
  this->recovered_candidate_.clear();
  this->candidate_profile_.clear();
}

bool IsolatedDeviceAuthorizationBinder::configure(
    IsolatedAcceptancePackage *package, IsolatedDeviceDriver *driver) {
  this->clear();
  if (package == nullptr || driver == nullptr)
    return false;
  this->package_ = package;
  this->driver_ = driver;
  return true;
}

bool IsolatedDeviceAuthorizationBinder::grant(
    IsolatedAcceptanceWriteOperation operation, uint32_t active_generation,
    uint32_t candidate_generation,
    const std::string &authorization_digest) {
  if (this->package_ == nullptr || this->driver_ == nullptr ||
      !this->driver_->arm_write_authorization(
          operation, active_generation, candidate_generation,
          authorization_digest)) {
    return false;
  }
  if (!this->package_->grant_write_authorization(
          operation, active_generation, candidate_generation,
          authorization_digest)) {
    this->driver_->clear_write_authorization();
    return false;
  }
  return true;
}

void IsolatedDeviceAuthorizationBinder::clear() {
  if (this->driver_ != nullptr)
    this->driver_->clear_write_authorization();
  this->package_ = nullptr;
  this->driver_ = nullptr;
}

const char *IsolatedDeviceDriver::failure_name(
    IsolatedDeviceDriverFailure failure) {
  switch (failure) {
    case IsolatedDeviceDriverFailure::NONE:
      return "none";
    case IsolatedDeviceDriverFailure::INVALID_CONFIGURATION:
      return "invalid_configuration";
    case IsolatedDeviceDriverFailure::INVALID_STATE:
      return "invalid_state";
    case IsolatedDeviceDriverFailure::TEST_KEY_REQUIRED:
      return "test_key_required";
    case IsolatedDeviceDriverFailure::READ_ONLY_OPEN_FAILED:
      return "read_only_open_failed";
    case IsolatedDeviceDriverFailure::READ_ONLY_RECOVERY_FAILED:
      return "read_only_recovery_failed";
    case IsolatedDeviceDriverFailure::WRITE_AUTHORIZATION_NOT_ARMED:
      return "write_authorization_not_armed";
    case IsolatedDeviceDriverFailure::WRITE_AUTHORIZATION_MISMATCH:
      return "write_authorization_mismatch";
    case IsolatedDeviceDriverFailure::PREPARE_WRITE_FAILED:
      return "prepare_write_failed";
    case IsolatedDeviceDriverFailure::PREPARE_VERIFY_FAILED:
      return "prepare_verify_failed";
    case IsolatedDeviceDriverFailure::MQTT_CONFIGURATION_FAILED:
      return "mqtt_configuration_failed";
    case IsolatedDeviceDriverFailure::VALIDATION_START_FAILED:
      return "validation_start_failed";
    case IsolatedDeviceDriverFailure::VALIDATION_FAILED:
      return "validation_failed";
    case IsolatedDeviceDriverFailure::ACTIVATION_AUTHORIZATION_REJECTED:
      return "activation_authorization_rejected";
    case IsolatedDeviceDriverFailure::ACTIVATION_START_FAILED:
      return "activation_start_failed";
    case IsolatedDeviceDriverFailure::PERSISTENCE_COMMIT_FAILED:
      return "persistence_commit_failed";
    case IsolatedDeviceDriverFailure::MARKER_LAST_NOT_PROVEN:
      return "marker_last_not_proven";
    case IsolatedDeviceDriverFailure::PROMOTION_FAILED:
      return "promotion_failed";
    case IsolatedDeviceDriverFailure::ROLLBACK_FAILED:
      return "rollback_failed";
    case IsolatedDeviceDriverFailure::CLEANUP_FAILED:
      return "cleanup_failed";
    case IsolatedDeviceDriverFailure::AUTHORITY_AMBIGUOUS:
      return "authority_ambiguous";
    case IsolatedDeviceDriverFailure::REBOOT_REQUIRED:
      return "reboot_required";
  }
  return "unknown";
}

}  // namespace esphome::greenhouse_pairing_client
