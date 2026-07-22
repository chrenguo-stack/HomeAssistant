#include "isolated_device_esp32_ports.h"

#ifdef USE_ESP32

#include <algorithm>
#include <utility>

#include "esp_err.h"
#include "nvs.h"
#include "nvs_flash.h"

namespace esphome::greenhouse_pairing_client {
namespace {

void clone_bundle(const RamCredentialBundle &source,
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

void wipe_string(std::string *value) {
  if (value == nullptr)
    return;
  std::fill(value->begin(), value->end(), '\0');
  value->clear();
  value->shrink_to_fit();
}

}  // namespace

AuditedEspIdfNvsBackend::AuditedEspIdfNvsBackend(
    const std::string &partition_label, const std::string &namespace_name)
    : backend_(std::make_unique<EspIdfNvsPersistenceBackend>(partition_label,
                                                             namespace_name)) {}

bool AuditedEspIdfNvsBackend::open(PersistenceOpenMode mode) {
  return this->backend_ != nullptr && this->backend_->open(mode);
}

bool AuditedEspIdfNvsBackend::opened() const {
  return this->backend_ != nullptr && this->backend_->opened();
}

bool AuditedEspIdfNvsBackend::writable() const {
  return this->backend_ != nullptr && this->backend_->writable();
}

bool AuditedEspIdfNvsBackend::namespace_missing() const {
  return this->backend_ != nullptr && this->backend_->namespace_missing();
}

PersistenceReadResult AuditedEspIdfNvsBackend::read_blob(
    const char *key, std::vector<uint8_t> *value) {
  return this->backend_ == nullptr
             ? PersistenceReadResult::ERROR
             : this->backend_->read_blob(key, value);
}

bool AuditedEspIdfNvsBackend::write_blob(const char *key,
                                         const uint8_t *value,
                                         size_t length) {
  if (this->backend_ == nullptr || key == nullptr ||
      !this->backend_->write_blob(key, value, length)) {
    return false;
  }
  this->pending_key_ = key;
  return true;
}

bool AuditedEspIdfNvsBackend::erase_key(const char *key) {
  if (this->backend_ == nullptr || key == nullptr ||
      !this->backend_->erase_key(key)) {
    return false;
  }
  this->pending_key_ = std::string("erase:") + key;
  return true;
}

bool AuditedEspIdfNvsBackend::commit() {
  if (this->backend_ == nullptr || !this->backend_->commit())
    return false;
  this->successful_commit_count_++;
  this->committed_keys_.push_back(this->pending_key_.empty()
                                      ? "unknown"
                                      : this->pending_key_);
  this->pending_key_.clear();
  return true;
}

bool EspIdfIsolatedPersistencePort::configure(
    const IsolatedDeviceDriverConfig &config,
    VolatileTestPersistenceKeyProvider *test_key_provider) {
  this->quiesce();
  this->config_ = config;
  this->test_key_provider_ = test_key_provider;
  this->persistent_write_count_ = 0;
  this->marker_committed_ = false;
  this->marker_last_observed_ = false;
  this->configured_ = config.valid() && test_key_provider != nullptr;
  return this->configured_;
}

bool EspIdfIsolatedPersistencePort::inspect_read_only(
    IsolatedDevicePersistenceSnapshot *snapshot,
    RamCredentialBundle *active_credentials,
    RamCredentialBundle *candidate_credentials) {
  if (!this->configured_ || snapshot == nullptr)
    return false;
  *snapshot = {};
  if (active_credentials != nullptr)
    active_credentials->clear();
  if (candidate_credentials != nullptr)
    candidate_credentials->clear();

  this->close_store_();
  this->backend_ = std::make_unique<AuditedEspIdfNvsBackend>(
      this->config_.partition_label, this->config_.namespace_name);
  if (!this->backend_->open(PersistenceOpenMode::READ_ONLY)) {
    if (this->backend_->namespace_missing()) {
      snapshot->read_only_opened = true;
      snapshot->namespace_missing = true;
      snapshot->recovery_valid = true;
      snapshot->recovery_status = "empty";
      snapshot->persistent_write_count = this->persistent_write_count_;
      this->close_store_();
      return true;
    }
    snapshot->persistent_write_count = this->persistent_write_count_;
    this->close_store_();
    return false;
  }
  if (this->test_key_provider_ == nullptr ||
      !this->test_key_provider_->loaded()) {
    snapshot->read_only_opened = true;
    snapshot->persistent_write_count = this->persistent_write_count_;
    this->close_store_();
    return false;
  }

  this->crypto_ = std::make_unique<PairingPersistenceCrypto>(
      this->test_key_provider_);
  this->store_ = std::make_unique<PairingPersistentStore>(this->backend_.get(),
                                                          this->crypto_.get());
  const bool recovered = this->recover_open_store_(
      snapshot, active_credentials, candidate_credentials);
  this->close_store_();
  return recovered;
}

bool EspIdfIsolatedPersistencePort::prepare_candidate(
    const RamCredentialBundle &candidate,
    IsolatedDevicePersistenceSnapshot *snapshot) {
  if (!this->configured_ || snapshot == nullptr || !candidate.valid() ||
      this->test_key_provider_ == nullptr ||
      !this->test_key_provider_->loaded() ||
      !this->open_store_(PersistenceOpenMode::READ_WRITE)) {
    return false;
  }

  const bool prepared = this->store_->prepare(candidate);
  this->absorb_audit_();
  this->close_store_();
  if (!prepared) {
    snapshot->persistent_write_count = this->persistent_write_count_;
    return false;
  }
  return this->reopen_and_recover_(snapshot);
}

bool EspIdfIsolatedPersistencePort::commit_prepared(
    IsolatedDevicePersistenceSnapshot *snapshot,
    RamCredentialBundle *new_active_credentials) {
  if (!this->configured_ || snapshot == nullptr ||
      new_active_credentials == nullptr ||
      this->test_key_provider_ == nullptr ||
      !this->test_key_provider_->loaded() ||
      !this->open_store_(PersistenceOpenMode::READ_WRITE)) {
    return false;
  }

  this->marker_committed_ = false;
  this->marker_last_observed_ = false;
  const bool committed = this->store_->commit_prepared();
  const std::vector<std::string> audit = this->backend_->committed_keys();
  this->marker_committed_ =
      std::find(audit.begin(), audit.end(), "active") != audit.end();
  this->marker_last_observed_ = marker_last_(audit);
  this->absorb_audit_();
  this->close_store_();

  IsolatedDevicePersistenceSnapshot recovered{};
  RamCredentialBundle active;
  const bool recovery_ok = this->reopen_and_recover_(&recovered, &active);
  recovered.marker_committed = this->marker_committed_;
  recovered.marker_last_observed = this->marker_last_observed_;
  recovered.persistent_write_count = this->persistent_write_count_;
  *snapshot = recovered;
  if (!committed || !recovery_ok) {
    active.clear();
    return false;
  }
  clone_bundle(active, new_active_credentials);
  active.clear();
  return snapshot->recovery_status == "active" &&
         snapshot->marker_last_observed;
}

bool EspIdfIsolatedPersistencePort::cleanup_test_namespace(
    IsolatedDevicePersistenceSnapshot *snapshot) {
  if (!this->configured_ || snapshot == nullptr ||
      !this->erase_namespace_()) {
    return false;
  }
  this->persistent_write_count_++;
  this->marker_committed_ = false;
  this->marker_last_observed_ = false;

  IsolatedDevicePersistenceSnapshot recovered{};
  const bool recovery_ok = this->reopen_and_recover_(&recovered);
  recovered.cleanup_confirmed =
      recovery_ok && recovered.recovery_status == "empty" &&
      recovered.active_generation == 0 && recovered.candidate_generation == 0;
  recovered.persistent_write_count = this->persistent_write_count_;
  *snapshot = recovered;
  return recovered.cleanup_confirmed;
}

void EspIdfIsolatedPersistencePort::quiesce() { this->close_store_(); }

bool EspIdfIsolatedPersistencePort::open_store_(PersistenceOpenMode mode,
                                                bool *namespace_missing) {
  if (namespace_missing != nullptr)
    *namespace_missing = false;
  this->close_store_();
  if (!this->configured_ || this->test_key_provider_ == nullptr ||
      !this->test_key_provider_->loaded()) {
    return false;
  }
  this->backend_ = std::make_unique<AuditedEspIdfNvsBackend>(
      this->config_.partition_label, this->config_.namespace_name);
  if (!this->backend_->open(mode)) {
    if (namespace_missing != nullptr)
      *namespace_missing = this->backend_->namespace_missing();
    this->close_store_();
    return false;
  }
  this->crypto_ = std::make_unique<PairingPersistenceCrypto>(
      this->test_key_provider_);
  this->store_ = std::make_unique<PairingPersistentStore>(this->backend_.get(),
                                                          this->crypto_.get());
  return true;
}

bool EspIdfIsolatedPersistencePort::recover_open_store_(
    IsolatedDevicePersistenceSnapshot *snapshot,
    RamCredentialBundle *active_credentials,
    RamCredentialBundle *candidate_credentials) {
  if (snapshot == nullptr || this->store_ == nullptr || this->backend_ == nullptr)
    return false;
  PersistentRecoverySnapshot recovery{};
  const bool recovered = this->store_->recover(
      &recovery, active_credentials, candidate_credentials);
  snapshot->read_only_opened = this->backend_->opened() &&
                               !this->backend_->writable();
  snapshot->namespace_missing = false;
  snapshot->recovery_valid = recovered;
  snapshot->recovery_status = PairingPersistentStore::status_name(recovery.status);
  snapshot->active_generation = recovery.active_generation;
  snapshot->candidate_generation = recovery.candidate_generation;
  snapshot->marker_committed = this->marker_committed_;
  snapshot->marker_last_observed = this->marker_last_observed_;
  snapshot->persistent_write_count = this->persistent_write_count_;
  snapshot->reboot_required =
      !recovered || recovery.status == PersistentRecoveryStatus::STORAGE_ERROR ||
      recovery.status == PersistentRecoveryStatus::CONFLICT ||
      recovery.status == PersistentRecoveryStatus::INVALID_RECORD;
  return recovered;
}

bool EspIdfIsolatedPersistencePort::reopen_and_recover_(
    IsolatedDevicePersistenceSnapshot *snapshot,
    RamCredentialBundle *active_credentials,
    RamCredentialBundle *candidate_credentials) {
  if (snapshot == nullptr)
    return false;
  if (!this->open_store_(PersistenceOpenMode::READ_ONLY)) {
    bool missing = false;
    this->close_store_();
    this->backend_ = std::make_unique<AuditedEspIdfNvsBackend>(
        this->config_.partition_label, this->config_.namespace_name);
    if (!this->backend_->open(PersistenceOpenMode::READ_ONLY))
      missing = this->backend_->namespace_missing();
    this->close_store_();
    if (missing) {
      *snapshot = {};
      snapshot->read_only_opened = true;
      snapshot->namespace_missing = true;
      snapshot->recovery_valid = true;
      snapshot->recovery_status = "empty";
      snapshot->persistent_write_count = this->persistent_write_count_;
      return true;
    }
    return false;
  }
  const bool recovered = this->recover_open_store_(
      snapshot, active_credentials, candidate_credentials);
  this->close_store_();
  return recovered;
}

bool EspIdfIsolatedPersistencePort::erase_namespace_() {
  this->close_store_();
  nvs_handle_t handle = 0;
  const esp_err_t opened = nvs_open_from_partition(
      this->config_.partition_label.c_str(),
      this->config_.namespace_name.c_str(), NVS_READWRITE, &handle);
  if (opened == ESP_ERR_NVS_NOT_FOUND)
    return true;
  if (opened != ESP_OK)
    return false;
  const esp_err_t erased = nvs_erase_all(handle);
  const esp_err_t committed = erased == ESP_OK ? nvs_commit(handle) : erased;
  nvs_close(handle);
  return erased == ESP_OK && committed == ESP_OK;
}

void EspIdfIsolatedPersistencePort::close_store_() {
  this->store_.reset();
  this->crypto_.reset();
  this->backend_.reset();
}

void EspIdfIsolatedPersistencePort::absorb_audit_() {
  if (this->backend_ == nullptr)
    return;
  this->persistent_write_count_ += this->backend_->successful_commit_count();
}

bool EspIdfIsolatedPersistencePort::marker_last_(
    const std::vector<std::string> &committed_keys) {
  if (committed_keys.size() < 2 || committed_keys.back() != "active")
    return false;
  const std::string &record = committed_keys[committed_keys.size() - 2];
  return record == "slot_a" || record == "slot_b";
}

bool EspIdfIsolatedMqttPort::configure(
    const RamCredentialBundle *active_credentials,
    const IsolatedCandidateProfile &candidate,
    uint32_t validation_timeout_ms, uint32_t activation_timeout_ms) {
  this->quiesce();
  if (!candidate.valid() || validation_timeout_ms < 1000 ||
      validation_timeout_ms > 60000 || activation_timeout_ms < 1000 ||
      activation_timeout_ms > 60000) {
    return false;
  }
  if (active_credentials != nullptr) {
    if (!active_credentials->valid())
      return false;
    clone_bundle(*active_credentials, &this->active_credentials_);
  }
  this->candidate_ = candidate;
  this->candidate_profile_ = profile_from_candidate_(candidate);
  if (!this->candidate_profile_.valid() || !this->build_exchange_(&this->exchange_)) {
    this->clear_sensitive_material_();
    return false;
  }
  this->active_session_ = std::make_unique<EspIdfProductionMqttSession>();
  this->probe_session_ = std::make_unique<EspIdfProductionMqttSession>();
  this->candidate_session_ = std::make_unique<EspIdfProductionMqttSession>();
  this->validation_timeout_ms_ = validation_timeout_ms;
  this->activation_timeout_ms_ = activation_timeout_ms;
  this->validation_elapsed_ms_ = 0;
  this->configured_ = true;
  this->failure_point_ = "none";
  this->rollback_result_ = "not_applicable";
  return true;
}

bool EspIdfIsolatedMqttPort::begin_validation(
    IsolatedDeviceMqttSnapshot *snapshot) {
  if (!this->configured_ || snapshot == nullptr || this->validation_started_ ||
      !this->start_active_if_present_() || this->probe_session_ == nullptr) {
    this->failure_point_ = "validation_start";
    this->refresh_snapshot_(snapshot);
    return false;
  }
  CandidateMqttProfile profile = profile_from_candidate_(this->candidate_);
  CandidateMqttProbeExchange exchange = this->exchange_;
  if (!this->probe_session_->configure(std::move(profile), std::move(exchange),
                                       true) ||
      !this->probe_session_->start()) {
    this->probe_session_->destroy();
    this->failure_point_ = "validation_probe_start";
    this->refresh_snapshot_(snapshot);
    return false;
  }
  this->validation_started_ = true;
  this->refresh_snapshot_(snapshot);
  return true;
}

bool EspIdfIsolatedMqttPort::poll_validation(
    uint32_t elapsed_ms, IsolatedDeviceMqttSnapshot *snapshot) {
  if (!this->configured_ || !this->validation_started_ ||
      this->validation_complete_ || elapsed_ms == 0 || snapshot == nullptr ||
      this->probe_session_ == nullptr) {
    return false;
  }
  this->validation_elapsed_ms_ += elapsed_ms;
  ProductionMqttSessionObservation observation{};
  if (!this->probe_session_->poll(&observation)) {
    this->failure_point_ = "validation_poll";
    this->refresh_snapshot_(snapshot);
    return false;
  }
  if (observation.terminal_failure) {
    this->validation_complete_ = true;
    this->validation_success_ = false;
    this->failure_point_ = "validation_transport";
    this->probe_session_->destroy();
    this->refresh_snapshot_(snapshot);
    return true;
  }
  if (observation.round_trip) {
    this->validation_complete_ = true;
    this->validation_success_ = true;
    this->probe_session_->destroy();
  } else if (this->validation_elapsed_ms_ >= this->validation_timeout_ms_) {
    this->validation_complete_ = true;
    this->validation_success_ = false;
    this->failure_point_ = "validation_timeout";
    this->probe_session_->destroy();
  }
  this->refresh_snapshot_(snapshot);
  return true;
}

bool EspIdfIsolatedMqttPort::begin_activation(
    IsolatedDeviceMqttSnapshot *snapshot) {
  if (!this->configured_ || !this->validation_complete_ ||
      !this->validation_success_ || this->activation_started_ ||
      this->candidate_session_ == nullptr || snapshot == nullptr) {
    return false;
  }
  CandidateMqttProfile profile = profile_from_candidate_(this->candidate_);
  CandidateMqttProbeExchange exchange = this->exchange_;
  if (!this->candidate_session_->configure(std::move(profile),
                                           std::move(exchange), true) ||
      !this->candidate_session_->start() ||
      !this->candidate_session_->wait_round_trip(
          this->activation_timeout_ms_)) {
    this->candidate_session_->destroy();
    this->failure_point_ = "activation_candidate_round_trip";
    this->refresh_snapshot_(snapshot);
    return false;
  }
  this->activation_started_ = true;
  this->refresh_snapshot_(snapshot);
  return true;
}

bool EspIdfIsolatedMqttPort::rollback_activation(
    IsolatedDeviceMqttSnapshot *snapshot) {
  if (this->candidate_session_ != nullptr)
    this->candidate_session_->destroy();
  this->activation_started_ = false;
  this->rollback_completed_ =
      !this->active_credentials_.valid() ||
      (this->active_session_ != nullptr && this->active_session_->live());
  this->rollback_result_ = this->rollback_completed_
                               ? "old_active_retained"
                               : "old_active_unavailable";
  this->refresh_snapshot_(snapshot);
  return this->rollback_completed_;
}

bool EspIdfIsolatedMqttPort::promote_candidate(
    IsolatedDeviceMqttSnapshot *snapshot) {
  if (!this->activation_started_ || this->candidate_session_ == nullptr ||
      !this->candidate_session_->live() || snapshot == nullptr) {
    return false;
  }
  if (this->active_session_ != nullptr && this->active_session_->live() &&
      !this->active_session_->stop()) {
    this->reboot_required_ = true;
    this->failure_point_ = "old_active_stop_after_marker";
    this->refresh_snapshot_(snapshot);
    return false;
  }
  if (this->active_session_ != nullptr)
    this->active_session_->destroy();
  std::swap(this->active_session_, this->candidate_session_);
  this->promotion_complete_ = this->active_session_ != nullptr &&
                              this->active_session_->live() &&
                              (this->candidate_session_ == nullptr ||
                               !this->candidate_session_->live());
  this->activation_started_ = false;
  this->refresh_snapshot_(snapshot);
  return this->promotion_complete_;
}

void EspIdfIsolatedMqttPort::quiesce() {
  if (this->active_session_ != nullptr)
    this->active_session_->destroy();
  if (this->probe_session_ != nullptr)
    this->probe_session_->destroy();
  if (this->candidate_session_ != nullptr)
    this->candidate_session_->destroy();
  this->active_session_.reset();
  this->probe_session_.reset();
  this->candidate_session_.reset();
  this->clear_sensitive_material_();
  this->validation_elapsed_ms_ = 0;
  this->configured_ = false;
  this->validation_started_ = false;
  this->validation_complete_ = false;
  this->validation_success_ = false;
  this->activation_started_ = false;
  this->promotion_complete_ = false;
  this->rollback_completed_ = false;
  this->reboot_required_ = false;
  this->failure_point_ = "none";
  this->rollback_result_ = "not_applicable";
}

CandidateMqttProfile EspIdfIsolatedMqttPort::profile_from_bundle_(
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

CandidateMqttProfile EspIdfIsolatedMqttPort::profile_from_candidate_(
    const IsolatedCandidateProfile &candidate) {
  CandidateMqttProfile profile;
  profile.system_id = candidate.system_id;
  profile.node_id = candidate.node_id;
  profile.broker_host = candidate.broker_host;
  profile.broker_port = candidate.broker_port;
  profile.broker_tls_server_name = candidate.broker_tls_server_name;
  profile.ca_pem = candidate.ca_pem;
  profile.mqtt_username = candidate.mqtt_username;
  profile.mqtt_client_id = candidate.mqtt_client_id;
  profile.credential_generation = candidate.credential_generation;
  profile.mqtt_password = candidate.mqtt_password;
  return profile;
}

bool EspIdfIsolatedMqttPort::build_exchange_(
    CandidateMqttProbeExchange *exchange) {
  if (exchange == nullptr || !this->candidate_.valid())
    return false;
  std::string nonce;
  if (!this->nonce_source_.next_nonce_hex(&nonce))
    return false;
  exchange->clear();
  exchange->publish_topic = this->candidate_.test_topic_root + "/probe/request";
  exchange->subscribe_topic =
      this->candidate_.test_topic_root + "/probe/confirm";
  exchange->request_payload =
      "{\"credential_generation\":" +
      std::to_string(this->candidate_.credential_generation) +
      ",\"node_id\":\"" + this->candidate_.node_id +
      "\",\"nonce\":\"" + nonce +
      "\",\"schema\":\"gh.test.telemetry-probe/1\"}";
  exchange->expected_payload =
      "{\"credential_generation\":" +
      std::to_string(this->candidate_.credential_generation) +
      ",\"node_id\":\"" + this->candidate_.node_id +
      "\",\"nonce\":\"" + nonce +
      "\",\"schema\":\"gh.test.telemetry-probe-confirm/1\",\"status\":\"accepted\"}";
  wipe_string(&nonce);
  return exchange->valid() &&
         exchange->publish_topic.rfind("gh-test/", 0) == 0 &&
         exchange->subscribe_topic.rfind("gh-test/", 0) == 0;
}

bool EspIdfIsolatedMqttPort::start_active_if_present_() {
  if (!this->active_credentials_.valid())
    return true;
  if (this->active_session_ == nullptr || this->active_session_->live())
    return this->active_session_ != nullptr && this->active_session_->live();
  CandidateMqttProfile profile =
      profile_from_bundle_(this->active_credentials_);
  CandidateMqttProbeExchange empty_exchange;
  return this->active_session_->configure(std::move(profile),
                                          std::move(empty_exchange), false) &&
         this->active_session_->start() &&
         this->active_session_->wait_connected(this->validation_timeout_ms_);
}

void EspIdfIsolatedMqttPort::refresh_snapshot_(
    IsolatedDeviceMqttSnapshot *snapshot) const {
  if (snapshot == nullptr)
    return;
  *snapshot = {};
  snapshot->configured = this->configured_;
  snapshot->validation_complete = this->validation_complete_;
  snapshot->validation_success = this->validation_success_;
  snapshot->active_session_live =
      this->active_session_ != nullptr && this->active_session_->live();
  snapshot->candidate_session_live =
      this->candidate_session_ != nullptr && this->candidate_session_->live();
  snapshot->probe_session_live =
      this->probe_session_ != nullptr && this->probe_session_->live();
  snapshot->rollback_completed = this->rollback_completed_;
  snapshot->promotion_complete = this->promotion_complete_;
  snapshot->reboot_required = this->reboot_required_;
  snapshot->failure_point = this->failure_point_;
  snapshot->rollback_result = this->rollback_result_;
}

void EspIdfIsolatedMqttPort::clear_sensitive_material_() {
  this->active_credentials_.clear();
  this->candidate_.clear();
  this->candidate_profile_.clear();
  this->exchange_.clear();
}

}  // namespace esphome::greenhouse_pairing_client

#endif  // USE_ESP32
