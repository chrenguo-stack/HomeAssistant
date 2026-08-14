#include "n3w_product_core.h"

#include <algorithm>
#include <limits>

namespace esphome::greenhouse_n3w_product_core {
namespace {

uint8_t saturating_increment(uint8_t value) {
  return value == std::numeric_limits<uint8_t>::max()
             ? value
             : static_cast<uint8_t>(value + 1U);
}

bool zero_mac(const MacAddress &mac) {
  return std::all_of(mac.begin(), mac.end(), [](uint8_t value) { return value == 0; });
}

}  // namespace

bool valid_identity(const std::string &value) {
  if (value.empty() || value.size() > 96) return false;
  return std::all_of(value.begin(), value.end(), [](unsigned char ch) {
    return (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') ||
           (ch >= '0' && ch <= '9') || ch == '_' || ch == '-';
  });
}

bool valid_channel(uint8_t channel) { return channel >= 1 && channel <= 14; }

bool same_mac(const MacAddress &left, const MacAddress &right) { return left == right; }

bool WifiDirectHealthPolicy::valid() const {
  return failures_to_degraded > 0 && failures_to_unavailable >= failures_to_degraded &&
         recoveries_to_healthy > 0;
}

ProductCoreError WifiDirectHealthDetector::note_direct_result(bool success) {
  if (!policy_.valid()) return ProductCoreError::POLICY_INVALID;
  if (state_ == WifiDirectHealthState::UNAVAILABLE ||
      state_ == WifiDirectHealthState::RECOVERING) {
    return ProductCoreError::STATE_REJECTED;
  }
  if (success) {
    failures_ = 0;
    recoveries_ = 0;
    state_ = WifiDirectHealthState::HEALTHY;
    return ProductCoreError::NONE;
  }

  recoveries_ = 0;
  failures_ = saturating_increment(failures_);
  if (failures_ >= policy_.failures_to_unavailable) {
    state_ = WifiDirectHealthState::UNAVAILABLE;
  } else if (failures_ >= policy_.failures_to_degraded) {
    state_ = WifiDirectHealthState::DEGRADED;
  }
  return ProductCoreError::NONE;
}

ProductCoreError WifiDirectHealthDetector::note_recovery_probe(bool success) {
  if (!policy_.valid()) return ProductCoreError::POLICY_INVALID;
  if (state_ != WifiDirectHealthState::UNAVAILABLE &&
      state_ != WifiDirectHealthState::RECOVERING) {
    return ProductCoreError::STATE_REJECTED;
  }
  if (!success) {
    recoveries_ = 0;
    state_ = WifiDirectHealthState::UNAVAILABLE;
    return ProductCoreError::NONE;
  }

  recoveries_ = saturating_increment(recoveries_);
  if (recoveries_ >= policy_.recoveries_to_healthy) {
    failures_ = 0;
    recoveries_ = 0;
    state_ = WifiDirectHealthState::HEALTHY;
  } else {
    state_ = WifiDirectHealthState::RECOVERING;
  }
  return ProductCoreError::NONE;
}

bool RelayCandidateObservation::valid() const {
  return valid_identity(gateway_id) && !zero_mac(source_mac) && valid_channel(channel) &&
         rssi_dbm >= -127 && rssi_dbm <= 0;
}

bool RelayCandidateEligibility::valid_shape() const {
  return uplink_quality_pct <= 100 && load_pct <= 100 && battery_pct <= 100 &&
         credential_generation > 0 && valid_until_ms > verified_at_ms;
}

bool RelayCandidateEligibility::eligible_at(uint64_t now_ms) const {
  if (!valid_shape() || now_ms < verified_at_ms || now_ms >= valid_until_ms) return false;
  return manager_verified && registered && same_system && wifi_up && uplink_available &&
         direct_uplink && relay_capable && !low_battery && !overloaded && !retired && !revoked;
}

bool RelayCandidatePolicy::valid() const {
  return capacity > 0 && observation_ttl_ms > 0 && minimum_rssi_dbm >= -127 &&
         minimum_rssi_dbm <= 0 && switch_score_margin >= 0;
}

ProductCoreError RelayCandidateTable::observe(const RelayCandidateObservation &observation) {
  if (!policy_.valid()) return ProductCoreError::POLICY_INVALID;
  if (!observation.valid()) return ProductCoreError::INVALID_ARGUMENT;

  for (auto &record : records_) {
    if (!same_mac(record.observation.source_mac, observation.source_mac)) continue;
    if (observation.observed_at_ms < record.observation.observed_at_ms) {
      return ProductCoreError::INVALID_ARGUMENT;
    }
    const bool identity_changed = record.observation.gateway_id != observation.gateway_id;
    record.observation = observation;
    if (identity_changed) {
      record.eligibility = RelayCandidateEligibility{};
      record.has_eligibility = false;
    }
    return ProductCoreError::NONE;
  }

  if (records_.size() >= policy_.capacity) return ProductCoreError::CAPACITY_EXHAUSTED;
  RelayCandidateRecord record;
  record.observation = observation;
  records_.push_back(record);
  return ProductCoreError::NONE;
}

ProductCoreError RelayCandidateTable::apply_manager_eligibility(
    const MacAddress &source_mac,
    const std::string &gateway_id,
    const RelayCandidateEligibility &eligibility) {
  if (!policy_.valid()) return ProductCoreError::POLICY_INVALID;
  if (!valid_identity(gateway_id) || !eligibility.valid_shape()) {
    return ProductCoreError::INVALID_ARGUMENT;
  }
  for (auto &record : records_) {
    if (!same_mac(record.observation.source_mac, source_mac)) continue;
    if (record.observation.gateway_id != gateway_id) {
      return ProductCoreError::AUTHORIZATION_REJECTED;
    }
    record.eligibility = eligibility;
    record.has_eligibility = true;
    return ProductCoreError::NONE;
  }
  return ProductCoreError::NOT_FOUND;
}

void RelayCandidateTable::prune(uint64_t now_ms) {
  if (!policy_.valid()) return;
  records_.erase(
      std::remove_if(records_.begin(), records_.end(), [&](const RelayCandidateRecord &record) {
        return !observation_fresh_(record, now_ms);
      }),
      records_.end());
}

const RelayCandidateRecord *RelayCandidateTable::find(const MacAddress &source_mac) const {
  for (const auto &record : records_) {
    if (same_mac(record.observation.source_mac, source_mac)) return &record;
  }
  return nullptr;
}

bool RelayCandidateTable::observation_fresh_(
    const RelayCandidateRecord &record,
    uint64_t now_ms) const {
  if (now_ms < record.observation.observed_at_ms) return false;
  return now_ms - record.observation.observed_at_ms <= policy_.observation_ttl_ms;
}

bool RelayCandidateTable::eligible_(const RelayCandidateRecord &record, uint64_t now_ms) const {
  return observation_fresh_(record, now_ms) && record.has_eligibility &&
         record.observation.rssi_dbm >= policy_.minimum_rssi_dbm &&
         record.eligibility.eligible_at(now_ms);
}

int32_t RelayCandidateTable::score(const RelayCandidateRecord &record) const {
  const int32_t rssi_component = static_cast<int32_t>(record.observation.rssi_dbm) * 2;
  const int32_t uplink_component = static_cast<int32_t>(record.eligibility.uplink_quality_pct);
  const int32_t load_penalty = static_cast<int32_t>(record.eligibility.load_pct);
  const int32_t battery_component = static_cast<int32_t>(record.eligibility.battery_pct) / 4;
  return rssi_component + uplink_component - load_penalty + battery_component;
}

bool RelayCandidateTable::select(
    const std::optional<MacAddress> &current_mac,
    uint64_t current_since_ms,
    uint64_t now_ms,
    RelayCandidateRecord *selected) const {
  if (selected == nullptr || !policy_.valid()) return false;

  const RelayCandidateRecord *best = nullptr;
  for (const auto &record : records_) {
    if (!eligible_(record, now_ms)) continue;
    if (best == nullptr || score(record) > score(*best) ||
        (score(record) == score(*best) &&
         record.observation.gateway_id < best->observation.gateway_id)) {
      best = &record;
    }
  }
  if (best == nullptr) return false;

  const RelayCandidateRecord *current = nullptr;
  if (current_mac.has_value()) {
    current = find(*current_mac);
    if (current != nullptr && !eligible_(*current, now_ms)) current = nullptr;
  }

  if (current != nullptr && !same_mac(current->observation.source_mac, best->observation.source_mac)) {
    const bool hold_active = now_ms >= current_since_ms &&
                             now_ms - current_since_ms < policy_.minimum_hold_ms;
    const bool insufficient_margin = score(*best) < score(*current) + policy_.switch_score_margin;
    if (hold_active || insufficient_margin) best = current;
  }

  *selected = *best;
  return true;
}

bool DynamicPeerAuthorization::valid_shape() const {
  return valid_identity(authorization_id) && valid_identity(gateway_id) && !zero_mac(peer_mac) &&
         valid_channel(channel) && relay_credential_generation > 0 &&
         expires_at_ms > issued_at_ms;
}

ProductCoreError DynamicPeerLifecycle::observe(const RelayCandidateRecord &candidate) {
  if (!candidate.observation.valid() || !candidate.has_eligibility) {
    return ProductCoreError::INVALID_ARGUMENT;
  }
  candidate_ = candidate;
  authorization_.reset();
  state_ = DynamicPeerState::DISCOVERED;
  return ProductCoreError::NONE;
}

ProductCoreError DynamicPeerLifecycle::begin_authorization() {
  if (state_ != DynamicPeerState::DISCOVERED || !candidate_.has_value()) {
    return ProductCoreError::STATE_REJECTED;
  }
  state_ = DynamicPeerState::AUTHORIZING;
  return ProductCoreError::NONE;
}

bool DynamicPeerLifecycle::authorization_matches_candidate_(
    const DynamicPeerAuthorization &authorization) const {
  if (!candidate_.has_value()) return false;
  return authorization.gateway_id == candidate_->observation.gateway_id &&
         same_mac(authorization.peer_mac, candidate_->observation.source_mac) &&
         authorization.channel == candidate_->observation.channel &&
         authorization.relay_credential_generation ==
             candidate_->eligibility.credential_generation;
}

ProductCoreError DynamicPeerLifecycle::accept_authorization(
    const DynamicPeerAuthorization &authorization,
    uint64_t now_ms) {
  if (state_ != DynamicPeerState::AUTHORIZING || !candidate_.has_value()) {
    return ProductCoreError::STATE_REJECTED;
  }
  if (!authorization.valid_shape() || !authorization.manager_authorized ||
      !authorization.same_system || !authorization_matches_candidate_(authorization)) {
    return ProductCoreError::AUTHORIZATION_REJECTED;
  }
  if (now_ms < authorization.issued_at_ms || now_ms >= authorization.expires_at_ms) {
    return ProductCoreError::EXPIRED;
  }
  authorization_ = authorization;
  state_ = DynamicPeerState::AUTHORIZED;
  return ProductCoreError::NONE;
}

ProductCoreError DynamicPeerLifecycle::activate(uint64_t now_ms) {
  if (state_ != DynamicPeerState::AUTHORIZED || !authorization_.has_value()) {
    return ProductCoreError::STATE_REJECTED;
  }
  if (now_ms < authorization_->issued_at_ms || now_ms >= authorization_->expires_at_ms) {
    state_ = DynamicPeerState::EXPIRED;
    return ProductCoreError::EXPIRED;
  }
  state_ = DynamicPeerState::ACTIVE;
  return ProductCoreError::NONE;
}

void DynamicPeerLifecycle::reject_authorization() {
  authorization_.reset();
  candidate_.reset();
  state_ = DynamicPeerState::EMPTY;
}

bool DynamicPeerLifecycle::maintenance(uint64_t now_ms) {
  if (!authorization_.has_value()) return false;
  if ((state_ == DynamicPeerState::AUTHORIZED || state_ == DynamicPeerState::ACTIVE) &&
      now_ms >= authorization_->expires_at_ms) {
    state_ = DynamicPeerState::EXPIRED;
    return true;
  }
  return false;
}

void DynamicPeerLifecycle::revoke() {
  authorization_.reset();
  candidate_.reset();
  state_ = DynamicPeerState::REVOKED;
}

void DynamicPeerLifecycle::reset() {
  authorization_.reset();
  candidate_.reset();
  state_ = DynamicPeerState::EMPTY;
}

bool DynamicPeerLifecycle::telemetry_allowed(uint64_t now_ms) const {
  return state_ == DynamicPeerState::ACTIVE && authorization_.has_value() &&
         authorization_->manager_authorized && authorization_->same_system &&
         now_ms >= authorization_->issued_at_ms && now_ms < authorization_->expires_at_ms;
}

bool AutoPathStateMachine::relay_side_state_(AutoPathState state) {
  return state == AutoPathState::DISCOVERY || state == AutoPathState::RELAY_AUTH ||
         state == AutoPathState::RELAY_ACTIVE || state == AutoPathState::REDISCOVERY;
}

ProductCoreError AutoPathStateMachine::on_direct_health(WifiDirectHealthState health) {
  if (!policy_.valid()) return ProductCoreError::POLICY_INVALID;
  switch (health) {
    case WifiDirectHealthState::HEALTHY:
      state_ = AutoPathState::DIRECT;
      relay_failures_ = 0;
      return ProductCoreError::NONE;
    case WifiDirectHealthState::DEGRADED:
      if (state_ == AutoPathState::DIRECT) state_ = AutoPathState::DIRECT_DEGRADED;
      return ProductCoreError::NONE;
    case WifiDirectHealthState::UNAVAILABLE:
      if (state_ == AutoPathState::DIRECT || state_ == AutoPathState::DIRECT_DEGRADED) {
        state_ = AutoPathState::DISCOVERY;
      } else if (state_ == AutoPathState::DIRECT_RECOVERY) {
        state_ = relay_side_state_(pre_recovery_state_) ? pre_recovery_state_
                                                        : AutoPathState::REDISCOVERY;
      }
      return ProductCoreError::NONE;
    case WifiDirectHealthState::RECOVERING:
      if (relay_side_state_(state_) && state_ != AutoPathState::DIRECT_RECOVERY) {
        pre_recovery_state_ = state_;
        state_ = AutoPathState::DIRECT_RECOVERY;
      }
      return ProductCoreError::NONE;
  }
  return ProductCoreError::INVALID_ARGUMENT;
}

ProductCoreError AutoPathStateMachine::on_candidate_selected() {
  if (state_ != AutoPathState::DISCOVERY && state_ != AutoPathState::REDISCOVERY) {
    return ProductCoreError::STATE_REJECTED;
  }
  state_ = AutoPathState::RELAY_AUTH;
  relay_failures_ = 0;
  return ProductCoreError::NONE;
}

ProductCoreError AutoPathStateMachine::on_relay_authorization(bool accepted) {
  if (state_ != AutoPathState::RELAY_AUTH) return ProductCoreError::STATE_REJECTED;
  state_ = accepted ? AutoPathState::RELAY_ACTIVE : AutoPathState::REDISCOVERY;
  relay_failures_ = 0;
  return ProductCoreError::NONE;
}

ProductCoreError AutoPathStateMachine::on_relay_result(bool success) {
  if (state_ != AutoPathState::RELAY_ACTIVE) return ProductCoreError::STATE_REJECTED;
  if (success) {
    relay_failures_ = 0;
    return ProductCoreError::NONE;
  }
  relay_failures_ = saturating_increment(relay_failures_);
  if (relay_failures_ >= policy_.relay_failures_to_rediscovery) {
    state_ = AutoPathState::REDISCOVERY;
    relay_failures_ = 0;
  }
  return ProductCoreError::NONE;
}

ProductCoreError AutoPathStateMachine::on_peer_lost() {
  if (state_ == AutoPathState::RELAY_ACTIVE || state_ == AutoPathState::RELAY_AUTH) {
    state_ = AutoPathState::REDISCOVERY;
    relay_failures_ = 0;
    return ProductCoreError::NONE;
  }
  if (state_ == AutoPathState::DIRECT_RECOVERY) {
    pre_recovery_state_ = AutoPathState::REDISCOVERY;
    return ProductCoreError::NONE;
  }
  return ProductCoreError::STATE_REJECTED;
}

ProductCoreError AutoPathStateMachine::on_rediscovery_cycle() {
  if (state_ != AutoPathState::REDISCOVERY) return ProductCoreError::STATE_REJECTED;
  state_ = AutoPathState::DISCOVERY;
  return ProductCoreError::NONE;
}

ProductCoreError RelayOrchestrationCore::note_direct_result(bool success, uint64_t now_ms) {
  (void) now_ms;
  const ProductCoreError error = direct_health_.note_direct_result(success);
  if (error != ProductCoreError::NONE) return error;
  return path_.on_direct_health(direct_health_.state());
}

ProductCoreError RelayOrchestrationCore::note_direct_recovery_probe(
    bool success,
    uint64_t now_ms) {
  (void) now_ms;
  const ProductCoreError error = direct_health_.note_recovery_probe(success);
  if (error != ProductCoreError::NONE) return error;
  return path_.on_direct_health(direct_health_.state());
}

ProductCoreError RelayOrchestrationCore::observe_candidate(
    const RelayCandidateObservation &observation) {
  return candidates_.observe(observation);
}

ProductCoreError RelayOrchestrationCore::apply_manager_eligibility(
    const MacAddress &source_mac,
    const std::string &gateway_id,
    const RelayCandidateEligibility &eligibility) {
  return candidates_.apply_manager_eligibility(source_mac, gateway_id, eligibility);
}

ProductCoreError RelayOrchestrationCore::select_candidate(uint64_t now_ms) {
  if (path_.state() == AutoPathState::REDISCOVERY) {
    const ProductCoreError cycle = path_.on_rediscovery_cycle();
    if (cycle != ProductCoreError::NONE) return cycle;
  }
  if (path_.state() != AutoPathState::DISCOVERY) return ProductCoreError::STATE_REJECTED;

  candidates_.prune(now_ms);
  RelayCandidateRecord candidate;
  if (!candidates_.select(selected_mac_, selected_since_ms_, now_ms, &candidate)) {
    return ProductCoreError::NOT_FOUND;
  }

  const bool changed = !selected_mac_.has_value() ||
                       !same_mac(*selected_mac_, candidate.observation.source_mac);
  selected_mac_ = candidate.observation.source_mac;
  if (changed) selected_since_ms_ = now_ms;

  ProductCoreError error = peer_.observe(candidate);
  if (error != ProductCoreError::NONE) return error;
  error = peer_.begin_authorization();
  if (error != ProductCoreError::NONE) return error;
  return path_.on_candidate_selected();
}

ProductCoreError RelayOrchestrationCore::accept_peer_authorization(
    const DynamicPeerAuthorization &authorization,
    uint64_t now_ms) {
  ProductCoreError error = peer_.accept_authorization(authorization, now_ms);
  if (error != ProductCoreError::NONE) return error;
  error = peer_.activate(now_ms);
  if (error != ProductCoreError::NONE) return error;
  return path_.on_relay_authorization(true);
}

ProductCoreError RelayOrchestrationCore::reject_peer_authorization() {
  peer_.reject_authorization();
  return path_.on_relay_authorization(false);
}

ProductCoreError RelayOrchestrationCore::note_relay_result(bool success, uint64_t now_ms) {
  (void) now_ms;
  const AutoPathState before = path_.state();
  const ProductCoreError error = path_.on_relay_result(success);
  if (error != ProductCoreError::NONE) return error;
  if (before == AutoPathState::RELAY_ACTIVE && path_.state() == AutoPathState::REDISCOVERY) {
    peer_.reset();
    selected_mac_.reset();
    selected_since_ms_ = 0;
  }
  return ProductCoreError::NONE;
}

void RelayOrchestrationCore::maintenance(uint64_t now_ms) {
  candidates_.prune(now_ms);
  if (peer_.maintenance(now_ms)) {
    (void) path_.on_peer_lost();
    peer_.reset();
    selected_mac_.reset();
    selected_since_ms_ = 0;
  }
}

}  // namespace esphome::greenhouse_n3w_product_core
