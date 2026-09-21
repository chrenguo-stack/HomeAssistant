#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>

#include "n3w_core.h"
#include "n3w_radio.h"

namespace esphome::greenhouse_n3w_core {

// Phase 5-B quarantine only. This interface exists solely so the frozen P5 lab
// can still compile as a regression reference. Release/runtime code must not
// include this header.
constexpr std::size_t kDataFragmentPayloadBytes = 180;
constexpr std::size_t kMaxDataFragments =
    (kMaxCiphertextBytes + kDataFragmentPayloadBytes - 1) /
    kDataFragmentPayloadBytes;

enum class ReceiptStatus : uint8_t {
  ACCEPTED_FOR_FORWARDING = 0,
  REJECTED = 1,
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

  RadioError enqueue(const RelayFrame &frame, uint64_t now_ms);
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
  bool full() const {
    return capacity_ == 0 || entries_.size() >= capacity_;
  }

 protected:
  CachedRelayFrame *find_(uint64_t boot_session, uint32_t seq);
  static uint64_t saturating_add_(uint64_t left, uint64_t right);

  std::size_t capacity_{0};
  RetryPolicy policy_{};
  std::vector<CachedRelayFrame> entries_;
};

}  // namespace esphome::greenhouse_n3w_core
