#include "stage2d9r_g3r_ready_repeater_20260727_v1.h"

#include "esp_partition.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#include "nvs.h"

namespace esphome::greenhouse_pairing_client {
namespace {

static const char *const TAG = "gh_stage2d9r_ready_v1";
constexpr uint32_t TEST_PARTITION_ADDRESS = 0x400000;
constexpr uint32_t TEST_PARTITION_SIZE = 0x10000;

}  // namespace

float Stage2D9RG3RReadyRepeaterV1::get_setup_priority() const {
  // The frozen executor uses setup_priority::DATA. Run immediately after it so
  // its read-only/initialization boundary is already established.
  return setup_priority::DATA - 1.0f;
}

bool Stage2D9RG3RReadyRepeaterV1::inspect_read_only_() {
  const esp_partition_t *partition = esp_partition_find_first(
      ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS,
      this->partition_label_.c_str());
  if (partition == nullptr || partition->readonly ||
      partition->address != TEST_PARTITION_ADDRESS ||
      partition->size != TEST_PARTITION_SIZE) {
    ESP_LOGE(TAG, "stage2d9r_ready_repeater=disabled reason=partition_geometry");
    return false;
  }

  nvs_handle_t handle{};
  const esp_err_t status = nvs_open_from_partition(
      this->partition_label_.c_str(), this->namespace_name_.c_str(),
      NVS_READONLY, &handle);
  if (status == ESP_ERR_NVS_NOT_FOUND) {
    this->ready_mode_ = ReadyMode::PREPARE;
    return true;
  }
  if (status == ESP_OK) {
    nvs_close(handle);
    this->ready_mode_ = ReadyMode::VERIFY;
    return true;
  }

  ESP_LOGE(TAG, "stage2d9r_ready_repeater=disabled reason=namespace_probe status=%s",
           esp_err_to_name(status));
  return false;
}

void Stage2D9RG3RReadyRepeaterV1::emit_ready_marker_() const {
  switch (this->ready_mode_) {
    case ReadyMode::PREPARE:
      ESP_LOGI(TAG,
               "stage2d9r_command_ready=PREPARE expected_schema=GH2D9R_PREPARE_V1 "
               "execution_authorized=false ca_digest_bound=true "
               "stage2d9r_ready_repeat=true interval_ms=%" PRIu32,
               this->repeat_interval_ms_);
      break;
    case ReadyMode::VERIFY:
      ESP_LOGI(TAG,
               "stage2d9r_command_ready=VERIFY expected_schema=GH2D9R_VERIFY_V1 "
               "manual_reset_required=false ca_replay_required=false "
               "stage2d9r_ready_repeat=true interval_ms=%" PRIu32,
               this->repeat_interval_ms_);
      break;
    case ReadyMode::NONE:
      break;
  }
}

void Stage2D9RG3RReadyRepeaterV1::setup() {
  if (this->repeat_interval_ms_ != 1000 || this->repeat_window_ms_ != 180000) {
    ESP_LOGE(TAG, "stage2d9r_ready_repeater=disabled reason=timing_contract");
    this->mark_failed();
    return;
  }
  if (!this->inspect_read_only_()) {
    this->mark_failed();
    return;
  }

  this->started_ms_ = millis();
  this->last_emit_ms_ = this->started_ms_;
  this->enabled_ = true;
  this->emit_ready_marker_();
}

void Stage2D9RG3RReadyRepeaterV1::loop() {
  if (!this->enabled_)
    return;

  const uint32_t now = millis();
  if (now - this->started_ms_ >= this->repeat_window_ms_) {
    this->enabled_ = false;
    ESP_LOGI(TAG,
             "stage2d9r_ready_repeater=complete reason=bounded_window_elapsed");
    return;
  }
  if (now - this->last_emit_ms_ < this->repeat_interval_ms_)
    return;

  this->last_emit_ms_ = now;
  this->emit_ready_marker_();
}

void Stage2D9RG3RReadyRepeaterV1::dump_config() {
  ESP_LOGCONFIG(TAG, "Stage2D9R G3R ready-marker repeater:");
  ESP_LOGCONFIG(TAG, "  Read-only companion: true");
  ESP_LOGCONFIG(TAG, "  Repeat interval: %" PRIu32 " ms",
                this->repeat_interval_ms_);
  ESP_LOGCONFIG(TAG, "  Repeat window: %" PRIu32 " ms",
                this->repeat_window_ms_);
  ESP_LOGCONFIG(TAG, "  Command parser: false");
  ESP_LOGCONFIG(TAG, "  NVS write path: false");
}

}  // namespace esphome::greenhouse_pairing_client
