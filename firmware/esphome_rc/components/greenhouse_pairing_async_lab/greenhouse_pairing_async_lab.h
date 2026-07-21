#pragma once

#include <cstdint>
#include <string>

#include "esphome/core/component.h"
#include "esphome/components/greenhouse_pairing_client/greenhouse_pairing_client.h"
#include "esphome/components/greenhouse_pairing_client/pairing_async_worker.h"

namespace esphome::greenhouse_pairing_async_lab {

using greenhouse_pairing_client::GreenhousePairingClient;
using greenhouse_pairing_client::PairingAsyncDelegate;
using greenhouse_pairing_client::PairingAsyncExecutionContext;
using greenhouse_pairing_client::PairingAsyncOutcome;
using greenhouse_pairing_client::PairingAsyncPhase;
using greenhouse_pairing_client::PairingAsyncSnapshot;
using greenhouse_pairing_client::PairingAsyncWorker;
using greenhouse_pairing_client::PairingClientError;
using greenhouse_pairing_client::PairingClientSnapshot;
using greenhouse_pairing_client::PairingClientState;

class GreenhousePairingAsyncLab final : public Component, protected PairingAsyncDelegate {
 public:
  void set_hardware_id(const std::string &value) { this->client_.set_hardware_id(value); }
  void set_pairing_id(const std::string &value) { this->client_.set_pairing_id(value); }
  void set_pairing_secret(const std::string &value) { this->client_.set_pairing_secret(value); }
  void set_max_candidates(size_t value) { this->client_.set_max_candidates(value); }
  void set_candidate_ttl_cap_s(uint16_t value) { this->client_.set_candidate_ttl_cap_s(value); }
  void set_mdns_enabled(bool value) { this->client_.set_mdns_enabled(value); }
  void set_udp_enabled(bool value) { this->client_.set_udp_enabled(value); }
  void set_udp_target(const std::string &value) { this->client_.set_udp_target(value); }
  void set_udp_port(uint16_t value) { this->client_.set_udp_port(value); }
  void set_udp_attempts(uint8_t value) { this->client_.set_udp_attempts(value); }
  void set_udp_initial_backoff_ms(uint32_t value) {
    this->client_.set_udp_initial_backoff_ms(value);
  }
  void set_mdns_timeout_ms(uint32_t value) { this->client_.set_mdns_timeout_ms(value); }
  void set_http_timeout_ms(uint32_t value) { this->client_.set_http_timeout_ms(value); }
  void set_response_max_bytes(size_t value) { this->client_.set_response_max_bytes(value); }
  void set_worker_stack_size(uint32_t value) { this->worker_stack_size_ = value; }
  void set_worker_priority(uint8_t value) { this->worker_priority_ = value; }

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override;

  bool request_pairing();
  bool cancel_pairing();
  bool select_candidate(size_t index);
  void reset_unbound();

  const char *state_name() const;
  const char *error_name() const;
  const char *network_result_name() const;
  const char *async_phase_name() const;
  const char *async_outcome_name() const;
  bool async_active() const { return this->worker_.active(); }
  bool selection_required() const {
    return this->worker_.active() ? this->async_snapshot_.selection_required
                                  : this->client_.selection_required();
  }
  bool ram_credentials_present() const {
    return this->worker_.active() ? this->async_snapshot_.credentials_staged
                                  : this->client_.ram_credentials_present();
  }
  uint32_t credential_generation() const {
    return this->worker_.active() ? this->async_snapshot_.credential_generation
                                  : this->client_.credential_generation();
  }

 protected:
  PairingAsyncOutcome execute_async_pairing(PairingAsyncExecutionContext *context) override;
  PairingClientSnapshot async_client_snapshot() const override;

  static const char *state_to_name_(PairingClientState value);
  static const char *error_to_name_(PairingClientError value);
  static PairingClientState state_from_name_(const char *value);
  static PairingClientError error_from_name_(const char *value);

  GreenhousePairingClient client_{};
  PairingAsyncWorker worker_{};
  PairingAsyncSnapshot async_snapshot_{};
  uint32_t next_operation_id_{1};
  uint32_t worker_stack_size_{8192};
  uint8_t worker_priority_{1};
};

}  // namespace esphome::greenhouse_pairing_async_lab
