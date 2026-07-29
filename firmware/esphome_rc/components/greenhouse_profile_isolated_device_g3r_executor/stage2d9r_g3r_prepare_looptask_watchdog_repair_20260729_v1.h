#pragma once

#include <cstdint>

#include "stage2d9r_g3r_prepare_executor_20260723_v1.h"

namespace esphome::greenhouse_pairing_client {

// D2-09 root-cause repair: the old executor called POSIX read() from the
// ESPHome loop task without first setting STDIN to O_NONBLOCK. Once PREPARE
// rebooted into VERIFY-ready state and no VERIFY command had yet arrived,
// loopTask slept inside esp_cpu_wait_for_intr until the task watchdog aborted.
//
// This successor preserves the command and persistence semantics. It only
// repairs the console scheduling boundary and records bounded-loop telemetry.
class Stage2D9RG3RPrepareLoopTaskWatchdogRepairV1 final
    : public Stage2D9RG3RPrepareExecutorV1 {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;

  bool console_nonblocking_for_test() const {
    return this->console_nonblocking_;
  }
  uint32_t max_console_loop_us_for_test() const {
    return this->max_console_loop_us_;
  }

 protected:
  bool configure_console_nonblocking_();

  bool console_nonblocking_{false};
  uint32_t max_console_loop_us_{0};
};

}  // namespace esphome::greenhouse_pairing_client
