#pragma once

#include <cstdint>

namespace esphome::greenhouse_n3w_core {

enum class RegistrationDisplayState : uint8_t {
  IDLE_UNREGISTERED = 0,
  DISCOVERING,
  WAIT_CONFIRM,
  REGISTERING,
  SUCCESS,
  ERROR,
};

enum class RegistrationDisplayError : uint8_t {
  NONE = 0,
  E01_NO_HOST = 1,
  E02_HOST_UNAVAILABLE = 2,
  E03_HOST_BUSY = 3,
  E04_NETWORK_INTERRUPTED = 4,
  E05_REGISTRATION_TIMEOUT = 5,
  E06_REGISTRATION_FAILED = 6,
  E07_QR_INVALID = 7,
};

inline constexpr uint64_t kRegistrationSuccessDisplayMs = 3000ULL;
inline constexpr uint64_t kRegistrationErrorDisplayMs = 5000ULL;

class RegistrationDisplayController {
 public:
  void clear();
  void show_success(uint64_t now_ms);
  void show_error(RegistrationDisplayError error, uint64_t now_ms);

  RegistrationDisplayState resolve(
      RegistrationDisplayState base_state,
      uint64_t now_ms) const;
  RegistrationDisplayError current_error(uint64_t now_ms) const;

 private:
  enum class LatchKind : uint8_t {
    NONE = 0,
    SUCCESS,
    ERROR,
  };

  bool latch_active_(uint64_t now_ms) const;

  LatchKind latch_kind_{LatchKind::NONE};
  RegistrationDisplayError error_{RegistrationDisplayError::NONE};
  uint64_t latch_started_ms_{0};
  uint64_t latch_duration_ms_{0};
};

}  // namespace esphome::greenhouse_n3w_core
