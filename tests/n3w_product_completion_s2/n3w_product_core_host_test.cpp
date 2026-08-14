#include <cassert>
#include <cstdint>
#include <iostream>
#include <optional>

#include "n3w_product_core.h"

using namespace esphome::greenhouse_n3w_product_core;

namespace {

MacAddress mac(uint8_t last) {
  return MacAddress{0x02, 0x31, 0x42, 0x53, 0x64, last};
}

RelayCandidateObservation observation(
    const char *gateway,
    uint8_t mac_last,
    int16_t rssi,
    uint64_t now_ms,
    uint8_t channel = 6) {
  RelayCandidateObservation result;
  result.gateway_id = gateway;
  result.source_mac = mac(mac_last);
  result.channel = channel;
  result.rssi_dbm = rssi;
  result.advertisement_generation = 1;
  result.observed_at_ms = now_ms;
  return result;
}

RelayCandidateEligibility eligibility(
    uint64_t now_ms,
    uint32_t generation = 1,
    uint8_t uplink_quality = 80,
    uint8_t load = 20,
    uint8_t battery = 80) {
  RelayCandidateEligibility result;
  result.manager_verified = true;
  result.registered = true;
  result.same_system = true;
  result.wifi_up = true;
  result.uplink_available = true;
  result.direct_uplink = true;
  result.relay_capable = true;
  result.low_battery = false;
  result.overloaded = false;
  result.retired = false;
  result.revoked = false;
  result.uplink_quality_pct = uplink_quality;
  result.load_pct = load;
  result.battery_pct = battery;
  result.credential_generation = generation;
  result.verified_at_ms = now_ms;
  result.valid_until_ms = now_ms + 60000;
  return result;
}

DynamicPeerAuthorization authorization(
    const char *authorization_id,
    const char *gateway,
    uint8_t mac_last,
    uint8_t channel,
    uint32_t generation,
    uint64_t now_ms) {
  DynamicPeerAuthorization result;
  result.authorization_id = authorization_id;
  result.gateway_id = gateway;
  result.peer_mac = mac(mac_last);
  result.channel = channel;
  result.relay_credential_generation = generation;
  result.issued_at_ms = now_ms;
  result.expires_at_ms = now_ms + 30000;
  result.manager_authorized = true;
  result.same_system = true;
  return result;
}

void test_direct_failure_detector() {
  WifiDirectHealthDetector detector(WifiDirectHealthPolicy{1, 3, 3});
  assert(detector.state() == WifiDirectHealthState::HEALTHY);
  assert(detector.note_direct_result(false) == ProductCoreError::NONE);
  assert(detector.state() == WifiDirectHealthState::DEGRADED);
  assert(detector.note_direct_result(false) == ProductCoreError::NONE);
  assert(detector.state() == WifiDirectHealthState::DEGRADED);
  assert(detector.note_direct_result(false) == ProductCoreError::NONE);
  assert(detector.state() == WifiDirectHealthState::UNAVAILABLE);
  assert(detector.note_direct_result(true) == ProductCoreError::STATE_REJECTED);
  assert(detector.state() == WifiDirectHealthState::UNAVAILABLE);

  assert(detector.note_recovery_probe(true) == ProductCoreError::NONE);
  assert(detector.state() == WifiDirectHealthState::RECOVERING);
  assert(detector.note_recovery_probe(true) == ProductCoreError::NONE);
  assert(detector.state() == WifiDirectHealthState::RECOVERING);
  assert(detector.note_recovery_probe(false) == ProductCoreError::NONE);
  assert(detector.state() == WifiDirectHealthState::UNAVAILABLE);
  assert(detector.note_recovery_probe(true) == ProductCoreError::NONE);
  assert(detector.note_recovery_probe(true) == ProductCoreError::NONE);
  assert(detector.note_recovery_probe(true) == ProductCoreError::NONE);
  assert(detector.state() == WifiDirectHealthState::HEALTHY);
}

void test_candidate_filter_score_and_hysteresis() {
  RelayCandidateTable table(RelayCandidatePolicy{4, 60000, -92, 12, 30000});
  const uint64_t now = 100000;
  const auto a = observation("relay_a", 0x11, -65, now);
  const auto b = observation("relay_b", 0x22, -62, now);
  assert(table.observe(a) == ProductCoreError::NONE);
  assert(table.observe(b) == ProductCoreError::NONE);

  RelayCandidateRecord selected;
  assert(!table.select(std::nullopt, 0, now, &selected));

  auto a_eligibility = eligibility(now, 7, 90, 10, 90);
  auto b_eligibility = eligibility(now, 8, 92, 10, 90);
  assert(table.apply_manager_eligibility(a.source_mac, a.gateway_id, a_eligibility) ==
         ProductCoreError::NONE);
  assert(table.apply_manager_eligibility(b.source_mac, b.gateway_id, b_eligibility) ==
         ProductCoreError::NONE);
  assert(table.select(std::nullopt, 0, now, &selected));
  const MacAddress first = selected.observation.source_mac;

  // A current relay is held during the minimum hold window even if B scores slightly better.
  RelayCandidateRecord held;
  assert(table.select(first, now, now + 10000, &held));
  assert(same_mac(held.observation.source_mac, first));

  // Make the competing candidate decisively better after the hold window.
  b_eligibility.uplink_quality_pct = 100;
  b_eligibility.load_pct = 0;
  assert(table.apply_manager_eligibility(b.source_mac, b.gateway_id, b_eligibility) ==
         ProductCoreError::NONE);
  RelayCandidateRecord switched;
  assert(table.select(first, now, now + 31000, &switched));
  assert(same_mac(switched.observation.source_mac, b.source_mac));

  // A relay using another relay as its uplink is never eligible in single-hop product mode.
  auto invalid = b_eligibility;
  invalid.direct_uplink = false;
  assert(table.apply_manager_eligibility(b.source_mac, b.gateway_id, invalid) ==
         ProductCoreError::NONE);
  RelayCandidateRecord fallback;
  assert(table.select(b.source_mac, now, now + 32000, &fallback));
  assert(same_mac(fallback.observation.source_mac, a.source_mac));

  // Changing an untrusted advertised gateway identity invalidates prior Manager eligibility.
  auto changed = a;
  changed.gateway_id = "relay_a_changed";
  changed.observed_at_ms = now + 1000;
  assert(table.observe(changed) == ProductCoreError::NONE);
  const RelayCandidateRecord *record = table.find(a.source_mac);
  assert(record != nullptr && !record->has_eligibility);

  auto stale = changed;
  stale.observed_at_ms = now;
  assert(table.observe(stale) == ProductCoreError::INVALID_ARGUMENT);
}

void test_dynamic_peer_lifecycle_is_manager_bound_and_expiring() {
  const uint64_t now = 200000;
  RelayCandidateRecord candidate;
  candidate.observation = observation("relay_secure", 0x33, -55, now, 11);
  candidate.eligibility = eligibility(now, 12);
  candidate.has_eligibility = true;

  DynamicPeerLifecycle peer;
  assert(peer.observe(candidate) == ProductCoreError::NONE);
  assert(peer.begin_authorization() == ProductCoreError::NONE);

  auto wrong = authorization("auth_wrong", "relay_secure", 0x44, 11, 12, now);
  assert(peer.accept_authorization(wrong, now) == ProductCoreError::AUTHORIZATION_REJECTED);

  auto accepted = authorization("auth_runtime_1", "relay_secure", 0x33, 11, 12, now);
  assert(peer.accept_authorization(accepted, now) == ProductCoreError::NONE);
  assert(peer.activate(now) == ProductCoreError::NONE);
  assert(peer.telemetry_allowed(now + 1));
  assert(peer.maintenance(accepted.expires_at_ms));
  assert(peer.state() == DynamicPeerState::EXPIRED);
  assert(!peer.telemetry_allowed(accepted.expires_at_ms));
}

void test_full_automatic_path_state_machine() {
  AutoPathStateMachine path(AutoPathPolicy{2});
  assert(path.on_direct_health(WifiDirectHealthState::DEGRADED) == ProductCoreError::NONE);
  assert(path.state() == AutoPathState::DIRECT_DEGRADED);
  assert(path.on_direct_health(WifiDirectHealthState::UNAVAILABLE) == ProductCoreError::NONE);
  assert(path.state() == AutoPathState::DISCOVERY);
  assert(path.on_candidate_selected() == ProductCoreError::NONE);
  assert(path.state() == AutoPathState::RELAY_AUTH);
  assert(path.on_relay_authorization(true) == ProductCoreError::NONE);
  assert(path.state() == AutoPathState::RELAY_ACTIVE);
  assert(path.on_relay_result(false) == ProductCoreError::NONE);
  assert(path.state() == AutoPathState::RELAY_ACTIVE);
  assert(path.on_relay_result(false) == ProductCoreError::NONE);
  assert(path.state() == AutoPathState::REDISCOVERY);
  assert(path.on_rediscovery_cycle() == ProductCoreError::NONE);
  assert(path.state() == AutoPathState::DISCOVERY);
  assert(path.on_direct_health(WifiDirectHealthState::RECOVERING) == ProductCoreError::NONE);
  assert(path.state() == AutoPathState::DIRECT_RECOVERY);
  assert(path.on_direct_health(WifiDirectHealthState::UNAVAILABLE) == ProductCoreError::NONE);
  assert(path.state() == AutoPathState::DISCOVERY);
  assert(path.on_direct_health(WifiDirectHealthState::RECOVERING) == ProductCoreError::NONE);
  assert(path.on_direct_health(WifiDirectHealthState::HEALTHY) == ProductCoreError::NONE);
  assert(path.state() == AutoPathState::DIRECT);
}

void test_simulated_dynamic_discovery_failover_and_direct_return() {
  RelayOrchestrationCore core(
      WifiDirectHealthPolicy{1, 3, 3},
      RelayCandidatePolicy{8, 20000, -95, 10, 10000},
      AutoPathPolicy{2});
  const uint64_t start = 300000;
  assert(core.direct_telemetry_ready());

  assert(core.note_direct_result(false, start) == ProductCoreError::NONE);
  assert(core.path_state() == AutoPathState::DIRECT_DEGRADED);
  assert(core.note_direct_result(false, start + 10) == ProductCoreError::NONE);
  assert(core.note_direct_result(false, start + 20) == ProductCoreError::NONE);
  assert(core.path_state() == AutoPathState::DISCOVERY);

  // A node that did not exist at factory-flash time can appear now and be accepted dynamically.
  const auto relay_a = observation("relay_runtime_a", 0x51, -58, start + 30, 6);
  assert(core.observe_candidate(relay_a) == ProductCoreError::NONE);
  assert(core.select_candidate(start + 31) == ProductCoreError::NOT_FOUND);
  assert(core.apply_manager_eligibility(
             relay_a.source_mac, relay_a.gateway_id, eligibility(start + 30, 21, 90, 10, 90)) ==
         ProductCoreError::NONE);
  assert(core.select_candidate(start + 32) == ProductCoreError::NONE);
  assert(core.path_state() == AutoPathState::RELAY_AUTH);
  assert(core.peer_state() == DynamicPeerState::AUTHORIZING);

  const auto auth_a = authorization(
      "auth_runtime_a", relay_a.gateway_id.c_str(), 0x51, 6, 21, start + 32);
  assert(core.accept_peer_authorization(auth_a, start + 33) == ProductCoreError::NONE);
  assert(core.path_state() == AutoPathState::RELAY_ACTIVE);
  assert(core.relay_telemetry_ready(start + 34));

  assert(core.note_relay_result(false, start + 40) == ProductCoreError::NONE);
  assert(core.note_relay_result(false, start + 50) == ProductCoreError::NONE);
  assert(core.path_state() == AutoPathState::REDISCOVERY);
  assert(core.peer_state() == DynamicPeerState::EMPTY);

  const auto relay_b = observation("relay_runtime_b", 0x52, -50, start + 60, 1);
  assert(core.observe_candidate(relay_b) == ProductCoreError::NONE);
  assert(core.apply_manager_eligibility(
             relay_b.source_mac, relay_b.gateway_id, eligibility(start + 60, 22, 95, 5, 95)) ==
         ProductCoreError::NONE);
  assert(core.select_candidate(start + 61) == ProductCoreError::NONE);
  const auto auth_b = authorization(
      "auth_runtime_b", relay_b.gateway_id.c_str(), 0x52, 1, 22, start + 61);
  assert(core.accept_peer_authorization(auth_b, start + 62) == ProductCoreError::NONE);
  assert(core.path_state() == AutoPathState::RELAY_ACTIVE);

  assert(core.note_direct_recovery_probe(true, start + 70) == ProductCoreError::NONE);
  assert(core.path_state() == AutoPathState::DIRECT_RECOVERY);
  assert(core.note_direct_recovery_probe(true, start + 80) == ProductCoreError::NONE);
  assert(core.path_state() == AutoPathState::DIRECT_RECOVERY);
  assert(core.note_direct_recovery_probe(true, start + 90) == ProductCoreError::NONE);
  assert(core.path_state() == AutoPathState::DIRECT);
  assert(core.direct_telemetry_ready());
}

}  // namespace

int main() {
  test_direct_failure_detector();
  test_candidate_filter_score_and_hysteresis();
  test_dynamic_peer_lifecycle_is_manager_bound_and_expiring();
  test_full_automatic_path_state_machine();
  test_simulated_dynamic_discovery_failover_and_direct_return();
  std::cout << "N3-W Product Completion S2 host-only core tests PASS\n";
  return 0;
}
