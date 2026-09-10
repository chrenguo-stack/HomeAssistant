#include "n3w_simple_product_runtime.h"

#include <algorithm>
#include <utility>

namespace esphome::greenhouse_n3w_core {

bool SimpleProductPolicy::valid() const {
  if (!path.valid() || allowed_channels.empty() || scan_dwell_ms == 0 ||
      challenge_timeout_ms == 0 || relay_advertisement_interval_ms == 0 ||
      max_relay_children == 0) {
    return false;
  }
  return std::all_of(
      allowed_channels.begin(),
      allowed_channels.end(),
      [](uint8_t channel) { return valid_radio_channel(channel); });
}

bool SimpleProductRelayPeer::valid() const {
  return valid_simple_identity_v2(node_id) && valid_radio_channel(channel) &&
         SimpleProductRuntime::valid_unicast_mac_(mac) &&
         std::any_of(
             lmk.begin(), lmk.end(), [](uint8_t value) { return value != 0; });
}

SimpleProductRuntime::SimpleProductRuntime(
    SimpleProductPort *port,
    SimpleProductClock *clock,
    SimpleProductRandom *random,
    SimpleProductPolicy policy)
    : port_(port),
      clock_(clock),
      random_(random),
      policy_(std::move(policy)),
      path_(policy_.path) {}

SimpleProductError SimpleProductRuntime::start(
    const ProvisionedPeerStateV2 &state,
    const MacAddress &local_mac,
    uint8_t direct_channel,
    SimpleProductStartMode start_mode) {
  const bool direct_start = start_mode == SimpleProductStartMode::DIRECT;
  const bool discovery_start = start_mode == SimpleProductStartMode::DISCOVERY;
  const bool channel_valid_for_mode =
      direct_start ? valid_radio_channel(direct_channel)
                   : (direct_channel == 0 || valid_radio_channel(direct_channel));
  if (started_ || port_ == nullptr || clock_ == nullptr || random_ == nullptr ||
      !policy_.valid() || !state.valid() || !valid_unicast_mac_(local_mac) ||
      (!direct_start && !discovery_start) || !channel_valid_for_mode) {
    return SimpleProductError::INVALID_ARGUMENT;
  }
  state_ = state;
  direct_channel_ = direct_channel;
  peer_credential_.system_id = state.system_id;
  peer_credential_.generation = state.peer_trust_generation;
  peer_credential_.key = state.system_peer_key;
  local_endpoint_.node_id = state.node_id;
  local_endpoint_.mac = local_mac;
  application_key_.lifecycle = KeyLifecycle::ACTIVE;
  application_key_.key_epoch = state.n3w_key_epoch;
  application_key_.key = state.n3w_application_key;
  application_key_.session_floor = 0;
  if (!peer_credential_.valid() || !local_endpoint_.valid() ||
      !application_key_.valid_for_encrypt() || !fill_nonce_(&local_boot_nonce_)) {
    stop();
    return SimpleProductError::CRYPTO_FAILED;
  }
  const LocalPathState initial_path =
      direct_start ? LocalPathState::DIRECT : LocalPathState::DISCOVERY;
  if (path_.reset(initial_path) != RadioError::NONE ||
      scan_.configure(direct_channel_, policy_.allowed_channels) !=
          RadioError::NONE) {
    stop();
    return SimpleProductError::RADIO_FAILED;
  }
  const uint64_t now = clock_->now_ms();
  if (direct_start) {
    if (!port_->set_radio_channel(direct_channel_)) {
      stop();
      return SimpleProductError::RADIO_FAILED;
    }
    next_advertisement_ms_ = now;
  } else {
    const uint8_t channel = scan_.current();
    if (diagnostic_sink_ != nullptr) {
      diagnostic_sink_->on_scan_attempt(channel, now);
    }
    const bool channel_set =
        valid_radio_channel(channel) && port_->set_radio_channel(channel);
    if (diagnostic_sink_ != nullptr) {
      diagnostic_sink_->on_scan_result(
          channel,
          channel_set,
          port_->last_channel_observed(),
          port_->last_channel_error_raw(),
          clock_->now_ms());
    }
    if (!channel_set) {
      stop();
      return SimpleProductError::RADIO_FAILED;
    }
    next_scan_switch_ms_ = now + policy_.scan_dwell_ms;
  }
  started_ = true;
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_runtime_start(
        static_cast<uint8_t>(start_mode),
        static_cast<uint8_t>(path_.state()));
  }
  return SimpleProductError::NONE;
}

