#include <cassert>
#include <string>
#include <vector>

#include "n3w_manager_discovery.h"

using namespace esphome::greenhouse_n3w_core;

static SimpleManagerCandidateV2 candidate(
    const std::string &system_id,
    const std::string &host,
    uint16_t ttl_s) {
  SimpleManagerCandidateV2 value;
  value.manager_id = "manager-a";
  value.system_id = system_id;
  value.host = host;
  value.port = 8883;
  value.pairing_path = "/v2/pairing";
  value.ttl_s = ttl_s;
  return value;
}

int main() {
  const SimpleDiscoveryFilterContext context{
      "system-a", "192.0.2.20", "255.255.255.0"};
  assert(simple_discovery_candidate_allowed(candidate("system-a", "192.0.2.30", 30), "192.0.2.30", context));
  assert(!simple_discovery_candidate_allowed(candidate("system-b", "192.0.2.30", 30), "192.0.2.30", context));
  assert(!simple_discovery_candidate_allowed(candidate("system-a", "192.0.2.20", 30), "192.0.2.20", context));
  assert(!simple_discovery_candidate_allowed(candidate("system-a", "192.0.2.30", 30), "192.0.2.31", context));
  assert(!simple_discovery_candidate_allowed(candidate("system-a", "198.51.100.30", 30), "198.51.100.30", context));
  assert(!simple_discovery_candidate_allowed(candidate("system-a", "192.0.2.30", 0), "192.0.2.30", context));
  assert(!simple_discovery_candidate_allowed(candidate("system-a", "192.0.2.30", 121), "192.0.2.30", context));
  assert(!simple_discovery_candidate_allowed(candidate("system-a", "192.0.2.255", 30), "192.0.2.255", context));
  const std::vector<SimpleManagerCandidateV2> candidates{
      candidate("system-a", "192.0.2.30", 30),
      candidate("system-a", "192.0.2.30", 30),
      candidate("system-a", "192.0.2.31", 30),
  };
  const std::vector<std::string> sources{
      "192.0.2.30", "192.0.2.30", "192.0.2.31"};
  const auto filtered = filter_simple_discovery_candidates(candidates, sources, context);
  assert(filtered.size() == 2U);
  const auto targets = make_simple_broker_recovery_targets(filtered, 8883);
  assert(targets.size() == 2U);
  assert(targets[0].port == 8883);
  assert(targets[1].port == 8883);
  return 0;
}
