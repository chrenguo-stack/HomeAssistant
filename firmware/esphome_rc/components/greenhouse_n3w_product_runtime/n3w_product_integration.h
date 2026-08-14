#pragma once

#include <memory>
#include <optional>
#include <string>

#include "esphome/core/component.h"
#include "n3w_product_runtime.h"

namespace esphome::greenhouse_n3w_product_runtime {

class GreenhouseN3wProductIntegration final : public Component,
                                               public ProductRuntimeClock,
                                               public ProductManagerIntegrationPort {
 public:
  void set_execution_enabled(bool value) { execution_enabled_ = value; }
  void set_role(const std::string &value) { role_ = value; }
  void set_pmk_hex(const std::string &value) { pmk_hex_ = value; }
  void set_last_direct_channel(uint8_t value) { last_direct_channel_ = value; }

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

  bool manager_eligibility_requested() const { return eligibility_requested_; }
  bool peer_authorization_requested() const { return authorization_requested_; }
  const std::optional<RelayCandidateRecord> &pending_manager_candidate() const {
    return pending_manager_candidate_;
  }

 private:
  static bool parse_hex_key_(const std::string &value, LinkKey *output);

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
};

}  // namespace esphome::greenhouse_n3w_product_runtime