void SimpleProductRuntime::stop() {
  if (port_ != nullptr) {
    if (active_relay_.has_value()) {
      (void) port_->remove_peer(active_relay_->mac);
    }
    for (const auto &child : relay_children_) {
      (void) port_->remove_peer(child.mac);
    }
  }
  active_relay_.reset();
  relay_children_.clear();
  pending_challenge_.reset();
  state_.clear();
  peer_credential_.clear();
  application_key_.clear();
  local_endpoint_.node_id.clear();
  local_endpoint_.mac.fill(0);
  local_boot_nonce_.fill(0);
  direct_channel_ = 0;
  next_scan_switch_ms_ = 0;
  next_advertisement_ms_ = 0;
  (void) path_.reset(LocalPathState::DIRECT);
  started_ = false;
}

SimpleProductError SimpleProductRuntime::tick() {
  if (!started_) return SimpleProductError::NOT_READY;
  const uint64_t now = clock_->now_ms();
  if (path_.state() == LocalPathState::DIRECT) {
    return maybe_advertise_relay_(now);
  }
  if (path_.state() == LocalPathState::DISCOVERY) {
    if (pending_challenge_.has_value() &&
        now >= pending_challenge_->expires_at_ms) {
      pending_challenge_.reset();
    }
    return maybe_advance_scan_(now);
  }
  return SimpleProductError::NONE;
}

SimpleProductError SimpleProductRuntime::note_direct_result(bool success) {
  if (!started_) return SimpleProductError::NOT_READY;
  const LocalPathState before = path_.state();
  const RadioError result = path_.note_direct_result(success);
  if (result != RadioError::NONE) return SimpleProductError::STATE_REJECTED;
  if (before != path_.state() &&
      path_.state() == LocalPathState::DISCOVERY) {
    return begin_discovery_();
  }
  return SimpleProductError::NONE;
}

SimpleProductError SimpleProductRuntime::note_direct_recovery_probe(bool success) {
  if (!started_) return SimpleProductError::NOT_READY;
  const LocalPathState before = path_.state();
  const RadioError result = path_.note_direct_recovery_probe(success);
  if (result != RadioError::NONE) return SimpleProductError::STATE_REJECTED;
  if (before != path_.state() && path_.state() == LocalPathState::DIRECT) {
    return restore_direct_();
  }
  return SimpleProductError::NONE;
}

bool SimpleProductRuntime::update_direct_channel_hint(uint8_t channel) {
  if (!started_ || !valid_radio_channel(channel)) return false;
  direct_channel_ = channel;
  return true;
}

SimpleProductError SimpleProductRuntime::send_telemetry(
    const std::string &telemetry_json,
    const std::string &boot_id,
    uint32_t seq) {
  if (!started_ || telemetry_json.empty()) {
    return SimpleProductError::NOT_READY;
  }
  if (path_.state() == LocalPathState::DIRECT) {
    const std::string topic =
        "gh/v1/" + state_.system_id + "/ingress/node/" + state_.node_id +
        "/telemetry";
    const bool success = port_->publish_direct(topic, telemetry_json);
    const SimpleProductError state_result = note_direct_result(success);
    if (state_result != SimpleProductError::NONE) return state_result;
    return success ? SimpleProductError::NONE : SimpleProductError::MQTT_FAILED;
  }
  if (path_.state() != LocalPathState::RELAY_ACTIVE ||
      !active_relay_.has_value()) {
    return SimpleProductError::NOT_READY;
  }
  CompactTelemetryFrameV2 frame;
  if (encrypt_compact_telemetry_v2(
          state_.system_id,
          state_.node_id,
          state_.n3w_key_epoch,
          boot_id,
          seq,
          application_key_,
          telemetry_json,
          &frame) != CompactTelemetryError::NONE) {
    return SimpleProductError::CRYPTO_FAILED;
  }
  std::vector<uint8_t> encoded;
  if (encode_compact_telemetry_frame_v2(frame, &encoded) !=
      CompactTelemetryError::NONE) {
    return SimpleProductError::CRYPTO_FAILED;
  }
  const bool success = port_->send_encrypted_peer(
      active_relay_->mac, encoded.data(), encoded.size());
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_relay_telemetry(success, clock_->now_ms());
  }
  const LocalPathState before = path_.state();
  if (path_.note_relay_result(success) != RadioError::NONE) {
    return SimpleProductError::STATE_REJECTED;
  }
  if (before != path_.state() &&
      path_.state() == LocalPathState::DISCOVERY) {
    const SimpleProductError transition = leave_relay_for_discovery_();
    if (transition != SimpleProductError::NONE) return transition;
  }
  return success ? SimpleProductError::NONE : SimpleProductError::RADIO_FAILED;
}

