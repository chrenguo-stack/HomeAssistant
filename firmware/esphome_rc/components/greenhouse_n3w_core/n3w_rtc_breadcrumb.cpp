#include "n3w_rtc_breadcrumb.h"

#ifdef GREENHOUSE_N3W_ENABLE_PHASE4_LAB

#ifdef USE_ESP32
#include "esp_attr.h"
#endif

namespace esphome::greenhouse_n3w_core {
namespace {

constexpr uint32_t kBreadcrumbMagic = 0x4E335742U;  // "N3WB"
constexpr uint32_t kBreadcrumbVersion = 1U;

#ifdef USE_ESP32
struct RtcBreadcrumbStorage {
  uint32_t magic;
  uint32_t version;
  uint32_t stage;
  uint32_t stage_inverse;
  uint32_t arg0;
  uint32_t arg0_inverse;
  uint32_t arg1;
  uint32_t arg1_inverse;
  uint32_t uptime_ms;
  uint32_t uptime_ms_inverse;
  uint32_t marker_sequence;
  uint32_t marker_sequence_inverse;
};

RTC_NOINIT_ATTR volatile RtcBreadcrumbStorage g_rtc_breadcrumb;

bool storage_valid_() {
  return g_rtc_breadcrumb.magic == kBreadcrumbMagic &&
         g_rtc_breadcrumb.version == kBreadcrumbVersion &&
         g_rtc_breadcrumb.stage_inverse == ~g_rtc_breadcrumb.stage &&
         g_rtc_breadcrumb.arg0_inverse == ~g_rtc_breadcrumb.arg0 &&
         g_rtc_breadcrumb.arg1_inverse == ~g_rtc_breadcrumb.arg1 &&
         g_rtc_breadcrumb.uptime_ms_inverse == ~g_rtc_breadcrumb.uptime_ms &&
         g_rtc_breadcrumb.marker_sequence_inverse ==
             ~g_rtc_breadcrumb.marker_sequence;
}
#endif

}  // namespace

void n3w_rtc_breadcrumb_capture(N3wRtcBreadcrumbSnapshot *snapshot) {
  if (snapshot == nullptr) return;
  *snapshot = N3wRtcBreadcrumbSnapshot{};
#ifdef USE_ESP32
  if (!storage_valid_()) return;
  snapshot->valid = true;
  snapshot->stage = g_rtc_breadcrumb.stage;
  snapshot->arg0 = g_rtc_breadcrumb.arg0;
  snapshot->arg1 = g_rtc_breadcrumb.arg1;
  snapshot->uptime_ms = g_rtc_breadcrumb.uptime_ms;
  snapshot->marker_sequence = g_rtc_breadcrumb.marker_sequence;
#endif
}

void n3w_rtc_breadcrumb_mark(
    N3wRtcBreadcrumbStage stage,
    uint32_t arg0,
    uint32_t arg1,
    uint32_t uptime_ms) {
#ifdef USE_ESP32
  const uint32_t next_sequence =
      storage_valid_() ? g_rtc_breadcrumb.marker_sequence + 1U : 1U;

  // Clear magic first and restore it last. A reset in the middle of this very
  // small update therefore produces an invalid record instead of a false one.
  g_rtc_breadcrumb.magic = 0U;
  g_rtc_breadcrumb.version = kBreadcrumbVersion;
  g_rtc_breadcrumb.stage = static_cast<uint32_t>(stage);
  g_rtc_breadcrumb.stage_inverse = ~g_rtc_breadcrumb.stage;
  g_rtc_breadcrumb.arg0 = arg0;
  g_rtc_breadcrumb.arg0_inverse = ~arg0;
  g_rtc_breadcrumb.arg1 = arg1;
  g_rtc_breadcrumb.arg1_inverse = ~arg1;
  g_rtc_breadcrumb.uptime_ms = uptime_ms;
  g_rtc_breadcrumb.uptime_ms_inverse = ~uptime_ms;
  g_rtc_breadcrumb.marker_sequence = next_sequence;
  g_rtc_breadcrumb.marker_sequence_inverse = ~next_sequence;
  g_rtc_breadcrumb.magic = kBreadcrumbMagic;
#else
  (void) stage;
  (void) arg0;
  (void) arg1;
  (void) uptime_ms;
#endif
}

const char *n3w_rtc_breadcrumb_stage_name(uint32_t stage) {
  switch (static_cast<N3wRtcBreadcrumbStage>(stage)) {
    case N3wRtcBreadcrumbStage::NONE:
      return "NONE";
    case N3wRtcBreadcrumbStage::BOOT_SETUP:
      return "BOOT_SETUP";
    case N3wRtcBreadcrumbStage::TELEMETRY_BEGIN:
      return "TELEMETRY_BEGIN";
    case N3wRtcBreadcrumbStage::TELEMETRY_OK:
      return "TELEMETRY_OK";
    case N3wRtcBreadcrumbStage::TELEMETRY_FAIL:
      return "TELEMETRY_FAIL";
    case N3wRtcBreadcrumbStage::TELEMETRY_BUFFERED:
      return "TELEMETRY_BUFFERED";
    case N3wRtcBreadcrumbStage::DIRECT_PUBLISH_BEGIN:
      return "DIRECT_PUBLISH_BEGIN";
    case N3wRtcBreadcrumbStage::DIRECT_PUBLISH_OK:
      return "DIRECT_PUBLISH_OK";
    case N3wRtcBreadcrumbStage::DIRECT_PUBLISH_FAIL:
      return "DIRECT_PUBLISH_FAIL";
    case N3wRtcBreadcrumbStage::RADIO_CHANNEL_SET_BEGIN:
      return "RADIO_CHANNEL_SET_BEGIN";
    case N3wRtcBreadcrumbStage::RADIO_CHANNEL_SET_OK:
      return "RADIO_CHANNEL_SET_OK";
    case N3wRtcBreadcrumbStage::RADIO_CHANNEL_SET_FAIL:
      return "RADIO_CHANNEL_SET_FAIL";
    case N3wRtcBreadcrumbStage::CHALLENGE_SUBMIT_BEGIN:
      return "CHALLENGE_SUBMIT_BEGIN";
    case N3wRtcBreadcrumbStage::CHALLENGE_SUBMIT_OK:
      return "CHALLENGE_SUBMIT_OK";
    case N3wRtcBreadcrumbStage::CHALLENGE_SUBMIT_FAIL:
      return "CHALLENGE_SUBMIT_FAIL";
    default:
      return "UNKNOWN";
  }
}

}  // namespace esphome::greenhouse_n3w_core

#endif  // GREENHOUSE_N3W_ENABLE_PHASE4_LAB
