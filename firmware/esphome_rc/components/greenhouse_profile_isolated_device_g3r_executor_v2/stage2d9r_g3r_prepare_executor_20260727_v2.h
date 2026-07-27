#pragma once

// Reuse the exact frozen V1 declaration under new symbols. The V1 source files
// remain byte-for-byte unchanged; this translation unit obtains an independent
// V2Core type and then layers only the readiness-repeat behavior on top.
#define Stage2D9RCommandEnvelopeV1 Stage2D9RCommandEnvelopeV2
#define Stage2D9RG3RPrepareExecutorV1 Stage2D9RG3RPrepareExecutorV2Core
#define final
#include "../greenhouse_profile_isolated_device_g3r_executor/stage2d9r_g3r_prepare_executor_20260723_v1.h"
#undef final
#undef Stage2D9RG3RPrepareExecutorV1
#undef Stage2D9RCommandEnvelopeV1

namespace esphome::greenhouse_pairing_client {

class Stage2D9RG3RPrepareExecutorV2 final
    : public Stage2D9RG3RPrepareExecutorV2Core {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;

 protected:
  void emit_repeated_ready_marker_();

  static constexpr int64_t READY_REPEAT_INTERVAL_US = 1000000;
  int64_t last_ready_emit_us_{0};
};

}  // namespace esphome::greenhouse_pairing_client