SimpleProductError SimpleProductRuntime::on_radio_receive(
    const MacAddress &source,
    const uint8_t *data,
    std::size_t size,
    uint8_t channel) {
  if (!started_ || data == nullptr || size == 0 ||
      !valid_unicast_mac_(source) || !valid_radio_channel(channel)) {
    return SimpleProductError::INVALID_ARGUMENT;
  }

  SimpleRelayDiscovery discovery;
  if (decode_simple_relay_discovery(data, size, &discovery) ==
      SimpleRuntimeError::NONE) {
    return handle_discovery_(source, discovery, channel);
  }
  SimplePeerChallenge challenge;
  if (decode_simple_peer_challenge(data, size, &challenge) ==
      SimpleRuntimeError::NONE) {
    return handle_challenge_(source, challenge, channel);
  }
  SimplePeerAccept accept;
  if (decode_simple_peer_accept(data, size, &accept) ==
      SimpleRuntimeError::NONE) {
    return handle_accept_(source, accept, channel);
  }
  return handle_compact_(source, data, size);
}

SimpleProductError SimpleProductRuntime::begin_discovery_() {
  pending_challenge_.reset();
  if (active_relay_.has_value()) {
    (void) port_->remove_peer(active_relay_->mac);
    active_relay_.reset();
  }
  for (const auto &child : relay_children_) {
    (void) port_->remove_peer(child.mac);
  }
  relay_children_.clear();
  if (scan_.configure(direct_channel_, policy_.allowed_channels) !=
      RadioError::NONE) {
    return SimpleProductError::RADIO_FAILED;
  }
  const uint8_t channel = scan_.current();
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_scan_attempt(channel, clock_->now_ms());
  }
  const bool channel_set = port_->set_radio_channel(channel);
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_scan_result(
        channel,
        channel_set,
        port_->last_channel_observed(),
        port_->last_channel_error_raw(),
        clock_->now_ms());
  }
  if (!channel_set) {
    return SimpleProductError::RADIO_FAILED;
  }
  next_scan_switch_ms_ = clock_->now_ms() + policy_.scan_dwell_ms;
  return SimpleProductError::NONE;
}

SimpleProductError SimpleProductRuntime::leave_relay_for_discovery_() {
  if (active_relay_.has_value()) {
    (void) port_->remove_peer(active_relay_->mac);
    active_relay_.reset();
  }
  return begin_discovery_();
}

SimpleProductError SimpleProductRuntime::restore_direct_() {
  pending_challenge_.reset();
  if (active_relay_.has_value()) {
    (void) port_->remove_peer(active_relay_->mac);
    active_relay_.reset();
  }
  if (!port_->set_radio_channel(direct_channel_)) {
    return SimpleProductError::RADIO_FAILED;
  }
  next_advertisement_ms_ = clock_->now_ms();
  return SimpleProductError::NONE;
}

