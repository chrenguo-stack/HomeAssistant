#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>

#include "n3w_core.h"
#include "n3w_radio.h"

using namespace esphome::greenhouse_n3w_core;

namespace {

MacAddress mac(uint8_t last) {
  return MacAddress{0x02, 0x11, 0x22, 0x33, 0x44, last};
}

LinkKey link_key(uint8_t seed = 1) {
  LinkKey key{};
  for (std::size_t i = 0; i < key.size(); ++i) {
    key[i] = static_cast<uint8_t>(seed + i);
  }
  return key;
}

RelayFrame frame_with_size(std::size_t size, uint64_t session = 7, uint32_t seq = 9) {
  RelayFrame frame;
  frame.header.gateway_id = "gateway_t1";
  frame.header.node_id = "node_01";
  frame.header.key_epoch = 4;
  frame.header.boot_id = format_boot_id(session);
  frame.header.seq = seq;
  assert(derive_nonce(frame.header.boot_id, seq, &frame.nonce) == CoreError::NONE);
  frame.ciphertext.resize(size);
  for (std::size_t i = 0; i < size; ++i) {
    frame.ciphertext[i] = static_cast<uint8_t>((i * 17U + 3U) & 0xffU);
  }
  for (std::size_t i = 0; i < frame.tag.size(); ++i) {
    frame.tag[i] = static_cast<uint8_t>(0xa0U + i);
  }
  return frame;
}

void test_binding_and_discovery() {
  RelayPeerBinding binding;
  binding.gateway_id = "gateway_t1";
  binding.peer_mac = mac(0x55);
  binding.lmk = link_key();
  binding.preferred_channel = 6;
  assert(binding.valid());

  DiscoveryAdvertisement adv{binding.gateway_id, 6};
  std::vector<uint8_t> encoded;
  assert(encode_discovery_advertisement(adv, &encoded) == RadioError::NONE);
  assert(encoded.size() <= kEspNowDatagramLimit);
  DiscoveryAdvertisement parsed;
  assert(decode_discovery_advertisement(encoded.data(), encoded.size(), &parsed) ==
         RadioError::NONE);
  assert(discovery_matches_binding(binding, binding.peer_mac, parsed));

  auto wrong_mac = binding.peer_mac;
  wrong_mac[5] ^= 0x02;
  assert(!discovery_matches_binding(binding, wrong_mac, parsed));
  parsed.gateway_id = "gateway_other";
  assert(!discovery_matches_binding(binding, binding.peer_mac, parsed));
}

void test_probe_and_control_auth() {
  RelayPeerBinding relay;
  relay.gateway_id = "gateway_t1";
  relay.peer_mac = mac(0x55);
  relay.lmk = link_key(7);
  relay.preferred_channel = 11;

  ChildPeerBinding child;
  child.node_id = "node_01";
  child.peer_mac = mac(0x66);
  child.lmk = relay.lmk;

  std::vector<uint8_t> probe;
  constexpr uint64_t challenge = 0x0102030405060708ULL;
  assert(encode_authenticated_probe(relay, child.node_id, challenge, &probe) ==
         RadioError::NONE);
  ProbePacket parsed;
  assert(decode_authenticated_probe(
             probe.data(), probe.size(), relay.gateway_id, child, &parsed) ==
         RadioError::NONE);
  assert(parsed.challenge == challenge);
  assert(parsed.gateway_id == relay.gateway_id);
  assert(parsed.node_id == child.node_id);

  auto tampered = probe;
  tampered[tampered.size() - 1] ^= 0x01;
  assert(decode_authenticated_probe(
             tampered.data(), tampered.size(), relay.gateway_id, child, &parsed) ==
         RadioError::AUTH_FAILED);

  std::vector<uint8_t> probe_ack;
  assert(encode_authenticated_probe_ack(relay.lmk, challenge, true, &probe_ack) ==
         RadioError::NONE);
  ProbeAckPacket ack{};
  assert(decode_authenticated_probe_ack(
             probe_ack.data(), probe_ack.size(), relay.lmk, &ack) ==
         RadioError::NONE);
  assert(ack.accepted && ack.challenge == challenge);

  std::vector<uint8_t> receipt;
  assert(encode_authenticated_receipt_ack(
             relay.lmk,
             7,
             9,
             ReceiptStatus::ACCEPTED_FOR_FORWARDING,
             &receipt) == RadioError::NONE);
  ReceiptAckPacket parsed_receipt{};
  assert(decode_authenticated_receipt_ack(
             receipt.data(), receipt.size(), relay.lmk, &parsed_receipt) ==
         RadioError::NONE);
  assert(parsed_receipt.boot_session == 7 && parsed_receipt.seq == 9);
  assert(parsed_receipt.status == ReceiptStatus::ACCEPTED_FOR_FORWARDING);

  receipt[5] ^= 0x40;
  assert(decode_authenticated_receipt_ack(
             receipt.data(), receipt.size(), relay.lmk, &parsed_receipt) ==
         RadioError::AUTH_FAILED);
}

void check_fragment_size(std::size_t ciphertext_size, std::size_t expected_count) {
  RelayFrame source = frame_with_size(ciphertext_size);
  std::vector<std::vector<uint8_t>> datagrams;
  assert(fragment_relay_frame(source, &datagrams) == RadioError::NONE);
  assert(datagrams.size() == expected_count);
  for (const auto &packet : datagrams) {
    assert(!packet.empty());
    assert(packet.size() <= kEspNowDatagramLimit);
  }

  RelayReassembler reassembler;
  RelayFrame rebuilt;
  bool complete = false;
  for (auto it = datagrams.rbegin(); it != datagrams.rend(); ++it) {
    const RadioError err = reassembler.accept(
        it->data(), it->size(), source.header.gateway_id, source.header.node_id,
        &rebuilt, &complete);
    assert(err == RadioError::NONE);
  }
  assert(complete);
  assert(rebuilt.header.gateway_id == source.header.gateway_id);
  assert(rebuilt.header.node_id == source.header.node_id);
  assert(rebuilt.header.key_epoch == source.header.key_epoch);
  assert(rebuilt.header.boot_id == source.header.boot_id);
  assert(rebuilt.header.seq == source.header.seq);
  assert(rebuilt.nonce == source.nonce);
  assert(rebuilt.tag == source.tag);
  assert(rebuilt.ciphertext == source.ciphertext);
}

void test_fragmentation_and_reassembly() {
  check_fragment_size(1, 1);
  check_fragment_size(180, 1);
  check_fragment_size(181, 2);
  check_fragment_size(1024, 6);

  RelayFrame source = frame_with_size(400);
  std::vector<std::vector<uint8_t>> datagrams;
  assert(fragment_relay_frame(source, &datagrams) == RadioError::NONE);
  RelayReassembler reassembler;
  RelayFrame rebuilt;
  bool complete = false;
  assert(reassembler.accept(
             datagrams[0].data(), datagrams[0].size(), source.header.gateway_id,
             source.header.node_id, &rebuilt, &complete) == RadioError::NONE);
  assert(!complete);
  assert(reassembler.accept(
             datagrams[0].data(), datagrams[0].size(), source.header.gateway_id,
             source.header.node_id, &rebuilt, &complete) ==
         RadioError::DUPLICATE_FRAGMENT);

  auto conflict = datagrams[0];
  conflict.back() ^= 0x01;
  assert(reassembler.accept(
             conflict.data(), conflict.size(), source.header.gateway_id,
             source.header.node_id, &rebuilt, &complete) ==
         RadioError::FRAGMENT_CONFLICT);

  RelayFrame other = frame_with_size(200, 8, 1);
  std::vector<std::vector<uint8_t>> other_packets;
  assert(fragment_relay_frame(other, &other_packets) == RadioError::NONE);
  assert(reassembler.accept(
             other_packets[0].data(), other_packets[0].size(), source.header.gateway_id,
             source.header.node_id, &rebuilt, &complete) ==
         RadioError::REASSEMBLY_BUSY);
}

class RecordingSink : public RelayForwardSink {
 public:
  explicit RecordingSink(bool accepted) : accepted_(accepted) {}
  bool accept_for_forwarding(const RelayFrame &frame) override {
    ++calls;
    last = frame;
    return accepted_;
  }
  bool accepted_{true};
  int calls{0};
  RelayFrame last{};
};

void test_receipt_is_after_forward_sink_acceptance() {
  RelayFrame source = frame_with_size(512, 55, 123);
  std::vector<std::vector<uint8_t>> datagrams;
  assert(fragment_relay_frame(source, &datagrams) == RadioError::NONE);
  RecordingSink sink(true);
  RelayIngressController ingress(&sink);
  ReceiptAckPacket receipt{};
  bool ready = false;
  for (std::size_t i = 0; i < datagrams.size(); ++i) {
    assert(ingress.accept_fragment(
               datagrams[i].data(), datagrams[i].size(), source.header.gateway_id,
               source.header.node_id, &receipt, &ready) == RadioError::NONE);
    if (i + 1 < datagrams.size()) {
      assert(!ready);
    }
  }
  assert(ready);
  assert(sink.calls == 1);
  assert(receipt.boot_session == 55 && receipt.seq == 123);
  assert(receipt.status == ReceiptStatus::ACCEPTED_FOR_FORWARDING);

  RecordingSink rejecting(false);
  RelayIngressController rejected_ingress(&rejecting);
  ready = false;
  for (const auto &packet : datagrams) {
    assert(rejected_ingress.accept_fragment(
               packet.data(), packet.size(), source.header.gateway_id,
               source.header.node_id, &receipt, &ready) == RadioError::NONE);
  }
  assert(!ready);
  assert(receipt.status == ReceiptStatus::REJECTED);
}

void test_cache_retry_and_exact_ack() {
  RelayFrame source = frame_with_size(300, 91, 44);
  RetryPolicy policy{100, 800, 3};
  ChildRelayCache cache(2, policy);
  assert(cache.enqueue(source, 1000) == RadioError::NONE);
  assert(cache.size() == 1);
  const CachedRelayFrame *first = cache.next_due(1000);
  assert(first != nullptr);
  const auto immutable_datagrams = first->datagrams;

  assert(cache.note_attempt(91, 44, 1000) == RadioError::NONE);
  assert(cache.next_due(1099) == nullptr);
  const CachedRelayFrame *second = cache.next_due(1100);
  assert(second != nullptr);
  assert(second->datagrams == immutable_datagrams);
  assert(cache.note_attempt(91, 44, 1100) == RadioError::NONE);
  assert(cache.next_due(1299) == nullptr);
  assert(cache.next_due(1300) != nullptr);
  assert(cache.note_attempt(91, 44, 1300) == RadioError::RETRY_EXHAUSTED);
  assert(cache.next_due(UINT64_MAX) == nullptr);

  ReceiptAckPacket wrong{91, 43, ReceiptStatus::ACCEPTED_FOR_FORWARDING};
  assert(!cache.acknowledge(wrong));
  ReceiptAckPacket rejected{91, 44, ReceiptStatus::REJECTED};
  assert(!cache.acknowledge(rejected));
  ReceiptAckPacket accepted{91, 44, ReceiptStatus::ACCEPTED_FOR_FORWARDING};
  assert(cache.acknowledge(accepted));
  assert(cache.size() == 0);
}

void test_channel_scan_and_local_path_fsm() {
  ChannelScanPlan channels;
  assert(channels.configure(6, {1, 6, 11}) == RadioError::NONE);
  assert(channels.size() == 3);
  assert(channels.current() == 6);
  assert(channels.advance() == 1);
  assert(channels.advance() == 11);
  assert(channels.advance() == 6);

  LocalPathController path(LocalPathPolicy{2, 2, 2});
  assert(path.state() == LocalPathState::DIRECT);
  assert(path.note_direct_result(false) == RadioError::NONE);
  assert(path.state() == LocalPathState::DIRECT);
  assert(path.note_direct_result(false) == RadioError::NONE);
  assert(path.state() == LocalPathState::DISCOVERY);
  assert(path.note_authenticated_relay_ready(true) == RadioError::NONE);
  assert(path.state() == LocalPathState::RELAY_ACTIVE);
  assert(path.note_direct_recovery_probe(true) == RadioError::NONE);
  assert(path.state() == LocalPathState::RELAY_ACTIVE);
  assert(path.note_direct_recovery_probe(true) == RadioError::NONE);
  assert(path.state() == LocalPathState::DIRECT);

  LocalPathController relay_failure(LocalPathPolicy{1, 2, 2});
  relay_failure.note_direct_result(false);
  relay_failure.note_authenticated_relay_ready(true);
  assert(relay_failure.note_relay_result(false) == RadioError::NONE);
  assert(relay_failure.state() == LocalPathState::RELAY_ACTIVE);
  assert(relay_failure.note_relay_result(false) == RadioError::NONE);
  assert(relay_failure.state() == LocalPathState::DISCOVERY);
  assert(relay_failure.note_direct_recovery_probe(true) == RadioError::NONE);
  assert(relay_failure.note_direct_recovery_probe(true) == RadioError::NONE);
  assert(relay_failure.state() == LocalPathState::DIRECT);
}

}  // namespace

int main() {
  static_assert(kEspNowDatagramLimit <= 240);
  static_assert(kMaxDataFragments == 6);
  test_binding_and_discovery();
  test_probe_and_control_auth();
  test_fragmentation_and_reassembly();
  test_receipt_is_after_forward_sink_acceptance();
  test_cache_retry_and_exact_ack();
  test_channel_scan_and_local_path_fsm();
  std::cout << "N3-W P4b host-only radio contract tests PASS\n";
  return 0;
}
