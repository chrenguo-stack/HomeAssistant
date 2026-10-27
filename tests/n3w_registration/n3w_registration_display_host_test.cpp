#include <cassert>
#include <cstdint>

#include "n3w_registration_display.h"

using esphome::greenhouse_n3w_core::RegistrationDisplayController;
using esphome::greenhouse_n3w_core::RegistrationDisplayError;
using esphome::greenhouse_n3w_core::RegistrationDisplayState;
using esphome::greenhouse_n3w_core::kRegistrationErrorDisplayMs;
using esphome::greenhouse_n3w_core::kRegistrationSuccessDisplayMs;

int main() {
  static_assert(static_cast<uint8_t>(RegistrationDisplayState::IDLE_UNREGISTERED) == 0);
  static_assert(static_cast<uint8_t>(RegistrationDisplayState::DISCOVERING) == 1);
  static_assert(static_cast<uint8_t>(RegistrationDisplayState::WAIT_CONFIRM) == 2);
  static_assert(static_cast<uint8_t>(RegistrationDisplayState::REGISTERING) == 3);
  static_assert(static_cast<uint8_t>(RegistrationDisplayState::SUCCESS) == 4);
  static_assert(static_cast<uint8_t>(RegistrationDisplayState::ERROR) == 5);

  static_assert(static_cast<uint8_t>(RegistrationDisplayError::E01_NO_HOST) == 1);
  static_assert(static_cast<uint8_t>(RegistrationDisplayError::E02_HOST_UNAVAILABLE) == 2);
  static_assert(static_cast<uint8_t>(RegistrationDisplayError::E03_HOST_BUSY) == 3);
  static_assert(static_cast<uint8_t>(RegistrationDisplayError::E04_NETWORK_INTERRUPTED) == 4);
  static_assert(static_cast<uint8_t>(RegistrationDisplayError::E05_REGISTRATION_TIMEOUT) == 5);
  static_assert(static_cast<uint8_t>(RegistrationDisplayError::E06_REGISTRATION_FAILED) == 6);
  static_assert(static_cast<uint8_t>(RegistrationDisplayError::E07_QR_INVALID) == 7);

  assert(kRegistrationSuccessDisplayMs == 3000ULL);
  assert(kRegistrationErrorDisplayMs == 5000ULL);

  RegistrationDisplayController display;
  assert(display.resolve(RegistrationDisplayState::DISCOVERING, 1000) ==
         RegistrationDisplayState::DISCOVERING);
  assert(display.current_error(1000) == RegistrationDisplayError::NONE);

  display.show_error(RegistrationDisplayError::E01_NO_HOST, 1000);
  assert(display.resolve(RegistrationDisplayState::IDLE_UNREGISTERED, 5999) ==
         RegistrationDisplayState::ERROR);
  assert(display.current_error(5999) == RegistrationDisplayError::E01_NO_HOST);

  // Re-reporting the same still-visible error must not extend the latch.
  display.show_error(RegistrationDisplayError::E01_NO_HOST, 4000);
  assert(display.resolve(RegistrationDisplayState::IDLE_UNREGISTERED, 6000) ==
         RegistrationDisplayState::IDLE_UNREGISTERED);
  assert(display.current_error(6000) == RegistrationDisplayError::NONE);

  // A different error replaces the previous error with its own bounded window.
  display.show_error(RegistrationDisplayError::E02_HOST_UNAVAILABLE, 7000);
  display.show_error(RegistrationDisplayError::E03_HOST_BUSY, 8000);
  assert(display.current_error(12999) == RegistrationDisplayError::E03_HOST_BUSY);
  assert(display.current_error(13000) == RegistrationDisplayError::NONE);

  // Durable success wins over an earlier error and cannot be covered by a late error.
  display.show_error(RegistrationDisplayError::E06_REGISTRATION_FAILED, 14000);
  display.show_success(15000);
  display.show_error(RegistrationDisplayError::E04_NETWORK_INTERRUPTED, 16000);
  assert(display.resolve(RegistrationDisplayState::REGISTERING, 17999) ==
         RegistrationDisplayState::SUCCESS);
  assert(display.current_error(17999) == RegistrationDisplayError::NONE);
  assert(display.resolve(RegistrationDisplayState::REGISTERING, 18000) ==
         RegistrationDisplayState::REGISTERING);

  display.clear();
  assert(display.resolve(RegistrationDisplayState::WAIT_CONFIRM, 20000) ==
         RegistrationDisplayState::WAIT_CONFIRM);
  assert(display.current_error(20000) == RegistrationDisplayError::NONE);

  return 0;
}