SimpleProductError SimpleProductRuntime::handle_discovery_(
    const MacAddress &source,
    const SimpleRelayDiscovery &packet,
    uint8_t channel) {
  const bool accepted =
      path_.state() == LocalPathState::DISCOVERY &&
      !pending_challenge_.has_value() && packet.valid() &&
      packet.peer_trust_generation == peer_credential_.generation &&
      packet.relay_node_id != state_.node_id && packet.channel == channel;
  if (diagnostic_sink_ != nullptr) {
    const uint64_t now_ms = clock_->now_ms();
    if (!accepted) {
      DiscoveryRejectReason reason = DiscoveryRejectReason::NONE;
      if (path_.state() != LocalPathState::DISCOVERY) {
        reason = DiscoveryRejectReason::STATE_NOT_DISCOVERY;
      } else if (pending_challenge_.has_value()) {
        reason = DiscoveryRejectReason::PENDING_CHALLENGE;
      } else if (!packet.valid()) {
        reason = DiscoveryRejectReason::PACKET_INVALID;
      } else if (packet.peer_trust_generation != peer_credential_.generation) {
        reason = DiscoveryRejectReason::TRUST_GENERATION_MISMATCH;
      } else if (packet.relay_node_id == state_.node_id) {
        reason = DiscoveryRejectReason::SELF_RELAY;
      } else if (packet.channel != channel) {
        reason = DiscoveryRejectReason::CHANNEL_MISMATCH;
      }
      diagnostic_sink_->on_discovery_rejected(
          reason, packet.channel, channel, now_ms);
    }
    diagnostic_sink_->on_discovery_rx(accepted, now_ms);
  }
  if (path_.state() != LocalPathState::DISCOVERY ||
      pending_challenge_.has_value()) {
    return SimpleProductError::STATE_REJECTED;
  }
  if (!accepted) {
    return SimpleProductError::PACKET_REJECTED;
  }
  PeerEndpointV2 relay{packet.relay_node_id, source};
  HandshakeNonce challenge_nonce{};
  if (!relay.valid() || !fill_nonce_(&challenge_nonce)) {
    return SimpleProductError::CRYPTO_FAILED;
  }
  SimplePeerChallenge challenge;
  if (build_simple_peer_challenge(
          peer_credential_,
          local_endpoint_,
          relay,
          local_boot_nonce_,
          challenge_nonce,
          &challenge) != SimpleRuntimeError::NONE) {
    return SimpleProductError::CRYPTO_FAILED;
  }
  std::vector<uint8_t> encoded;
  const bool challenge_sent =
      encode_simple_peer_challenge(challenge, &encoded) ==
          SimpleRuntimeError::NONE &&
      port_->broadcast_control(encoded.data(), encoded.size());
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_challenge_tx(challenge_sent, clock_->now_ms());
  }
  if (!challenge_sent) {
    return SimpleProductError::RADIO_FAILED;
  }
  PendingChallenge pending;
  pending.relay_node_id = packet.relay_node_id;
  pending.relay_mac = source;
  pending.challenge_nonce = challenge_nonce;
  pending.channel = channel;
  pending.expires_at_ms = clock_->now_ms() + policy_.challenge_timeout_ms;
  pending_challenge_ = std::move(pending);
  return SimpleProductError::NONE;
}

SimpleProductError SimpleProductRuntime::handle_challenge_(
    const MacAddress &source,
    const SimplePeerChallenge &packet,
    uint8_t channel) {
  const uint64_t now = clock_->now_ms();
  if (path_.state() != LocalPathState::DIRECT || !relay_capable_ ||
      packet.relay_node_id != state_.node_id ||
      packet.child_node_id == state_.node_id ||
      packet.peer_trust_generation != peer_credential_.generation) {
    if (diagnostic_sink_ != nullptr) {
      diagnostic_sink_->on_challenge_rx(false, now);
    }
    return SimpleProductError::STATE_REJECTED;
  }
  PeerEndpointV2 child{packet.child_node_id, source};
  if (!child.valid()) {
    if (diagnostic_sink_ != nullptr) {
      diagnostic_sink_->on_challenge_rx(false, now);
    }
    return SimpleProductError::PACKET_REJECTED;
  }
  SimpleLmk lmk{};
  if (verify_simple_peer_challenge(
      peer_credential_, source, local_endpoint_, packet, &lmk) !=
      SimpleRuntimeError::NONE) {
    if (diagnostic_sink_ != nullptr) {
      diagnostic_sink_->on_challenge_rx(false, now);
    }
    return SimpleProductError::PACKET_REJECTED;
  }
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_challenge_rx(true, now);
  }
  SimplePeerAccept accept;
  if (build_simple_peer_accept(
          peer_credential_,
          local_endpoint_,
          child,
          local_boot_nonce_,
          packet.challenge_nonce,
          &accept) != SimpleRuntimeError::NONE) {
    return SimpleProductError::CRYPTO_FAILED;
  }
  std::vector<uint8_t> encoded;
  const bool accept_sent =
      encode_simple_peer_accept(accept, &encoded) == SimpleRuntimeError::NONE &&
      port_->broadcast_control(encoded.data(), encoded.size());
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_accept_tx(accept_sent, now);
  }
  if (!accept_sent) {
    return SimpleProductError::RADIO_FAILED;
  }
  const LinkKey link_key = as_link_key_(lmk);
  if (!port_->install_encrypted_peer(source, link_key, channel)) {
    return SimpleProductError::RADIO_FAILED;
  }
  SimpleProductRelayPeer peer;
  peer.node_id = packet.child_node_id;
  peer.mac = source;
  peer.lmk = link_key;
  peer.channel = channel;
  if (!peer.valid()) return SimpleProductError::PACKET_REJECTED;
  if (SimpleProductRelayPeer *existing = find_relay_child_(source);
      existing != nullptr) {
    *existing = peer;
    return SimpleProductError::NONE;
  }
  if (relay_children_.size() >= policy_.max_relay_children) {
    (void) port_->remove_peer(source);
    return SimpleProductError::STATE_REJECTED;
  }
  relay_children_.push_back(std::move(peer));
  return SimpleProductError::NONE;
}

