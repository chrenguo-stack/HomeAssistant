#pragma once

#include <memory>
#include <optional>
#include <string>

#include "esphome/core/component.h"
#include "n3w_product_runtime.h"
#include "n3w_product_s5_peer_coordinator.h"
#include "n3w_product_s5_telemetry.h"

namespace esphome::greenhouse_n3w_product_runtime {

// S5 may load only this node's own post-registration runtime material. The
// interface intentionally has no peer argument and cannot return a peer MAC,
// peer NODE_ID, pair LMK, Wi-Fi credential, or Manager address.
class ProductS5SelfCredentialProvider {
 public:
  virtual ~ProductS5SelfCredentialProvider() = default;
  virtual bool load_self(
      ProductS5NodeCredentials *credentials,
      MacAddress *local_mac) = 0;
};

class GreenhouseN3wProductIntegration final : public Component,
                                               public ProductRuntimeClock,
                                               public ProductManagerIntegrationPort {
 public:
  void set_execution_enabled(bool value) { execution_enabled_ = value; }
  void set_role(const std::string &value) { role_ = value; }
  void set_pmk_hex(const std::string &value) { pmk_hex_ = value; }
  void set_last_direct_channel(uint8_t value) { last_direct_channel_ = value; }

  // Isolated S5 composition is enabled only when a private runtime provides
  // this node's own credential provider. Public/factory profiles never call
  // this method and therefore retain the frozen inert S3/S4 board path.
  void configure_s5_isolated(
      ProductS5SelfCredentialProvider *self_credentials,
      ProductS5RelayHealthProvider *relay_health,
      ProductS5ManagerPort *manager,
      RelayForwardSink *relay_forward_sink = nullptr);

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override;
  uint64_t now_ms() const override;

  bool request_manager_eligibility(const RelayCandidateRecord &candidate) override;
  bool poll_manager_eligibility(ManagerEligibilityDecision *decision) override;
  bool request_peer_authorization(const RelayCandidateRecord &candidate) override;
  bool poll_peer_authorization(ManagerPeerAuthorizationDecision *decision) override;

  bool submit_manager_eligibility(const ManagerEligibilityDecision &decision);
  bool submit_peer_authorization(const ManagerPeerAuthorizationDecision &decision);
  ProductRuntimeError note_direct_result(bool success);

  ProductS5CoordinatorError submit_s5_manager_authorization(
      const ProductPeerGrant &child_grant,
      const ProductPeerGrant &relay_grant);
  ProductS5TelemetryError send_s5_relay_frame(
      const RelayFrame &frame,
      uint64_t now_ms);

  bool manager_eligibility_requested() const { return eligibility_requested_; }
  bool peer_authorization_requested() const { return authorization_requested_; }
  bool s5_isolated_configured() const { return s5_self_credentials_ != nullptr; }
  const std::optional<RelayCandidateRecord> &pending_manager_candidate() const {
    return pending_manager_candidate_;
  }

 private:
  static bool parse_hex_key_(const std::string &value, LinkKey *output);
  static void zeroize_(void *data, std::size_t length);
  bool setup_s5_isolated_();

  bool execution_enabled_{false};
  std::string role_{"child"};
  std::string pmk_hex_{};
  uint8_t last_direct_channel_{1};
  LinkKey pmk_{};
  bool eligibility_requested_{false};
  bool authorization_requested_{false};
  std::optional<RelayCandidateRecord> pending_manager_candidate_{};
  std::optional<ManagerEligibilityDecision> eligibility_decision_{};
  std::optional<ManagerPeerAuthorizationDecision> authorization_decision_{};
  EspNowDriverRuntimePort radio_{};
  std::unique_ptr<ProductEspNowRuntime> runtime_{};
  std::unique_ptr<ProductRuntimeCoordinator> coordinator_{};

  ProductS5SelfCredentialProvider *s5_self_credentials_{nullptr};
  ProductS5RelayHealthProvider *s5_relay_health_{nullptr};
  ProductS5ManagerPort *s5_manager_{nullptr};
  RelayForwardSink *s5_relay_forward_sink_{nullptr};
  ProductS5CryptoRandomSource s5_random_{};
  std::unique_ptr<ProductS5PeerCoordinator> s5_coordinator_{};
  std::unique_ptr<ProductS5RadioMux> s5_radio_mux_{};
  std::unique_ptr<ProductS5TelemetryBridge> s5_telemetry_{};
};

}  // namespace esphome::greenhouse_n3w_product_runtime
