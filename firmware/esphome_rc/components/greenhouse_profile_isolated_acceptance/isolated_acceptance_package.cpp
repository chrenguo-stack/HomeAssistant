#include "isolated_acceptance_package.h"

#include <algorithm>
#include <cctype>
#include <sstream>
#include <utility>

namespace esphome::greenhouse_pairing_client {
namespace {

bool starts_with(const std::string &value, const char *prefix) {
  return prefix != nullptr && value.rfind(prefix, 0) == 0;
}

void wipe_string(std::string *value) {
  if (value == nullptr)
    return;
  std::fill(value->begin(), value->end(), '\0');
  value->clear();
  value->shrink_to_fit();
}

bool valid_test_identifier(const std::string &value) {
  if (!starts_with(value, "gh-test-") || value.size() > 96)
    return false;
  return std::all_of(value.begin(), value.end(), [](unsigned char character) {
    return std::isalnum(character) != 0 || character == '-' ||
           character == '_' || character == '.';
  });
}

bool valid_test_topic_root(const std::string &value) {
  return starts_with(value, "gh-test/") && value.size() <= 160 &&
         value.find("homeassistant") == std::string::npos &&
         value.find("gh/v1/") == std::string::npos &&
         value.find("#") == std::string::npos &&
         value.find("+") == std::string::npos;
}

const char *bool_json(bool value) { return value ? "true" : "false"; }

}  // namespace

bool IsolatedCandidateProfile::valid() const {
  return this->schema == "gh.h3.n2.isolated-candidate-profile/1" &&
         valid_test_identifier(this->test_run_id) &&
         valid_test_identifier(this->system_id) &&
         valid_test_identifier(this->node_id) &&
         !this->broker_host.empty() && this->broker_host.size() <= 253 &&
         this->broker_port != 0 &&
         !this->broker_tls_server_name.empty() &&
         this->broker_tls_server_name.size() <= 253 && !this->ca_pem.empty() &&
         !this->mqtt_username.empty() &&
         valid_test_identifier(this->mqtt_client_id) &&
         this->mqtt_client_id.find(this->test_run_id) != std::string::npos &&
         !this->mqtt_password.empty() &&
         valid_test_topic_root(this->test_topic_root) &&
         this->test_topic_root.find(this->test_run_id) != std::string::npos &&
         this->credential_generation != 0;
}

void IsolatedCandidateProfile::clear() {
  wipe_string(&this->schema);
  wipe_string(&this->test_run_id);
  wipe_string(&this->system_id);
  wipe_string(&this->node_id);
  wipe_string(&this->broker_host);
  this->broker_port = 0;
  wipe_string(&this->broker_tls_server_name);
  wipe_string(&this->ca_pem);
  wipe_string(&this->mqtt_username);
  wipe_string(&this->mqtt_client_id);
  wipe_string(&this->mqtt_password);
  wipe_string(&this->test_topic_root);
  this->credential_generation = 0;
}

bool IsolatedAcceptanceTestConfiguration::valid() const {
  return this->schema == "gh.h3.n2.stage2d7-isolated-test-config/1" &&
         IsolatedAcceptancePackage::valid_hex_(this->firmware_commit_sha, 40) &&
         IsolatedAcceptancePackage::valid_hex_(this->configuration_digest, 64) &&
         IsolatedAcceptancePackage::valid_hex_(
             this->broker_configuration_digest, 64) &&
         valid_test_identifier(this->test_device_identifier) &&
         this->candidate.valid();
}

void IsolatedAcceptanceTestConfiguration::clear() {
  wipe_string(&this->schema);
  wipe_string(&this->firmware_commit_sha);
  wipe_string(&this->configuration_digest);
  wipe_string(&this->broker_configuration_digest);
  wipe_string(&this->test_device_identifier);
  this->candidate.clear();
}

VolatileTestPersistenceKeyProvider::~VolatileTestPersistenceKeyProvider() {
  this->destroy();
}

bool VolatileTestPersistenceKeyProvider::load(
    const std::array<uint8_t, 32> &key_material) {
  this->destroy();
  const bool all_zero = std::all_of(
      key_material.begin(), key_material.end(),
      [](uint8_t value) { return value == 0; });
  if (all_zero)
    return false;
  this->key_material_ = key_material;
  this->loaded_ = true;
  return true;
}

void VolatileTestPersistenceKeyProvider::destroy() {
  zeroize_(this->key_material_.data(), this->key_material_.size());
  this->loaded_ = false;
}

bool VolatileTestPersistenceKeyProvider::derive_key(
    CredentialSlot slot, uint32_t generation, std::array<uint8_t, 32> *key) {
  if (!this->loaded_ || key == nullptr || slot == CredentialSlot::NONE ||
      generation == 0)
    return false;

  *key = this->key_material_;
  const uint8_t slot_value = static_cast<uint8_t>(slot);
  for (size_t index = 0; index < key->size(); index++) {
    const uint8_t generation_byte = static_cast<uint8_t>(
        (generation >> ((index % sizeof(generation)) * 8U)) & 0xFFU);
    (*key)[index] = static_cast<uint8_t>(
        (*key)[index] ^ generation_byte ^ slot_value ^
        static_cast<uint8_t>((index * 29U) & 0xFFU));
  }
  return true;
}

void VolatileTestPersistenceKeyProvider::zeroize_(void *data, size_t length) {
  volatile uint8_t *cursor = static_cast<volatile uint8_t *>(data);
  while (cursor != nullptr && length-- > 0)
    *cursor++ = 0;
}

bool OneShotGenerationAuthorization::arm(
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
  this->consumed_ = false;
  return true;
}

bool OneShotGenerationAuthorization::consume(
    IsolatedAcceptanceWriteOperation operation, uint32_t active_generation,
    uint32_t candidate_generation) {
  if (!this->armed_ || this->operation_ != operation ||
      this->active_generation_ != active_generation ||
      this->candidate_generation_ != candidate_generation) {
    return false;
  }
  this->armed_ = false;
  this->consumed_ = true;
  this->active_generation_ = 0;
  this->candidate_generation_ = 0;
  wipe_string(&this->authorization_digest_);
  return true;
}

bool OneShotGenerationAuthorization::authorize(
    ProfileLifecycleMutationOperation operation, uint32_t active_generation,
    uint32_t candidate_generation) {
  if (operation !=
      ProfileLifecycleMutationOperation::COMMIT_PREPARED_PROFILE) {
    return false;
  }
  return this->consume(IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE,
                       active_generation, candidate_generation);
}

void OneShotGenerationAuthorization::clear() {
  this->operation_ = IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE;
  this->active_generation_ = 0;
  this->candidate_generation_ = 0;
  wipe_string(&this->authorization_digest_);
  this->armed_ = false;
  this->consumed_ = false;
}

bool IsolatedAcceptancePackage::configure(
    IsolatedAcceptanceDriver *driver,
    VolatileTestPersistenceKeyProvider *test_key_provider,
    IsolatedAcceptanceEvidenceSink *evidence_sink) {
  this->configuration_.clear();
  this->authorization_.clear();
  this->driver_ = driver;
  this->test_key_provider_ = test_key_provider;
  this->evidence_sink_ = evidence_sink;
  this->snapshot_ = {};
  wipe_string(&this->evidence_firmware_commit_sha_);
  wipe_string(&this->evidence_configuration_digest_);
  wipe_string(&this->evidence_broker_configuration_digest_);
  wipe_string(&this->evidence_test_device_identifier_);
  wipe_string(&this->evidence_test_run_id_);

  if (this->test_key_provider_ != nullptr)
    this->test_key_provider_->destroy();
  if (driver == nullptr || test_key_provider == nullptr ||
      evidence_sink == nullptr) {
    this->snapshot_.phase = IsolatedAcceptancePhase::FAILED;
    this->snapshot_.failure =
        IsolatedAcceptanceFailure::INVALID_CONFIGURATION;
    return false;
  }
  return true;
}

bool IsolatedAcceptancePackage::inspect_read_only() {
  if (this->driver_ == nullptr ||
      (this->snapshot_.phase != IsolatedAcceptancePhase::COLD &&
       this->snapshot_.phase != IsolatedAcceptancePhase::CLEANED)) {
    return this->reject_(IsolatedAcceptanceFailure::INVALID_STATE);
  }

  IsolatedAcceptanceDriverSnapshot driver_snapshot{};
  if (!this->driver_->inspect_read_only(&driver_snapshot) ||
      !driver_snapshot.read_only_observed ||
      driver_snapshot.active_session_live ||
      driver_snapshot.candidate_session_live ||
      driver_snapshot.probe_session_live) {
    return this->fail_(
        IsolatedAcceptanceFailure::READ_ONLY_INSPECTION_FAILED,
        driver_snapshot.reboot_required);
  }

  this->refresh_driver_snapshot_(driver_snapshot);
  this->snapshot_.failure = IsolatedAcceptanceFailure::NONE;
  this->snapshot_.reboot_required = false;
  this->snapshot_.evidence_exported = false;
  this->snapshot_.cleanup_confirmed = false;
  this->transition_(IsolatedAcceptancePhase::READ_ONLY,
                    IsolatedAcceptanceCommand::INSPECT_READ_ONLY);
  return true;
}

bool IsolatedAcceptancePackage::load_test_configuration(
    IsolatedAcceptanceTestConfiguration config) {
  if (this->snapshot_.phase != IsolatedAcceptancePhase::READ_ONLY) {
    config.clear();
    return this->reject_(IsolatedAcceptanceFailure::INVALID_STATE);
  }
  if (this->test_key_provider_ == nullptr ||
      !this->test_key_provider_->loaded()) {
    config.clear();
    return this->reject_(IsolatedAcceptanceFailure::TEST_KEY_REQUIRED);
  }
  const bool configuration_valid = config.valid();
  const bool generation_valid =
      config.candidate.credential_generation > this->snapshot_.active_generation;
  if (!configuration_valid || !generation_valid) {
    config.clear();
    return this->reject_(
        configuration_valid ? IsolatedAcceptanceFailure::GENERATION_MISMATCH
                            : IsolatedAcceptanceFailure::TEST_CONFIGURATION_INVALID);
  }

  this->configuration_.clear();
  this->configuration_ = std::move(config);
  this->evidence_firmware_commit_sha_ =
      this->configuration_.firmware_commit_sha;
  this->evidence_configuration_digest_ =
      this->configuration_.configuration_digest;
  this->evidence_broker_configuration_digest_ =
      this->configuration_.broker_configuration_digest;
  this->evidence_test_device_identifier_ =
      this->configuration_.test_device_identifier;
  this->evidence_test_run_id_ = this->configuration_.candidate.test_run_id;
  this->snapshot_.candidate_generation =
      this->configuration_.candidate.credential_generation;
  this->snapshot_.test_configuration_loaded = true;
  this->snapshot_.test_key_loaded = true;
  this->snapshot_.failure = IsolatedAcceptanceFailure::NONE;
  this->transition_(IsolatedAcceptancePhase::CONFIG_LOADED,
                    IsolatedAcceptanceCommand::LOAD_TEST_CONFIGURATION);
  return true;
}

bool IsolatedAcceptancePackage::grant_write_authorization(
    IsolatedAcceptanceWriteOperation operation, uint32_t active_generation,
    uint32_t candidate_generation,
    const std::string &authorization_digest) {
  bool state_ok = false;
  switch (operation) {
    case IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE:
      state_ok = this->snapshot_.phase ==
                 IsolatedAcceptancePhase::CONFIG_LOADED;
      break;
    case IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE:
      state_ok = this->snapshot_.phase == IsolatedAcceptancePhase::VERIFIED;
      break;
    case IsolatedAcceptanceWriteOperation::CLEANUP_TEST_STATE:
      state_ok = this->snapshot_.phase == IsolatedAcceptancePhase::PREPARED ||
                 this->snapshot_.phase == IsolatedAcceptancePhase::VERIFIED ||
                 this->snapshot_.phase == IsolatedAcceptancePhase::ACTIVATED ||
                 this->snapshot_.phase == IsolatedAcceptancePhase::FAILED;
      break;
  }
  if (!state_ok ||
      !this->exact_generation_pair_(active_generation,
                                    candidate_generation)) {
    return this->reject_(state_ok
                             ? IsolatedAcceptanceFailure::GENERATION_MISMATCH
                             : IsolatedAcceptanceFailure::INVALID_STATE);
  }
  if (!this->authorization_.arm(operation, active_generation,
                                candidate_generation,
                                authorization_digest)) {
    return this->reject_(IsolatedAcceptanceFailure::AUTHORIZATION_INVALID);
  }

  this->snapshot_.write_authorization_armed = true;
  this->snapshot_.write_authorization_consumed = false;
  this->snapshot_.failure = IsolatedAcceptanceFailure::NONE;
  this->snapshot_.last_command =
      IsolatedAcceptanceCommand::GRANT_WRITE_AUTHORIZATION;
  this->snapshot_.transition_count++;
  return true;
}

bool IsolatedAcceptancePackage::prepare_candidate() {
  if (this->snapshot_.phase != IsolatedAcceptancePhase::CONFIG_LOADED ||
      !this->configuration_.valid() || this->test_key_provider_ == nullptr ||
      !this->test_key_provider_->loaded()) {
    return this->reject_(this->test_key_provider_ == nullptr ||
                                 !this->test_key_provider_->loaded()
                             ? IsolatedAcceptanceFailure::TEST_KEY_REQUIRED
                             : IsolatedAcceptanceFailure::INVALID_STATE);
  }
  if (!this->authorization_.armed() ||
      this->authorization_.operation() !=
          IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE) {
    return this->reject_(IsolatedAcceptanceFailure::AUTHORIZATION_NOT_ARMED);
  }
  if (!this->authorization_.consume(
          IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE,
          this->snapshot_.active_generation,
          this->snapshot_.candidate_generation)) {
    return this->reject_(IsolatedAcceptanceFailure::AUTHORIZATION_INVALID);
  }

  this->snapshot_.write_authorization_armed = false;
  this->snapshot_.write_authorization_consumed = true;
  IsolatedAcceptanceDriverSnapshot driver_snapshot{};
  const bool prepared = this->driver_->prepare_candidate(
      this->configuration_.candidate, &driver_snapshot);
  this->authorization_.acknowledge_consumption();
  this->refresh_driver_snapshot_(driver_snapshot);
  if (!prepared || driver_snapshot.reboot_required ||
      driver_snapshot.candidate_generation !=
          this->configuration_.candidate.credential_generation) {
    return this->fail_(IsolatedAcceptanceFailure::PREPARE_FAILED,
                       driver_snapshot.reboot_required);
  }

  this->snapshot_.failure = IsolatedAcceptanceFailure::NONE;
  this->transition_(IsolatedAcceptancePhase::PREPARED,
                    IsolatedAcceptanceCommand::PREPARE_CANDIDATE);
  return true;
}

bool IsolatedAcceptancePackage::begin_validation() {
  if (this->snapshot_.phase != IsolatedAcceptancePhase::PREPARED)
    return this->reject_(IsolatedAcceptanceFailure::INVALID_STATE);

  IsolatedAcceptanceDriverSnapshot driver_snapshot{};
  if (!this->driver_->begin_validation(&driver_snapshot)) {
    this->refresh_driver_snapshot_(driver_snapshot);
    return this->fail_(IsolatedAcceptanceFailure::VALIDATION_START_FAILED,
                       driver_snapshot.reboot_required);
  }
  this->refresh_driver_snapshot_(driver_snapshot);
  this->snapshot_.failure = IsolatedAcceptanceFailure::NONE;
  this->transition_(IsolatedAcceptancePhase::VALIDATING,
                    IsolatedAcceptanceCommand::BEGIN_VALIDATION);
  return true;
}

bool IsolatedAcceptancePackage::poll_validation(uint32_t elapsed_ms) {
  if (this->snapshot_.phase != IsolatedAcceptancePhase::VALIDATING ||
      elapsed_ms == 0)
    return this->reject_(IsolatedAcceptanceFailure::INVALID_STATE);

  IsolatedAcceptanceDriverSnapshot driver_snapshot{};
  const bool progress =
      this->driver_->poll_validation(elapsed_ms, &driver_snapshot);
  this->refresh_driver_snapshot_(driver_snapshot);
  this->snapshot_.last_command = IsolatedAcceptanceCommand::POLL_VALIDATION;
  this->snapshot_.transition_count++;
  if (!progress || driver_snapshot.reboot_required) {
    return this->fail_(IsolatedAcceptanceFailure::VALIDATION_FAILED,
                       driver_snapshot.reboot_required);
  }
  if (!driver_snapshot.validation_complete)
    return true;
  if (!driver_snapshot.validation_success)
    return this->fail_(IsolatedAcceptanceFailure::VALIDATION_FAILED);

  this->snapshot_.failure = IsolatedAcceptanceFailure::NONE;
  this->transition_(IsolatedAcceptancePhase::VERIFIED,
                    IsolatedAcceptanceCommand::POLL_VALIDATION);
  return true;
}

bool IsolatedAcceptancePackage::activate() {
  if (this->snapshot_.phase != IsolatedAcceptancePhase::VERIFIED)
    return this->reject_(IsolatedAcceptanceFailure::INVALID_STATE);
  if (!this->authorization_.armed() ||
      this->authorization_.operation() !=
          IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE) {
    return this->reject_(IsolatedAcceptanceFailure::AUTHORIZATION_NOT_ARMED);
  }

  this->transition_(IsolatedAcceptancePhase::ACTIVATING,
                    IsolatedAcceptanceCommand::ACTIVATE);
  IsolatedAcceptanceDriverSnapshot driver_snapshot{};
  const bool activated =
      this->driver_->activate(&this->authorization_, &driver_snapshot);
  this->refresh_driver_snapshot_(driver_snapshot);
  if (!this->authorization_.consumed()) {
    this->driver_->quiesce_for_reboot();
    return this->fail_(
        IsolatedAcceptanceFailure::AUTHORIZATION_NOT_CONSUMED, true);
  }
  this->authorization_.acknowledge_consumption();
  this->snapshot_.write_authorization_armed = false;
  this->snapshot_.write_authorization_consumed = true;

  if (!activated || !driver_snapshot.activation_complete ||
      !driver_snapshot.activation_success ||
      !driver_snapshot.marker_last_observed ||
      driver_snapshot.reboot_required) {
    return this->fail_(IsolatedAcceptanceFailure::ACTIVATION_FAILED,
                       driver_snapshot.reboot_required ||
                           (activated && !driver_snapshot.marker_last_observed));
  }

  this->snapshot_.failure = IsolatedAcceptanceFailure::NONE;
  this->transition_(IsolatedAcceptancePhase::ACTIVATED,
                    IsolatedAcceptanceCommand::ACTIVATE);
  return true;
}

bool IsolatedAcceptancePackage::export_evidence() {
  if (!this->evidence_metadata_available_() || this->evidence_sink_ == nullptr ||
      this->snapshot_.phase == IsolatedAcceptancePhase::COLD ||
      this->snapshot_.phase == IsolatedAcceptancePhase::CONFIG_LOADED ||
      this->snapshot_.phase == IsolatedAcceptancePhase::VALIDATING ||
      this->snapshot_.phase == IsolatedAcceptancePhase::ACTIVATING) {
    return this->reject_(IsolatedAcceptanceFailure::INVALID_STATE);
  }

  if (!this->evidence_sink_->write_redacted_json(this->evidence_json_()))
    return this->reject_(IsolatedAcceptanceFailure::EVIDENCE_EXPORT_FAILED);

  this->snapshot_.evidence_exported = true;
  this->snapshot_.last_command = IsolatedAcceptanceCommand::EXPORT_EVIDENCE;
  this->snapshot_.transition_count++;
  this->snapshot_.failure = IsolatedAcceptanceFailure::NONE;
  return true;
}

bool IsolatedAcceptancePackage::cleanup_test_state() {
  const bool phase_ok =
      this->snapshot_.phase == IsolatedAcceptancePhase::PREPARED ||
      this->snapshot_.phase == IsolatedAcceptancePhase::VERIFIED ||
      this->snapshot_.phase == IsolatedAcceptancePhase::ACTIVATED ||
      this->snapshot_.phase == IsolatedAcceptancePhase::FAILED;
  if (!phase_ok)
    return this->reject_(IsolatedAcceptanceFailure::INVALID_STATE);
  if (!this->snapshot_.evidence_exported)
    return this->reject_(
        IsolatedAcceptanceFailure::CLEANUP_REQUIRES_EVIDENCE);
  if (!this->authorization_.armed() ||
      this->authorization_.operation() !=
          IsolatedAcceptanceWriteOperation::CLEANUP_TEST_STATE) {
    return this->reject_(IsolatedAcceptanceFailure::AUTHORIZATION_NOT_ARMED);
  }
  if (!this->authorization_.consume(
          IsolatedAcceptanceWriteOperation::CLEANUP_TEST_STATE,
          this->snapshot_.active_generation,
          this->snapshot_.candidate_generation)) {
    return this->reject_(IsolatedAcceptanceFailure::AUTHORIZATION_INVALID);
  }

  this->snapshot_.write_authorization_armed = false;
  this->snapshot_.write_authorization_consumed = true;
  IsolatedAcceptanceDriverSnapshot driver_snapshot{};
  const bool cleaned =
      this->driver_->cleanup_test_state(&driver_snapshot);
  this->authorization_.acknowledge_consumption();
  this->refresh_driver_snapshot_(driver_snapshot);
  if (!cleaned || !driver_snapshot.cleanup_confirmed ||
      driver_snapshot.active_session_live ||
      driver_snapshot.candidate_session_live ||
      driver_snapshot.probe_session_live || driver_snapshot.reboot_required) {
    return this->fail_(IsolatedAcceptanceFailure::CLEANUP_FAILED,
                       driver_snapshot.reboot_required);
  }

  this->test_key_provider_->destroy();
  this->configuration_.clear();
  this->authorization_.clear();
  this->snapshot_.test_key_loaded = false;
  this->snapshot_.test_configuration_loaded = false;
  this->snapshot_.cleanup_confirmed = true;
  this->snapshot_.failure = IsolatedAcceptanceFailure::NONE;
  this->transition_(IsolatedAcceptancePhase::CLEANED,
                    IsolatedAcceptanceCommand::CLEANUP_TEST_STATE);
  return true;
}

void IsolatedAcceptancePackage::quiesce_for_reboot() {
  if (this->driver_ != nullptr)
    this->driver_->quiesce_for_reboot();
  if (this->test_key_provider_ != nullptr)
    this->test_key_provider_->destroy();
  this->configuration_.clear();
  this->authorization_.clear();
  this->snapshot_.phase = IsolatedAcceptancePhase::REBOOT_REQUIRED;
  this->snapshot_.last_command =
      IsolatedAcceptanceCommand::QUIESCE_FOR_REBOOT;
  this->snapshot_.failure = IsolatedAcceptanceFailure::REBOOT_REQUIRED;
  this->snapshot_.test_key_loaded = false;
  this->snapshot_.test_configuration_loaded = false;
  this->snapshot_.write_authorization_armed = false;
  this->snapshot_.reboot_required = true;
  this->snapshot_.transition_count++;
}

bool IsolatedAcceptancePackage::reject_(
    IsolatedAcceptanceFailure failure) {
  this->snapshot_.failure = failure;
  this->snapshot_.write_authorization_armed = this->authorization_.armed();
  this->snapshot_.write_authorization_consumed =
      this->snapshot_.write_authorization_consumed ||
      this->authorization_.consumed();
  this->snapshot_.transition_count++;
  return false;
}

bool IsolatedAcceptancePackage::fail_(IsolatedAcceptanceFailure failure,
                                      bool reboot_required) {
  this->snapshot_.failure = failure;
  this->snapshot_.write_authorization_armed = this->authorization_.armed();
  this->snapshot_.write_authorization_consumed =
      this->snapshot_.write_authorization_consumed ||
      this->authorization_.consumed();
  this->snapshot_.reboot_required = reboot_required;
  this->snapshot_.phase = reboot_required
                              ? IsolatedAcceptancePhase::REBOOT_REQUIRED
                              : IsolatedAcceptancePhase::FAILED;
  this->snapshot_.transition_count++;
  if (reboot_required) {
    if (this->driver_ != nullptr)
      this->driver_->quiesce_for_reboot();
    if (this->test_key_provider_ != nullptr)
      this->test_key_provider_->destroy();
    this->configuration_.clear();
    this->authorization_.clear();
    this->snapshot_.test_key_loaded = false;
    this->snapshot_.test_configuration_loaded = false;
    this->snapshot_.write_authorization_armed = false;
  }
  return false;
}

bool IsolatedAcceptancePackage::exact_generation_pair_(
    uint32_t active_generation, uint32_t candidate_generation) const {
  return active_generation == this->snapshot_.active_generation &&
         candidate_generation == this->snapshot_.candidate_generation;
}

bool IsolatedAcceptancePackage::evidence_metadata_available_() const {
  return valid_hex_(this->evidence_firmware_commit_sha_, 40) &&
         valid_hex_(this->evidence_configuration_digest_, 64) &&
         valid_hex_(this->evidence_broker_configuration_digest_, 64) &&
         valid_test_identifier(this->evidence_test_device_identifier_) &&
         valid_test_identifier(this->evidence_test_run_id_);
}

void IsolatedAcceptancePackage::transition_(
    IsolatedAcceptancePhase phase, IsolatedAcceptanceCommand command) {
  this->snapshot_.phase = phase;
  this->snapshot_.last_command = command;
  this->snapshot_.transition_count++;
}

void IsolatedAcceptancePackage::refresh_driver_snapshot_(
    const IsolatedAcceptanceDriverSnapshot &driver_snapshot) {
  this->snapshot_.driver = driver_snapshot;
  this->snapshot_.active_generation = driver_snapshot.active_generation;
  this->snapshot_.candidate_generation = driver_snapshot.candidate_generation;
  this->snapshot_.cleanup_confirmed = driver_snapshot.cleanup_confirmed;
  this->snapshot_.reboot_required = driver_snapshot.reboot_required;
  this->snapshot_.test_key_loaded =
      this->test_key_provider_ != nullptr && this->test_key_provider_->loaded();
  this->snapshot_.write_authorization_armed = this->authorization_.armed();
}

std::string IsolatedAcceptancePackage::evidence_json_() const {
  std::ostringstream output;
  output << '{'
         << "\"schema\":\"gh.h3.n2.stage2d7-isolated-evidence/1\","
         << "\"firmware_commit_sha\":\""
         << json_escape_(this->evidence_firmware_commit_sha_) << "\","
         << "\"test_configuration_digest\":\""
         << json_escape_(this->evidence_configuration_digest_) << "\","
         << "\"broker_configuration_digest\":\""
         << json_escape_(this->evidence_broker_configuration_digest_) << "\","
         << "\"test_device_identifier\":\""
         << json_escape_(this->evidence_test_device_identifier_) << "\","
         << "\"test_run_id\":\""
         << json_escape_(this->evidence_test_run_id_) << "\","
         << "\"phase\":\"" << phase_name(this->snapshot_.phase) << "\","
         << "\"last_command\":\""
         << command_name(this->snapshot_.last_command) << "\","
         << "\"final_status_code\":\""
         << failure_name(this->snapshot_.failure) << "\","
         << "\"active_generation\":" << this->snapshot_.active_generation
         << ','
         << "\"candidate_generation\":"
         << this->snapshot_.candidate_generation << ','
         << "\"persistence_status\":\""
         << json_escape_(this->snapshot_.driver.persistence_status) << "\","
         << "\"controller_phase\":\""
         << json_escape_(this->snapshot_.driver.controller_phase) << "\","
         << "\"sessions\":{"
         << "\"active\":"
         << bool_json(this->snapshot_.driver.active_session_live) << ','
         << "\"candidate\":"
         << bool_json(this->snapshot_.driver.candidate_session_live) << ','
         << "\"probe\":"
         << bool_json(this->snapshot_.driver.probe_session_live) << "},"
         << "\"marker_last_observed\":"
         << bool_json(this->snapshot_.driver.marker_last_observed) << ','
         << "\"failure_injection_point\":\""
         << json_escape_(this->snapshot_.driver.failure_injection_point)
         << "\","
         << "\"rollback_completed\":"
         << bool_json(this->snapshot_.driver.rollback_completed) << ','
         << "\"rollback_result\":\""
         << json_escape_(this->snapshot_.driver.rollback_result) << "\","
         << "\"persistent_write_count\":"
         << this->snapshot_.driver.persistent_write_count << ','
         << "\"authorization\":{"
         << "\"armed\":"
         << bool_json(this->snapshot_.write_authorization_armed) << ','
         << "\"consumed\":"
         << bool_json(this->snapshot_.write_authorization_consumed) << "},"
         << "\"cleanup_confirmed\":"
         << bool_json(this->snapshot_.cleanup_confirmed) << ','
         << "\"reboot_required\":"
         << bool_json(this->snapshot_.reboot_required) << ','
         << "\"transition_count\":" << this->snapshot_.transition_count
         << '}';
  return output.str();
}

std::string IsolatedAcceptancePackage::json_escape_(
    const std::string &value) {
  std::ostringstream output;
  for (unsigned char character : value) {
    switch (character) {
      case '\\':
        output << "\\\\";
        break;
      case '"':
        output << "\\\"";
        break;
      case '\n':
        output << "\\n";
        break;
      case '\r':
        output << "\\r";
        break;
      case '\t':
        output << "\\t";
        break;
      default:
        if (character < 0x20U) {
          static const char hex[] = "0123456789abcdef";
          output << "\\u00" << hex[(character >> 4U) & 0x0FU]
                 << hex[character & 0x0FU];
        } else {
          output << static_cast<char>(character);
        }
    }
  }
  return output.str();
}

bool IsolatedAcceptancePackage::valid_hex_(const std::string &value,
                                            size_t length) {
  return value.size() == length &&
         std::all_of(value.begin(), value.end(), [](unsigned char character) {
           return std::isdigit(character) != 0 ||
                  (character >= 'a' && character <= 'f');
         });
}

void IsolatedAcceptancePackage::secure_clear_(std::string *value) {
  wipe_string(value);
}

const char *IsolatedAcceptancePackage::phase_name(
    IsolatedAcceptancePhase phase) {
  switch (phase) {
    case IsolatedAcceptancePhase::COLD:
      return "cold";
    case IsolatedAcceptancePhase::READ_ONLY:
      return "read_only";
    case IsolatedAcceptancePhase::CONFIG_LOADED:
      return "config_loaded";
    case IsolatedAcceptancePhase::PREPARED:
      return "prepared";
    case IsolatedAcceptancePhase::VALIDATING:
      return "validating";
    case IsolatedAcceptancePhase::VERIFIED:
      return "verified";
    case IsolatedAcceptancePhase::ACTIVATING:
      return "activating";
    case IsolatedAcceptancePhase::ACTIVATED:
      return "activated";
    case IsolatedAcceptancePhase::FAILED:
      return "failed";
    case IsolatedAcceptancePhase::REBOOT_REQUIRED:
      return "reboot_required";
    case IsolatedAcceptancePhase::CLEANED:
      return "cleaned";
  }
  return "unknown";
}

const char *IsolatedAcceptancePackage::command_name(
    IsolatedAcceptanceCommand command) {
  switch (command) {
    case IsolatedAcceptanceCommand::NONE:
      return "none";
    case IsolatedAcceptanceCommand::INSPECT_READ_ONLY:
      return "inspect_read_only";
    case IsolatedAcceptanceCommand::LOAD_TEST_CONFIGURATION:
      return "load_test_configuration";
    case IsolatedAcceptanceCommand::GRANT_WRITE_AUTHORIZATION:
      return "grant_write_authorization";
    case IsolatedAcceptanceCommand::PREPARE_CANDIDATE:
      return "prepare_candidate";
    case IsolatedAcceptanceCommand::BEGIN_VALIDATION:
      return "begin_validation";
    case IsolatedAcceptanceCommand::POLL_VALIDATION:
      return "poll_validation";
    case IsolatedAcceptanceCommand::ACTIVATE:
      return "activate";
    case IsolatedAcceptanceCommand::EXPORT_EVIDENCE:
      return "export_evidence";
    case IsolatedAcceptanceCommand::CLEANUP_TEST_STATE:
      return "cleanup_test_state";
    case IsolatedAcceptanceCommand::QUIESCE_FOR_REBOOT:
      return "quiesce_for_reboot";
  }
  return "unknown";
}

const char *IsolatedAcceptancePackage::failure_name(
    IsolatedAcceptanceFailure failure) {
  switch (failure) {
    case IsolatedAcceptanceFailure::NONE:
      return "none";
    case IsolatedAcceptanceFailure::INVALID_CONFIGURATION:
      return "invalid_configuration";
    case IsolatedAcceptanceFailure::INVALID_STATE:
      return "invalid_state";
    case IsolatedAcceptanceFailure::READ_ONLY_INSPECTION_FAILED:
      return "read_only_inspection_failed";
    case IsolatedAcceptanceFailure::TEST_KEY_REQUIRED:
      return "test_key_required";
    case IsolatedAcceptanceFailure::TEST_CONFIGURATION_INVALID:
      return "test_configuration_invalid";
    case IsolatedAcceptanceFailure::GENERATION_MISMATCH:
      return "generation_mismatch";
    case IsolatedAcceptanceFailure::AUTHORIZATION_INVALID:
      return "authorization_invalid";
    case IsolatedAcceptanceFailure::AUTHORIZATION_NOT_ARMED:
      return "authorization_not_armed";
    case IsolatedAcceptanceFailure::AUTHORIZATION_NOT_CONSUMED:
      return "authorization_not_consumed";
    case IsolatedAcceptanceFailure::PREPARE_FAILED:
      return "prepare_failed";
    case IsolatedAcceptanceFailure::VALIDATION_START_FAILED:
      return "validation_start_failed";
    case IsolatedAcceptanceFailure::VALIDATION_FAILED:
      return "validation_failed";
    case IsolatedAcceptanceFailure::ACTIVATION_FAILED:
      return "activation_failed";
    case IsolatedAcceptanceFailure::EVIDENCE_EXPORT_FAILED:
      return "evidence_export_failed";
    case IsolatedAcceptanceFailure::CLEANUP_REQUIRES_EVIDENCE:
      return "cleanup_requires_evidence";
    case IsolatedAcceptanceFailure::CLEANUP_FAILED:
      return "cleanup_failed";
    case IsolatedAcceptanceFailure::REBOOT_REQUIRED:
      return "reboot_required";
  }
  return "unknown";
}

const char *IsolatedAcceptancePackage::write_operation_name(
    IsolatedAcceptanceWriteOperation operation) {
  switch (operation) {
    case IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE:
      return "prepare_candidate";
    case IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE:
      return "activate_profile";
    case IsolatedAcceptanceWriteOperation::CLEANUP_TEST_STATE:
      return "cleanup_test_state";
  }
  return "unknown";
}

}  // namespace esphome::greenhouse_pairing_client
