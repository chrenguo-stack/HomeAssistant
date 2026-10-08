#include <cassert>
#include <cstdint>
#include <iostream>

#include "n3w_first_pair_boot_policy.h"

using esphome::greenhouse_n3w_core::BootSessionManager;
using esphome::greenhouse_n3w_core::BootSessionStore;
using esphome::greenhouse_n3w_core::CoreError;
using esphome::greenhouse_n3w_core::StartupIdentityRecordState;
using esphome::greenhouse_n3w_core::StartupProductIdentityState;
using esphome::greenhouse_n3w_core::StoreStatus;
using esphome::greenhouse_n3w_core::classify_startup_product_identity;
using esphome::greenhouse_n3w_core::prepare_initial_boot_floor;

namespace {

struct FakeBootStore final : BootSessionStore {
  StoreStatus load_status{StoreStatus::MISSING};
  StoreStatus save_status{StoreStatus::OK};
  uint64_t value{0};
  unsigned save_count{0};
  bool corrupt_readback{false};

  StoreStatus load(uint64_t *last_session) override {
    if (load_status != StoreStatus::OK) return load_status;
    *last_session = corrupt_readback ? value + 1U : value;
    return StoreStatus::OK;
  }

  StoreStatus save(uint64_t last_session) override {
    ++save_count;
    if (save_status != StoreStatus::OK) return save_status;
    value = last_session;
    load_status = StoreStatus::OK;
    return StoreStatus::OK;
  }
};

void test_startup_identity_classification() {
  const auto missing = StartupIdentityRecordState::MISSING;
  const auto valid = StartupIdentityRecordState::VALID;
  const auto invalid = StartupIdentityRecordState::INVALID;

  assert(classify_startup_product_identity(missing, missing, false, missing) ==
         StartupProductIdentityState::PROVEN_FRESH);
  assert(classify_startup_product_identity(valid, valid, true, missing) ==
         StartupProductIdentityState::EXISTING_IDENTITY);
  assert(classify_startup_product_identity(valid, valid, true, valid) ==
         StartupProductIdentityState::EXISTING_IDENTITY);

  assert(classify_startup_product_identity(valid, missing, false, missing) ==
         StartupProductIdentityState::INVALID_OR_PARTIAL);
  assert(classify_startup_product_identity(missing, valid, false, missing) ==
         StartupProductIdentityState::INVALID_OR_PARTIAL);
  assert(classify_startup_product_identity(missing, missing, false, valid) ==
         StartupProductIdentityState::INVALID_OR_PARTIAL);
  assert(classify_startup_product_identity(invalid, missing, false, missing) ==
         StartupProductIdentityState::INVALID_OR_PARTIAL);
  assert(classify_startup_product_identity(missing, invalid, false, missing) ==
         StartupProductIdentityState::INVALID_OR_PARTIAL);
  assert(classify_startup_product_identity(missing, missing, false, invalid) ==
         StartupProductIdentityState::INVALID_OR_PARTIAL);
  assert(classify_startup_product_identity(valid, valid, false, missing) ==
         StartupProductIdentityState::INVALID_OR_PARTIAL);
}

void test_initial_floor_policy() {
  {
    FakeBootStore store;
    BootSessionManager manager;
    assert(prepare_initial_boot_floor(&manager, &store) == CoreError::NONE);
    assert(store.load_status == StoreStatus::OK);
    assert(store.value == 0);
    assert(store.save_count == 1);
  }

  {
    FakeBootStore store;
    store.load_status = StoreStatus::OK;
    store.value = 0;
    BootSessionManager manager;
    assert(prepare_initial_boot_floor(&manager, &store) == CoreError::NONE);
    assert(store.value == 0);
    assert(store.save_count == 0);
  }

  {
    FakeBootStore store;
    store.load_status = StoreStatus::OK;
    store.value = 7;
    BootSessionManager manager;
    assert(prepare_initial_boot_floor(&manager, &store) ==
           CoreError::SESSION_ROLLBACK);
    assert(store.value == 7);
    assert(store.save_count == 0);
  }

  {
    FakeBootStore store;
    store.load_status = StoreStatus::CORRUPT;
    BootSessionManager manager;
    assert(prepare_initial_boot_floor(&manager, &store) ==
           CoreError::STORE_CORRUPT);
    assert(store.save_count == 0);
  }

  {
    FakeBootStore store;
    store.load_status = StoreStatus::IO_ERROR;
    BootSessionManager manager;
    assert(prepare_initial_boot_floor(&manager, &store) ==
           CoreError::STORE_IO_ERROR);
    assert(store.save_count == 0);
  }

  {
    FakeBootStore store;
    store.save_status = StoreStatus::IO_ERROR;
    BootSessionManager manager;
    assert(prepare_initial_boot_floor(&manager, &store) ==
           CoreError::STORE_IO_ERROR);
    assert(store.save_count == 1);
  }

  {
    FakeBootStore store;
    store.corrupt_readback = true;
    BootSessionManager manager;
    assert(prepare_initial_boot_floor(&manager, &store) ==
           CoreError::DURABILITY_VERIFY_FAILED);
    assert(store.save_count == 1);
  }
}

void test_first_pair_pretelemetry_reboot_and_monotonicity() {
  FakeBootStore store;
  BootSessionManager preparation;
  assert(prepare_initial_boot_floor(&preparation, &store) == CoreError::NONE);
  assert(store.value == 0);

  assert(classify_startup_product_identity(
             StartupIdentityRecordState::VALID,
             StartupIdentityRecordState::VALID,
             true,
             StartupIdentityRecordState::MISSING) ==
         StartupProductIdentityState::EXISTING_IDENTITY);

  BootSessionManager after_pairing_reboot;
  assert(after_pairing_reboot.begin(&store, 0) == CoreError::NONE);
  assert(after_pairing_reboot.session() == 1);
  assert(after_pairing_reboot.boot_id() == "boot_0000000000000001");

  BootSessionManager next_reboot;
  assert(next_reboot.begin(&store, 0) == CoreError::NONE);
  assert(next_reboot.session() == 2);
  assert(next_reboot.boot_id() == "boot_0000000000000002");

  FakeBootStore missing_counter;
  BootSessionManager existing_identity;
  assert(existing_identity.begin(&missing_counter, 0) == CoreError::STORE_MISSING);
  assert(!existing_identity.ready());
}

}  // namespace

int main() {
  test_startup_identity_classification();
  test_initial_floor_policy();
  test_first_pair_pretelemetry_reboot_and_monotonicity();
  std::cout << "N3W_FIRST_PAIR_BOOT_POLICY_PASS\n";
  return 0;
}
