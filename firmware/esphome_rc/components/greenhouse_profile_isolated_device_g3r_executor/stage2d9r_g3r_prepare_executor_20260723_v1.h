#pragma once

#include <array>
#include <cstdint>
#include <string>
#include <vector>

#include "esphome/core/component.h"
#include "../greenhouse_profile_isolated_device_driver/isolated_device_driver.h"
#include "../greenhouse_profile_isolated_device_driver/isolated_device_esp32_ports.h"
#include "../greenhouse_profile_isolated_device_g3_prepare/stage2d9_g3_locked_prepare_harness.h"

#ifndef mbedtls_sha256_ret
#define mbedtls_sha256_ret mbedtls_sha256
#endif

namespace esphome::greenhouse_pairing_client {

struct Stage2D9RCommandEnvelopeV1 {
  bool verify_only{false};
  std::string run_suffix{};
  std::array<uint8_t, 32> unlock_token{};
  std::array<uint8_t, 32> persistence_key{};
  std::string authorization_digest{};
  std::string ca_pem{};
  std::string ca_pem_sha256{};
  std::string candidate_digest{};

  void clear();
};

class Stage2D9RG3RPrepareExecutorV1 final : public Component {
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
  void set_unlock_digest(const std::string &value) {
    this->unlock_digest_ = value;
  }
  void set_ca_pem_sha256(const std::string &value) {
    this->ca_pem_sha256_ = value;
  }

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override;

 protected:
  enum class AwaitingCommand : uint8_t {
    NONE = 0,
    PREPARE = 1,
    VERIFY = 2,
  };

  bool verify_partition_();
  bool initialize_partition_();
  bool namespace_exists_(bool *exists);
  bool configure_runtime_();
  bool inspect_empty_();
  bool parse_command_(const std::string &line,
                      Stage2D9RCommandEnvelopeV1 *envelope) const;
  bool parse_prepare_(const std::vector<std::string> &fields,
                      Stage2D9RCommandEnvelopeV1 *envelope) const;
  bool parse_verify_(const std::vector<std::string> &fields,
                     Stage2D9RCommandEnvelopeV1 *envelope) const;
  bool execute_prepare_(Stage2D9RCommandEnvelopeV1 *envelope);
  bool execute_verify_(Stage2D9RCommandEnvelopeV1 *envelope);
  bool verify_recovered_candidate_(const std::string &expected_digest,
                                   uint32_t expected_generation);
  IsolatedAcceptanceTestConfiguration build_configuration_(
      const Stage2D9RCommandEnvelopeV1 &envelope) const;
  bool build_candidate_digest_(const RamCredentialBundle &bundle,
                               std::string *digest) const;
  bool expected_candidate_digest_(
      const Stage2D9RCommandEnvelopeV1 &envelope,
      std::string *digest) const;
  void read_console_();
  void process_line_(std::string line);
  void emit_snapshot_(const char *label) const;
  void emit_failure_detail_(const char *stage) const;
  bool fail_step_(const char *stage);
  void fail_closed_(const char *reason);
  void close_partition_();
  void wipe_runtime_();

  static bool all_zero_hex_(const std::string &value);
  static bool valid_lower_hex_(const std::string &value, size_t length);
  static bool valid_suffix_(const std::string &value);
  static bool decode_hex_32_(const std::string &value,
                             std::array<uint8_t, 32> *output);
  static bool sha256_(const uint8_t *data, size_t length,
                      std::array<uint8_t, 32> *output);
  static std::string hex_(const std::array<uint8_t, 32> &value);
  static bool constant_equal_(const std::string &left,
                              const std::string &right);
  static bool validate_ca_pem_(const std::string &value);

  std::string partition_label_{};
  std::string namespace_name_{};
  std::string build_binding_{};
  std::string unlock_digest_{};
  std::string ca_pem_sha256_{};
  std::string input_buffer_{};
  std::string failure_stage_{"none"};

  VolatileTestPersistenceKeyProvider test_key_provider_{};
  EspIdfIsolatedPersistencePort persistence_{};
  Stage2D9NullMqttPort mqtt_{};
  IsolatedDeviceDriver driver_{};
  Stage2D9SerialEvidenceSink evidence_sink_{};
  IsolatedAcceptancePackage package_{};
  IsolatedDeviceAuthorizationBinder authorization_binder_{};

  AwaitingCommand awaiting_{AwaitingCommand::NONE};
  bool partition_verified_{false};
  bool partition_initialized_{false};
  bool configured_{false};
  bool command_surface_enabled_{false};
  bool command_attempted_{false};
  bool command_accepted_{false};
  bool prepare_succeeded_{false};
  bool verify_succeeded_{false};
  bool terminal_{false};
};

}  // namespace esphome::greenhouse_pairing_client
