#pragma once

#include <cstddef>
#include <cstdint>

#include "pairing_client_core.h"

namespace esphome::greenhouse_pairing_client {

enum class PairingAsyncPhase : uint8_t {
  IDLE = 0,
  QUEUED = 1,
  DISCOVERING = 2,
  WAITING_SELECTION = 3,
  SECURE_PAIRING = 4,
  RAM_STAGED = 5,
  PERSISTENCE_PREPARED = 6,
  MQTT_PROBING = 7,
  COMPLETED = 8,
  CANCELLED = 9,
  FAILED = 10,
};

enum class PairingAsyncOutcome : uint8_t {
  NONE = 0,
  SUCCESS = 1,
  BUSY = 2,
  SELECTION_REQUIRED = 3,
  CANCELLED = 4,
  INVALID_TRANSITION = 5,
  DISCOVERY_FAILED = 6,
  PAIRING_FAILED = 7,
  PERSISTENCE_FAILED = 8,
  MQTT_PROBE_FAILED = 9,
};

struct PairingAsyncSnapshot {
  uint32_t operation_id{0};
  uint32_t state_version{0};
  PairingAsyncPhase phase{PairingAsyncPhase::IDLE};
  PairingAsyncOutcome outcome{PairingAsyncOutcome::NONE};
  PairingClientState client_state{PairingClientState::UNBOUND};
  PairingClientError client_error{PairingClientError::NONE};
  size_t candidate_count{0};
  uint32_t credential_generation{0};
  bool active{false};
  bool cancel_requested{false};
  bool selection_required{false};
  bool credentials_staged{false};
};

class PairingAsyncContract {
 public:
  bool queue(uint32_t operation_id, const PairingClientSnapshot &client);
  bool begin(const PairingClientSnapshot &client);
  bool publish(PairingAsyncPhase phase, const PairingClientSnapshot &client);
  bool request_cancel();
  bool finish(PairingAsyncOutcome outcome, const PairingClientSnapshot &client);
  void reset(const PairingClientSnapshot &client);

  const PairingAsyncSnapshot &snapshot() const { return this->snapshot_; }

  static bool terminal(PairingAsyncPhase phase);
  static bool valid_transition(PairingAsyncPhase from, PairingAsyncPhase to);
  static const char *phase_name(PairingAsyncPhase phase);
  static const char *outcome_name(PairingAsyncOutcome outcome);

 protected:
  void copy_client_(const PairingClientSnapshot &client);
  void bump_();

  PairingAsyncSnapshot snapshot_{};
};

}  // namespace esphome::greenhouse_pairing_client
