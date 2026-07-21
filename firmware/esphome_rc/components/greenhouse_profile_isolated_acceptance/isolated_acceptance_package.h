#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>

#include "../greenhouse_pairing_client/pairing_persistence_crypto.h"
#include "../greenhouse_profile_lifecycle_controller/profile_lifecycle_controller.h"

namespace esphome::greenhouse_pairing_client {

enum class IsolatedAcceptancePhase : uint8_t {
  COLD = 0,
  READ_ONLY = 1,
  CONFIG_LOADED = 2,
  PREPARED = 3,
  VALIDATING = 4,
  VERIFIED = 5,
  ACTIVATING = 6,
  ACTIVATED = 7,
  FAILED = 8,
  REBOOT_REQUIRED = 9,
  CLEANED = 10,
};

enum class IsolatedAcceptanceCommand : uint8_t {
  NONE = 0,
  INSPECT_READ_ONLY = 1,
  LOAD_TEST_CONFIGURATION = 2,
  GRANT_WRITE_AUTHORIZATION = 3,
  PREPARE_CANDIDATE = 4,
  BEGIN_VALIDATION = 5,
  POLL_VALIDATION = 6,
  ACTIVATE = 7,
  EXPORT_EVIDENCE = 8,
  CLEANUP_TEST_STATE = 9,
  QUIESCE_FOR_REBOOT = 10,
};

enum class IsolatedAcceptanceFailure : uint8_t {
  NONE = 0,
  INVALID_CONFIGURATION = 1,
  INVALID_STATE = 2,
  READ_ONLY_INSPECTION_FAILED = 3,
  TEST_KEY_REQUIRED = 4,
  TEST_CONFIGURATION_INVALID = 5,
  GENERATION_MISMATCH = 6,
  AUTHORIZATION_INVALID = 7,
  AUTHORIZATION_NOT_ARMED = 8,
  AUTHORIZATION_NOT_CONSUMED = 9,
  PREPARE_FAILED = 10,
  VALIDATION_START_FAILED = 11,
  VALIDATION_FAILED = 12,
  ACTIVATION_FAILED = 13,
  EVIDENCE_EXPORT_FAILED = 14,
  CLEANUP_REQUIRES_EVIDENCE = 15,
  CLEANUP_FAILED = 16,
  REBOOT_REQUIRED = 17,
};

enum class IsolatedAcceptanceWriteOperation : uint8_t {
  PREPARE_CANDIDATE = 0,
  ACTIVATE_PROFILE = 1,
  CLEANUP_TEST_STATE = 2,
};

struct IsolatedCandidateProfile {
  std::string schema;
  std::string test_run_id;
  std::string system_id;
  std::string node_id;
  std::string broker_host;
  uint16_t broker_port{0};
  std::string broker_tls_server_name;
  std::string ca_pem;
  std::string mqtt_username;
  std::string mqtt_client_id;
  std::string mqtt_password;
  std::string test_topic_root;
  uint32_t credential_generation{0};

  bool valid() const;
  void clear();
};

struct IsolatedAcceptanceTestConfiguration {
  std::string schema;
  std::string firmware_commit_sha;
  std::string configuration_digest;
  std::string broker_configuration_digest;
  std::string test_device_identifier;
  IsolatedCandidateProfile candidate{};

  bool valid() const;
  void clear();
};

struct IsolatedAcceptanceDriverSnapshot {
  bool read_only_observed{false};
  uint32_t active_generation{0};
  uint32_t candidate_generation{0};
  std::string persistence_status{"unknown"};
  std::string controller_phase{"unknown"};
  bool active_session_live{false};
  bool candidate_session_live{false};
  bool probe_session_live{false};
  bool validation_complete{false};
  bool validation_success{false};
  bool activation_complete{false};
  bool activation_success{false};
  bool marker_last_observed{false};
  bool rollback_completed{false};
  bool cleanup_confirmed{false};
  bool reboot_required{false};
  uint32_t persistent_write_count{0};
  std::string failure_injection_point{"none"};
  std::string rollback_result{"not_applicable"};
};

static constexpr size_t ISOLATED_ACCEPTANCE_MAX_TRANSITIONS = 32;

struct IsolatedAcceptanceTransitionEvidence {
  uint32_t sequence{0};
  IsolatedAcceptancePhase from_phase{IsolatedAcceptancePhase::COLD};
  IsolatedAcceptancePhase to_phase{IsolatedAcceptancePhase::COLD};
  IsolatedAcceptanceCommand command{IsolatedAcceptanceCommand::NONE};
  IsolatedAcceptanceFailure failure{IsolatedAcceptanceFailure::NONE};
  uint32_t active_generation{0};
  uint32_t candidate_generation{0};
  bool authorization_consumed{false};
};

class IsolatedAcceptanceDriver {
 public:
  virtual ~IsolatedAcceptanceDriver() = default;

  virtual bool inspect_read_only(IsolatedAcceptanceDriverSnapshot *snapshot) = 0;
  virtual bool prepare_candidate(
      const IsolatedCandidateProfile &candidate,
      IsolatedAcceptanceDriverSnapshot *snapshot) = 0;
  virtual bool begin_validation(IsolatedAcceptanceDriverSnapshot *snapshot) = 0;
  virtual bool poll_validation(uint32_t elapsed_ms,
                               IsolatedAcceptanceDriverSnapshot *snapshot) = 0;
  virtual bool activate(ProfileLifecycleMutationAuthorizer *authorizer,
                        IsolatedAcceptanceDriverSnapshot *snapshot) = 0;
  virtual bool cleanup_test_state(
      IsolatedAcceptanceDriverSnapshot *snapshot) = 0;
  virtual void quiesce_for_reboot() = 0;
};

class IsolatedAcceptanceEvidenceSink {
 public:
  virtual ~IsolatedAcceptanceEvidenceSink() = default;
  virtual bool write_redacted_json(const std::string &json) = 0;
};

class VolatileTestPersistenceKeyProvider final : public PersistenceKeyProvider {
 public:
  VolatileTestPersistenceKeyProvider() = default;
  ~VolatileTestPersistenceKeyProvider() override;

