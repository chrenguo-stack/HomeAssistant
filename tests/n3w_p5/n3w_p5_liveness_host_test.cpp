#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>

#include "n3w_core.h"
#include "n3w_radio.h"

using namespace esphome::greenhouse_n3w_core;

namespace {

RelayFrame frame(uint64_t session, uint32_t seq) {
  RelayFrame result;
  result.header.gateway_id = "n3wp5_relay01";
  result.header.node_id = "n3wp5_child01";
  result.header.key_epoch = 1;
  result.header.boot_id = format_boot_id(session);
  result.header.seq = seq;
  assert(derive_nonce(result.header.boot_id, seq, &result.nonce) == CoreError::NONE);
  result.ciphertext.assign(240, static_cast<uint8_t>(seq & 0xffU));
  result.tag.fill(0x5a);
  return result;
}

class RejectingSink final : public RelayForwardSink {
 public:
  bool accept_for_forwarding(const RelayFrame &value) override {
    ++calls;
    last_seq = value.header.seq;
    return false;
  }

  int calls{0};
  uint32_t last_seq{0};
};

void test_exhausted_entry_can_be_discarded_and_capacity_recovers() {
  ChildRelayCache cache(2, RetryPolicy{100, 400, 2});
  assert(cache.enqueue(frame(77, 1), 1000) == RadioError::NONE);
  assert(cache.enqueue(frame(77, 2), 1000) == RadioError::NONE);
  assert(cache.size() == 2);
  assert(cache.full());
  assert(cache.enqueue(frame(77, 3), 1000) == RadioError::CACHE_FULL);

  assert(cache.note_attempt(77, 1, 1000) == RadioError::NONE);
  assert(cache.note_attempt(77, 1, 1100) == RadioError::RETRY_EXHAUSTED);
  assert(cache.discard(77, 1));
  assert(cache.size() == 1);
  assert(!cache.full());
  assert(cache.enqueue(frame(77, 3), 1100) == RadioError::NONE);
  assert(cache.full());

  assert(!cache.discard(77, 99));
  assert(!cache.discard(0, 2));
}

void test_repeated_retry_exhaustion_never_permanently_fills_cache() {
  ChildRelayCache cache(2, RetryPolicy{1, 1, 1});
  for (uint32_t seq = 1; seq <= 100; ++seq) {
    assert(!cache.full());
    assert(cache.enqueue(frame(88, seq), seq) == RadioError::NONE);
    assert(cache.note_attempt(88, seq, seq) == RadioError::RETRY_EXHAUSTED);
    assert(cache.discard(88, seq));
    assert(cache.size() == 0);
    assert(!cache.full());
  }
}

void test_rejected_forwarding_has_exact_rejected_receipt_identity() {
  RelayFrame source = frame(99, 42);
  std::vector<std::vector<uint8_t>> datagrams;
  assert(fragment_relay_frame(source, &datagrams) == RadioError::NONE);

  RejectingSink sink;
  RelayIngressController ingress(&sink);
  ReceiptAckPacket receipt{};
  bool receipt_ready = false;
  for (const auto &packet : datagrams) {
    assert(ingress.accept_fragment(
               packet.data(), packet.size(), source.header.gateway_id,
               source.header.node_id, &receipt, &receipt_ready) == RadioError::NONE);
  }

  assert(sink.calls == 1);
  assert(sink.last_seq == 42);
  assert(!receipt_ready);
  assert(receipt.boot_session == 99);
  assert(receipt.seq == 42);
  assert(receipt.status == ReceiptStatus::REJECTED);
}

void test_rejected_receipt_does_not_claim_forward_success() {
  ChildRelayCache cache(1, RetryPolicy{100, 400, 2});
  assert(cache.enqueue(frame(101, 7), 0) == RadioError::NONE);
  ReceiptAckPacket rejected{101, 7, ReceiptStatus::REJECTED};
  assert(!cache.acknowledge(rejected));
  assert(cache.size() == 1);
  ReceiptAckPacket accepted{101, 7, ReceiptStatus::ACCEPTED_FOR_FORWARDING};
  assert(cache.acknowledge(accepted));
  assert(cache.size() == 0);
}

}  // namespace

int main() {
  test_exhausted_entry_can_be_discarded_and_capacity_recovers();
  test_repeated_retry_exhaustion_never_permanently_fills_cache();
  test_rejected_forwarding_has_exact_rejected_receipt_identity();
  test_rejected_receipt_does_not_claim_forward_success();
  std::cout << "N3-W P5 relay cache liveness host-only tests PASS\n";
  return 0;
}
