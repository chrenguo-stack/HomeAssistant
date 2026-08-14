#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace esphome::greenhouse_n3w_product_core {

constexpr std::size_t kProductMacBytes = 6;
using MacAddress = std::array<uint8_t, kProductMacBytes>;

enum class ProductCoreError : uint8_t {
  NONE = 0,
  INVALID_ARGUMENT,
  POLICY_INVALID,
  CAPACITY_EXHAUSTED,
  NOT_FOUND,
  STATE_REJECTED,
  AUTHORIZATION_REJECTED,
  EXPIRED,
};

bool valid_identity(const std::string &value);
bool valid_channel(uint8_t channel);
bool same_mac(const MacAddress &left, const MacAddress &right);

enum class WifiDirectHealthState : uint8_t {
  HEALTHY = 0,
  DEGRADED,
  UNAVAILABLE,
  RECOVERING,
};

struct WifiDirectHealthPolicy {
  uint8_t failures_to_degraded{1};
  uint8_t failures_to_unavailable{3};
  uint8_t recoveries_to_healthy{3};

  bool valid() const;
};

class WifiDirectHealthDetector {
 public:
  explicit WifiDirectHealthDetector(WifiDirectHealthPolicy policy) : policy_(policy) {}

  ProductCoreError note_direct_result(bool success);
  ProductCoreError note_recovery_probe(bool success);
  WifiDirectHealthState state() const { return state_; }
  uint8_t consecutive_failures() const { return failures_; }
  uint8_t consecutive_recoveries() const { return recoveries_; }

 private:
  WifiDirectHealthPolicy policy_{};
  WifiDirectHealthState state_{WifiDirectHealthState::HEALTHY};
  uint8_t failures_{0};
  uint8_t recoveries_{0};
};

struct RelayCandidateObservation {
  std::string gateway_id;
  MacAddress source_mac{};
  uint8_t channel{0};
  int16_t rssi_dbm{-127};
  uint32_t advertisement_generation{0};
  uint64_t observed_at_ms{0};

  bool valid() const;
};

struct RelayCandidateEligibility {
  bool manager_verified{false};
  bool registered{false};
  bool same_system{false};
  bool wifi_up{false};
  bool uplink_available{false};
  bool direct_uplink{false};
  bool relay_capable{false};
  bool low_battery{true};
  bool overloaded{true};
  bool retired{true};
  bool revoked{true};
  uint8_t uplink_quality_pct{0};
  uint8_t load_pct{100};
  uint8_t battery_pct{0};
  uint32_t credential_generation{0};
  uint64_t verified_at_ms{0};
  uint64_t valid_until_ms{0};

  bool valid_shape() const;
  bool eligible_at(uint64_t now_ms) const;
};

struct RelayCandidateRecord {
  RelayCandidateObservation observation{};
  RelayCandidateEligibility eligibility{};
  bool has_eligibility{false};
};

struct RelayCandidatePolicy {
  std::size_t capacity{8};
  uint64_t observation_ttl_ms{15000};
  int16_t minimum_rssi_dbm{-92};
  int32_t switch_score_margin{12};
  uint64_t minimum_hold_ms{30000};

  bool valid() const;
};

class RelayCandidateTable {
 public:
  explicit RelayCandidateTable(RelayCandidatePolicy policy) : policy_(policy) {}

  ProductCoreError observe(const RelayCandidateObservation &observation);
  ProductCoreError apply_manager_eligibility(
      const MacAddress &source_mac,
      const std::string &gateway_id,
      const RelayCandidateEligibility &eligibility);
  void prune(uint64_t now_ms);
  std::size_t size() const { return records_.size(); }
  const RelayCandidateRecord *find(const MacAddress &source_mac) const;
  bool select(
      const std::optional<MacAddress> &current_mac,
      uint64_t current_since_ms,
      uint64_t now_ms,
      RelayCandidateRecord *selected) const;
  int32_t score(const RelayCandidateRecord &record) const;

 private:
  bool observation_fresh_(const RelayCandidateRecord &record, uint64_t now_ms) const;
  bool eligible_(const RelayCandidateRecord &record, uint64_t now_ms) const;

  RelayCandidatePolicy policy_{};
  std::vector<RelayCandidateRecord> records_{};
};

enum class DynamicPeerState : uint8_t {
  EMPTY = 0,
  DISCOVERED,
  AUTHORIZING,
  AUTHORIZED,
  ACTIVE,
  EXPIRED,
  REVOKED,
};

