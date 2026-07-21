#pragma once

#include <cstdint>

namespace esphome::greenhouse_pairing_client {

enum class MqttActivationPhase : uint8_t {
  UNCHANGED = 0,
  CANDIDATE_STAGED = 1,
  PROBING = 2,
  VERIFIED = 3,
  ACTIVATED = 4,
  ROLLED_BACK = 5,
  FAILED = 6,
};

struct MqttActivationSnapshot {
  MqttActivationPhase phase{MqttActivationPhase::UNCHANGED};
  uint32_t active_generation{0};
  uint32_t candidate_generation{0};
  bool authenticated{false};
  bool subscribe_ready{false};
  bool telemetry_round_trip{false};
};

class MqttActivationContract {
 public:
  bool configure(uint32_t active_generation);
  bool stage(uint32_t candidate_generation);
  bool begin_probe();
  bool record_probe(bool authenticated, bool subscribe_ready,
                    bool telemetry_round_trip);
  bool activate();
  void rollback();

  const MqttActivationSnapshot &snapshot() const { return this->snapshot_; }
  static const char *phase_name(MqttActivationPhase phase);

 protected:
  MqttActivationSnapshot snapshot_{};
};

}  // namespace esphome::greenhouse_pairing_client
