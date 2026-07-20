#include <cassert>
#include <iostream>
#include <string>

#include "pairing_client_core.h"

using esphome::greenhouse_pairing_client::ManagerCandidate;
using esphome::greenhouse_pairing_client::PairingClientCore;
using esphome::greenhouse_pairing_client::PairingClientError;
using esphome::greenhouse_pairing_client::PairingClientState;

namespace {

constexpr const char *REQUEST_ID = "11111111-2222-4333-8444-555555555555";
constexpr const char *PAIRING_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
constexpr const char *SESSION_ID = "99999999-8888-4777-8666-555555555555";
constexpr const char *NONCE = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
constexpr const char *MANAGER_NONCE = "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB";
constexpr const char *MANAGER_KEY = "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC";
constexpr const char *CIPHER = "X25519-HKDF-SHA256-CHACHA20-POLY1305";

ManagerCandidate candidate(const std::string &manager_id, const std::string &host, uint16_t port = 47110,
                           uint16_t ttl_s = 120) {
  return ManagerCandidate{
      .schema = "gh.manager.candidate/1",
      .manager_id = manager_id,
      .system_id = "greenhouse",
      .host = host,
      .scheme = "http",
      .port = port,
      .pairing_path = "/v1/pairing",
      .protocol = "gh-h3-secure-pairing/1",
      .priority = 100,
      .ttl_s = ttl_s,
  };
}

PairingClientCore configured(size_t max_candidates = 4, uint16_t ttl_cap_s = 120) {
  PairingClientCore core;
  assert(core.configure("ghw-c6-test-node", PAIRING_ID, max_candidates, ttl_cap_s));
  return core;
}

void test_one_candidate_auto_resolves() {
  auto core = configured();
  assert(core.start_discovery(REQUEST_ID, NONCE, 1000));
  assert(core.observe_candidate(REQUEST_ID, NONCE, candidate("manager-a", "manager-a.local"), 1100));
  const auto snapshot = core.snapshot();
  assert(snapshot.state == PairingClientState::CLAIM_READY);
  assert(snapshot.candidate_count == 1);
  assert(snapshot.candidate_selected);
  assert(!snapshot.selection_required);
  assert(core.selected_candidate()->manager_id == "manager-a");
}

void test_multiple_candidates_require_explicit_selection() {
  auto core = configured();
  assert(core.start_discovery(REQUEST_ID, NONCE, 1000));
  assert(core.observe_candidate(REQUEST_ID, NONCE, candidate("manager-a", "manager-a.local"), 1100));
  assert(core.observe_candidate(REQUEST_ID, NONCE, candidate("manager-b", "manager-b.local"), 1200));
  assert(core.snapshot().state == PairingClientState::SELECTION_REQUIRED);
  assert(!core.snapshot().candidate_selected);
  assert(!core.mark_claim_sent());
  assert(core.snapshot().error == PairingClientError::CANDIDATE_SELECTION_REQUIRED);
  assert(core.select_candidate(1));
  assert(core.selected_candidate()->manager_id == "manager-b");
  assert(core.mark_claim_sent());
}

void test_same_manager_conflicting_endpoint_is_not_collapsed() {
  auto core = configured();
  assert(core.start_discovery(REQUEST_ID, NONCE, 1000));
  assert(core.observe_candidate(REQUEST_ID, NONCE, candidate("manager-a", "manager-a.local", 47110), 1100));
  assert(core.observe_candidate(REQUEST_ID, NONCE, candidate("manager-a", "manager-a.local", 47112), 1200));
  assert(core.snapshot().candidate_count == 2);
  assert(core.snapshot().selection_required);
}

void test_exact_duplicate_refreshes_ttl_without_growth() {
  auto core = configured();
  assert(core.start_discovery(REQUEST_ID, NONCE, 1000));
  const auto item = candidate("manager-a", "manager-a.local", 47110, 10);
  assert(core.observe_candidate(REQUEST_ID, NONCE, item, 1100));
  assert(core.observe_candidate(REQUEST_ID, NONCE, item, 5000));
  assert(core.snapshot().candidate_count == 1);
  core.prune_candidates(14999);
  assert(core.snapshot().candidate_count == 1);
  core.prune_candidates(15000);
  assert(core.snapshot().candidate_count == 0);
  assert(core.snapshot().state == PairingClientState::DISCOVERING);
}

void test_request_context_is_bound() {
  auto core = configured();
  assert(core.start_discovery(REQUEST_ID, NONCE, 1000));
  assert(!core.observe_candidate("00000000-0000-4000-8000-000000000000", NONCE,
                                 candidate("manager-a", "manager-a.local"), 1100));
  assert(core.snapshot().error == PairingClientError::INVALID_DISCOVERY_CONTEXT);
  assert(!core.observe_candidate(REQUEST_ID, MANAGER_NONCE, candidate("manager-a", "manager-a.local"), 1100));
  assert(core.snapshot().candidate_count == 0);
}

void test_capacity_is_bounded() {
  auto core = configured(2);
  assert(core.start_discovery(REQUEST_ID, NONCE, 1000));
  assert(core.observe_candidate(REQUEST_ID, NONCE, candidate("manager-a", "manager-a.local"), 1100));
  assert(core.observe_candidate(REQUEST_ID, NONCE, candidate("manager-b", "manager-b.local"), 1200));
  assert(!core.observe_candidate(REQUEST_ID, NONCE, candidate("manager-c", "manager-c.local"), 1300));
  assert(core.snapshot().candidate_count == 2);
  assert(core.snapshot().error == PairingClientError::CANDIDATE_CAPACITY_REACHED);
}

void test_local_host_contract() {
  assert(PairingClientCore::valid_local_host("manager.local"));
  assert(PairingClientCore::valid_local_host("127.0.0.1"));
  assert(!PairingClientCore::valid_local_host("192.0.2.10"));
  assert(!PairingClientCore::valid_local_host("manager.example"));
  assert(!PairingClientCore::valid_local_host("bad host.local"));
}

void test_secure_lifecycle_requires_order() {
  auto core = configured();
  assert(core.start_discovery(REQUEST_ID, NONCE, 1000));
  assert(core.observe_candidate(REQUEST_ID, NONCE, candidate("manager-a", "manager-a.local"), 1100));
  assert(core.mark_claim_sent());
  assert(!core.mark_channel_established());
  assert(core.accept_secure_offer(SESSION_ID, MANAGER_NONCE, MANAGER_KEY, CIPHER));
  assert(core.mark_channel_established());
  assert(core.stage_credentials("gh-n1-test-node", 3));
  assert(core.commit_credentials());
  const auto snapshot = core.snapshot();
  assert(snapshot.state == PairingClientState::COMMITTED);
  assert(snapshot.committed);
  assert(snapshot.credential_generation == 3);
  assert(core.node_id() == "gh-n1-test-node");
  assert(!core.start_discovery(REQUEST_ID, NONCE, 2000));
}

void test_claim_transcript_is_frozen() {
  const std::string expected =
      "gh.pair.claim/1\nmanager-a\nghw-c6-test-node\naaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
  assert(PairingClientCore::build_claim_transcript("manager-a", "ghw-c6-test-node", PAIRING_ID) == expected);
  assert(PairingClientCore::build_claim_transcript("bad manager", "ghw-c6-test-node", PAIRING_ID).empty());
}

void test_invalid_candidate_is_rejected() {
  auto core = configured();
  assert(core.start_discovery(REQUEST_ID, NONCE, 1000));
  auto item = candidate("manager-a", "manager-a.local");
  item.protocol = "unsupported/1";
  assert(!core.observe_candidate(REQUEST_ID, NONCE, item, 1100));
  assert(core.snapshot().error == PairingClientError::INVALID_CANDIDATE);
}

}  // namespace

int main() {
  test_one_candidate_auto_resolves();
  test_multiple_candidates_require_explicit_selection();
  test_same_manager_conflicting_endpoint_is_not_collapsed();
  test_exact_duplicate_refreshes_ttl_without_growth();
  test_request_context_is_bound();
  test_capacity_is_bounded();
  test_local_host_contract();
  test_secure_lifecycle_requires_order();
  test_claim_transcript_is_frozen();
  test_invalid_candidate_is_rejected();
  std::cout << "pairing_client_core_test: passed\n";
  return 0;
}