SimpleProductError SimpleProductRuntime::handle_accept_(
    const MacAddress &source,
    const SimplePeerAccept &packet,
    uint8_t channel) {
  const uint64_t now = clock_->now_ms();
  if (path_.state() != LocalPathState::DISCOVERY ||
      !pending_challenge_.has_value()) {
    if (diagnostic_sink_ != nullptr) {
      diagnostic_sink_->on_accept_rx(false, now);
    }
    return SimpleProductError::STATE_REJECTED;
  }
  const PendingChallenge &pending = *pending_challenge_;
  if (source != pending.relay_mac || channel != pending.channel ||
      packet.relay_node_id != pending.relay_node_id ||
      packet.child_node_id != state_.node_id ||
      packet.peer_trust_generation != peer_credential_.generation ||
      packet.challenge_nonce != pending.challenge_nonce) {
    if (diagnostic_sink_ != nullptr) {
      diagnostic_sink_->on_accept_rx(false, now);
    }
    return SimpleProductError::PACKET_REJECTED;
  }
  SimpleLmk lmk{};
  if (verify_simple_peer_accept(
      peer_credential_, source, local_endpoint_, packet, &lmk) !=
      SimpleRuntimeError::NONE) {
    if (diagnostic_sink_ != nullptr) {
      diagnostic_sink_->on_accept_rx(false, now);
    }
    return SimpleProductError::PACKET_REJECTED;
  }
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_accept_rx(true, now);
  }
  const LinkKey link_key = as_link_key_(lmk);
  if (!port_->install_encrypted_peer(source, link_key, channel)) {
    return SimpleProductError::RADIO_FAILED;
  }
  SimpleProductRelayPeer relay;
  relay.node_id = packet.relay_node_id;
  relay.mac = source;
  relay.lmk = link_key;
  relay.channel = channel;
  if (!relay.valid() ||
      path_.note_authenticated_relay_ready(true) != RadioError::NONE) {
    (void) port_->remove_peer(source);
    return SimpleProductError::STATE_REJECTED;
  }
  active_relay_ = std::move(relay);
  pending_challenge_.reset();
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_relay_active(now);
  }
  return SimpleProductError::NONE;
}

SimpleProductError SimpleProductRuntime::handle_compact_(
    const MacAddress &source,
    const uint8_t *data,
    std::size_t size) {
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_compact_rx(clock_->now_ms());
  }
  if (path_.state() != LocalPathState::DIRECT || !relay_capable_) {
    if (diagnostic_sink_ != nullptr) {
      diagnostic_sink_->on_compact_state_rejected(clock_->now_ms());
    }
    return SimpleProductError::STATE_REJECTED;
  }
  SimpleProductRelayPeer *child = find_relay_child_(source);
  if (child == nullptr) {
    if (diagnostic_sink_ != nullptr) {
      diagnostic_sink_->on_compact_child_binding_failure(clock_->now_ms());
    }
    return SimpleProductError::PACKET_REJECTED;
  }
  CompactTelemetryFrameV2 frame;
  if (decode_compact_telemetry_frame_v2(data, size, &frame) !=
      CompactTelemetryError::NONE) {
    if (diagnostic_sink_ != nullptr) {
      diagnostic_sink_->on_compact_decode(false, clock_->now_ms());
    }
    return SimpleProductError::PACKET_REJECTED;
  }
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_compact_decode(true, clock_->now_ms());
  }
  std::vector<uint8_t> encoded(data, data + size);
  std::string payload;
  if (wrap_compact_relay_mqtt_v2(encoded, &payload) !=
      CompactTelemetryError::NONE) {
    if (diagnostic_sink_ != nullptr) {
      diagnostic_sink_->on_compact_wrap_failure(clock_->now_ms());
    }
    return SimpleProductError::PACKET_REJECTED;
  }
  const std::string topic =
      "gh/v1/" + state_.system_id + "/ingress/gateway/" + state_.node_id +
      "/" + child->node_id + "/frame";
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_compact_forward_attempt(clock_->now_ms());
  }
  const bool submitted = port_->publish_relay(topic, payload);
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_compact_forward_submit(submitted, clock_->now_ms());
  }
  return submitted ? SimpleProductError::NONE : SimpleProductError::MQTT_FAILED;
}

