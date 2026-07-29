#include "stage2d9r_g3r_prepare_looptask_watchdog_repair_20260729_v1.h"

#include <algorithm>
#include <cerrno>
#include <cinttypes>
#include <cstdint>
#include <fcntl.h>
#include <unistd.h>

#include "esp_timer.h"
#include "esphome/core/log.h"

namespace esphome::greenhouse_pairing_client {
namespace {

static const char *const REPAIR_TAG = "gh_stage2d9r_wdt";
constexpr uint32_t MAX_BOUNDED_CONSOLE_LOOP_US = 4000000;

}  // namespace

bool Stage2D9RG3RPrepareLoopTaskWatchdogRepairV1::
    configure_console_nonblocking_() {
  errno = 0;
  const int flags = ::fcntl(STDIN_FILENO, F_GETFL, 0);
  if (flags < 0) {
    ESP_LOGE(REPAIR_TAG,
             "stage2d9r_console_nonblocking=fail point=get_flags errno=%d",
             errno);
    return false;
  }

  if ((flags & O_NONBLOCK) == 0) {
    errno = 0;
    if (::fcntl(STDIN_FILENO, F_SETFL, flags | O_NONBLOCK) < 0) {
      ESP_LOGE(REPAIR_TAG,
               "stage2d9r_console_nonblocking=fail point=set_flags errno=%d",
               errno);
      return false;
    }
  }

  errno = 0;
  const int verified = ::fcntl(STDIN_FILENO, F_GETFL, 0);
  if (verified < 0 || (verified & O_NONBLOCK) == 0) {
    ESP_LOGE(REPAIR_TAG,
             "stage2d9r_console_nonblocking=fail point=verify_flags errno=%d",
             errno);
    return false;
  }

  this->console_nonblocking_ = true;
  ESP_LOGI(REPAIR_TAG,
           "stage2d9r_console_nonblocking=pass stdin=nonblocking "
           "watchdog_disabled=false watchdog_timeout_extended=false");
  return true;
}

void Stage2D9RG3RPrepareLoopTaskWatchdogRepairV1::setup() {
  Stage2D9RG3RPrepareExecutorV1::setup();
  if (this->terminal_ || !this->command_surface_enabled_ ||
      this->awaiting_ == AwaitingCommand::NONE) {
    return;
  }

  if (!this->configure_console_nonblocking_()) {
    this->failure_stage_ = "console_nonblocking_configuration";
    this->fail_closed_("console_nonblocking_configuration");
  }
}

void Stage2D9RG3RPrepareLoopTaskWatchdogRepairV1::loop() {
  if (this->terminal_ || !this->command_surface_enabled_ ||
      this->awaiting_ == AwaitingCommand::NONE) {
    return;
  }
  if (!this->console_nonblocking_) {
    this->failure_stage_ = "console_nonblocking_not_armed";
    this->fail_closed_("console_nonblocking_not_armed");
    return;
  }

  const int64_t started_us = esp_timer_get_time();
  this->read_console_();
  const int64_t finished_us = esp_timer_get_time();
  const int64_t elapsed_signed = finished_us >= started_us
                                     ? finished_us - started_us
                                     : 0;
  const uint32_t elapsed_us = static_cast<uint32_t>(
      std::min<int64_t>(elapsed_signed, UINT32_MAX));
  this->max_console_loop_us_ = std::max(this->max_console_loop_us_, elapsed_us);

  // This is a fail-closed timing guard, not a watchdog bypass. It can reject a
  // near-watchdog operation after it returns, but it never feeds, disables, or
  // extends the ESP-IDF task watchdog.
  if (!this->terminal_ && elapsed_us > MAX_BOUNDED_CONSOLE_LOOP_US) {
    ESP_LOGE(REPAIR_TAG,
             "stage2d9r_console_loop_bound=fail elapsed_us=%" PRIu32
             " limit_us=%" PRIu32,
             elapsed_us, MAX_BOUNDED_CONSOLE_LOOP_US);
    this->failure_stage_ = "console_loop_time_bound";
    this->fail_closed_("console_loop_time_bound");
  }
}

void Stage2D9RG3RPrepareLoopTaskWatchdogRepairV1::dump_config() {
  Stage2D9RG3RPrepareExecutorV1::dump_config();
  ESP_LOGCONFIG(REPAIR_TAG, "Stage2D9R loopTask watchdog repair:");
  ESP_LOGCONFIG(REPAIR_TAG, "  STDIN nonblocking: %s",
                this->console_nonblocking_ ? "true" : "false");
  ESP_LOGCONFIG(REPAIR_TAG, "  Watchdog disabled: false");
  ESP_LOGCONFIG(REPAIR_TAG, "  Watchdog timeout extended: false");
  ESP_LOGCONFIG(REPAIR_TAG, "  Maximum observed console loop: %" PRIu32 " us",
                this->max_console_loop_us_);
}

}  // namespace esphome::greenhouse_pairing_client