struct DynamicPeerAuthorization {
  std::string authorization_id;
  std::string gateway_id;
  MacAddress peer_mac{};
  uint8_t channel{0};
  uint32_t relay_credential_generation{0};
  uint64_t issued_at_ms{0};
  uint64_t expires_at_ms{0};
  bool manager_authorized{false};
  bool same_system{false};

  bool valid_shape() const;
};

class DynamicPeerLifecycle {
 public:
  ProductCoreError observe(const RelayCandidateRecord &candidate);
  ProductCoreError begin_authorization();
  ProductCoreError accept_authorization(
      const DynamicPeerAuthorization &authorization,
      uint64_t now_ms);
  ProductCoreError activate(uint64_t now_ms);
  void reject_authorization();
  bool maintenance(uint64_t now_ms);
  void revoke();
  void reset();

  DynamicPeerState state() const { return state_; }
  bool telemetry_allowed(uint64_t now_ms) const;
  const std::optional<DynamicPeerAuthorization> &authorization() const {
    return authorization_;
  }

 private:
  bool authorization_matches_candidate_(
      const DynamicPeerAuthorization &authorization) const;

  DynamicPeerState state_{DynamicPeerState::EMPTY};
  std::optional<RelayCandidateRecord> candidate_{};
  std::optional<DynamicPeerAuthorization> authorization_{};
};

enum class AutoPathState : uint8_t {
  DIRECT = 0,
  DIRECT_DEGRADED,
  DISCOVERY,
  RELAY_AUTH,
  RELAY_ACTIVE,
  REDISCOVERY,
  DIRECT_RECOVERY,
};

struct AutoPathPolicy {
  uint8_t relay_failures_to_rediscovery{2};

  bool valid() const { return relay_failures_to_rediscovery > 0; }
};

class AutoPathStateMachine {
 public:
  explicit AutoPathStateMachine(AutoPathPolicy policy) : policy_(policy) {}

  ProductCoreError on_direct_health(WifiDirectHealthState health);
  ProductCoreError on_candidate_selected();
  ProductCoreError on_relay_authorization(bool accepted);
  ProductCoreError on_relay_result(bool success);
  ProductCoreError on_peer_lost();
  ProductCoreError on_rediscovery_cycle();

  AutoPathState state() const { return state_; }

 private:
  static bool relay_side_state_(AutoPathState state);

  AutoPathPolicy policy_{};
  AutoPathState state_{AutoPathState::DIRECT};
  AutoPathState pre_recovery_state_{AutoPathState::REDISCOVERY};
  uint8_t relay_failures_{0};
};

class RelayOrchestrationCore {
 public:
  RelayOrchestrationCore(
      WifiDirectHealthPolicy direct_policy,
      RelayCandidatePolicy candidate_policy,
      AutoPathPolicy path_policy)
      : direct_health_(direct_policy),
        candidates_(candidate_policy),
        path_(path_policy) {}

  ProductCoreError note_direct_result(bool success, uint64_t now_ms);
  ProductCoreError note_direct_recovery_probe(bool success, uint64_t now_ms);
  ProductCoreError observe_candidate(const RelayCandidateObservation &observation);
  ProductCoreError apply_manager_eligibility(
      const MacAddress &source_mac,
      const std::string &gateway_id,
      const RelayCandidateEligibility &eligibility);
  ProductCoreError select_candidate(uint64_t now_ms);
  ProductCoreError accept_peer_authorization(
      const DynamicPeerAuthorization &authorization,
      uint64_t now_ms);
  ProductCoreError reject_peer_authorization();
  ProductCoreError note_relay_result(bool success, uint64_t now_ms);
  void maintenance(uint64_t now_ms);

  AutoPathState path_state() const { return path_.state(); }
  WifiDirectHealthState direct_health_state() const { return direct_health_.state(); }
  DynamicPeerState peer_state() const { return peer_.state(); }
  bool direct_telemetry_ready() const { return path_.state() == AutoPathState::DIRECT; }
  bool relay_telemetry_ready(uint64_t now_ms) const {
    return path_.state() == AutoPathState::RELAY_ACTIVE && peer_.telemetry_allowed(now_ms);
  }
  const std::optional<MacAddress> &selected_mac() const { return selected_mac_; }

 private:
  WifiDirectHealthDetector direct_health_;
  RelayCandidateTable candidates_;
  DynamicPeerLifecycle peer_{};
  AutoPathStateMachine path_;
  std::optional<MacAddress> selected_mac_{};
  uint64_t selected_since_ms_{0};
};

}  // namespace esphome::greenhouse_n3w_product_core