  VolatileTestPersistenceKeyProvider(
      const VolatileTestPersistenceKeyProvider &) = delete;
  VolatileTestPersistenceKeyProvider &operator=(
      const VolatileTestPersistenceKeyProvider &) = delete;

  bool load(const std::array<uint8_t, 32> &key_material);
  void destroy();
  bool loaded() const { return this->loaded_; }

  bool derive_key(CredentialSlot slot, uint32_t generation,
                  std::array<uint8_t, 32> *key) override;

 protected:
  static void zeroize_(void *data, size_t length);

  std::array<uint8_t, 32> key_material_{};
  bool loaded_{false};
};

class OneShotGenerationAuthorization final
    : public ProfileLifecycleMutationAuthorizer {
 public:
  bool arm(IsolatedAcceptanceWriteOperation operation,
           uint32_t active_generation, uint32_t candidate_generation,
           const std::string &authorization_digest);
  bool consume(IsolatedAcceptanceWriteOperation operation,
               uint32_t active_generation, uint32_t candidate_generation);
  bool authorize(ProfileLifecycleMutationOperation operation,
                 uint32_t active_generation,
                 uint32_t candidate_generation) override;
  void clear();
  void acknowledge_consumption() { this->consumed_ = false; }

  bool armed() const { return this->armed_; }
  bool consumed() const { return this->consumed_; }
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
  bool consumed_{false};
};

struct IsolatedAcceptancePackageSnapshot {
  IsolatedAcceptancePhase phase{IsolatedAcceptancePhase::COLD};
  IsolatedAcceptanceCommand last_command{IsolatedAcceptanceCommand::NONE};
  IsolatedAcceptanceFailure failure{IsolatedAcceptanceFailure::NONE};
  uint32_t active_generation{0};
  uint32_t candidate_generation{0};
  bool test_key_loaded{false};
  bool test_configuration_loaded{false};
  bool write_authorization_armed{false};
  bool write_authorization_consumed{false};
  bool evidence_exported{false};
  bool cleanup_confirmed{false};
  bool reboot_required{false};
  uint32_t transition_count{0};
  std::array<IsolatedAcceptanceTransitionEvidence,
             ISOLATED_ACCEPTANCE_MAX_TRANSITIONS>
      transitions{};
  size_t transition_record_count{0};
  bool transition_history_truncated{false};
  IsolatedAcceptanceDriverSnapshot driver{};
};

class IsolatedAcceptancePackage {
 public:
  bool configure(IsolatedAcceptanceDriver *driver,
                 VolatileTestPersistenceKeyProvider *test_key_provider,
                 IsolatedAcceptanceEvidenceSink *evidence_sink);

  bool inspect_read_only();
  bool load_test_configuration(IsolatedAcceptanceTestConfiguration config);
  bool grant_write_authorization(
      IsolatedAcceptanceWriteOperation operation, uint32_t active_generation,
      uint32_t candidate_generation,
      const std::string &authorization_digest);
  bool prepare_candidate();
  bool begin_validation();
  bool poll_validation(uint32_t elapsed_ms);
  bool activate();
  bool export_evidence();
  bool cleanup_test_state();
  void quiesce_for_reboot();

  const IsolatedAcceptancePackageSnapshot &snapshot() const {
    return this->snapshot_;
  }

  static const char *phase_name(IsolatedAcceptancePhase phase);
  static const char *command_name(IsolatedAcceptanceCommand command);
  static const char *failure_name(IsolatedAcceptanceFailure failure);
  static const char *write_operation_name(
      IsolatedAcceptanceWriteOperation operation);
  static bool valid_hex_(const std::string &value, size_t length);

 protected:
  bool reject_(IsolatedAcceptanceFailure failure);
  bool fail_(IsolatedAcceptanceFailure failure,
             bool reboot_required = false);
  bool exact_generation_pair_(uint32_t active_generation,
                              uint32_t candidate_generation) const;
  bool evidence_metadata_available_() const;
  void transition_(IsolatedAcceptancePhase phase,
                   IsolatedAcceptanceCommand command);
  void record_transition_(IsolatedAcceptancePhase from_phase,
                          IsolatedAcceptancePhase to_phase,
                          IsolatedAcceptanceCommand command,
                          IsolatedAcceptanceFailure failure);
  void refresh_driver_snapshot_(
      const IsolatedAcceptanceDriverSnapshot &driver_snapshot);
  std::string evidence_json_() const;
  static std::string json_escape_(const std::string &value);
  static void secure_clear_(std::string *value);

  IsolatedAcceptanceDriver *driver_{nullptr};
  VolatileTestPersistenceKeyProvider *test_key_provider_{nullptr};
  IsolatedAcceptanceEvidenceSink *evidence_sink_{nullptr};
  OneShotGenerationAuthorization authorization_{};
  IsolatedAcceptanceTestConfiguration configuration_{};
  IsolatedAcceptancePackageSnapshot snapshot_{};

  // Non-secret evidence metadata survives secret cleanup.
  std::string evidence_firmware_commit_sha_{};
  std::string evidence_configuration_digest_{};
  std::string evidence_broker_configuration_digest_{};
  std::string evidence_test_device_identifier_{};
  std::string evidence_test_run_id_{};
};

}  // namespace esphome::greenhouse_pairing_client
