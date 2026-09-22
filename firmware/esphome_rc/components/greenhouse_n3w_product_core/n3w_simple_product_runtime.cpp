#include "n3w_simple_product_runtime.h"

#include <algorithm>
#include <array>
#include <limits>
#include <utility>

#include "mbedtls/md.h"

namespace esphome::greenhouse_n3w_core {
namespace {

constexpr char kGatewaySelectionHashDomain[] = "N3W-GWSEL-V1";

bool gateway_selection_digest(
    const std::string &child_node_id,
    const std::string &relay_node_id,
    std::array<uint8_t, 32> *digest) {
  if (digest == nullptr ||
      child_node_id.size() > std::numeric_limits<uint16_t>::max() ||
      relay_node_id.size() > std::numeric_limits<uint16_t>::max()) {
    return false;
  }

  std::vector<uint8_t> input;
  input.reserve(
      sizeof(kGatewaySelectionHashDomain) + 4U +
      child_node_id.size() + relay_node_id.size());
  input.insert(
      input.end(),
      kGatewaySelectionHashDomain,
      kGatewaySelectionHashDomain + sizeof(kGatewaySelectionHashDomain) - 1U);
  input.push_back(0);

  const auto append_u16be = [&input](std::size_t value) {
    const uint16_t encoded = static_cast<uint16_t>(value);
    input.push_back(static_cast<uint8_t>(encoded >> 8U));
    input.push_back(static_cast<uint8_t>(encoded & 0xffU));
  };
  append_u16be(child_node_id.size());
  input.insert(input.end(), child_node_id.begin(), child_node_id.end());
  append_u16be(relay_node_id.size());
  input.insert(input.end(), relay_node_id.begin(), relay_node_id.end());

  const mbedtls_md_info_t *info =
      mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if (info == nullptr ||
      mbedtls_md(info, input.data(), input.size(), digest->data()) != 0) {
    digest->fill(0);
    return false;
  }
  return true;
}

}  // namespace

bool SimpleProductPolicy::valid() const {
  if (!path.valid() || allowed_channels.empty() || scan_dwell_ms == 0 ||
      challenge_timeout_ms == 0 || relay_advertisement_interval_ms == 0 ||
      candidate_window_ms == 0 ||
      gateway_selection_transaction_max_ms <= candidate_window_ms ||
      max_gateway_candidates == 0 || max_relay_children == 0) {
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

TelemetryAdmissionPlan plan_business_telemetry_admission(
    LocalPathState path_state,
    bool direct_mqtt_available) {
  const bool record_direct_unavailable =
      path_state == LocalPathState::DIRECT && !direct_mqtt_available;
  return TelemetryAdmissionPlan{
      record_direct_unavailable,
      record_direct_unavailable
          ? TelemetryPathAccounting::TRANSPORT_ONLY
          : TelemetryPathAccounting::RECORD_PATH_RESULT,
  };
}

bool gateway_selection_local_fault_requires_restore(
    SimpleProductError result,
    bool selection_busy_before,
    bool selection_busy_after) {
  if (!selection_busy_before || selection_busy_after) return false;
  return result == SimpleProductError::RADIO_FAILED ||
         result == SimpleProductError::CRYPTO_FAILED ||
         result == SimpleProductError::STATE_REJECTED;
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
  clear_gateway_selection_();
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
    if (gateway_selection_epoch_.has_value() &&
        now >= gateway_selection_epoch_->transaction_deadline_ms) {
      return begin_discovery_();
    }

    if (pending_challenge_.has_value() &&
        now >= pending_challenge_->expires_at_ms) {
      if (gateway_selection_epoch_.has_value()) {
        RelayCandidate *candidate =
            find_gateway_candidate_by_node_(pending_challenge_->relay_node_id);
        if (candidate != nullptr &&
            candidate->mac == pending_challenge_->relay_mac) {
          candidate->attempted = true;
        }
      }
      pending_challenge_.reset();
      const SimpleProductError fallback = attempt_next_gateway_candidate_();
      if (fallback != SimpleProductError::NONE) return fallback;
      if (gateway_selection_busy()) return SimpleProductError::NONE;
    }

    if (gateway_selection_epoch_.has_value() &&
        !gateway_selection_epoch_->frozen &&
        now >= gateway_selection_epoch_->deadline_ms) {
      gateway_selection_epoch_->frozen = true;
      const SimpleProductError selection = attempt_next_gateway_candidate_();
      if (selection != SimpleProductError::NONE) return selection;
      if (gateway_selection_busy()) return SimpleProductError::NONE;
    }

    const SimpleProductError scan_result = maybe_advance_scan_(now);
    if (scan_result != SimpleProductError::NONE &&
        gateway_selection_epoch_.has_value()) {
      pending_challenge_.reset();
      clear_gateway_selection_();
    }
    return scan_result;
  }
  return SimpleProductError::NONE;
}

SimpleProductError SimpleProductRuntime::note_direct_result(bool success) {
  if (!started_) return SimpleProductError::NOT_READY;
  const LocalPathState before = path_.state();
  const RadioError result = path_.note_direct_result(success);
  if (result != RadioError::NONE) return SimpleProductError::STATE_REJECTED;
  // This diagnostic follows the logical Direct path-health observation, not
  // merely MQTT publish calls. A new business sample with no MQTT opportunity
  // therefore advances the same physical timing oracle exactly once.
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_direct_path_result(success, clock_->now_ms());
  }
  if (before != path_.state() &&
      path_.state() == LocalPathState::DISCOVERY) {
    if (diagnostic_sink_ != nullptr) {
      diagnostic_sink_->on_discovery_enter(clock_->now_ms());
    }
    return begin_discovery_();
  }
  return SimpleProductError::NONE;
}

SimpleProductError SimpleProductRuntime::note_direct_recovery_probe(bool success) {
  if (!started_) return SimpleProductError::NOT_READY;

  // Direct is committed only after the concrete radio has already recovered.
  // If radio recovery fails, keep the logical path in Relay/Discovery and
  // reset the recovery hysteresis so the caller can retry or restore Relay.
  if (success && path_.direct_recovery_would_commit_on_success()) {
    const SimpleProductError restore_result = restore_direct_();
    if (restore_result != SimpleProductError::NONE) {
      (void) path_.note_direct_recovery_probe(false);
      return restore_result;
    }
  }

  const RadioError result = path_.note_direct_recovery_probe(success);
  return result == RadioError::NONE ? SimpleProductError::NONE
                                    : SimpleProductError::STATE_REJECTED;
}

DirectRecoveryCommitResult SimpleProductRuntime::commit_direct_recovery_before(
    uint64_t absolute_deadline_ms) {
  DirectRecoveryCommitResult result;
  result.completed_at_ms = clock_ != nullptr ? clock_->now_ms() : 0;

  if (!started_ || clock_ == nullptr || port_ == nullptr) {
    result.error = SimpleProductError::NOT_READY;
    return result;
  }

  if (!path_.direct_recovery_would_commit_on_success()) {
    result.error = SimpleProductError::STATE_REJECTED;
    return result;
  }

  if (result.completed_at_ms >= absolute_deadline_ms) {
    (void) path_.note_direct_recovery_probe(false);
    result.error = SimpleProductError::STATE_REJECTED;
    return result;
  }

  if (!port_->set_radio_channel(direct_channel_)) {
    (void) path_.note_direct_recovery_probe(false);
    result.completed_at_ms = clock_->now_ms();
    result.error = SimpleProductError::RADIO_FAILED;
    return result;
  }

  result.completed_at_ms = clock_->now_ms();
  if (result.completed_at_ms >= absolute_deadline_ms) {
    (void) path_.note_direct_recovery_probe(false);
    result.error = SimpleProductError::STATE_REJECTED;
    return result;
  }

  const RadioError path_result = path_.note_direct_recovery_probe(true);
  if (path_result != RadioError::NONE ||
      path_.state() != LocalPathState::DIRECT) {
    (void) path_.note_direct_recovery_probe(false);
    result.error = SimpleProductError::STATE_REJECTED;
    return result;
  }

  pending_challenge_.reset();
  clear_gateway_selection_();
  if (active_relay_.has_value()) {
    (void) port_->remove_peer(active_relay_->mac);
    active_relay_.reset();
  }
  next_advertisement_ms_ = result.completed_at_ms;
  result.committed = true;
  return result;
}

SimpleProductError SimpleProductRuntime::note_relay_delivery_result(
    const MacAddress &destination,
    bool success) {
  if (!started_) return SimpleProductError::NOT_READY;
  if (path_.state() != LocalPathState::RELAY_ACTIVE ||
      !active_relay_.has_value() || destination != active_relay_->mac) {
    return SimpleProductError::NONE;
  }
  const LocalPathState before = path_.state();
  if (path_.note_relay_result(success) != RadioError::NONE) {
    return SimpleProductError::STATE_REJECTED;
  }
  if (before != path_.state() &&
      path_.state() == LocalPathState::DISCOVERY) {
    return leave_relay_for_discovery_();
  }
  return SimpleProductError::NONE;
}

SimpleProductError SimpleProductRuntime::rebind_radio_state() {
  if (!started_) return SimpleProductError::NOT_READY;

  uint8_t channel = direct_channel_;
  if (path_.state() == LocalPathState::DISCOVERY) {
    channel = pending_challenge_.has_value()
                  ? pending_challenge_->channel
                  : scan_.current();
  } else if (path_.state() == LocalPathState::RELAY_ACTIVE) {
    if (!active_relay_.has_value()) return SimpleProductError::STATE_REJECTED;
    channel = active_relay_->channel;
  }
  if (!valid_radio_channel(channel) || !port_->set_radio_channel(channel)) {
    return SimpleProductError::RADIO_FAILED;
  }
  if (path_.state() == LocalPathState::RELAY_ACTIVE &&
      !port_->install_encrypted_peer(
          active_relay_->mac, active_relay_->lmk, active_relay_->channel)) {
    return SimpleProductError::RADIO_FAILED;
  }
  return SimpleProductError::NONE;
}

SimpleProductError SimpleProductRuntime::reset_to_discovery_after_radio_fault() {
  if (!started_) return SimpleProductError::NOT_READY;

  pending_challenge_.reset();
  clear_gateway_selection_();
  if (active_relay_.has_value()) {
    (void) port_->remove_peer(active_relay_->mac);
    active_relay_.reset();
  }
  for (const auto &child : relay_children_) {
    (void) port_->remove_peer(child.mac);
  }
  relay_children_.clear();

  if (path_.reset(LocalPathState::DISCOVERY) != RadioError::NONE ||
      scan_.configure(direct_channel_, policy_.allowed_channels) !=
          RadioError::NONE) {
    return SimpleProductError::STATE_REJECTED;
  }
  next_scan_switch_ms_ = clock_->now_ms() + policy_.scan_dwell_ms;
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_discovery_enter(clock_->now_ms());
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
    uint32_t seq,
    TelemetryPathAccounting accounting) {
  if (!started_ || telemetry_json.empty()) {
    return SimpleProductError::NOT_READY;
  }
  if (path_.state() == LocalPathState::DIRECT) {
    const std::string topic =
        "gh/v1/" + state_.system_id + "/ingress/node/" + state_.node_id +
        "/telemetry";
    const bool success = port_->publish_direct(topic, telemetry_json);
    if (accounting == TelemetryPathAccounting::RECORD_PATH_RESULT) {
      const SimpleProductError state_result = note_direct_result(success);
      if (state_result != SimpleProductError::NONE) return state_result;
    }
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
  const MacAddress relay_destination = active_relay_->mac;
  const bool submitted = port_->send_encrypted_peer(
      relay_destination, encoded.data(), encoded.size());
  if (diagnostic_sink_ != nullptr) {
    diagnostic_sink_->on_relay_telemetry(submitted, clock_->now_ms());
  }
  if (!submitted) {
    if (accounting == TelemetryPathAccounting::RECORD_PATH_RESULT) {
      const SimpleProductError state_result =
          note_relay_delivery_result(relay_destination, false);
      if (state_result != SimpleProductError::NONE) return state_result;
    }
    return SimpleProductError::RADIO_FAILED;
  }
  return SimpleProductError::NONE;
}

SimpleProductError SimpleProductRuntime::on_radio_receive(
    const MacAddress &source,
    const uint8_t *data,
    std::size_t size,
    uint8_t channel,
    int16_t rssi_dbm) {
  if (!started_ || data == nullptr || size == 0 ||
      !valid_unicast_mac_(source) || !valid_radio_channel(channel)) {
    return SimpleProductError::INVALID_ARGUMENT;
  }

  SimpleRelayDiscovery discovery;
  if (decode_simple_relay_discovery(data, size, &discovery) ==
      SimpleRuntimeError::NONE) {
    return handle_discovery_(source, discovery, channel, rssi_dbm);
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
  clear_gateway_selection_();
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
  // Make the radio transition first. Do not destroy the current Relay binding
  // until the Direct channel has been restored successfully.
  if (!port_->set_radio_channel(direct_channel_)) {
    return SimpleProductError::RADIO_FAILED;
  }
  pending_challenge_.reset();
  clear_gateway_selection_();
  if (active_relay_.has_value()) {
    (void) port_->remove_peer(active_relay_->mac);
    active_relay_.reset();
  }
  next_advertisement_ms_ = clock_->now_ms();
  return SimpleProductError::NONE;
}

SimpleProductError SimpleProductRuntime::handle_discovery_(
    const MacAddress &source,
    const SimpleRelayDiscovery &packet,
    uint8_t channel,
    int16_t rssi_dbm) {
  const uint64_t now = clock_->now_ms();
  DiscoveryRejectReason reject_reason = DiscoveryRejectReason::NONE;

  if (path_.state() != LocalPathState::DISCOVERY) {
    reject_reason = DiscoveryRejectReason::STATE_NOT_DISCOVERY;
  } else if (pending_challenge_.has_value()) {
    reject_reason = DiscoveryRejectReason::PENDING_CHALLENGE;
  } else if (!packet.valid()) {
    reject_reason = DiscoveryRejectReason::PACKET_INVALID;
  } else if (packet.peer_trust_generation != peer_credential_.generation) {
    reject_reason = DiscoveryRejectReason::TRUST_GENERATION_MISMATCH;
  } else if (packet.relay_node_id == state_.node_id) {
    reject_reason = DiscoveryRejectReason::SELF_RELAY;
  } else if (packet.channel != channel) {
    reject_reason = DiscoveryRejectReason::CHANNEL_MISMATCH;
  } else if (!valid_discovery_rssi_(rssi_dbm)) {
    reject_reason = DiscoveryRejectReason::RSSI_INVALID;
  } else if (gateway_selection_epoch_.has_value() &&
             (gateway_selection_epoch_->frozen ||
              now >= gateway_selection_epoch_->deadline_ms)) {
    // drain_radio_ runs before tick(), so enforce the deadline here as well.
    // A queued discovery received after the 6500 ms window must not enter the
    // candidate set merely because tick() has not frozen the epoch yet.
    reject_reason = DiscoveryRejectReason::SELECTION_FROZEN;
  } else if (gateway_selection_epoch_.has_value()) {
    RelayCandidate *same_node =
        find_gateway_candidate_by_node_(packet.relay_node_id);
    RelayCandidate *same_mac = find_gateway_candidate_by_mac_(source);
    if ((same_node != nullptr && same_node->mac != source) ||
        (same_mac != nullptr &&
         same_mac->relay_node_id != packet.relay_node_id)) {
      reject_reason = DiscoveryRejectReason::IDENTITY_CONFLICT;
    } else if (
        same_node == nullptr &&
        gateway_selection_epoch_->candidates.size() >=
            policy_.max_gateway_candidates) {
      reject_reason = DiscoveryRejectReason::CANDIDATE_CAPACITY;
    }
  }

  const bool accepted = reject_reason == DiscoveryRejectReason::NONE;
  if (diagnostic_sink_ != nullptr) {
    if (!accepted) {
      diagnostic_sink_->on_discovery_rejected(
          reject_reason, packet.channel, channel, now);
    }
    diagnostic_sink_->on_discovery_rx(accepted, now);
  }
  if (!accepted) {
    return reject_reason == DiscoveryRejectReason::STATE_NOT_DISCOVERY ||
                   reject_reason == DiscoveryRejectReason::PENDING_CHALLENGE ||
                   reject_reason == DiscoveryRejectReason::SELECTION_FROZEN
               ? SimpleProductError::STATE_REJECTED
               : SimpleProductError::PACKET_REJECTED;
  }

  if (!gateway_selection_epoch_.has_value()) {
    GatewaySelectionEpoch epoch;
    epoch.candidates.reserve(policy_.max_gateway_candidates);
    epoch.deadline_ms = now + policy_.candidate_window_ms;
    epoch.transaction_deadline_ms =
        now + policy_.gateway_selection_transaction_max_ms;
    gateway_selection_epoch_ = std::move(epoch);
  }
  return add_or_update_gateway_candidate_(
      source, packet, channel, rssi_dbm, now);
}

void SimpleProductRuntime::clear_gateway_selection_() {
  gateway_selection_epoch_.reset();
}

SimpleProductError SimpleProductRuntime::add_or_update_gateway_candidate_(
    const MacAddress &source,
    const SimpleRelayDiscovery &packet,
    uint8_t channel,
    int16_t rssi_dbm,
    uint64_t now_ms) {
  if (!gateway_selection_epoch_.has_value() ||
      gateway_selection_epoch_->frozen ||
      !valid_discovery_rssi_(rssi_dbm)) {
    return SimpleProductError::STATE_REJECTED;
  }

  RelayCandidate *same_node =
      find_gateway_candidate_by_node_(packet.relay_node_id);
  RelayCandidate *same_mac = find_gateway_candidate_by_mac_(source);
  if ((same_node != nullptr && same_node->mac != source) ||
      (same_mac != nullptr &&
       same_mac->relay_node_id != packet.relay_node_id)) {
    return SimpleProductError::PACKET_REJECTED;
  }

  if (same_node == nullptr) {
    if (gateway_selection_epoch_->candidates.size() >=
        policy_.max_gateway_candidates) {
      return SimpleProductError::PACKET_REJECTED;
    }
    RelayCandidate candidate;
    candidate.relay_node_id = packet.relay_node_id;
    candidate.mac = source;
    candidate.channel = channel;
    candidate.rssi_sum = rssi_dbm;
    candidate.rssi_sample_count = 1;
    candidate.first_seen_ms = now_ms;
    candidate.last_seen_ms = now_ms;
    gateway_selection_epoch_->candidates.push_back(std::move(candidate));
    return SimpleProductError::NONE;
  }

  if (same_node->channel != channel) {
    same_node->channel = channel;
    same_node->rssi_sum = rssi_dbm;
    same_node->rssi_sample_count = 1;
    same_node->last_seen_ms = now_ms;
    return SimpleProductError::NONE;
  }

  same_node->rssi_sum += rssi_dbm;
  ++same_node->rssi_sample_count;
  same_node->last_seen_ms = now_ms;
  return SimpleProductError::NONE;
}

SimpleProductError SimpleProductRuntime::select_next_gateway_candidate_(
    std::size_t *candidate_index) const {
  if (candidate_index == nullptr || !gateway_selection_epoch_.has_value() ||
      !gateway_selection_epoch_->frozen) {
    return SimpleProductError::STATE_REJECTED;
  }

  const auto &candidates = gateway_selection_epoch_->candidates;
  *candidate_index = candidates.size();
  std::size_t strongest = candidates.size();
  for (std::size_t i = 0; i < candidates.size(); ++i) {
    const RelayCandidate &candidate = candidates[i];
    if (candidate.attempted || candidate.rssi_sample_count == 0) continue;
    if (strongest == candidates.size()) {
      strongest = i;
      continue;
    }
    const RelayCandidate &current = candidates[strongest];
    const int64_t left =
        candidate.rssi_sum * static_cast<int64_t>(current.rssi_sample_count);
    const int64_t right =
        current.rssi_sum * static_cast<int64_t>(candidate.rssi_sample_count);
    if (left > right) strongest = i;
  }
  if (strongest == candidates.size()) return SimpleProductError::NONE;

  const RelayCandidate &anchor = candidates[strongest];
  std::size_t best = candidates.size();
  std::array<uint8_t, 32> best_digest{};
  for (std::size_t i = 0; i < candidates.size(); ++i) {
    const RelayCandidate &candidate = candidates[i];
    if (candidate.attempted || candidate.rssi_sample_count == 0) continue;

    const int64_t difference =
        anchor.rssi_sum * static_cast<int64_t>(candidate.rssi_sample_count) -
        candidate.rssi_sum * static_cast<int64_t>(anchor.rssi_sample_count);
    const int64_t band_limit =
        3LL * static_cast<int64_t>(anchor.rssi_sample_count) *
        static_cast<int64_t>(candidate.rssi_sample_count);
    if (difference > band_limit) continue;

    std::array<uint8_t, 32> digest{};
    if (!gateway_selection_digest(
            state_.node_id, candidate.relay_node_id, &digest)) {
      return SimpleProductError::CRYPTO_FAILED;
    }
    if (best == candidates.size() ||
        std::lexicographical_compare(
            digest.begin(), digest.end(),
            best_digest.begin(), best_digest.end()) ||
        (digest == best_digest &&
         candidate.relay_node_id < candidates[best].relay_node_id)) {
      best = i;
      best_digest = digest;
    }
  }

  *candidate_index = best;
  return SimpleProductError::NONE;
}

SimpleProductError SimpleProductRuntime::attempt_next_gateway_candidate_() {
  if (!gateway_selection_epoch_.has_value() ||
      !gateway_selection_epoch_->frozen ||
      pending_challenge_.has_value()) {
    return SimpleProductError::STATE_REJECTED;
  }

  if (clock_->now_ms() >=
      gateway_selection_epoch_->transaction_deadline_ms) {
    return begin_discovery_();
  }

  std::size_t candidate_index = 0;
  const SimpleProductError select_result =
      select_next_gateway_candidate_(&candidate_index);
  if (select_result != SimpleProductError::NONE) {
    clear_gateway_selection_();
    return select_result;
  }
  if (!gateway_selection_epoch_.has_value() ||
      candidate_index >= gateway_selection_epoch_->candidates.size()) {
    return begin_discovery_();
  }

  const RelayCandidate candidate =
      gateway_selection_epoch_->candidates[candidate_index];
  const SimpleProductError result =
      start_challenge_for_candidate_(candidate);
  if (result != SimpleProductError::NONE) {
    clear_gateway_selection_();
  }
  return result;
}

SimpleProductError SimpleProductRuntime::start_challenge_for_candidate_(
    const RelayCandidate &candidate) {
  PeerEndpointV2 relay{candidate.relay_node_id, candidate.mac};
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
  const SimpleRuntimeError encode_result =
      encode_simple_peer_challenge(challenge, &encoded);
  if (encode_result != SimpleRuntimeError::NONE) {
    if (diagnostic_sink_ != nullptr) {
      const uint64_t now = clock_->now_ms();
      diagnostic_sink_->on_challenge_tx(false, now);
      diagnostic_sink_->on_challenge_submit_result(
          false, false, 0, 0, now);
    }
    return SimpleProductError::CRYPTO_FAILED;
  }

  bool challenge_sent = false;
  uint8_t challenge_driver_error = 0;
  int32_t challenge_raw_error = 0;
  if (port_->set_radio_channel(candidate.channel)) {
    challenge_sent =
        port_->broadcast_control(encoded.data(), encoded.size());
    challenge_driver_error = port_->last_broadcast_send_error_code();
    challenge_raw_error = port_->last_broadcast_send_error_raw();
  }
  if (diagnostic_sink_ != nullptr) {
    const uint64_t now = clock_->now_ms();
    diagnostic_sink_->on_challenge_tx(challenge_sent, now);
    diagnostic_sink_->on_challenge_submit_result(
        true,
        challenge_sent,
        challenge_driver_error,
        challenge_raw_error,
        now);
  }
  if (!challenge_sent) return SimpleProductError::RADIO_FAILED;

  PendingChallenge pending;
  pending.relay_node_id = candidate.relay_node_id;
  pending.relay_mac = candidate.mac;
  pending.challenge_nonce = challenge_nonce;
  pending.channel = candidate.channel;
  pending.expires_at_ms =
      clock_->now_ms() + (2ULL * policy_.challenge_timeout_ms);
  pending_challenge_ = std::move(pending);
  return SimpleProductError::NONE;
}

SimpleProductRuntime::RelayCandidate *
SimpleProductRuntime::find_gateway_candidate_by_node_(
    const std::string &relay_node_id) {
  if (!gateway_selection_epoch_.has_value()) return nullptr;
  for (auto &candidate : gateway_selection_epoch_->candidates) {
    if (candidate.relay_node_id == relay_node_id) return &candidate;
  }
  return nullptr;
}

SimpleProductRuntime::RelayCandidate *
SimpleProductRuntime::find_gateway_candidate_by_mac_(const MacAddress &mac) {
  if (!gateway_selection_epoch_.has_value()) return nullptr;
  for (auto &candidate : gateway_selection_epoch_->candidates) {
    if (candidate.mac == mac) return &candidate;
  }
  return nullptr;
}

bool SimpleProductRuntime::valid_discovery_rssi_(int16_t rssi_dbm) {
  return rssi_dbm >= -127 && rssi_dbm <= 0;
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
  if (!gateway_selection_epoch_.has_value()) {
    pending_challenge_.reset();
    if (diagnostic_sink_ != nullptr) {
      diagnostic_sink_->on_accept_rx(false, now);
    }
    return SimpleProductError::STATE_REJECTED;
  }
  const PendingChallenge &pending = *pending_challenge_;
  if (now >= pending.expires_at_ms ||
      now >= gateway_selection_epoch_->transaction_deadline_ms) {
    if (diagnostic_sink_ != nullptr) {
      diagnostic_sink_->on_accept_rx(false, now);
    }
    return SimpleProductError::PACKET_REJECTED;
  }
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
  // Accept verification alone is not enough to enter RelayActive. Fix and
  // read back the concrete radio channel first, then bind the encrypted peer.
  if (!port_->set_radio_channel(channel)) {
    pending_challenge_.reset();
    clear_gateway_selection_();
    return SimpleProductError::RADIO_FAILED;
  }
  const LinkKey link_key = as_link_key_(lmk);
  if (!port_->install_encrypted_peer(source, link_key, channel)) {
    (void) port_->remove_peer(source);
    pending_challenge_.reset();
    clear_gateway_selection_();
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
    pending_challenge_.reset();
    clear_gateway_selection_();
    return SimpleProductError::STATE_REJECTED;
  }
  active_relay_ = std::move(relay);
  pending_challenge_.reset();
  clear_gateway_selection_();
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
  if (pending_challenge_.has_value()) return pending_challenge_->channel;
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
