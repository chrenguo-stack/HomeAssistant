#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace esphome::greenhouse_n3w_core {

constexpr std::size_t kEspNowMacBytes = 6;
constexpr std::size_t kEspNowLinkKeyBytes = 16;
constexpr std::size_t kControlAuthBytes = 16;
constexpr std::size_t kEspNowDatagramLimit = 240;
// Retired P5-lab compatibility note: kDataFragmentPayloadBytes = 180 now
// lives only in n3w_radio_legacy.h and is excluded from release builds.

using MacAddress = std::array<uint8_t, kEspNowMacBytes>;
using LinkKey = std::array<uint8_t, kEspNowLinkKeyBytes>;

enum class RadioError : uint8_t {
  NONE = 0,
  INVALID_ARGUMENT,
  PACKET_TOO_LARGE,
  PACKET_TRUNCATED,
  PACKET_FORMAT_REJECTED,
  PACKET_TYPE_REJECTED,
  AUTH_FAILED,
  BINDING_MISMATCH,
  CHANNEL_REJECTED,
  FRAGMENT_CONFLICT,
  DUPLICATE_FRAGMENT,
  REASSEMBLY_BUSY,
  CACHE_FULL,
  CACHE_NOT_FOUND,
  RETRY_EXHAUSTED,
};

enum class LinkPacketType : uint8_t {
  DISCOVERY_ADVERTISEMENT = 1,
  PROBE = 2,
  PROBE_ACK = 3,
#ifdef GREENHOUSE_N3W_ENABLE_LEGACY_RADIO
  DATA_FRAGMENT = 4,
  RECEIPT_ACK = 5,
#endif
};

struct RelayPeerBinding {
  std::string gateway_id;
  MacAddress peer_mac{};
  LinkKey lmk{};
  uint8_t preferred_channel{0};

  bool valid() const;
};

struct ChildPeerBinding {
  std::string node_id;
  MacAddress peer_mac{};
  LinkKey lmk{};

  bool valid() const;
};

struct DiscoveryAdvertisement {
  std::string gateway_id;
  uint8_t channel{0};
};

struct ProbePacket {
  uint64_t challenge{0};
  std::string gateway_id;
  std::string node_id;
};

struct ProbeAckPacket {
  uint64_t challenge{0};
  bool accepted{false};
};

bool valid_radio_channel(uint8_t channel);
bool same_mac(const MacAddress &left, const MacAddress &right);

RadioError encode_discovery_advertisement(
    const DiscoveryAdvertisement &packet,
    std::vector<uint8_t> *encoded);
RadioError decode_discovery_advertisement(
    const uint8_t *data,
    std::size_t size,
    DiscoveryAdvertisement *packet);
bool discovery_matches_binding(
    const RelayPeerBinding &binding,
    const MacAddress &source_mac,
    const DiscoveryAdvertisement &packet);

RadioError encode_authenticated_probe(
    const RelayPeerBinding &binding,
    const std::string &node_id,
    uint64_t challenge,
    std::vector<uint8_t> *encoded);
RadioError decode_authenticated_probe(
    const uint8_t *data,
    std::size_t size,
    const std::string &expected_gateway_id,
    const ChildPeerBinding &binding,
    ProbePacket *packet);

RadioError encode_authenticated_probe_ack(
    const LinkKey &lmk,
    uint64_t challenge,
    bool accepted,
    std::vector<uint8_t> *encoded);
RadioError decode_authenticated_probe_ack(
    const uint8_t *data,
    std::size_t size,
    const LinkKey &lmk,
    ProbeAckPacket *packet);

class ChannelScanPlan {
 public:
  RadioError configure(
      uint8_t last_direct_channel,
      const std::vector<uint8_t> &allowed_channels);
  uint8_t current() const;
  uint8_t advance();
  std::size_t size() const { return channels_.size(); }

 protected:
  std::vector<uint8_t> channels_;
  std::size_t index_{0};
};

enum class LocalPathState : uint8_t {
  DIRECT = 0,
  DISCOVERY,
  RELAY_ACTIVE,
};

struct LocalPathPolicy {
  uint8_t direct_failures_to_discovery{3};
  uint8_t direct_recoveries_to_direct{2};
  uint8_t relay_failures_to_discovery{2};

  bool valid() const;
};

class LocalPathController {
 public:
  explicit LocalPathController(LocalPathPolicy policy) : policy_(policy) {}

  LocalPathState state() const { return state_; }
  RadioError note_direct_result(bool success);
  RadioError note_authenticated_relay_ready(bool ready);
  RadioError note_relay_result(bool success);
  RadioError note_direct_recovery_probe(bool success);

 protected:
  LocalPathPolicy policy_{};
  LocalPathState state_{LocalPathState::DIRECT};
  uint8_t direct_failures_{0};
  uint8_t direct_recoveries_{0};
  uint8_t relay_failures_{0};
};

}  // namespace esphome::greenhouse_n3w_core

#ifdef GREENHOUSE_N3W_ENABLE_LEGACY_RADIO
#include "n3w_radio_legacy.h"
#endif
