#include "stage2d9_g3_prepare_executor_v69.h"

#include <algorithm>
#include <cerrno>
#include <cinttypes>
#include <sstream>
#include <utility>
#include <vector>

#include <unistd.h>

#include "esp_partition.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mbedtls/sha256.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "esphome/core/log.h"

#include "../greenhouse_pairing_client/secure_pairing_channel.h"

namespace esphome::greenhouse_pairing_client {
namespace {

static const char *const TAG = "gh_stage2d9_v69";
constexpr uint32_t TEST_PARTITION_ADDRESS = 0x400000;
constexpr uint32_t TEST_PARTITION_SIZE = 0x10000;
constexpr size_t MAX_COMMAND_LENGTH = 384;
constexpr const char *PREPARE_SCHEMA = "GH2D9_PREPARE_V2";
constexpr const char *VERIFY_SCHEMA = "GH2D9_VERIFY_V2";
constexpr const char *LOCAL_PLACEHOLDER_HOST = "stage2d9.local";

void secure_clear(std::string *value) {
  if (value == nullptr)
    return;
  std::fill(value->begin(), value->end(), '\0');
  value->clear();
  value->shrink_to_fit();
}

}  // namespace

void Stage2D9CommandEnvelopeV69::clear() {
  this->verify_only = false;
  secure_clear(&this->run_suffix);
  std::fill(this->unlock_token.begin(), this->unlock_token.end(), 0);
  std::fill(this->persistence_key.begin(), this->persistence_key.end(), 0);
  secure_clear(&this->authorization_digest);
  secure_clear(&this->candidate_digest);
}

float Stage2D9G3PrepareExecutorV69::get_setup_priority() const {
  return setup_priority::DATA;
}

bool Stage2D9G3PrepareExecutorV69::all_zero_hex_(
    const std::string &value) {
  return !value.empty() &&
         std::all_of(value.begin(), value.end(),
                     [](char character) { return character == '0'; });
}

bool Stage2D9G3PrepareExecutorV69::valid_lower_hex_(
    const std::string &value, size_t length) {
  return value.size() == length &&
         std::all_of(value.begin(), value.end(), [](unsigned char character) {
           return (character >= '0' && character <= '9') ||
                  (character >= 'a' && character <= 'f');
         });
}

bool Stage2D9G3PrepareExecutorV69::valid_suffix_(
    const std::string &value) {
  return value.size() >= 8 && value.size() <= 24 &&
         std::all_of(value.begin(), value.end(), [](unsigned char character) {
           return (character >= 'a' && character <= 'z') ||
                  (character >= '0' && character <= '9');
         });
}

bool Stage2D9G3PrepareExecutorV69::decode_hex_32_(
    const std::string &value, std::array<uint8_t, 32> *output) {
  if (output == nullptr || !valid_lower_hex_(value, 64))
    return false;
  output->fill(0);
  for (size_t index = 0; index < output->size(); index++) {
    const auto decode = [](char character) -> uint8_t {
      return character <= '9' ? static_cast<uint8_t>(character - '0')
                              : static_cast<uint8_t>(character - 'a' + 10);
    };
    (*output)[index] = static_cast<uint8_t>(
        (decode(value[index * 2]) << 4U) | decode(value[index * 2 + 1]));
  }
  return true;
}

bool Stage2D9G3PrepareExecutorV69::sha256_(
    const uint8_t *data, size_t length, std::array<uint8_t, 32> *output) {
  if (data == nullptr || output == nullptr)
    return false;
  output->fill(0);
  return mbedtls_sha256_ret(data, length, output->data(), 0) == 0;
}

std::string Stage2D9G3PrepareExecutorV69::hex_(
    const std::array<uint8_t, 32> &value) {
  static constexpr char HEX[] = "0123456789abcdef";
  std::string result;
  result.resize(value.size() * 2);
  for (size_t index = 0; index < value.size(); index++) {
    result[index * 2] = HEX[(value[index] >> 4U) & 0x0FU];
    result[index * 2 + 1] = HEX[value[index] & 0x0FU];
  }
  return result;
}

bool Stage2D9G3PrepareExecutorV69::constant_equal_(
    const std::string &left, const std::string &right) {
  if (left.size() != right.size())
    return false;
  uint8_t difference = 0;
  for (size_t index = 0; index < left.size(); index++)
    difference |= static_cast<uint8_t>(left[index] ^ right[index]);
  return difference == 0;
}

bool Stage2D9G3PrepareExecutorV69::verify_partition_() {
  const esp_partition_t *partition = esp_partition_find_first(
      ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS,
      this->partition_label_.c_str());
  this->partition_verified_ =
      partition != nullptr && !partition->readonly &&
      partition->address == TEST_PARTITION_ADDRESS &&
      partition->size == TEST_PARTITION_SIZE;
  return this->partition_verified_;
}

bool Stage2D9G3PrepareExecutorV69::initialize_partition_() {
  if (!this->partition_verified_)
    return false;
  const esp_err_t status =
      nvs_flash_init_partition(this->partition_label_.c_str());
  this->partition_initialized_ = status == ESP_OK;
  if (!this->partition_initialized_)
    ESP_LOGE(TAG, "stage2d9_v69_partition_init=%s", esp_err_to_name(status));
  return this->partition_initialized_;
}

bool Stage2D9G3PrepareExecutorV69::namespace_exists_(bool *exists) {
  if (!this->partition_initialized_ || exists == nullptr)
    return false;
  *exists = false;
  nvs_handle_t handle{};
  const esp_err_t status = nvs_open_from_partition(
      this->partition_label_.c_str(), this->namespace_name_.c_str(),
      NVS_READONLY, &handle);
  if (status == ESP_ERR_NVS_NOT_FOUND)
    return true;
  if (status != ESP_OK)
    return false;
  nvs_close(handle);
  *exists = true;
  return true;
}

bool Stage2D9G3PrepareExecutorV69::configure_runtime_() {
  IsolatedDeviceDriverConfig config;
  config.partition_label = this->partition_label_;
  config.namespace_name = this->namespace_name_;
  config.validation_timeout_ms = 15000;
  config.activation_timeout_ms = 15000;

  if (!this->driver_.configure(config, &this->persistence_, &this->mqtt_,
                               &this->test_key_provider_) ||
      !this->package_.configure(&this->driver_, &this->test_key_provider_,
                                &this->evidence_sink_) ||
      !this->authorization_binder_.configure(&this->package_, &this->driver_)) {
    return false;
  }
  this->configured_ = true;
  return true;
}

bool Stage2D9G3PrepareExecutorV69::inspect_empty_() {
  if (!this->configured_ || !this->package_.inspect_read_only())
    return false;
  const auto &snapshot = this->package_.snapshot();
  return snapshot.phase == IsolatedAcceptancePhase::READ_ONLY &&
         snapshot.failure == IsolatedAcceptanceFailure::NONE &&
         snapshot.driver.read_only_observed &&
         snapshot.driver.persistence_status == "empty" &&
         snapshot.active_generation == 0 && snapshot.candidate_generation == 0 &&
         snapshot.driver.persistent_write_count == 0 &&
         !snapshot.driver.active_session_live &&
         !snapshot.driver.candidate_session_live &&
         !snapshot.driver.probe_session_live &&
         !snapshot.write_authorization_armed &&
         !snapshot.write_authorization_consumed && !snapshot.reboot_required &&
         !this->test_key_provider_.loaded() && !this->mqtt_.operation_attempted();
}

bool Stage2D9G3PrepareExecutorV69::parse_command_(
    const std::string &line, Stage2D9CommandEnvelopeV69 *envelope) const {
  if (envelope == nullptr || line.empty() || line.size() > MAX_COMMAND_LENGTH)
    return false;
  std::istringstream stream(line);
  std::vector<std::string> fields;
  std::string field;
  while (stream >> field)
    fields.push_back(std::move(field));
  if (fields.size() != 6)
    return false;

  const char *expected_schema =
      this->awaiting_ == AwaitingCommand::PREPARE ? PREPARE_SCHEMA
                                                  : VERIFY_SCHEMA;
  if (fields[0] != expected_schema || !valid_suffix_(fields[1]) ||
      !valid_lower_hex_(fields[2], 64) ||
      !valid_lower_hex_(fields[3], 64) ||
      !valid_lower_hex_(fields[4], 64) ||
      !valid_lower_hex_(fields[5], 64) || all_zero_hex_(fields[2]) ||
      all_zero_hex_(fields[3]) || all_zero_hex_(fields[4])) {
    return false;
  }

  std::array<uint8_t, 32> unlock{};
  std::array<uint8_t, 32> unlock_hash{};
  if (!decode_hex_32_(fields[2], &unlock) ||
      !sha256_(unlock.data(), unlock.size(), &unlock_hash) ||
      !constant_equal_(hex_(unlock_hash), this->unlock_digest_)) {
    unlock.fill(0);
    unlock_hash.fill(0);
    return false;
  }
  unlock_hash.fill(0);

  Stage2D9CommandEnvelopeV69 parsed;
  parsed.verify_only = fields[0] == VERIFY_SCHEMA;
  parsed.run_suffix = fields[1];
  parsed.unlock_token = unlock;
  if (!decode_hex_32_(fields[3], &parsed.persistence_key)) {
    parsed.clear();
    return false;
  }
  parsed.authorization_digest = fields[4];
  parsed.candidate_digest = fields[5];

  std::string expected_digest;
  if (!this->expected_candidate_digest_(parsed, &expected_digest) ||
      !constant_equal_(expected_digest, parsed.candidate_digest)) {
    secure_clear(&expected_digest);
    parsed.clear();
    return false;
  }
  secure_clear(&expected_digest);
  *envelope = std::move(parsed);
  return true;
}

IsolatedAcceptanceTestConfiguration
Stage2D9G3PrepareExecutorV69::build_configuration_(
    const Stage2D9CommandEnvelopeV69 &envelope) const {
  IsolatedAcceptanceTestConfiguration config;
  const std::string test_run_id = "gh-test-run-" + envelope.run_suffix;
  config.schema = "gh.h3.n2.stage2d7-isolated-test-config/1";
  config.firmware_commit_sha = this->build_binding_;
  config.configuration_digest = envelope.candidate_digest;
  config.broker_configuration_digest = envelope.authorization_digest;
  config.test_device_identifier = "gh-test-device-" + envelope.run_suffix;
  config.candidate.schema = "gh.h3.n2.isolated-candidate-profile/1";
  config.candidate.test_run_id = test_run_id;
  config.candidate.system_id = "gh-test-system-" + envelope.run_suffix;
  config.candidate.node_id = "gh-test-node-" + envelope.run_suffix;
  config.candidate.broker_host = LOCAL_PLACEHOLDER_HOST;
  config.candidate.broker_port = 8883;
  config.candidate.broker_tls_server_name = LOCAL_PLACEHOLDER_HOST;
  config.candidate.ca_pem = "stage2d9-test-ca";
  config.candidate.mqtt_username = "stage2d9-test";
  config.candidate.mqtt_client_id = "gh-test-client-" + test_run_id;
  config.candidate.mqtt_password = envelope.authorization_digest;
  config.candidate.test_topic_root = "gh-test/" + test_run_id + "/node";
  config.candidate.credential_generation = 1;
  return config;
}

bool Stage2D9G3PrepareExecutorV69::build_candidate_digest_(
    const RamCredentialBundle &bundle, std::string *digest) const {
  if (digest == nullptr || !bundle.valid())
    return false;
  std::ostringstream material;
  material << bundle.schema << '\n'
           << bundle.system_id << '\n'
           << bundle.node_id << '\n'
           << bundle.broker_host << '\n'
           << bundle.broker_port << '\n'
           << bundle.broker_tls_server_name << '\n'
           << bundle.ca_pem << '\n'
           << bundle.mqtt_username << '\n'
           << bundle.mqtt_client_id << '\n'
           << bundle.credential_generation << '\n'
           << bundle.mqtt_password;
  std::string canonical = material.str();
  std::array<uint8_t, 32> observed{};
  const bool hashed = sha256_(
      reinterpret_cast<const uint8_t *>(canonical.data()), canonical.size(),
      &observed);
  secure_clear(&canonical);
  if (!hashed)
    return false;
  *digest = hex_(observed);
  observed.fill(0);
  return true;
}

bool Stage2D9G3PrepareExecutorV69::expected_candidate_digest_(
    const Stage2D9CommandEnvelopeV69 &envelope, std::string *digest) const {
  IsolatedAcceptanceTestConfiguration config =
      this->build_configuration_(envelope);
  RamCredentialBundle bundle;
  bundle.schema = CREDENTIALS_CONTENT_TYPE;
  bundle.system_id = config.candidate.system_id;
  bundle.node_id = config.candidate.node_id;
  bundle.broker_host = config.candidate.broker_host;
  bundle.broker_port = config.candidate.broker_port;
  bundle.broker_tls_server_name = config.candidate.broker_tls_server_name;
  bundle.ca_pem = config.candidate.ca_pem;
  bundle.mqtt_username = config.candidate.mqtt_username;
  bundle.mqtt_client_id = config.candidate.mqtt_client_id;
  bundle.credential_generation = config.candidate.credential_generation;
  bundle.mqtt_password = config.candidate.mqtt_password;
  const bool result = this->build_candidate_digest_(bundle, digest);
  bundle.clear();
  config.clear();
  return result;
}

bool Stage2D9G3PrepareExecutorV69::verify_recovered_candidate_(
    const Stage2D9CommandEnvelopeV69 &envelope,
    uint32_t expected_generation) {
  EspIdfIsolatedPersistencePort verifier;
  IsolatedDeviceDriverConfig config;
  config.partition_label = this->partition_label_;
  config.namespace_name = this->namespace_name_;
  config.validation_timeout_ms = 15000;
  config.activation_timeout_ms = 15000;
  if (!verifier.configure(config, &this->test_key_provider_))
    return false;

  IsolatedDevicePersistenceSnapshot snapshot{};
  RamCredentialBundle candidate;
  const bool inspected =
      verifier.inspect_read_only(&snapshot, nullptr, &candidate);
  verifier.quiesce();
  if (!inspected || !snapshot.read_only_opened || !snapshot.recovery_valid ||
      snapshot.recovery_status != "no_active_prepared" ||
      snapshot.active_generation != 0 ||
      snapshot.candidate_generation != expected_generation ||
      snapshot.reboot_required || !candidate.valid()) {
    candidate.clear();
    return false;
  }

  std::string observed_digest;
  const bool digest_ok =
      this->build_candidate_digest_(candidate, &observed_digest) &&
      constant_equal_(observed_digest, envelope.candidate_digest);
  secure_clear(&observed_digest);
  candidate.clear();
  return digest_ok;
}

bool Stage2D9G3PrepareExecutorV69::fail_step_(const char *stage) {
  this->failure_stage_ = stage == nullptr ? "unknown" : stage;
  this->emit_failure_detail_(this->failure_stage_.c_str());
  return false;
}

bool Stage2D9G3PrepareExecutorV69::execute_prepare_(
    Stage2D9CommandEnvelopeV69 *envelope) {
  if (envelope == nullptr || envelope->verify_only ||
      this->awaiting_ != AwaitingCommand::PREPARE ||
      this->package_.snapshot().phase != IsolatedAcceptancePhase::READ_ONLY) {
    return this->fail_step_("prepare_precondition");
  }
  if (!this->test_key_provider_.load(envelope->persistence_key))
    return this->fail_step_("prepare_key_load");

  IsolatedAcceptanceTestConfiguration config =
      this->build_configuration_(*envelope);
  if (!config.valid()) {
    config.clear();
    return this->fail_step_("prepare_config_invalid");
  }
  if (!this->package_.load_test_configuration(std::move(config))) {
    config.clear();
    return this->fail_step_("prepare_config_load");
  }
  if (!this->authorization_binder_.grant(
          IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE, 0, 1,
          envelope->authorization_digest)) {
    return this->fail_step_("prepare_authorization_grant");
  }

  const bool prepared = this->package_.prepare_candidate();
  this->emit_snapshot_("prepare");
  if (!prepared)
    return this->fail_step_("prepare_transaction");

  const auto &snapshot = this->package_.snapshot();
  if (snapshot.phase != IsolatedAcceptancePhase::PREPARED)
    return this->fail_step_("prepare_postcondition_phase");
  if (snapshot.failure != IsolatedAcceptanceFailure::NONE)
    return this->fail_step_("prepare_postcondition_package_failure");
  if (snapshot.active_generation != 0 || snapshot.candidate_generation != 1)
    return this->fail_step_("prepare_postcondition_generation");
  if (snapshot.driver.persistence_status != "no_active_prepared")
    return this->fail_step_("prepare_postcondition_persistence");
  if (!snapshot.driver.read_only_observed ||
      snapshot.driver.persistent_write_count == 0)
    return this->fail_step_("prepare_postcondition_write_proof");
  if (snapshot.driver.active_session_live ||
      snapshot.driver.candidate_session_live ||
      snapshot.driver.probe_session_live || this->mqtt_.operation_attempted())
    return this->fail_step_("prepare_postcondition_mqtt_boundary");
  if (snapshot.write_authorization_armed ||
      !snapshot.write_authorization_consumed)
    return this->fail_step_("prepare_postcondition_authorization");
  if (snapshot.reboot_required)
    return this->fail_step_("prepare_postcondition_reboot_flag");
  if (!this->verify_recovered_candidate_(*envelope, 1))
    return this->fail_step_("prepare_postcondition_recovered_candidate");

  this->command_accepted_ = true;
  this->prepare_succeeded_ = true;
  ESP_LOGI(TAG,
           "stage2d9_v69_prepare=pass active_generation=0 "
           "candidate_generation=1 candidate_state=PREPARED "
           "authorization_consumed=true mqtt=false rebooting=true");
  this->package_.quiesce_for_reboot();
  this->authorization_binder_.clear();
  envelope->clear();
  vTaskDelay(pdMS_TO_TICKS(250));
  esp_restart();
  return true;
}

bool Stage2D9G3PrepareExecutorV69::execute_verify_(
    Stage2D9CommandEnvelopeV69 *envelope) {
  if (envelope == nullptr || !envelope->verify_only ||
      this->awaiting_ != AwaitingCommand::VERIFY ||
      this->package_.snapshot().phase != IsolatedAcceptancePhase::COLD)
    return this->fail_step_("verify_precondition");
  if (!this->test_key_provider_.load(envelope->persistence_key))
    return this->fail_step_("verify_key_load");
  if (!this->package_.inspect_read_only())
    return this->fail_step_("verify_read_only_inspection");

  this->emit_snapshot_("verify");
  const auto &snapshot = this->package_.snapshot();
  if (snapshot.phase != IsolatedAcceptancePhase::READ_ONLY ||
      snapshot.failure != IsolatedAcceptanceFailure::NONE)
    return this->fail_step_("verify_postcondition_phase");
  if (snapshot.active_generation != 0 || snapshot.candidate_generation != 1)
    return this->fail_step_("verify_postcondition_generation");
  if (snapshot.driver.persistence_status != "no_active_prepared" ||
      !snapshot.driver.read_only_observed ||
      snapshot.driver.persistent_write_count != 0)
    return this->fail_step_("verify_postcondition_persistence");
  if (snapshot.driver.active_session_live ||
      snapshot.driver.candidate_session_live ||
      snapshot.driver.probe_session_live || this->mqtt_.operation_attempted())
    return this->fail_step_("verify_postcondition_mqtt_boundary");
  if (snapshot.write_authorization_armed ||
      snapshot.write_authorization_consumed || snapshot.reboot_required)
    return this->fail_step_("verify_postcondition_authorization");
  if (!this->verify_recovered_candidate_(*envelope, 1))
    return this->fail_step_("verify_postcondition_candidate_digest");

  this->command_accepted_ = true;
  this->verify_succeeded_ = true;
  ESP_LOGI(TAG,
           "stage2d9_v69_verify=pass active_generation=0 "
           "candidate_generation=1 candidate_state=PREPARED "
           "candidate_digest_match=true active_unchanged=true mqtt=false");
  envelope->clear();
  this->wipe_runtime_();
  this->close_partition_();
  this->terminal_ = true;
  this->awaiting_ = AwaitingCommand::NONE;
  return true;
}

void Stage2D9G3PrepareExecutorV69::emit_snapshot_(const char *label) const {
  const auto &snapshot = this->package_.snapshot();
  ESP_LOGI(
      TAG,
      "stage2d9_v69_%s_snapshot phase=%s command=%s failure=%s "
      "driver_failure=%s persistence=%s active_generation=%" PRIu32
      " candidate_generation=%" PRIu32 " writes=%" PRIu32
      " read_only=%s active_session=%s candidate_session=%s probe_session=%s "
      "key_loaded=%s authorization_armed=%s authorization_consumed=%s "
      "mqtt_operation_attempted=%s reboot_required=%s",
      label == nullptr ? "unknown" : label,
      IsolatedAcceptancePackage::phase_name(snapshot.phase),
      IsolatedAcceptancePackage::command_name(snapshot.last_command),
      IsolatedAcceptancePackage::failure_name(snapshot.failure),
      IsolatedDeviceDriver::failure_name(this->driver_.failure()),
      snapshot.driver.persistence_status.c_str(), snapshot.active_generation,
      snapshot.candidate_generation, snapshot.driver.persistent_write_count,
      snapshot.driver.read_only_observed ? "true" : "false",
      snapshot.driver.active_session_live ? "true" : "false",
      snapshot.driver.candidate_session_live ? "true" : "false",
      snapshot.driver.probe_session_live ? "true" : "false",
      this->test_key_provider_.loaded() ? "true" : "false",
      snapshot.write_authorization_armed ? "true" : "false",
      snapshot.write_authorization_consumed ? "true" : "false",
      this->mqtt_.operation_attempted() ? "true" : "false",
      snapshot.reboot_required ? "true" : "false");
}

void Stage2D9G3PrepareExecutorV69::emit_failure_detail_(
    const char *stage) const {
  const auto &snapshot = this->package_.snapshot();
  ESP_LOGE(
      TAG,
      "stage2d9_v69_failure stage=%s phase=%s command=%s "
      "package_failure=%s driver_failure=%s persistence=%s "
      "active_generation=%" PRIu32 " candidate_generation=%" PRIu32
      " writes=%" PRIu32 " key_loaded=%s authorization_armed=%s "
      "authorization_consumed=%s mqtt_operation_attempted=%s "
      "command_write_attempted=%s device_command_accepted=%s",
      stage == nullptr ? "unknown" : stage,
      IsolatedAcceptancePackage::phase_name(snapshot.phase),
      IsolatedAcceptancePackage::command_name(snapshot.last_command),
      IsolatedAcceptancePackage::failure_name(snapshot.failure),
      IsolatedDeviceDriver::failure_name(this->driver_.failure()),
      snapshot.driver.persistence_status.c_str(), snapshot.active_generation,
      snapshot.candidate_generation, snapshot.driver.persistent_write_count,
      this->test_key_provider_.loaded() ? "true" : "false",
      snapshot.write_authorization_armed ? "true" : "false",
      snapshot.write_authorization_consumed ? "true" : "false",
      this->mqtt_.operation_attempted() ? "true" : "false",
      this->command_attempted_ ? "true" : "false",
      this->command_accepted_ ? "true" : "false");
}

void Stage2D9G3PrepareExecutorV69::wipe_runtime_() {
  this->authorization_binder_.clear();
  this->driver_.clear_write_authorization();
  this->mqtt_.quiesce();
  this->persistence_.quiesce();
  this->test_key_provider_.destroy();
  secure_clear(&this->input_buffer_);
}

void Stage2D9G3PrepareExecutorV69::close_partition_() {
  if (!this->partition_initialized_)
    return;
  const esp_err_t status =
      nvs_flash_deinit_partition(this->partition_label_.c_str());
  if (status != ESP_OK)
    ESP_LOGW(TAG, "stage2d9_v69_partition_deinit=%s", esp_err_to_name(status));
  this->partition_initialized_ = false;
}

void Stage2D9G3PrepareExecutorV69::fail_closed_(const char *reason) {
  if (this->failure_stage_ == "none")
    this->failure_stage_ = reason == nullptr ? "unknown" : reason;
  this->emit_failure_detail_(this->failure_stage_.c_str());
  this->wipe_runtime_();
  this->close_partition_();
  this->awaiting_ = AwaitingCommand::NONE;
  this->terminal_ = true;
  ESP_LOGE(TAG,
           "stage2d9_v69_executor=fail reason=%s failure_stage=%s",
           reason == nullptr ? "unknown" : reason,
           this->failure_stage_.c_str());
  this->mark_failed();
}

void Stage2D9G3PrepareExecutorV69::process_line_(std::string line) {
  while (!line.empty() && (line.back() == '\r' || line.back() == '\n'))
    line.pop_back();
  if (line.empty())
    return;
  if (this->command_attempted_) {
    secure_clear(&line);
    this->failure_stage_ = "command_replay";
    this->fail_closed_("command_replay");
    return;
  }
  this->command_attempted_ = true;

  Stage2D9CommandEnvelopeV69 envelope;
  if (!this->parse_command_(line, &envelope)) {
    secure_clear(&line);
    envelope.clear();
    this->failure_stage_ = "command_validation";
    this->fail_closed_("command_validation");
    return;
  }
  secure_clear(&line);

  const bool success = envelope.verify_only
                           ? this->execute_verify_(&envelope)
                           : this->execute_prepare_(&envelope);
  envelope.clear();
  if (!success && !this->terminal_)
    this->fail_closed_("command_execution");
}

void Stage2D9G3PrepareExecutorV69::read_console_() {
  char buffer[64];
  const ssize_t count = ::read(STDIN_FILENO, buffer, sizeof(buffer));
  if (count < 0) {
    if (errno != EAGAIN && errno != EWOULDBLOCK) {
      this->failure_stage_ = "console_read";
      this->fail_closed_("console_read");
    }
    return;
  }
  if (count == 0)
    return;
  for (ssize_t index = 0; index < count; index++) {
    const char character = buffer[index];
    if (character == '\n') {
      std::string line = std::move(this->input_buffer_);
      this->input_buffer_.clear();
      this->process_line_(std::move(line));
      if (this->terminal_)
        return;
      continue;
    }
    if (character == '\r')
      continue;
    if (this->input_buffer_.size() >= MAX_COMMAND_LENGTH) {
      this->failure_stage_ = "command_length";
      this->fail_closed_("command_length");
      return;
    }
    this->input_buffer_.push_back(character);
  }
}

void Stage2D9G3PrepareExecutorV69::setup() {
  this->command_surface_enabled_ =
      valid_lower_hex_(this->unlock_digest_, 64) &&
      !all_zero_hex_(this->unlock_digest_);
  ESP_LOGI(TAG, "stage2d9_v69_executor_begin build_binding=%s",
           this->build_binding_.c_str());
  ESP_LOGI(
      TAG,
      "stage2d9_v69_boundary execution_authorized=false "
      "unlock_preimage_loaded=false prepare_authorization=false "
      "activate_authorization=false cleanup_authorization=false wifi=false "
      "mqtt=false broker=false efuse=false command_surface_enabled=%s "
      "candidate_host_contract=local_only",
      this->command_surface_enabled_ ? "true" : "false");

  if (!this->verify_partition_()) {
    this->failure_stage_ = "startup_partition_geometry";
    this->fail_closed_("startup_boundary");
    return;
  }
  if (!this->initialize_partition_()) {
    this->failure_stage_ = "startup_partition_init";
    this->fail_closed_("startup_boundary");
    return;
  }
  if (!this->configure_runtime_()) {
    this->failure_stage_ = "startup_runtime_configure";
    this->fail_closed_("startup_boundary");
    return;
  }

  bool namespace_exists = false;
  if (!this->namespace_exists_(&namespace_exists)) {
    this->failure_stage_ = "startup_namespace_probe";
    this->fail_closed_("namespace_probe");
    return;
  }

  if (!this->command_surface_enabled_) {
    if (namespace_exists || !this->inspect_empty_()) {
      this->failure_stage_ = "locked_state";
      this->fail_closed_("locked_state");
      return;
    }
    this->emit_snapshot_("locked");
    this->wipe_runtime_();
    this->close_partition_();
    this->terminal_ = true;
    ESP_LOGI(TAG, "stage2d9_v69_executor=locked command_surface=false");
    return;
  }

  if (namespace_exists) {
    this->awaiting_ = AwaitingCommand::VERIFY;
    ESP_LOGI(TAG,
             "stage2d9_v69_command_ready=VERIFY expected_schema=%s "
             "manual_reset_required=false",
             VERIFY_SCHEMA);
    return;
  }

  if (!this->inspect_empty_()) {
    this->failure_stage_ = "initial_empty_inspection";
    this->fail_closed_("initial_empty_inspection");
    return;
  }
  this->emit_snapshot_("initial");
  this->awaiting_ = AwaitingCommand::PREPARE;
  ESP_LOGI(TAG,
           "stage2d9_v69_command_ready=PREPARE expected_schema=%s "
           "execution_authorized=false",
           PREPARE_SCHEMA);
}

void Stage2D9G3PrepareExecutorV69::loop() {
  if (this->terminal_ || !this->command_surface_enabled_ ||
      this->awaiting_ == AwaitingCommand::NONE)
    return;
  this->read_console_();
}

void Stage2D9G3PrepareExecutorV69::dump_config() {
  ESP_LOGCONFIG(TAG, "Stage2D9 G3 V69 corrected PREPARE executor:");
  ESP_LOGCONFIG(TAG, "  Build binding: %s", this->build_binding_.c_str());
  ESP_LOGCONFIG(TAG, "  Test partition: %s", this->partition_label_.c_str());
  ESP_LOGCONFIG(TAG, "  Test namespace: %s", this->namespace_name_.c_str());
  ESP_LOGCONFIG(TAG, "  Candidate host contract: %s", LOCAL_PLACEHOLDER_HOST);
  ESP_LOGCONFIG(TAG, "  Command surface enabled: %s",
                this->command_surface_enabled_ ? "true" : "false");
  ESP_LOGCONFIG(TAG, "  Command write attempted: %s",
                this->command_attempted_ ? "true" : "false");
  ESP_LOGCONFIG(TAG, "  Device command accepted: %s",
                this->command_accepted_ ? "true" : "false");
  ESP_LOGCONFIG(TAG, "  PREPARE succeeded: %s",
                this->prepare_succeeded_ ? "true" : "false");
  ESP_LOGCONFIG(TAG, "  VERIFY succeeded: %s",
                this->verify_succeeded_ ? "true" : "false");
  ESP_LOGCONFIG(TAG, "  Failure stage: %s", this->failure_stage_.c_str());
  ESP_LOGCONFIG(TAG, "  MQTT operation attempted: %s",
                this->mqtt_.operation_attempted() ? "true" : "false");
}

}  // namespace esphome::greenhouse_pairing_client
