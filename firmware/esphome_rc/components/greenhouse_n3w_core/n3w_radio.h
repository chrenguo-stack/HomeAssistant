#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>

#include "n3w_core.h"

namespace esphome::greenhouse_n3w_core {

constexpr std::size_t kEspNowMacBytes = 6;
constexpr std::size_t kEspNowLinkKeyBytes = 16;
constexpr std::size_t kControlAuthBytes = 16;
constexpr std::size_t kEspNowDatagramLimit = 240;
constexpr std::size_t kDataFragmentPayloadBytes = 180;
constexpr std::size_t kMaxDataFragments =
    (kMaxCiphertextBytes + kDataFragmentPayloadBytes - 1) /
    kDataFragmentPayloadBytes;

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
  DATA_FRAGMENT = 4,
  RECEIPT_ACK = 5,
};

enum class ReceiptStatus : uint8_t {
  ACCEPTED_FOR_FORWARDING = 0,
  REJECTED = 1,
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

struct ReceiptAckPacket {
  uint64_t boot_session{0};
  uint32_t seq{0};
  ReceiptStatus status{ReceiptStatus::REJECTED};
};

struct DataFragment {
  uint64_t boot_session{0};
  uint32_t seq{0};
  uint32_t key_epoch{0};
  uint16_t total_ciphertext{0};
  uint8_t fragment_index{0};
  uint8_t fragment_count{0};
  uint16_t offset{0};
  std::array<uint8_t, kNonceBytes> nonce{};
  std::array<uint8_t, kTagBytes> tag{};
  std::vector<uint8_t> payload;
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

RadioError encode_authenticated_receipt_ack(
    const LinkKey &lmk,
    uint64_t boot_session,
    uint32_t seq,
    ReceiptStatus status,
    std::vector<uint8_t> *encoded);
RadioError decode_authenticated_receipt_ack(
    const uint8_t *data,
    std::size_t size,
    const LinkKey &lmk,
    ReceiptAckPacket *packet);

RadioError encode_data_fragment(
    const DataFragment &fragment,
    std::vector<uint8_t> *encoded);
RadioError decode_data_fragment(
    const uint8_t *data,
    std::size_t size,
    DataFragment *fragment);

RadioError fragment_relay_frame(
    const RelayFrame &frame,
    std::vector<std::vector<uint8_t>> *datagrams);

class RelayReassembler {
 public:
  RadioError accept(
      const uint8_t *data,
      std::size_t size,
      const std::string &gateway_id,
      const std::string &node_id,
      RelayFrame *frame,
      bool *complete);
  void reset();

 protected:
  bool active_{false};
  uint64_t boot_session_{0};
  uint32_t seq_{0};
  uint32_t key_epoch_{0};
  uint16_t total_ciphertext_{0};
  uint8_t fragment_count_{0};
  std::array<uint8_t, kNonceBytes> nonce_{};
  std::array<uint8_t, kTagBytes> tag_{};
  std::vector<uint8_t> ciphertext_;
  std::vector<bool> received_;
};

class RelayForwardSink {
 public:
  virtual ~RelayForwardSink() = default;
  virtual bool accept_for_forwarding(const RelayFrame &frame) = 0;
};

class RelayIngressController {
 public:
  explicit RelayIngressController(RelayForwardSink *sink) : sink_(sink) {}

  RadioError accept_fragment(
      const uint8_t *data,
      std::size_t size,
      const std::string &gateway_id,
      const std::string &node_id,
      ReceiptAckPacket *receipt,
      bool *receipt_ready);
  void reset() { reassembler_.reset(); }

 protected:
  RelayForwardSink *sink_{nullptr};
  RelayReassembler reassembler_{};
};

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

struct RetryPolicy {
  uint32_t initial_delay_ms{500};
  uint32_t max_delay_ms{8000};
  uint8_t max_attempts{5};

  bool valid() const;
};

struct CachedRelayFrame {
  uint64_t boot_session{0};
  uint32_t seq{0};
  std::vector<std::vector<uint8_t>> datagrams;
  uint8_t attempts{0};
  uint64_t next_due_ms{0};
  bool exhausted{false};
};

class ChildRelayCache {
 public:
  ChildRelayCache(std::size_t capacity, RetryPolicy policy)
      : capacity_(capacity), policy_(policy) {}

  RadioError enqueue(
      const RelayFrame &frame,
      uint64_t now_ms);
  const CachedRelayFrame *next_due(uint64_t now_ms) const;
  RadioError note_attempt(
      uint64_t boot_session,
      uint32_t seq,
      uint64_t now_ms);
  bool acknowledge(const ReceiptAckPacket &ack);
  bool discard(uint64_t boot_session, uint32_t seq) {
    if (boot_session == 0) return false;
    for (auto it = entries_.begin(); it != entries_.end(); ++it) {
      if (it->boot_session == boot_session && it->seq == seq) {
        entries_.erase(it);
        return true;
      }
    }
    return false;
  }
  std::size_t size() const { return entries_.size(); }
  bool full() const { return capacity_ == 0 || entries_.size() >= capacity_; }

 protected:
  CachedRelayFrame *find_(uint64_t boot_session, uint32_t seq);
  static uint64_t saturating_add_(uint64_t left, uint64_t right);

  std::size_t capacity_{0};
  RetryPolicy policy_{};
  std::vector<CachedRelayFrame> entries_;
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
