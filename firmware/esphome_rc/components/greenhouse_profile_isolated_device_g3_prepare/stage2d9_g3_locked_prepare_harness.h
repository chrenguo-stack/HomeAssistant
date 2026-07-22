#pragma once

#include <string>

#include "esphome/core/component.h"
#include "../greenhouse_profile_isolated_acceptance/isolated_acceptance_package.h"
#include "../greenhouse_profile_isolated_device_driver/isolated_device_driver.h"
#include "../greenhouse_profile_isolated_device_driver/isolated_device_esp32_ports.h"

namespace esphome::greenhouse_pairing_client {

class Stage2D9NullMqttPort final : public IsolatedDeviceMqttPort {
 public:
  bool configure(const RamCredentialBundle *active_credentials,
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

  bool operation_attempted() const { return this->operation_attempted_; }

 protected:
  bool reject_(IsolatedDeviceMqttSnapshot *snapshot, const char *point);
  bool operation_attempted_{false};
};

class Stage2D9SerialEvidenceSink final : public IsolatedAcceptanceEvidenceSink {
 public:
  bool write_redacted_json(const std::string &json) override;
};

class Stage2D9G3LockedPrepareHarness final : public Component {
 public:
  void set_partition_label(const std::string &value) {
    this->partition_label_ = value;
  }
  void set_namespace_name(const std::string &value) {
    this->namespace_name_ = value;
  }
  void set_build_binding(const std::string &value) {
    this->build_binding_ = value;
  }

  void setup() override;
  void dump_config() override;
  float get_setup_priority() const override;

 protected:
  void emit_snapshot_() const;
  void close_partition_();
  void fail_closed_(const char *reason);

  std::string partition_label_{};
  std::string namespace_name_{};
  std::string build_binding_{};

  VolatileTestPersistenceKeyProvider test_key_provider_{};
  EspIdfIsolatedPersistencePort persistence_{};
  Stage2D9NullMqttPort mqtt_{};
  IsolatedDeviceDriver driver_{};
  Stage2D9SerialEvidenceSink evidence_sink_{};
  IsolatedAcceptancePackage package_{};

  bool partition_verified_writable_capable_{false};
  bool partition_initialized_{false};
  bool configured_{false};
  bool inspection_attempted_{false};
  bool inspection_passed_{false};
  bool prepare_attempted_{false};
};

}  // namespace esphome::greenhouse_pairing_client