SimpleProductError SimpleProductRuntime::maybe_advertise_relay_(
    uint64_t now_ms) {
  if (!relay_capable_ || now_ms < next_advertisement_ms_) {
    return SimpleProductError::NONE;
  }
  SimpleRelayDiscovery discovery;
  discovery.peer_trust_generation = peer_credential_.generation;
  discovery.channel = direct_channel_;
  discovery.relay_node_id = state_.node_id;
  std::vector<uint8_t> encoded;
  const bool submitted =
      encode_simple_relay_discovery(discovery, &encoded) ==
          SimpleRuntimeError::NONE &&
      port_->broadcast_control(encoded.data(), encoded.size());
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_relay_advertisement(submitted, now_ms);
  }
  if (!submitted) {
    next_advertisement_ms_ = now_ms + policy_.relay_advertisement_interval_ms;
    return SimpleProductError::RADIO_FAILED;
  }
  next_advertisement_ms_ = now_ms + policy_.relay_advertisement_interval_ms;
  return SimpleProductError::NONE;
}

SimpleProductError SimpleProductRuntime::maybe_advance_scan_(uint64_t now_ms) {
  if (pending_challenge_.has_value() || now_ms < next_scan_switch_ms_) {
    return SimpleProductError::NONE;
  }
  next_scan_switch_ms_ = now_ms + policy_.scan_dwell_ms;
  const uint8_t channel = scan_.advance();
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_scan_attempt(channel, now_ms);
  }
  const bool channel_set =
      valid_radio_channel(channel) && port_->set_radio_channel(channel);
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_scan_result(
        channel,
        channel_set,
        port_->last_channel_observed(),
        port_->last_channel_error_raw(),
        clock_->now_ms());
  }
  if (!channel_set) {
    return SimpleProductError::RADIO_FAILED;
  }
  return SimpleProductError::NONE;
}

uint8_t SimpleProductRuntime::working_channel() const {
  if (active_relay_.has_value()) return active_relay_->channel;
  if (path_.state() == LocalPathState::DIRECT) return direct_channel_;
  return scan_.current();
}

SimpleProductRelayPeer *SimpleProductRuntime::find_relay_child_(
    const MacAddress &mac) {
  for (auto &peer : relay_children_) {
    if (peer.mac == mac) return &peer;
  }
  return nullptr;
}

bool SimpleProductRuntime::fill_nonce_(HandshakeNonce *nonce) {
  if (nonce == nullptr || !random_->fill(nonce->data(), nonce->size())) {
    return false;
  }
  return std::any_of(
      nonce->begin(), nonce->end(), [](uint8_t value) { return value != 0; });
}

bool SimpleProductRuntime::valid_unicast_mac_(const MacAddress &mac) {
  const bool all_zero = std::all_of(
      mac.begin(), mac.end(), [](uint8_t value) { return value == 0; });
  const bool all_ff = std::all_of(
      mac.begin(), mac.end(), [](uint8_t value) { return value == 0xff; });
  return !all_zero && !all_ff && (mac[0] & 0x01U) == 0;
}

LinkKey SimpleProductRuntime::as_link_key_(const SimpleLmk &lmk) {
  LinkKey key{};
  std::copy(lmk.begin(), lmk.end(), key.begin());
  return key;
}

}  // namespace esphome::greenhouse_n3w_core
