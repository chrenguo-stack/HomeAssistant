#include "stage2d9r_g3r_prepare_executor_20260727_v2.h"

// Compile an exact copy of the frozen V1 implementation under V2Core symbols.
// The original V1 files are not edited and their prior Artifact bindings remain
// intact on their frozen branches.
#define Stage2D9RCommandEnvelopeV1 Stage2D9RCommandEnvelopeV2
#define Stage2D9RG3RPrepareExecutorV1 Stage2D9RG3RPrepareExecutorV2Core
#include "../greenhouse_profile_isolated_device_g3r_executor/stage2d9r_g3r_prepare_executor_20260723_v1.cpp"
#undef Stage2D9RG3RPrepareExecutorV1
#undef Stage2D9RCommandEnvelopeV1

#include "esp_timer.h"
#include "esphome/core/log.h"

namespace esphome::greenhouse_pairing_client {
namespace {

static const char *const TAG_V2 = "gh_stage2d9r_v2";

}  // namespace

void Stage2D9RG3RPrepareExecutorV2::setup() {
  Stage2D9RG3RPrepareExecutorV2Core::setup();
  this->last_ready_emit_us_ = esp_timer_get_time();
}

void Stage2D9RG3RPrepareExecutorV2::emit_repeated_ready_marker_() {
  switch (this->awaiting_) {
    case AwaitingCommand::PREPARE:
      ESP_LOGI(TAG_V2,
               "stage2d9r_command_ready=PREPARE expected_schema=GH2D9R_PREPARE_V1 "
               "execution_authorized=false ca_digest_bound=true "
               "stage2d9r_ready_repeat=true interval_ms=1000");
      break;
    case AwaitingCommand::VERIFY:
      ESP_LOGI(TAG_V2,
               "stage2d9r_command_ready=VERIFY expected_schema=GH2D9R_VERIFY_V1 "
               "manual_reset_required=false ca_replay_required=false "
               "stage2d9r_ready_repeat=true interval_ms=1000");
      break;
    case AwaitingCommand::NONE:
      break;
  }
}

void Stage2D9RG3RPrepareExecutorV2::loop() {
  Stage2D9RG3RPrepareExecutorV2Core::loop();
  if (this->terminal_ || !this->command_surface_enabled_ ||
      this->awaiting_ == AwaitingCommand::NONE) {
    return;
  }

  const int64_t now = esp_timer_get_time();
  if (this->last_ready_emit_us_ == 0 ||
      now - this->last_ready_emit_us_ >= READY_REPEAT_INTERVAL_US) {
    this->emit_repeated_ready_marker_();
    this->last_ready_emit_us_ = now;
  }
}

void Stage2D9RG3RPrepareExecutorV2::dump_config() {
  Stage2D9RG3RPrepareExecutorV2Core::dump_config();
  ESP_LOGCONFIG(TAG_V2, "  Ready marker repeat interval: 1000 ms");
  ESP_LOGCONFIG(TAG_V2, "  Ready marker repeat enabled: true");
}

}  // namespace esphome::greenhouse_pairing_client
