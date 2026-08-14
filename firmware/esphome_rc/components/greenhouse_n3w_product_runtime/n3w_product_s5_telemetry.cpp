#include "n3w_product_s5_telemetry.h"

#include <algorithm>
#include <utility>
#include <vector>

namespace esphome::greenhouse_n3w_product_runtime {

ProductS5TelemetryBridge::ProductS5TelemetryBridge(
    ProductS5TelemetryRole role,
    std::string local_node_id,
    ProductRuntimeRadioPort *radio,
    RelayForwardSink *forward_sink,
    std::size_t cache_capacity,
    RetryPolicy retry_policy)
    : role_(role),
      local_node_id_(std::move(local_node_id)),
      radio_(radio),
      forward_sink_(forward_sink),
      cache_capacity_(cache_capacity),
      retry_policy_(retry_policy),
      child_cache_(cache_capacity, retry_policy),
      relay_ingress_(this) {}

ProductS5TelemetryBridge::~ProductS5TelemetryBridge() { clear_active_peer_(); }

bool ProductS5TelemetryBridge::same_mac_(const MacAddress &left, const MacAddress &right) {
  return std::equal(left.begin(), left.end(), right.begin());
}

bool ProductS5TelemetryBridge::nonzero_key_(const LinkKey &key) {
  uint8_t aggregate = 0;
  for (uint8_t value : key) aggregate |= value;
  return aggregate != 0;
}

void ProductS5TelemetryBridge::zeroize_(void *data, std::size_t length) {
  if (data == nullptr) return;
  volatile uint8_t *cursor = static_cast<volatile uint8_t *>(data);
  while (length-- > 0) *cursor++ = 0;
}

void ProductS5TelemetryBridge::clear_active_peer_() {
  active_peer_mac_.reset();
  zeroize_(active_lmk_.data(), active_lmk_.size());
  active_channel_ = 0;
  relay_child_node_id_.clear();
  relay_ingress_.reset();
  if (role_ == ProductS5TelemetryRole::CHILD) {
    child_cache_ = ChildRelayCache(cache_capacity_, retry_policy_);
  }
}

bool ProductS5TelemetryBridge::set_relay_child_node_id(const std::string &node_id) {
  if (role_ != ProductS5TelemetryRole::RELAY ||
      !greenhouse_n3w_core::valid_identity(node_id) || node_id == local_node_id_) {
    return false;
  }
  relay_child_node_id_ = node_id;
  return true;
}

void ProductS5TelemetryBridge::clear_relay_child_node_id() {
  relay_child_node_id_.clear();
  relay_ingress_.reset();
}

void ProductS5TelemetryBridge::on_s5_peer_installed(
    const MacAddress &peer_mac,
    const LinkKey &lmk,
    uint8_t channel) {
  if (!nonzero_key_(lmk) || !greenhouse_n3w_core::valid_radio_channel(channel)) {
    last_error_ = ProductS5TelemetryError::INVALID_ARGUMENT;
    return;
  }
  if (active_peer_mac_.has_value()) clear_active_peer_();
  active_peer_mac_ = peer_mac;
  active_lmk_ = lmk;
  active_channel_ = channel;
  last_error_ = ProductS5TelemetryError::NONE;
}

void ProductS5TelemetryBridge::on_s5_peer_removed(const MacAddress &peer_mac) {
  if (active_peer_mac_.has_value() && same_mac_(*active_peer_mac_, peer_mac)) {
    clear_active_peer_();
  }
}

bool ProductS5TelemetryBridge::accept_for_forwarding(const RelayFrame &frame) {
  if (role_ != ProductS5TelemetryRole::RELAY || forward_sink_ == nullptr ||
      frame.header.schema != "gh.relay/1" || frame.header.transport != "esp_now" ||
      frame.header.gateway_id != local_node_id_ ||
      frame.header.node_id != relay_child_node_id_) {
    return false;
  }
  return forward_sink_->accept_for_forwarding(frame);
}

ProductS5TelemetryError ProductS5TelemetryBridge::flush_due_(uint64_t now_ms) {
  if (role_ != ProductS5TelemetryRole::CHILD || radio_ == nullptr ||
      !active_peer_mac_.has_value() || !nonzero_key_(active_lmk_)) {
    return ProductS5TelemetryError::NOT_READY;
  }
  const auto *due = child_cache_.next_due(now_ms);
  if (due == nullptr) return ProductS5TelemetryError::NONE;

  const uint64_t boot_session = due->boot_session;
  const uint32_t seq = due->seq;
  const auto datagrams = due->datagrams;
  const auto attempt = child_cache_.note_attempt(boot_session, seq, now_ms);
  if (attempt != greenhouse_n3w_core::RadioError::NONE &&
      attempt != greenhouse_n3w_core::RadioError::RETRY_EXHAUSTED) {
    return ProductS5TelemetryError::CACHE_FAILED;
  }
  for (const auto &datagram : datagrams) {
    if (radio_->send_peer(*active_peer_mac_, datagram.data(), datagram.size()) != DriverError::NONE) {
      return ProductS5TelemetryError::RADIO_FAILED;
    }
  }
  return ProductS5TelemetryError::NONE;
}

ProductS5TelemetryError ProductS5TelemetryBridge::send_relay_frame(
    const RelayFrame &frame,
    uint64_t now_ms) {
  if (role_ != ProductS5TelemetryRole::CHILD || radio_ == nullptr ||
      !active_peer_mac_.has_value() || !nonzero_key_(active_lmk_)) {
    return ProductS5TelemetryError::NOT_READY;
  }
  if (frame.header.schema != "gh.relay/1" || frame.header.transport != "esp_now" ||
      frame.header.node_id != local_node_id_) {
    return ProductS5TelemetryError::FRAME_REJECTED;
  }
  const auto queued = child_cache_.enqueue(frame, now_ms);
  if (queued != greenhouse_n3w_core::RadioError::NONE) {
    return ProductS5TelemetryError::CACHE_FAILED;
  }
  last_error_ = flush_due_(now_ms);
  return last_error_;
}

ProductS5TelemetryError ProductS5TelemetryBridge::tick(uint64_t now_ms) {
  if (role_ != ProductS5TelemetryRole::CHILD) return ProductS5TelemetryError::NONE;
  if (!active_peer_mac_.has_value()) return ProductS5TelemetryError::NONE;
  last_error_ = flush_due_(now_ms);
  return last_error_;
}

void ProductS5TelemetryBridge::on_s5_telemetry_datagram(
    const MacAddress &source,
    const uint8_t *data,
    std::size_t size,
    const EspNowReceiveMetadata &metadata) {
  (void) metadata;
  if (data == nullptr || size == 0 || !active_peer_mac_.has_value() ||
      !same_mac_(source, *active_peer_mac_) || !nonzero_key_(active_lmk_)) {
    return;
  }

  if (role_ == ProductS5TelemetryRole::CHILD) {
    greenhouse_n3w_core::ReceiptAckPacket receipt;
    if (greenhouse_n3w_core::decode_authenticated_receipt_ack(
            data, size, active_lmk_, &receipt) == greenhouse_n3w_core::RadioError::NONE) {
      (void) child_cache_.acknowledge(receipt);
      last_error_ = ProductS5TelemetryError::NONE;
    }
    return;
  }

  if (relay_child_node_id_.empty() || forward_sink_ == nullptr) {
    last_error_ = ProductS5TelemetryError::NOT_READY;
    return;
  }
  greenhouse_n3w_core::ReceiptAckPacket receipt;
  bool receipt_ready = false;
  const auto accepted = relay_ingress_.accept_fragment(
      data,
      size,
      local_node_id_,
      relay_child_node_id_,
      &receipt,
      &receipt_ready);
  if (accepted != greenhouse_n3w_core::RadioError::NONE &&
      accepted != greenhouse_n3w_core::RadioError::DUPLICATE_FRAGMENT) {
    last_error_ = ProductS5TelemetryError::FRAME_REJECTED;
    return;
  }
  if (!receipt_ready) return;

  std::vector<uint8_t> encoded;
  if (greenhouse_n3w_core::encode_authenticated_receipt_ack(
          active_lmk_, receipt.boot_session, receipt.seq, receipt.status, &encoded) !=
          greenhouse_n3w_core::RadioError::NONE ||
      radio_ == nullptr ||
      radio_->send_peer(source, encoded.data(), encoded.size()) != DriverError::NONE) {
    last_error_ = ProductS5TelemetryError::RADIO_FAILED;
    return;
  }
  last_error_ = ProductS5TelemetryError::NONE;
}

}  // namespace esphome::greenhouse_n3w_product_runtime
