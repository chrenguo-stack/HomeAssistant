#include "n3w_broker_relocation_policy.h"

#include <algorithm>
#include <limits>

namespace esphome::greenhouse_n3w_core {
namespace {

bool has_room(uint64_t now_ms, uint64_t deadline_ms, uint64_t required_ms) {
  return deadline_ms > now_ms && deadline_ms - now_ms >= required_ms;
}

uint64_t add_saturated(uint64_t value, uint64_t delta) {
  if (value > std::numeric_limits<uint64_t>::max() - delta) {
    return std::numeric_limits<uint64_t>::max();
  }
  return value + delta;
}

}

bool broker_relocation_trigger_due(uint64_t started_ms, uint64_t now_ms) {
  return started_ms != 0U && now_ms >= started_ms &&
         now_ms - started_ms >= kBrokerRelocationMqttFailureTriggerMs;
}

bool broker_relocation_discovery_can_start(
    uint64_t now_ms,
    uint64_t mqtt_phase_deadline_ms,
    uint64_t absolute_deadline_ms,
    uint32_t direct_confirm_reserve_ms) {
  const uint64_t mqtt_required =
      static_cast<uint64_t>(kBrokerRelocationDiscoveryBudgetMs) +
      kBrokerRelocationCandidateBudgetMs +
      kBrokerRelocationCleanupReserveMs;
  const uint64_t absolute_required =
      mqtt_required + static_cast<uint64_t>(direct_confirm_reserve_ms);
  return has_room(now_ms, mqtt_phase_deadline_ms, mqtt_required) &&
         has_room(now_ms, absolute_deadline_ms, absolute_required);
}

uint64_t broker_relocation_candidate_deadline(
    uint64_t now_ms,
    uint64_t mqtt_phase_deadline_ms,
    uint64_t absolute_deadline_ms,
    uint32_t direct_confirm_reserve_ms) {
  if (!has_room(now_ms, mqtt_phase_deadline_ms, kBrokerRelocationCleanupReserveMs) ||
      !has_room(
now_ms,
absolute_deadline_ms,
static_cast<uint64_t>(kBrokerRelocationCleanupReserveMs) +
    direct_confirm_reserve_ms)) {
    return 0U;
  }
  const uint64_t candidate_cap =
      add_saturated(now_ms, kBrokerRelocationCandidateBudgetMs);
  const uint64_t mqtt_cap =
      mqtt_phase_deadline_ms - kBrokerRelocationCleanupReserveMs;
  const uint64_t absolute_cap =
      absolute_deadline_ms - kBrokerRelocationCleanupReserveMs -
      direct_confirm_reserve_ms;
  const uint64_t deadline = std::min({candidate_cap, mqtt_cap, absolute_cap});
  return deadline > now_ms ? deadline : 0U;
}

}
