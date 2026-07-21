#pragma once

#include <algorithm>
#include <cinttypes>
#include <cstddef>
#include <cstdint>
#include <string>

#include "esphome/core/component.h"
#include "pairing_client_core.h"
#include "pairing_network_transport.h"
#include "pairing_ram_credentials.h"

namespace esphome::greenhouse_pairing_client {

class GreenhousePairingClient final : public Component {
 public:
  ~GreenhousePairingClient();

  void set_hardware_id(const std::string &value) { this->hardware_id_ = value; }
  void set_pairing_id(const std::string &value) { this->pairing_id_ = value; }
  void set_pairing_secret(const std::string &value) { this->pairing_secret_ = value; }
  void set_max_candidates(size_t value) { this->max_candidates_ = value; }
  void set_candidate_ttl_cap_s(uint16_t value) { this->candidate_ttl_cap_s_ = value; }
  void set_network_enabled(bool value) { this->network_options_.enabled = value; }
  void set_mdns_enabled(bool value) { this->network_options_.mdns_enabled = value; }
  void set_udp_enabled(bool value) { this->network_options_.udp_enabled = value; }
  void set_udp_target(const std::string &value) { this->network_options_.udp_target = value; }
  void set_udp_port(uint16_t value) { this->network_options_.limits.udp_port = value; }
  void set_udp_attempts(uint8_t value) { this->network_options_.limits.udp_attempts = value; }
  void set_udp_initial_backoff_ms(uint32_t value) {
    this->network_options_.limits.udp_initial_backoff_ms = value;
  }
  void set_mdns_timeout_ms(uint32_t value) { this->network_options_.limits.mdns_timeout_ms = value; }
  void set_http_timeout_ms(uint32_t value) { this->network_options_.limits.http_timeout_ms = value; }
  void set_response_max_bytes(size_t value) {
    this->network_options_.limits.response_max_bytes = value;
  }

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override;

  bool start_discovery(const std::string &request_id, const std::string &nonce);
  bool start_random_discovery();
  bool observe_candidate(const std::string &manager_id, const std::string &system_id,
                         const std::string &host, const std::string &scheme, uint16_t port,
                         const std::string &pairing_path, uint16_t priority, uint16_t ttl_s);
  bool discover_network();
  bool complete_network_pairing();
  bool run_network_pairing_once();
  bool select_candidate(size_t index);
  bool mark_claim_sent();
  bool accept_secure_offer_for_test(const std::string &session_id, const std::string &manager_nonce,
                                    const std::string &manager_public_key,
                                    const std::string &cipher_suite);
  bool mark_channel_established_for_test();
  bool stage_credentials_for_test(const std::string &node_id, uint32_t credential_generation);
  bool commit_credentials_for_test();
  void reset_unbound();

  std::string build_discovery_request_json() const;
  std::string build_claim_request_json() const;

  const char *state_name() const { return this->core_.state_name(); }
  const char *error_name() const { return this->core_.error_name(); }
  const char *network_result_name() const { return this->network_.last_result_name(); }
  size_t candidate_count() const { return this->core_.snapshot().candidate_count; }
  bool selection_required() const { return this->core_.snapshot().selection_required; }
  bool candidate_selected() const { return this->core_.snapshot().candidate_selected; }
  bool pairing_secret_present() const { return !this->pairing_secret_.empty(); }
  bool ram_credentials_present() const { return this->ram_credentials_.present(); }
  bool local_operation_healthy() const { return !this->is_failed(); }
  const std::string &node_id() const { return this->core_.node_id(); }
  uint32_t credential_generation() const { return this->core_.snapshot().credential_generation; }

 protected:
  static std::string json_escape_(const std::string &value);
  bool claim_proof_(std::string *output) const;
  static bool decode_pairing_secret_(const std::string &value, uint8_t output[32]);
  static bool encode_base64url_(const uint8_t *data, size_t length, std::string *output);
  static bool random_discovery_context_(std::string *request_id, std::string *nonce);
  void clear_pairing_secret_();

  PairingClientCore core_;
  PairingNetworkTransport network_;
  PairingNetworkOptions network_options_{};
  RamCredentialBundle ram_credentials_{};
  std::string hardware_id_;
  std::string pairing_id_;
  std::string pairing_secret_;
  size_t max_candidates_{4};
  uint16_t candidate_ttl_cap_s_{120};
  uint32_t last_prune_ms_{0};
};

}  // namespace esphome::greenhouse_pairing_client
