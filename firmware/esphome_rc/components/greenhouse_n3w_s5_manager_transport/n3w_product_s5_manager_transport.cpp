#include "n3w_product_s5_manager_transport.h"

#include <limits>
#include <utility>

namespace esphome::greenhouse_n3w_s5_manager_transport {

ProductS5IsolatedManagerTransport::ProductS5IsolatedManagerTransport(
    std::string system_id,
    std::string relay_node_id,
    ProductRuntimeClock *clock,
    ProductS5MessageBusPort *bus,
    ProductS5ManagerAuthorizationSink *authorization_sink,
    ProductS5ManagerTransportPolicy policy)
    : system_id_(std::move(system_id)),
      relay_node_id_(std::move(relay_node_id)),
      clock_(clock),
      bus_(bus),
      authorization_sink_(authorization_sink),
      policy_(policy) {}

bool ProductS5IsolatedManagerTransport::start() {
  if (started_ || clock_ == nullptr || bus_ == nullptr ||
      authorization_sink_ == nullptr || !policy_.valid() ||
      !ProductPeerSecurity::valid_identifier_(system_id_) ||
      !ProductPeerSecurity::valid_identifier_(relay_node_id_)) {
    return false;
  }

  response_subscription_ =
      product_peer_authorization_response_subscription(
          system_id_, relay_node_id_);
  time_request_topic_ =
      product_peer_authority_time_request_topic(
          system_id_, relay_node_id_);
  time_response_topic_ =
      product_peer_authority_time_response_topic(
          system_id_, relay_node_id_);
  if (response_subscription_.empty() || time_request_topic_.empty() ||
      time_response_topic_.empty() ||
      !bus_->begin(response_subscription_, this)) {
    return false;
  }

  started_ = true;
  return true;
}

void ProductS5IsolatedManagerTransport::clear_authority_anchor_() {
  authority_anchor_valid_ = false;
  authority_anchor_epoch_ms_ = 0;
  authority_anchor_local_ms_ = 0;
}

bool ProductS5IsolatedManagerTransport::request_authority_time_(
    uint64_t local_now_ms) {
  if (!started_ || bus_ == nullptr || !bus_->connected() ||
      time_request_pending_) {
    return false;
  }

  ++time_request_counter_;
  if (time_request_counter_ == 0) ++time_request_counter_;
  const std::string nonce =
      "s5t-" + std::to_string(time_request_counter_) + "-" +
      std::to_string(local_now_ms);
  std::string payload;
  if (!valid_product_transport_nonce(nonce) ||
      !encode_peer_authority_time_request_json(nonce, &payload) ||
      !bus_->publish_message(time_request_topic_, payload, 1, false)) {
    return false;
  }

  time_request_pending_ = true;
  time_request_local_ms_ = local_now_ms;
  time_request_nonce_ = nonce;
  return true;
}

bool ProductS5IsolatedManagerTransport::authority_now_ms(uint64_t *now_ms) {
  if (now_ms == nullptr || !started_ || clock_ == nullptr) return false;

  const uint64_t local_now_ms = clock_->now_ms();
  if (time_request_pending_ &&
      (local_now_ms < time_request_local_ms_ ||
       local_now_ms - time_request_local_ms_ >
           policy_.authority_request_timeout_ms)) {
    time_request_pending_ = false;
    time_request_local_ms_ = 0;
    time_request_nonce_.clear();
  }

  if (authority_anchor_valid_) {
    if (local_now_ms < authority_anchor_local_ms_) {
      clear_authority_anchor_();
    } else {
      const uint64_t age = local_now_ms - authority_anchor_local_ms_;
      if (age > policy_.authority_max_age_ms ||
          authority_anchor_epoch_ms_ >
              std::numeric_limits<uint64_t>::max() - age) {
        clear_authority_anchor_();
      } else {
        *now_ms = authority_anchor_epoch_ms_ + age;
        if (age >= policy_.authority_refresh_interval_ms &&
            !time_request_pending_) {
          (void) request_authority_time_(local_now_ms);
        }
        return *now_ms != 0;
      }
    }
  }

  if (!time_request_pending_) {
    (void) request_authority_time_(local_now_ms);
  }
  return false;
}

bool ProductS5IsolatedManagerTransport::submit_peer_authorization(
    const ProductPeerRequest &request) {
  if (!started_ || bus_ == nullptr || !bus_->connected() ||
      !pending_authorization_session_.empty() ||
      !request.valid_shape(true) ||
      request.system_id != system_id_ ||
      request.relay.node_id != relay_node_id_) {
    return false;
  }

  uint64_t authority_now = 0;
  if (!authority_now_ms(&authority_now)) return false;
  const uint64_t delta = request.requested_at_ms > authority_now
                             ? request.requested_at_ms - authority_now
                             : authority_now - request.requested_at_ms;
  if (delta > policy_.authority_request_timeout_ms) return false;

  const std::string topic =
      product_peer_authorization_request_topic(
          system_id_, relay_node_id_);
  std::string payload;
  if (topic.empty() ||
      !encode_peer_authorization_request_json(request, &payload) ||
      !bus_->publish_message(topic, payload, 1, false)) {
    return false;
  }

  pending_authorization_session_ = request.session_id;
  return true;
}

bool ProductS5IsolatedManagerTransport::same_grant_pair_(
    const ProductPeerGrant &child,
    const ProductPeerGrant &relay) {
  return child.role == ProductPeerRole::CHILD &&
         relay.role == ProductPeerRole::RELAY &&
         child.authorization_id == relay.authorization_id &&
         child.system_id == relay.system_id &&
         child.session_id == relay.session_id &&
         child.child_node_id == relay.child_node_id &&
         child.relay_node_id == relay.relay_node_id &&
         child.child_credential_generation ==
             relay.child_credential_generation &&
         child.relay_credential_generation ==
             relay.relay_credential_generation &&
         child.child_key_epoch == relay.child_key_epoch &&
         child.relay_key_epoch == relay.relay_key_epoch &&
         child.child_ephemeral_public_key ==
             relay.child_ephemeral_public_key &&
         child.relay_ephemeral_public_key ==
             relay.relay_ephemeral_public_key &&
         child.child_nonce == relay.child_nonce &&
         child.relay_nonce == relay.relay_nonce &&
         child.issued_at_ms == relay.issued_at_ms &&
         child.expires_at_ms == relay.expires_at_ms &&
         child.authorization_epoch == relay.authorization_epoch;
}

void ProductS5IsolatedManagerTransport::on_s5_message(
    const std::string &topic,
    const std::string &payload) {
  if (!started_ || clock_ == nullptr) return;

  if (topic == time_response_topic_) {
    if (!time_request_pending_) return;
    std::string nonce;
    uint64_t authority_now = 0;
    if (!decode_peer_authority_time_response_json(
            payload, &nonce, &authority_now) ||
        nonce != time_request_nonce_) {
      return;
    }
    const uint64_t local_now = clock_->now_ms();
    if (local_now < time_request_local_ms_ ||
        local_now - time_request_local_ms_ >
            policy_.authority_request_timeout_ms) {
      time_request_pending_ = false;
      time_request_local_ms_ = 0;
      time_request_nonce_.clear();
      return;
    }
    authority_anchor_epoch_ms_ = authority_now;
    authority_anchor_local_ms_ = local_now;
    authority_anchor_valid_ = true;
    time_request_pending_ = false;
    time_request_local_ms_ = 0;
    time_request_nonce_.clear();
    return;
  }

  if (pending_authorization_session_.empty()) return;
  const std::string expected =
      product_peer_authorization_response_topic(
          system_id_, relay_node_id_, pending_authorization_session_);
  if (expected.empty() || topic != expected) return;

  ProductPeerGrant child;
  ProductPeerGrant relay;
  if (!decode_peer_authorization_response_json(payload, &child, &relay) ||
      !same_grant_pair_(child, relay) ||
      child.system_id != system_id_ ||
      child.relay_node_id != relay_node_id_ ||
      child.session_id != pending_authorization_session_) {
    return;
  }

  if (!authorization_sink_->queue_s5_manager_authorization(
          child, relay)) {
    return;
  }
  pending_authorization_session_.clear();
}

bool ProductS5IsolatedManagerTransport::accept_for_forwarding(
    const RelayFrame &frame) {
  if (!started_ || bus_ == nullptr || !bus_->connected() ||
      frame.header.gateway_id != relay_node_id_) {
    return false;
  }
  const std::string topic = product_relay_ingress_topic(
      system_id_, relay_node_id_, frame.header.node_id);
  std::string payload;
  if (topic.empty() ||
      greenhouse_n3w_core::serialize_relay_frame_json(frame, &payload) !=
          greenhouse_n3w_core::CoreError::NONE) {
    return false;
  }
  return bus_->publish_message(topic, payload, 1, false);
}

#ifdef USE_MQTT
bool ProductS5EspHomeMqttBus::begin(
    const std::string &subscription,
    ProductS5MessageBusSink *sink) {
  if (started_ || subscription.empty() || sink == nullptr) return false;
  sink_ = sink;
  this->subscribe(
      subscription,
      &ProductS5EspHomeMqttBus::on_message_,
      1);
  started_ = true;
  return true;
}

bool ProductS5EspHomeMqttBus::connected() {
  return started_ && this->is_connected();
}

bool ProductS5EspHomeMqttBus::publish_message(
    const std::string &topic,
    const std::string &payload,
    uint8_t qos,
    bool retain) {
  if (!connected() || topic.empty()) return false;
  return this->publish(topic, payload, qos, retain);
}

void ProductS5EspHomeMqttBus::on_message_(
    const std::string &topic,
    const std::string &payload) {
  if (sink_ != nullptr) sink_->on_s5_message(topic, payload);
}
#endif

}  // namespace esphome::greenhouse_n3w_s5_manager_transport
