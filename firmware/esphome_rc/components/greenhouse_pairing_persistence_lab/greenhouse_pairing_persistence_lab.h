#pragma once

#include <cstdint>
#include <memory>
#include <string>

#include "esphome/core/component.h"
#include "esphome/components/greenhouse_pairing_client/pairing_persistent_store.h"

namespace esphome::greenhouse_pairing_persistence_lab {

using greenhouse_pairing_client::EfuseHmacPersistenceKeyProvider;
using greenhouse_pairing_client::EspIdfNvsPersistenceBackend;
using greenhouse_pairing_client::PairingPersistenceCrypto;
using greenhouse_pairing_client::PersistenceOpenMode;
using greenhouse_pairing_client::PairingPersistentStore;
using greenhouse_pairing_client::PersistentRecoverySnapshot;
using greenhouse_pairing_client::PersistentRecoveryStatus;

class GreenhousePairingPersistenceLab final : public Component {
 public:
  void set_partition_label(const std::string &value) {
    this->partition_label_ = value;
  }
  void set_namespace_name(const std::string &value) {
    this->namespace_name_ = value;
  }
  void set_hmac_key_id(uint8_t value) { this->hmac_key_id_ = value; }

  void setup() override;
  void dump_config() override;
  float get_setup_priority() const override;

  // Manual read-only lab probe. It opens the namespace and performs recovery,
  // but never prepares, commits, erases, or mutates a credential record.
  bool recover_for_lab();

  const char *recovery_status_name() const;
  uint32_t active_generation() const {
    return this->snapshot_.active_generation;
  }
  uint32_t candidate_generation() const {
    return this->snapshot_.candidate_generation;
  }
  bool backend_opened() const {
    return this->backend_ != nullptr && this->backend_->opened();
  }

 private:
  std::string partition_label_{"nvs"};
  std::string namespace_name_{"gh_pair_v1"};
  uint8_t hmac_key_id_{0};

  std::unique_ptr<EspIdfNvsPersistenceBackend> backend_;
  std::unique_ptr<EfuseHmacPersistenceKeyProvider> key_provider_;
  std::unique_ptr<PairingPersistenceCrypto> crypto_;
  std::unique_ptr<PairingPersistentStore> store_;
  PersistentRecoverySnapshot snapshot_{};
};

}  // namespace esphome::greenhouse_pairing_persistence_lab
