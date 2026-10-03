#include "n3w_manager_discovery.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>

namespace esphome::greenhouse_n3w_core {
namespace {

bool parse_ipv4(const std::string &text, uint32_t *value) {
  if (value == nullptr || text.empty() || text.size() > 15U) return false;
  std::array<uint32_t, 4> octets{};
  std::size_t octet_index = 0;
  std::size_t token_start = 0;
  for (std::size_t index = 0; index <= text.size(); ++index) {
    if (index != text.size() && text[index] != '.') continue;
    if (octet_index >= octets.size() || index == token_start) return false;
    if (index - token_start > 1U && text[token_start] == '0') return false;
    uint32_t octet = 0;
    for (std::size_t pos = token_start; pos < index; ++pos) {
      const unsigned char ch = static_cast<unsigned char>(text[pos]);
      if (!std::isdigit(ch)) return false;
      octet = octet * 10U + static_cast<uint32_t>(ch - '0');
      if (octet > 255U) return false;
    }
    octets[octet_index++] = octet;
    token_start = index + 1U;
  }
  if (octet_index != 4U) return false;
  *value = (octets[0] << 24U) | (octets[1] << 16U) |
           (octets[2] << 8U) | octets[3];
  return true;
}

bool valid_subnet_mask(uint32_t mask) {
  if (mask == 0U) return false;
  const uint32_t inverse = ~mask;
  return (inverse & (inverse + 1U)) == 0U;
}

bool valid_unicast_ipv4(uint32_t address) {
  const uint8_t first = static_cast<uint8_t>(address >> 24U);
  if (first == 0U || first == 127U || first >= 224U) return false;
  return address != 0xffffffffU;
}

bool same_candidate_host(
    const SimpleManagerCandidateV2 &left,
    const SimpleManagerCandidateV2 &right) {
  return left.host == right.host;
}

}

bool simple_discovery_candidate_allowed(
    const SimpleManagerCandidateV2 &candidate,
    const std::string &source_ipv4,
    const SimpleDiscoveryFilterContext &context) {
  if (context.expected_system_id.empty() ||
      candidate.system_id != context.expected_system_id) {
    return false;
  }

  uint32_t local = 0;
  uint32_t mask = 0;
  uint32_t advertised = 0;
  uint32_t source = 0;
  if (!parse_ipv4(context.local_ipv4, &local) ||
      !parse_ipv4(context.subnet_mask, &mask) ||
      !parse_ipv4(candidate.host, &advertised) ||
      !parse_ipv4(source_ipv4, &source) ||
      !valid_subnet_mask(mask) ||
      !valid_unicast_ipv4(local) ||
      !valid_unicast_ipv4(advertised) ||
      !valid_unicast_ipv4(source) ||
      advertised != source ||
      (advertised & mask) != (local & mask)) {
    return false;
  }

  const uint32_t host_mask = ~mask;
  if (host_mask != 0U) {
    const uint32_t network = local & mask;
    const uint32_t broadcast = network | host_mask;
    if (advertised == network || advertised == broadcast) return false;
  }
  return true;
}

std::vector<SimpleManagerCandidateV2> filter_simple_discovery_candidates(
    const std::vector<SimpleManagerCandidateV2> &candidates,
    const std::vector<std::string> &source_ipv4s,
    const SimpleDiscoveryFilterContext &context) {
  std::vector<SimpleManagerCandidateV2> retained;
  const std::size_t count = std::min(
      {candidates.size(), source_ipv4s.size(), kManagerDiscoveryMaxParsedDatagrams});
  for (std::size_t index = 0;
       index < count && retained.size() < kManagerDiscoveryMaxRetainedCandidates;
       ++index) {
    if (!simple_discovery_candidate_allowed(
            candidates[index], source_ipv4s[index], context)) {
      continue;
    }
    if (std::any_of(
            retained.begin(), retained.end(), [&](const SimpleManagerCandidateV2 &existing) {
              return same_candidate_host(existing, candidates[index]);
            })) {
      continue;
    }
    retained.push_back(candidates[index]);
  }
  return retained;
}

std::vector<SimpleBrokerRecoveryTarget> make_simple_broker_recovery_targets(
    const std::vector<SimpleManagerCandidateV2> &candidates,
    uint16_t durable_broker_port) {
  std::vector<SimpleBrokerRecoveryTarget> targets;
  if (durable_broker_port == 0U) return targets;
  const std::size_t count =
      std::min(candidates.size(), kManagerDiscoveryMaxAttemptCandidates);
  targets.reserve(count);
  for (std::size_t index = 0; index < count; ++index) {
    if (candidates[index].host.empty()) continue;
    targets.push_back(SimpleBrokerRecoveryTarget{
        candidates[index].host,
        durable_broker_port,
    });
  }
  return targets;
}

}
