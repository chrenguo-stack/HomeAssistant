#pragma once

#include <cstdint>
#include <string>

#include "../greenhouse_pairing_client/pairing_ram_credentials.h"
#include "../greenhouse_profile_isolated_acceptance/isolated_acceptance_package.h"

namespace esphome::greenhouse_pairing_client {

enum class IsolatedDeviceDriverFailure : uint8_t {
  NONE = 0,
  INVALID_CONFIGURATION = 1,
  INVALID_STATE = 2,
  TEST_KEY_REQUIRED = 3,
  READ_ONLY_OPEN_FAILED = 4,
  READ_ONLY_RECOVERY_FAILED = 5,
  WRITE_AUTHORIZATION_NOT_ARMED = 6,
  WRITE_AUTHORIZATION_MISMATCH = 7,
  PREPARE_WRITE_FAILED = 8,
  PREPARE_VERIFY_FAILED = 9,
  MQTT_CONFIGURATION_FAILED = 10,
  VALIDATION_START_FAILED = 11,
  VALIDATION_FAILED = 12,
  ACTIVATION_AUTHORIZATION_REJECTED = 13,
  ACTIVATION_START_FAILED = 14,
  PERSISTENCE_COMMIT_FAILED = 15,
  MARKER_LAST_NOT_PROVEN = 16,
  PROMOTION_FAILED = 17,
  ROLLBACK_FAILED = 18,
  CLEANUP_FAILED = 19,
  AUTHORITY_AMBIGUOUS = 20,
  REBOOT_REQUIRED = 21,
};

struct IsolatedDeviceDriverConfig {
  std::string partition_label;
  std::string namespace_name;
  uint32_t validation_timeout_ms{15000};
  uint32_t activation_timeout_ms{15000};

  bool valid() const;
};

struct IsolatedDevicePersistenceSnapshot {
  bool read_only_opened{false};
  bool namespace_missing{false};
  bool recovery_valid{false};
  std::string recovery_status{"unknown"};
  uint32_t active_generation{0};
  uint32_t candidate_generation{0};
  bool marker_last_observed{false};
  bool marker_committed{false};
  bool cleanup_confirmed{false};
  bool reboot_required{false};
  uint32_t persistent_write_count{0};
};

class IsolatedDevicePersistencePort {
 public:
  virtual ~IsolatedDevicePersistencePort() = default;

  virtual bool configure(
      const IsolatedDeviceDriverConfig &config,
      VolatileTestPersistenceKeyProvider *test_key_provider) = 0;
  virtual bool inspect_read_only(
      IsolatedDevicePersistenceSnapshot *snapshot,
      RamCredentialBundle *active_credentials,
      RamCredentialBundle *candidate_credentials) = 0;
  virtual bool prepare_candidate(
      const RamCredentialBundle &candidate,
      IsolatedDevicePersistenceSnapshot *snapshot) = 0;
  virtual bool commit_prepared(
      IsolatedDevicePersistenceSnapshot *snapshot,
      RamCredentialBundle *new_active_credentials) = 0;
  virtual bool cleanup_test_namespace(
      IsolatedDevicePersistenceSnapshot *snapshot) = 0;
  virtual void quiesce() = 0;
};

struct IsolatedDeviceMqttSnapshot {
  bool configured{false};
  bool validation_complete{false};
  bool validation_success{false};
  bool active_session_live{false};
  bool candidate_session_live{false};
  bool probe_session_live{false};
  bool rollback_completed{false};
  bool promotion_complete{false};
  bool reboot_required{false};
  std::string failure_point{"none"};
  std::string rollback_result{"not_applicable"};
};

class IsolatedDeviceMqttPort {
 public:
  virtual ~IsolatedDeviceMqttPort() = default;

  virtual bool configure(
      const RamCredentialBundle *active_credentials,
      const IsolatedCandidateProfile &candidate,
      uint32_t validation_timeout_ms,
      uint32_t activation_timeout_ms) = 0;
  virtual bool begin_validation(IsolatedDeviceMqttSnapshot *snapshot) = 0;
  virtual bool poll_validation(uint32_t elapsed_ms,
                               IsolatedDeviceMqttSnapshot *snapshot) = 0;
  virtual bool begin_activation(IsolatedDeviceMqttSnapshot *snapshot) = 0;
  virtual bool rollback_activation(IsolatedDeviceMqttSnapshot *snapshot) = 0;
  virtual bool promote_candidate(IsolatedDeviceMqttSnapshot *snapshot) = 0;
  virtual void quiesce() = 0;
};

class MirroredGenerationWriteAuthorization {
 public:
  bool arm(IsolatedAcceptanceWriteOperation operation,
           uint32_t active_generation, uint32_t candidate_generation,
           const std::string &authorization_digest);
  bool consume(IsolatedAcceptanceWriteOperation operation,
               uint32_t active_generation, uint32_t candidate_generation);
  void clear();

