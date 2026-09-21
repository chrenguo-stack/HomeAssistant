#pragma once

#include <cstdint>
#include <string>
#include <utility>

#include "n3w_core.h"
#include "n3w_simple_crypto.h"

namespace esphome::greenhouse_n3w_core {

enum class SimpleNvsStatus : uint8_t {
  OK = 0,
  CREATED,
  MISSING,
  CORRUPT,
  IO_ERROR,
  INVALID_ARGUMENT,
};

struct ProvisionedPeerStateV2 {
  std::string system_id;
  std::string node_id;
  uint64_t peer_trust_generation{0};
  SystemPeerKey system_peer_key{};
  uint32_t n3w_key_epoch{0};
  std::array<uint8_t, kApplicationKeyBytes> n3w_application_key{};

  bool valid() const;
  void clear();
};

struct PendingPairingIntent {
  std::string random_pairing_id;

  bool valid() const;
  void clear();
};

class NvsPendingPairingIntentStore {
 public:
  explicit NvsPendingPairingIntentStore(
      std::string namespace_name = "gh_n3w_v2",
      std::string key_name = "pair_intent")
      : namespace_name_(std::move(namespace_name)), key_name_(std::move(key_name)) {}

  SimpleNvsStatus load(PendingPairingIntent *intent);
  SimpleNvsStatus save(const PendingPairingIntent &intent);
  SimpleNvsStatus erase();

 private:
  std::string namespace_name_;
  std::string key_name_;
};

class NvsSetupSecretStore {
 public:
  explicit NvsSetupSecretStore(
      std::string namespace_name = "gh_n3w_v2",
      std::string key_name = "setup")
      : namespace_name_(std::move(namespace_name)), key_name_(std::move(key_name)) {}

  // A missing Setup Secret is generated from the ESP32 hardware RNG at first use.
  // It is never compiled into factory firmware.
  SimpleNvsStatus load_or_create(SetupSecret *secret);
  SimpleNvsStatus erase();

 private:
  std::string namespace_name_;
  std::string key_name_;
};

class NvsPairingEpochStore {
 public:
  explicit NvsPairingEpochStore(
      std::string namespace_name = "gh_n3w_v2",
      std::string key_name = "pair_epoch")
      : namespace_name_(std::move(namespace_name)), key_name_(std::move(key_name)) {}

  // LEGACY_MIGRATION_ONLY / BOARD_LAB_ONLY. Product pairing does not use this.
  SimpleNvsStatus load(uint32_t *epoch);
  SimpleNvsStatus save(uint32_t epoch);

 private:
  std::string namespace_name_;
  std::string key_name_;
};

class NvsProvisionedPeerStoreV2 {
 public:
  explicit NvsProvisionedPeerStoreV2(
      std::string namespace_name = "gh_n3w_v2",
      std::string key_name = "peer")
      : namespace_name_(std::move(namespace_name)), key_name_(std::move(key_name)) {}

  SimpleNvsStatus load(ProvisionedPeerStateV2 *state);
  SimpleNvsStatus save(const ProvisionedPeerStateV2 &state);
  SimpleNvsStatus erase();

 private:
  std::string namespace_name_;
  std::string key_name_;
};

}  // namespace esphome::greenhouse_n3w_core
