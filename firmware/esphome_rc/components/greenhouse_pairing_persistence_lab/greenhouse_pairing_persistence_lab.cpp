#include "greenhouse_pairing_persistence_lab.h"

#include <cinttypes>

#include "esphome/core/log.h"

namespace esphome::greenhouse_pairing_persistence_lab {

static const char *const TAG = "greenhouse_pairing_persistence_lab";

void GreenhousePairingPersistenceLab::setup() {
  this->backend_ = std::make_unique<EspIdfNvsPersistenceBackend>(
      this->partition_label_, this->namespace_name_);
  this->key_provider_ =
      std::make_unique<EfuseHmacPersistenceKeyProvider>(this->hmac_key_id_);
  this->crypto_ =
      std::make_unique<PairingPersistenceCrypto>(this->key_provider_.get());
  this->store_ =
      std::make_unique<PairingPersistentStore>(this->backend_.get(),
                                               this->crypto_.get());
  this->snapshot_ = {};
}

void GreenhousePairingPersistenceLab::dump_config() {
  ESP_LOGCONFIG(TAG,
                "Greenhouse Pairing Persistence Lab:\n"
                "  Partition label: %s\n"
                "  Namespace: %s\n"
                "  HMAC eFuse key ID: %u\n"
                "  Automatic NVS access at boot: NO\n"
                "  NVS writes at boot: NO\n"
                "  Manual recovery probe: READ ONLY\n"
                "  HMAC key provisioning before write tests: REQUIRED\n"
                "  Production MQTT mutation: NO\n"
                "  Production RC2 integration: NO",
                this->partition_label_.c_str(),
                this->namespace_name_.c_str(),
                static_cast<unsigned>(this->hmac_key_id_));
}

float GreenhousePairingPersistenceLab::get_setup_priority() const {
  return setup_priority::DATA;
}

bool GreenhousePairingPersistenceLab::recover_for_lab() {
  if (this->is_failed() || this->backend_ == nullptr ||
      this->store_ == nullptr)
    return false;
  if (!this->backend_->opened() &&
      !this->backend_->open(PersistenceOpenMode::READ_ONLY)) {
    ESP_LOGE(TAG, "Stage 2D-1 read-only NVS open failed");
    return false;
  }

  PersistentRecoverySnapshot recovered{};
  if (!this->store_->recover(&recovered)) {
    this->snapshot_ = recovered;
    ESP_LOGE(TAG, "Stage 2D-1 read-only recovery failed: %s",
             PairingPersistentStore::status_name(recovered.status));
    return false;
  }
  this->snapshot_ = recovered;
  ESP_LOGI(TAG,
           "Stage 2D-1 read-only recovery: status=%s active_generation=%" PRIu32
           " candidate_generation=%" PRIu32,
           PairingPersistentStore::status_name(this->snapshot_.status),
           this->snapshot_.active_generation,
           this->snapshot_.candidate_generation);
  return true;
}

const char *GreenhousePairingPersistenceLab::recovery_status_name() const {
  return PairingPersistentStore::status_name(this->snapshot_.status);
}

}  // namespace esphome::greenhouse_pairing_persistence_lab
