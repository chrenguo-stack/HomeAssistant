#pragma once

#include "isolated_device_driver.h"

#ifdef USE_ESP32

#include <memory>
#include <string>
#include <vector>

#include "../greenhouse_pairing_client/pairing_persistence_backend.h"
#include "../greenhouse_pairing_client/pairing_persistence_crypto.h"
#include "../greenhouse_pairing_client/pairing_persistent_store.h"
#include "../greenhouse_profile_production_adapters/profile_production_adapters.h"

namespace esphome::greenhouse_pairing_client {

class AuditedEspIdfNvsBackend final : public PairingPersistenceBackend {
 public:
  AuditedEspIdfNvsBackend(const std::string &partition_label,
                          const std::string &namespace_name);
  ~AuditedEspIdfNvsBackend() override = default;

  bool open(PersistenceOpenMode mode);
  bool opened() const;
  bool writable() const;
  bool namespace_missing() const;

  PersistenceReadResult read_blob(const char *key,
                                  std::vector<uint8_t> *value) override;
  bool write_blob(const char *key, const uint8_t *value,
                  size_t length) override;
  bool erase_key(const char *key) override;
  bool commit() override;

  uint32_t successful_commit_count() const {
    return this->successful_commit_count_;
  }
  const std::vector<std::string> &committed_keys() const {
    return this->committed_keys_;
  }

 protected:
  std::unique_ptr<EspIdfNvsPersistenceBackend> backend_{};
  std::string pending_key_{};
  std::vector<std::string> committed_keys_{};
  uint32_t successful_commit_count_{0};
};

class EspIdfIsolatedPersistencePort final
    : public IsolatedDevicePersistencePort {
 public:
  bool configure(
      const IsolatedDeviceDriverConfig &config,
      VolatileTestPersistenceKeyProvider *test_key_provider) override;
  bool inspect_read_only(
      IsolatedDevicePersistenceSnapshot *snapshot,
      RamCredentialBundle *active_credentials,
      RamCredentialBundle *candidate_credentials) override;
  bool prepare_candidate(
      const RamCredentialBundle &candidate,
      IsolatedDevicePersistenceSnapshot *snapshot) override;
  bool commit_prepared(
      IsolatedDevicePersistenceSnapshot *snapshot,
      RamCredentialBundle *new_active_credentials) override;
  bool cleanup_test_namespace(
      IsolatedDevicePersistenceSnapshot *snapshot) override;
  void quiesce() override;

 protected:
  bool open_store_(PersistenceOpenMode mode, bool *namespace_missing = nullptr);
  bool recover_open_store_(IsolatedDevicePersistenceSnapshot *snapshot,
                           RamCredentialBundle *active_credentials,
                           RamCredentialBundle *candidate_credentials);
  bool reopen_and_recover_(IsolatedDevicePersistenceSnapshot *snapshot,
                           RamCredentialBundle *active_credentials = nullptr,
                           RamCredentialBundle *candidate_credentials = nullptr);
  bool erase_namespace_();
  void close_store_();
  void absorb_audit_();
  static bool marker_last_(const std::vector<std::string> &committed_keys);

  IsolatedDeviceDriverConfig config_{};
  VolatileTestPersistenceKeyProvider *test_key_provider_{nullptr};
  std::unique_ptr<AuditedEspIdfNvsBackend> backend_{};
  std::unique_ptr<PairingPersistenceCrypto> crypto_{};
  std::unique_ptr<PairingPersistentStore> store_{};
  uint32_t persistent_write_count_{0};
  bool configured_{false};
  bool marker_committed_{false};
  bool marker_last_observed_{false};
};

class EspIdfIsolatedMqttPort final : public IsolatedDeviceMqttPort {
 public:
  bool configure(
      const RamCredentialBundle *active_credentials,
      const IsolatedCandidateProfile &candidate,
      uint32_t validation_timeout_ms,
      uint32_t activation_timeout_ms) override;
  bool begin_validation(IsolatedDeviceMqttSnapshot *snapshot) override;
  bool poll_validation(uint32_t elapsed_ms,
                       IsolatedDeviceMqttSnapshot *snapshot) override;
  bool begin_activation(IsolatedDeviceMqttSnapshot *snapshot) override;
  bool rollback_activation(IsolatedDeviceMqttSnapshot *snapshot) override;
  bool promote_candidate(IsolatedDeviceMqttSnapshot *snapshot) override;
  void quiesce() override;

 protected:
  static CandidateMqttProfile profile_from_bundle_(
      const RamCredentialBundle &credentials);
  static CandidateMqttProfile profile_from_candidate_(
      const IsolatedCandidateProfile &candidate);
  bool build_exchange_(CandidateMqttProbeExchange *exchange);
  bool start_active_if_present_();
  void refresh_snapshot_(IsolatedDeviceMqttSnapshot *snapshot) const;
  void clear_sensitive_material_();

  RamCredentialBundle active_credentials_{};
  IsolatedCandidateProfile candidate_{};
  CandidateMqttProfile candidate_profile_{};
  CandidateMqttProbeExchange exchange_{};
  std::unique_ptr<EspIdfProductionMqttSession> active_session_{};
  std::unique_ptr<EspIdfProductionMqttSession> probe_session_{};
  std::unique_ptr<EspIdfProductionMqttSession> candidate_session_{};
  EspIdfActivationNonceSource nonce_source_{};
  uint32_t validation_timeout_ms_{15000};
  uint32_t activation_timeout_ms_{15000};
  uint32_t validation_elapsed_ms_{0};
  bool configured_{false};
  bool validation_started_{false};
  bool validation_complete_{false};
  bool validation_success_{false};
  bool activation_started_{false};
  bool promotion_complete_{false};
  bool rollback_completed_{false};
  bool reboot_required_{false};
  std::string failure_point_{"none"};
  std::string rollback_result_{"not_applicable"};
};

}  // namespace esphome::greenhouse_pairing_client

#endif  // USE_ESP32
