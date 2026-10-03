#pragma once

#include <cstdint>

namespace esphome::greenhouse_n3w_core {

inline constexpr uint32_t kBrokerRelocationMqttFailureTriggerMs = 10000;
inline constexpr uint32_t kBrokerRelocationDiscoveryBudgetMs = 1000;
inline constexpr uint32_t kBrokerRelocationCandidateBudgetMs = 6000;
inline constexpr uint32_t kBrokerRelocationCleanupReserveMs = 2000;
inline constexpr uint32_t kBrokerRelocationDiscoveryMinIntervalMs = 60000;

bool broker_relocation_trigger_due(uint64_t started_ms, uint64_t now_ms);
bool broker_relocation_discovery_can_start(
    uint64_t now_ms,
    uint64_t mqtt_phase_deadline_ms,
    uint64_t absolute_deadline_ms,
    uint32_t direct_confirm_reserve_ms);
uint64_t broker_relocation_candidate_deadline(
    uint64_t now_ms,
    uint64_t mqtt_phase_deadline_ms,
    uint64_t absolute_deadline_ms,
    uint32_t direct_confirm_reserve_ms);

}
