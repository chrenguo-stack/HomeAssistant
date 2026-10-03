#include <cassert>
#include <cstdint>
#include <limits>

#include "n3w_broker_relocation_policy.h"

using namespace esphome::greenhouse_n3w_core;

int main() {
  assert(!broker_relocation_trigger_due(1000U, 10999U));
  assert(broker_relocation_trigger_due(1000U, 11000U));

  const uint64_t now = 1000U;
  assert(!broker_relocation_discovery_can_start(
      now, now + 8999U, now + 20000U, 5000U));
  assert(!broker_relocation_discovery_can_start(
      now, now + 9000U, now + 13999U, 5000U));
  assert(broker_relocation_discovery_can_start(
      now, now + 9000U, now + 14000U, 5000U));

  assert(broker_relocation_candidate_deadline(
   now, now + 20000U, now + 30000U, 5000U) ==
         now + 6000U);
  assert(broker_relocation_candidate_deadline(
   now, now + 7000U, now + 30000U, 5000U) ==
         now + 5000U);
  assert(broker_relocation_candidate_deadline(
   now, now + 2000U, now + 30000U, 5000U) == 0U);
  assert(broker_relocation_candidate_deadline(
   now, now + 20000U, now + 7000U, 5000U) == 0U);

  const uint64_t near_max = std::numeric_limits<uint64_t>::max() - 1000U;
  const uint64_t deadline = broker_relocation_candidate_deadline(
      near_max,
      std::numeric_limits<uint64_t>::max(),
      std::numeric_limits<uint64_t>::max(),
      0U);
  assert(deadline == 0U);
  return 0;
}
