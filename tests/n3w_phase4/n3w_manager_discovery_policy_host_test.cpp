#include <cassert>
#include <string>
#include <vector>

#include "n3w_manager_discovery.h"

using esphome::greenhouse_n3w_core::SimpleDiscoveryFilterContext;
using esphome::greenhouse_n3w_core::SimpleManagerCandidateV2;
using esphome::greenhouse_n3w_core::filter_simple_discovery_candidates;
using esphome::greenhouse_n3w_core::kManagerDiscoveryMaxAttemptCandidates;
using esphome::greenhouse_n3w_core::kManagerDiscoveryMaxParsedDatagrams;
using esphome::greenhouse_n3w_core::kManagerDiscoveryMaxRetainedCandidates;
using esphome::greenhouse_n3w_core::make_simple_broker_recovery_targets;
using esphome::greenhouse_n3w_core::simple_discovery_candidate_allowed;

namespace {

SimpleManagerCandidateV2 candidate(
    const std::string &host,
    const std::string &system_id = "system-main",
    uint16_t port = 47112) {
  return SimpleManagerCandidateV2{
      "manager-main",
      system_id,
      host,
      port,
      "/v2/pairing",
  };
}

SimpleDiscoveryFilterContext context() {
  return SimpleDiscoveryFilterContext{
      "system-main",
      "198.51.100.20",
      "255.255.255.0",
  };
}

}

int main() {
  static_assert(kManagerDiscoveryMaxParsedDatagrams == 8U);
  static_assert(kManagerDiscoveryMaxRetainedCandidates == 3U);
  static_assert(kManagerDiscoveryMaxAttemptCandidates == 2U);

  const auto filter_context = context();
  assert(simple_discovery_candidate_allowed(
      candidate("198.51.100.30"), "198.51.100.30", filter_context));
  assert(!simple_discovery_candidate_allowed(
      candidate("198.51.100.30", "system-other"),
      "198.51.100.30",
      filter_context));
  assert(!simple_discovery_candidate_allowed(
      candidate("203.0.113.30"), "203.0.113.30", filter_context));
  assert(!simple_discovery_candidate_allowed(
      candidate("198.51.100.30"), "198.51.100.31", filter_context));
  assert(!simple_discovery_candidate_allowed(
      candidate("224.0.0.1"), "224.0.0.1", filter_context));
  assert(!simple_discovery_candidate_allowed(
      candidate("198.51.100.0"), "198.51.100.0", filter_context));
  assert(!simple_discovery_candidate_allowed(
      candidate("198.51.100.255"), "198.51.100.255", filter_context));

  std::vector<SimpleManagerCandidateV2> dedupe_candidates{
      candidate("198.51.100.30"),
      candidate("198.51.100.30"),
      candidate("198.51.100.31"),
      candidate("198.51.100.32"),
      candidate("198.51.100.33"),
  };
  std::vector<std::string> dedupe_sources{
      "198.51.100.30",
      "198.51.100.30",
      "198.51.100.31",
      "198.51.100.32",
      "198.51.100.33",
  };
  const auto retained = filter_simple_discovery_candidates(
      dedupe_candidates, dedupe_sources, filter_context);
  assert(retained.size() == 3U);
  assert(retained[0].host == "198.51.100.30");
  assert(retained[1].host == "198.51.100.31");
  assert(retained[2].host == "198.51.100.32");

  std::vector<SimpleManagerCandidateV2> parse_bound_candidates;
  std::vector<std::string> parse_bound_sources;
  for (std::size_t index = 0; index < 7U; ++index) {
    const std::string host = "198.51.100." + std::to_string(40U + index);
    parse_bound_candidates.push_back(candidate(host, "system-other"));
    parse_bound_sources.push_back(host);
  }
  parse_bound_candidates.push_back(candidate("198.51.100.50"));
  parse_bound_sources.push_back("198.51.100.50");
  parse_bound_candidates.push_back(candidate("198.51.100.51"));
  parse_bound_sources.push_back("198.51.100.51");
  const auto bounded = filter_simple_discovery_candidates(
      parse_bound_candidates, parse_bound_sources, filter_context);
  assert(bounded.size() == 1U);
  assert(bounded[0].host == "198.51.100.50");

  const auto targets = make_simple_broker_recovery_targets(retained, 8883U);
  assert(targets.size() == 2U);
  assert(targets[0].host == "198.51.100.30");
  assert(targets[0].port == 8883U);
  assert(targets[1].host == "198.51.100.31");
  assert(targets[1].port == 8883U);

  const auto no_port_targets = make_simple_broker_recovery_targets(retained, 0U);
  assert(no_port_targets.empty());
  return 0;
}