  bool armed() const { return this->armed_; }
  IsolatedAcceptanceWriteOperation operation() const {
    return this->operation_;
  }
  uint32_t active_generation() const { return this->active_generation_; }
  uint32_t candidate_generation() const { return this->candidate_generation_; }

 protected:
  IsolatedAcceptanceWriteOperation operation_{
      IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE};
  uint32_t active_generation_{0};
  uint32_t candidate_generation_{0};
  std::string authorization_digest_{};
  bool armed_{false};
};

class IsolatedDeviceDriver final : public IsolatedAcceptanceDriver {
 public:
  bool configure(const IsolatedDeviceDriverConfig &config,
                 IsolatedDevicePersistencePort *persistence,
                 IsolatedDeviceMqttPort *mqtt,
                 VolatileTestPersistenceKeyProvider *test_key_provider);

  bool arm_write_authorization(
      IsolatedAcceptanceWriteOperation operation, uint32_t active_generation,
      uint32_t candidate_generation,
      const std::string &authorization_digest);
  void clear_write_authorization();

  bool inspect_read_only(IsolatedAcceptanceDriverSnapshot *snapshot) override;
  bool prepare_candidate(const IsolatedCandidateProfile &candidate,
                         IsolatedAcceptanceDriverSnapshot *snapshot) override;
  bool begin_validation(IsolatedAcceptanceDriverSnapshot *snapshot) override;
  bool poll_validation(uint32_t elapsed_ms,
                       IsolatedAcceptanceDriverSnapshot *snapshot) override;
  bool activate(ProfileLifecycleMutationAuthorizer *authorizer,
                IsolatedAcceptanceDriverSnapshot *snapshot) override;
  bool cleanup_test_state(IsolatedAcceptanceDriverSnapshot *snapshot) override;
  void quiesce_for_reboot() override;

  IsolatedDeviceDriverFailure failure() const { return this->failure_; }
  bool reboot_required() const { return this->reboot_required_; }

  static const char *failure_name(IsolatedDeviceDriverFailure failure);

 protected:
  static RamCredentialBundle bundle_from_candidate_(
      const IsolatedCandidateProfile &candidate);
  static void clone_bundle_(const RamCredentialBundle &source,
                            RamCredentialBundle *target);
  bool consume_mirrored_authorization_(
      IsolatedAcceptanceWriteOperation operation, uint32_t active_generation,
      uint32_t candidate_generation);
  bool recover_persistence_(IsolatedDevicePersistenceSnapshot *snapshot);
  bool rollback_after_activation_failure_(
      IsolatedDeviceMqttSnapshot *mqtt_snapshot,
      IsolatedDevicePersistenceSnapshot *persistence_snapshot);
  bool fail_(IsolatedDeviceDriverFailure failure,
             IsolatedAcceptanceDriverSnapshot *snapshot,
             bool reboot_required = false);
  void update_snapshot_(IsolatedAcceptanceDriverSnapshot *snapshot) const;
  void clear_sensitive_material_();

  IsolatedDeviceDriverConfig config_{};
  IsolatedDevicePersistencePort *persistence_{nullptr};
  IsolatedDeviceMqttPort *mqtt_{nullptr};
  VolatileTestPersistenceKeyProvider *test_key_provider_{nullptr};
  MirroredGenerationWriteAuthorization write_authorization_{};
  RamCredentialBundle recovered_active_{};
  RamCredentialBundle recovered_candidate_{};
  IsolatedCandidateProfile candidate_profile_{};
  IsolatedDevicePersistenceSnapshot persistence_snapshot_{};
  IsolatedDeviceMqttSnapshot mqtt_snapshot_{};
  IsolatedDeviceDriverFailure failure_{IsolatedDeviceDriverFailure::NONE};
  bool configured_{false};
  bool inspected_{false};
  bool candidate_prepared_{false};
  bool validation_started_{false};
  bool validation_verified_{false};
  bool activated_{false};
  bool cleaned_{false};
  bool reboot_required_{false};
};

class IsolatedDeviceAuthorizationBinder {
 public:
  bool configure(IsolatedAcceptancePackage *package,
                 IsolatedDeviceDriver *driver);
  bool grant(IsolatedAcceptanceWriteOperation operation,
             uint32_t active_generation, uint32_t candidate_generation,
             const std::string &authorization_digest);
  void clear();

 protected:
  IsolatedAcceptancePackage *package_{nullptr};
  IsolatedDeviceDriver *driver_{nullptr};
};

}  // namespace esphome::greenhouse_pairing_client
