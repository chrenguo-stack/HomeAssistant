#include "n3w_registration_display.h"

namespace esphome::greenhouse_n3w_core {

void RegistrationDisplayController::clear() {
  latch_kind_ = LatchKind::NONE;
  error_ = RegistrationDisplayError::NONE;
  latch_started_ms_ = 0;
  latch_duration_ms_ = 0;
}

void RegistrationDisplayController::show_success(uint64_t now_ms) {
  if (now_ms == 0U) return;
  latch_kind_ = LatchKind::SUCCESS;
  error_ = RegistrationDisplayError::NONE;
  latch_started_ms_ = now_ms;
  latch_duration_ms_ = kRegistrationSuccessDisplayMs;
}

void RegistrationDisplayController::show_error(
    RegistrationDisplayError error,
    uint64_t now_ms) {
  if (error == RegistrationDisplayError::NONE || now_ms == 0U) return;
  if (latch_kind_ == LatchKind::ERROR && error_ == error &&
      latch_active_(now_ms)) {
    return;
  }
  latch_kind_ = LatchKind::ERROR;
  error_ = error;
  latch_started_ms_ = now_ms;
  latch_duration_ms_ = kRegistrationErrorDisplayMs;
}

bool RegistrationDisplayController::latch_active_(uint64_t now_ms) const {
  if (latch_kind_ == LatchKind::NONE || latch_started_ms_ == 0U ||
      latch_duration_ms_ == 0U || now_ms < latch_started_ms_) {
    return false;
  }
  return now_ms - latch_started_ms_ < latch_duration_ms_;
}

RegistrationDisplayState RegistrationDisplayController::resolve(
    RegistrationDisplayState base_state,
    uint64_t now_ms) const {
  if (!latch_active_(now_ms)) return base_state;
  if (latch_kind_ == LatchKind::SUCCESS) {
    return RegistrationDisplayState::SUCCESS;
  }
  if (latch_kind_ == LatchKind::ERROR) {
    return RegistrationDisplayState::ERROR;
  }
  return base_state;
}

RegistrationDisplayError RegistrationDisplayController::current_error(
    uint64_t now_ms) const {
  if (latch_kind_ != LatchKind::ERROR || !latch_active_(now_ms)) {
    return RegistrationDisplayError::NONE;
  }
  return error_;
}

}  // namespace esphome::greenhouse_n3w_core
