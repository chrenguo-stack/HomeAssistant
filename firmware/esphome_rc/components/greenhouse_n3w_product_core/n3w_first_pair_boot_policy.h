#pragma once

#include <cstdint>

#include "n3w_core.h"

namespace esphome::greenhouse_n3w_core {

enum class StartupIdentityRecordState : uint8_t {
  MISSING = 0,
  VALID,
  INVALID,
};

enum class StartupProductIdentityState : uint8_t {
  PROVEN_FRESH = 0,
  EXISTING_IDENTITY,
  INVALID_OR_PARTIAL,
};

inline StartupProductIdentityState classify_startup_product_identity(
    StartupIdentityRecordState peer_state,
    StartupIdentityRecordState broker_state,
    bool peer_broker_match,
    StartupIdentityRecordState ack_state) {
  if (peer_state == StartupIdentityRecordState::MISSING &&
      broker_state == StartupIdentityRecordState::MISSING &&
      ack_state == StartupIdentityRecordState::MISSING) {
    return StartupProductIdentityState::PROVEN_FRESH;
  }

  if (peer_state == StartupIdentityRecordState::VALID &&
      broker_state == StartupIdentityRecordState::VALID &&
      peer_broker_match &&
      (ack_state == StartupIdentityRecordState::MISSING ||
       ack_state == StartupIdentityRecordState::VALID)) {
    return StartupProductIdentityState::EXISTING_IDENTITY;
  }

  return StartupProductIdentityState::INVALID_OR_PARTIAL;
}

inline CoreError prepare_initial_boot_floor(
    BootSessionManager *manager,
    BootSessionStore *store) {
  if (manager == nullptr || store == nullptr) {
    return CoreError::INVALID_ARGUMENT;
  }

  uint64_t existing = 0;
  const StoreStatus status = store->load(&existing);
  switch (status) {
    case StoreStatus::MISSING:
      return manager->provision_recovery_floor(store, 0);
    case StoreStatus::OK:
      return existing == 0 ? CoreError::NONE : CoreError::SESSION_ROLLBACK;
    case StoreStatus::CORRUPT:
      return CoreError::STORE_CORRUPT;
    case StoreStatus::IO_ERROR:
      return CoreError::STORE_IO_ERROR;
  }
  return CoreError::STORE_IO_ERROR;
}

}  // namespace esphome::greenhouse_n3w_core
