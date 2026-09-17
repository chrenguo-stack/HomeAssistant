#pragma once

#include <cstdint>

namespace esphome::greenhouse_n3w_core {

// Lab-only breadcrumb stages used to identify the last completed step before a
// software/watchdog restart. Values are intentionally stable because the prior
// boot's value is emitted in telemetry after restart.
enum class N3wRtcBreadcrumbStage : uint32_t {
  NONE = 0,
  BOOT_SETUP = 1,

  TELEMETRY_BEGIN = 10,
  TELEMETRY_OK = 11,
  TELEMETRY_FAIL = 12,

  DIRECT_PUBLISH_BEGIN = 20,
  DIRECT_PUBLISH_OK = 21,
  DIRECT_PUBLISH_FAIL = 22,

  RADIO_CHANNEL_SET_BEGIN = 30,
  RADIO_CHANNEL_SET_OK = 31,
  RADIO_CHANNEL_SET_FAIL = 32,

  CHALLENGE_SUBMIT_BEGIN = 40,
  CHALLENGE_SUBMIT_OK = 41,
  CHALLENGE_SUBMIT_FAIL = 42,
};

struct N3wRtcBreadcrumbSnapshot {
  bool valid{false};
  uint32_t stage{0};
  uint32_t arg0{0};
  uint32_t arg1{0};
  uint32_t uptime_ms{0};
  uint32_t marker_sequence{0};
};

// Capture the value left by the previous boot before the current boot writes a
// new marker. Invalid/random RTC contents after a cold power-on are rejected.
void n3w_rtc_breadcrumb_capture(N3wRtcBreadcrumbSnapshot *snapshot);

// Record one small marker in RTC no-init memory. This does not write flash/NVS.
void n3w_rtc_breadcrumb_mark(
    N3wRtcBreadcrumbStage stage,
    uint32_t arg0,
    uint32_t arg1,
    uint32_t uptime_ms);

const char *n3w_rtc_breadcrumb_stage_name(uint32_t stage);

}  // namespace esphome::greenhouse_n3w_core
