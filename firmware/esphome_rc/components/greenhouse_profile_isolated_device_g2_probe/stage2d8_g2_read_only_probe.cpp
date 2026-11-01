#include "stage2d8_g2_read_only_probe.h"

#include <cinttypes>

#include "esp_partition.h"
#include "nvs_flash.h"
#include "esphome/core/log.h"

namespace esphome::greenhouse_pairing_client {
namespace {

static const char *const TAG = "gh_stage2d8_g2";
constexpr uint32_t STAGE2D8_TEST_PARTITION_ADDRESS = 0x400000;
constexpr uint32_t STAGE2D8_TEST_PARTITION_SIZE = 0x10000;

}  // namespace

bool Stage2D8SerialEvidenceSink::write_redacted_json(const std::string &json) {
  ESP_LOGI(TAG, "stage2d8_evidence_redacted=%s", json.c_str());
  return true;
}

float Stage2D8G2ReadOnlyProbe::get_setup_priority() const {
  return setup_priority::DATA;
}

void Stage2D8G2ReadOnlyProbe::close_partition_() {
  if (!this->partition_initialized_)
    return;
  const esp_err_t status =
      nvs_flash_deinit_partition(this->partition_label_.c_str());
  if (status != ESP_OK) {
    ESP_LOGW(TAG, "stage2d8_g2_partition_deinit=%s",
             esp_err_to_name(status));
  }
  this->partition_initialized_ = false;
}

void Stage2D8G2ReadOnlyProbe::fail_closed_(const char *reason) {
  this->mqtt_.quiesce();
  this->persistence_.quiesce();
  this->test_key_provider_.destroy();
  this->close_partition_();
  ESP_LOGE(TAG, "stage2d8_g2_probe=fail reason=%s",
           reason == nullptr ? "unknown" : reason);
  this->mark_failed();
}

void Stage2D8G2ReadOnlyProbe::emit_snapshot_() const {
  const auto &snapshot = this->package_.snapshot();
  ESP_LOGI(
      TAG,
      "stage2d8_g2_snapshot phase=%s command=%s failure=%s "
      "read_only=%s persistence=%s active_generation=%" PRIu32
      " candidate_generation=%" PRIu32 " writes=%" PRIu32
      " active_session=%s candidate_session=%s probe_session=%s "
      "reboot_required=%s partition_readonly=%s",
      IsolatedAcceptancePackage::phase_name(snapshot.phase),
      IsolatedAcceptancePackage::command_name(snapshot.last_command),
      IsolatedAcceptancePackage::failure_name(snapshot.failure),
      snapshot.driver.read_only_observed ? "true" : "false",
      snapshot.driver.persistence_status.c_str(), snapshot.active_generation,
      snapshot.candidate_generation, snapshot.driver.persistent_write_count,
      snapshot.driver.active_session_live ? "true" : "false",
      snapshot.driver.candidate_session_live ? "true" : "false",
      snapshot.driver.probe_session_live ? "true" : "false",
      snapshot.reboot_required ? "true" : "false",
      this->partition_verified_readonly_ ? "true" : "false");
}

void Stage2D8G2ReadOnlyProbe::setup() {
  ESP_LOGI(TAG, "stage2d8_g2_probe_begin build_binding=%s",
           this->build_binding_.c_str());
  ESP_LOGI(TAG,
           "stage2d8_g2_boundary key_loaded=false wifi=false mqtt=false "
           "write_authorization=false partition_readonly=true");

  const esp_partition_t *partition = esp_partition_find_first(
      ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS,
      this->partition_label_.c_str());
  this->partition_verified_readonly_ =
      partition != nullptr && partition->readonly &&
      partition->address == STAGE2D8_TEST_PARTITION_ADDRESS &&
      partition->size == STAGE2D8_TEST_PARTITION_SIZE;
  if (!this->partition_verified_readonly_) {
    this->fail_closed_("partition_boundary");
    return;
  }

  // The immutable full-flash package contains a pre-generated NVS seed image.
  // Initialization therefore only registers and scans the already formatted,
  // partition-table-enforced read-only partition. The target namespace remains
  // absent, and every flash mutation API is denied by the partition boundary.
  const esp_err_t init_status =
      nvs_flash_init_partition(this->partition_label_.c_str());
  if (init_status != ESP_OK) {
    ESP_LOGE(TAG, "stage2d8_g2_partition_init=%s",
             esp_err_to_name(init_status));
    this->fail_closed_("partition_initialization");
    return;
  }
  this->partition_initialized_ = true;

  IsolatedDeviceDriverConfig config;
  config.partition_label = this->partition_label_;
  config.namespace_name = this->namespace_name_;
  config.validation_timeout_ms = 15000;
  config.activation_timeout_ms = 15000;

  if (this->test_key_provider_.loaded()) {
    this->fail_closed_("unexpected_test_key");
    return;
  }
  if (!this->driver_.configure(config, &this->persistence_, &this->mqtt_,
                               &this->test_key_provider_)) {
    this->fail_closed_("driver_configuration");
    return;
  }
  if (!this->package_.configure(&this->driver_, &this->test_key_provider_,
                                &this->evidence_sink_)) {
    this->fail_closed_("package_configuration");
    return;
  }
  this->configured_ = true;
  this->inspection_attempted_ = true;

  const bool inspected = this->package_.inspect_read_only();
  this->emit_snapshot_();

  const auto &snapshot = this->package_.snapshot();
  this->inspection_passed_ =
      inspected && this->partition_verified_readonly_ &&
      snapshot.phase == IsolatedAcceptancePhase::READ_ONLY &&
      snapshot.last_command == IsolatedAcceptanceCommand::INSPECT_READ_ONLY &&
      snapshot.failure == IsolatedAcceptanceFailure::NONE &&
      snapshot.driver.read_only_observed &&
      snapshot.driver.persistence_status == "empty" &&
      snapshot.active_generation == 0 && snapshot.candidate_generation == 0 &&
      snapshot.driver.persistent_write_count == 0 &&
      !snapshot.driver.active_session_live &&
      !snapshot.driver.candidate_session_live &&
      !snapshot.driver.probe_session_live && !snapshot.reboot_required &&
      !this->test_key_provider_.loaded();

  this->mqtt_.quiesce();
  this->persistence_.quiesce();
  this->test_key_provider_.destroy();
  this->close_partition_();

  if (!this->inspection_passed_) {
    this->fail_closed_("read_only_contract");
    return;
  }
  ESP_LOGI(TAG, "stage2d8_g2_probe=pass");
}

void Stage2D8G2ReadOnlyProbe::dump_config() {
  ESP_LOGCONFIG(TAG, "Stage2D8 G2 read-only probe:");
  ESP_LOGCONFIG(TAG, "  Build binding: %s", this->build_binding_.c_str());
  ESP_LOGCONFIG(TAG, "  Test partition: %s", this->partition_label_.c_str());
  ESP_LOGCONFIG(TAG, "  Test namespace: %s", this->namespace_name_.c_str());
  ESP_LOGCONFIG(TAG, "  Partition verified read-only: %s",
                this->partition_verified_readonly_ ? "true" : "false");
  ESP_LOGCONFIG(TAG, "  Partition initialized: %s",
                this->partition_initialized_ ? "true" : "false");
  ESP_LOGCONFIG(TAG, "  Configured: %s", this->configured_ ? "true" : "false");
  ESP_LOGCONFIG(TAG, "  Inspection attempted: %s",
                this->inspection_attempted_ ? "true" : "false");
  ESP_LOGCONFIG(TAG, "  Inspection passed: %s",
                this->inspection_passed_ ? "true" : "false");
}

}  // namespace esphome::greenhouse_pairing_client
