#include "n3w_product_runtime.h"

#include <algorithm>
#include <utility>

namespace esphome::greenhouse_n3w_product_runtime {
namespace {

constexpr uint8_t kProductDiscoveryMagic0 = 'G';
constexpr uint8_t kProductDiscoveryMagic1 = 'P';
constexpr std::size_t kProductDiscoveryPrefixBytes = 10;

void append_u32(std::vector<uint8_t> *out, uint32_t value) {
  for (int shift = 24; shift >= 0; shift -= 8) {
    out->push_back(static_cast<uint8_t>((value >> shift) & 0xffU));
  }
}

bool read_u32(
    const uint8_t *data,
    std::size_t size,
    std::size_t *offset,
    uint32_t *value) {
  if (data == nullptr || offset == nullptr || value == nullptr || *offset + 4 > size) {
    return false;
  }
  uint32_t parsed = 0;
  for (int i = 0; i < 4; ++i) {
    parsed = (parsed << 8U) | data[*offset + static_cast<std::size_t>(i)];
  }
  *value = parsed;
  *offset += 4;
  return true;
}

}  // namespace

bool ProductDiscoveryAdvertisement::valid() const {
  return greenhouse_n3w_product_core::valid_identity(gateway_id) &&
         gateway_id.size() <= kProductDiscoveryMaxIdentityBytes &&
         greenhouse_n3w_product_core::valid_channel(channel) &&
         advertisement_generation > 0;
}

bool encode_product_discovery_advertisement(
    const ProductDiscoveryAdvertisement &advertisement,
    std::vector<uint8_t> *encoded) {
  if (encoded == nullptr || !advertisement.valid()) return false;
  encoded->clear();
  encoded->reserve(kProductDiscoveryPrefixBytes + advertisement.gateway_id.size());
  encoded->push_back(kProductDiscoveryMagic0);
  encoded->push_back(kProductDiscoveryMagic1);
  encoded->push_back(kProductDiscoveryWireVersion);
  encoded->push_back(kProductDiscoveryWireType);
  encoded->push_back(advertisement.channel);
  append_u32(encoded, advertisement.advertisement_generation);
  encoded->push_back(static_cast<uint8_t>(advertisement.gateway_id.size()));
  encoded->insert(
      encoded->end(), advertisement.gateway_id.begin(), advertisement.gateway_id.end());
  if (encoded->size() > greenhouse_n3w_core::kEspNowDatagramLimit) {
    encoded->clear();
    return false;
  }
  return true;
}

bool decode_product_discovery_advertisement(
    const uint8_t *data,
    std::size_t size,
    ProductDiscoveryAdvertisement *advertisement) {
  if (data == nullptr || advertisement == nullptr ||
      size < kProductDiscoveryPrefixBytes ||
      size > greenhouse_n3w_core::kEspNowDatagramLimit) {
    return false;
  }
  if (data[0] != kProductDiscoveryMagic0 || data[1] != kProductDiscoveryMagic1 ||
      data[2] != kProductDiscoveryWireVersion || data[3] != kProductDiscoveryWireType) {
    return false;
  }
  std::size_t offset = 4;
  ProductDiscoveryAdvertisement parsed;
  parsed.channel = data[offset++];
  if (!read_u32(data, size, &offset, &parsed.advertisement_generation) || offset >= size) {
    return false;
  }
  const std::size_t identity_size = data[offset++];
  if (identity_size == 0 || identity_size > kProductDiscoveryMaxIdentityBytes ||
      offset + identity_size != size) {
    return false;
  }
  parsed.gateway_id.assign(
      reinterpret_cast<const char *>(data + offset), identity_size);
  if (!parsed.valid()) return false;
  *advertisement = parsed;
  return true;
}

bool ProductRuntimePolicy::valid() const {
  if (allowed_channels.empty() || scan_dwell_ms == 0 ||
      candidate_select_interval_ms == 0 || advertisement_interval_ms == 0) {
    return false;
  }
  std::vector<uint8_t> seen;
  for (uint8_t channel : allowed_channels) {
    if (!greenhouse_n3w_core::valid_radio_channel(channel) ||
        std::find(seen.begin(), seen.end(), channel) != seen.end()) {
      return false;
    }
    seen.push_back(channel);
  }
  return true;
}

bool LocalRelayAdvertisement::valid() const {
  if (!enabled) return true;
  ProductDiscoveryAdvertisement advertisement;
  advertisement.gateway_id = gateway_id;
  advertisement.channel = channel;
  advertisement.advertisement_generation = advertisement_generation;
  return advertisement.valid();
}

DriverError EspNowDriverRuntimePort::initialize(EspNowEventSink *sink, const LinkKey &pmk) {
  return driver_.initialize(sink, pmk);
}

void EspNowDriverRuntimePort::shutdown() { driver_.shutdown(); }

DriverError EspNowDriverRuntimePort::set_channel(uint8_t channel) {
  return driver_.set_channel(channel);
}

DriverError EspNowDriverRuntimePort::prepare_broadcast_peer(uint8_t channel) {
  return driver_.prepare_broadcast_peer(channel);
}

DriverError EspNowDriverRuntimePort::add_encrypted_peer(
    const MacAddress &peer_mac,
    const LinkKey &lmk,
    uint8_t channel) {
  return driver_.add_encrypted_peer(peer_mac, lmk, channel);
}

DriverError EspNowDriverRuntimePort::remove_peer(const MacAddress &peer_mac) {
  return driver_.remove_peer(peer_mac);
}

DriverError EspNowDriverRuntimePort::send_peer(
    const MacAddress &peer_mac,
    const uint8_t *data,
    std::size_t size) {
  return driver_.send(peer_mac, data, size);
}

DriverError EspNowDriverRuntimePort::send_broadcast(
    const uint8_t *data,
    std::size_t size) {
  return driver_.send_broadcast(data, size);
}

ProductEspNowRuntime::ProductEspNowRuntime(
    ProductRuntimeRadioPort *radio,
    ProductRuntimeClock *clock,
    ProductRuntimeEventSink *events,
    WifiDirectHealthPolicy direct_policy,
    RelayCandidatePolicy candidate_policy,
    AutoPathPolicy path_policy,
    ProductRuntimePolicy runtime_policy)
    : radio_(radio),
      clock_(clock),
      events_(events),
      runtime_policy_(std::move(runtime_policy)),
      candidate_policy_(candidate_policy),
      orchestration_(direct_policy, candidate_policy, path_policy) {}

bool ProductEspNowRuntime::valid_unicast_mac_(const MacAddress &mac) {
  uint8_t aggregate = 0;
  for (uint8_t value : mac) aggregate |= value;
  return aggregate != 0 && (mac[0] & 0x01U) == 0;
}

bool ProductEspNowRuntime::nonzero_key_(const LinkKey &key) {
  uint8_t aggregate = 0;
  for (uint8_t value : key) aggregate |= value;
  return aggregate != 0;
}

ProductRuntimeError ProductEspNowRuntime::start(const LinkKey &pmk) {
  if (started_) return ProductRuntimeError::STATE_REJECTED;
  if (radio_ == nullptr || clock_ == nullptr || !runtime_policy_.valid() ||
      !candidate_policy_.valid() || !nonzero_key_(pmk)) {
    return ProductRuntimeError::INVALID_ARGUMENT;
  }
  const DriverError error = radio_->initialize(this, pmk);
  if (error != DriverError::NONE) return ProductRuntimeError::RADIO_ERROR;
  started_ = true;
  const uint64_t now_ms = clock_->now_ms();
  next_candidate_select_ms_ = now_ms;
  next_advertisement_ms_ = now_ms;
  return ProductRuntimeError::NONE;
}

void ProductEspNowRuntime::stop() {
  if (!started_) return;
  (void) release_active_peer_();
  scan_active_ = false;
  pending_authorization_mac_.reset();
  mirrors_.clear();
  radio_->shutdown();
  started_ = false;
}

ProductRuntimeError ProductEspNowRuntime::set_last_direct_channel(uint8_t channel) {
  if (!greenhouse_n3w_core::valid_radio_channel(channel)) {
    return ProductRuntimeError::INVALID_ARGUMENT;
  }
  last_direct_channel_ = channel;
  return ProductRuntimeError::NONE;
}

ProductRuntimeError ProductEspNowRuntime::set_local_relay_advertisement(
    const LocalRelayAdvertisement &advertisement) {
  if (!advertisement.valid()) return ProductRuntimeError::INVALID_ARGUMENT;
  local_advertisement_ = advertisement;
  next_advertisement_ms_ = 0;
  return ProductRuntimeError::NONE;
}

ProductRuntimeError ProductEspNowRuntime::note_direct_result(bool success) {
  if (!started_) return ProductRuntimeError::NOT_READY;
  const uint64_t now_ms = clock_->now_ms();
  const ProductCoreError error = orchestration_.note_direct_result(success, now_ms);
  if (error != ProductCoreError::NONE) return ProductRuntimeError::CORE_ERROR;
  return handle_path_state_(now_ms);
}

ProductRuntimeError ProductEspNowRuntime::note_direct_recovery_probe(bool success) {
  if (!started_) return ProductRuntimeError::NOT_READY;
  const uint64_t now_ms = clock_->now_ms();
  const ProductCoreError error = orchestration_.note_direct_recovery_probe(success, now_ms);
  if (error != ProductCoreError::NONE) return ProductRuntimeError::CORE_ERROR;
  return handle_path_state_(now_ms);
}

ProductRuntimeError ProductEspNowRuntime::begin_scan_(uint64_t now_ms) {
  if (scan_active_) return ProductRuntimeError::NONE;
  if (!started_) return ProductRuntimeError::NOT_READY;
  const greenhouse_n3w_core::RadioError configured =
      scan_plan_.configure(last_direct_channel_, runtime_policy_.allowed_channels);
  if (configured != greenhouse_n3w_core::RadioError::NONE || scan_plan_.size() == 0) {
    return ProductRuntimeError::POLICY_INVALID;
  }
  const uint8_t channel = scan_plan_.current();
  if (radio_->set_channel(channel) != DriverError::NONE) {
    return ProductRuntimeError::RADIO_ERROR;
  }
  scan_active_ = true;
  next_scan_switch_ms_ = now_ms + runtime_policy_.scan_dwell_ms;
  next_candidate_select_ms_ = now_ms;
  return ProductRuntimeError::NONE;
}

void ProductEspNowRuntime::stop_scan_() { scan_active_ = false; }

ProductRuntimeError ProductEspNowRuntime::advance_scan_(uint64_t now_ms) {
  if (!scan_active_ || now_ms < next_scan_switch_ms_) return ProductRuntimeError::NONE;
  const uint8_t channel = scan_plan_.advance();
  if (radio_->set_channel(channel) != DriverError::NONE) {
    return ProductRuntimeError::RADIO_ERROR;
  }
  next_scan_switch_ms_ = now_ms + runtime_policy_.scan_dwell_ms;
  return ProductRuntimeError::NONE;
}

ProductEspNowRuntime::CandidateMirror *ProductEspNowRuntime::find_mirror_(
    const MacAddress &source_mac) {
  for (auto &mirror : mirrors_) {
    if (greenhouse_n3w_product_core::same_mac(
            mirror.record.observation.source_mac, source_mac)) {
      return &mirror;
    }
  }
  return nullptr;
}

const ProductEspNowRuntime::CandidateMirror *ProductEspNowRuntime::find_mirror_(
    const MacAddress &source_mac) const {
  for (const auto &mirror : mirrors_) {
    if (greenhouse_n3w_product_core::same_mac(
            mirror.record.observation.source_mac, source_mac)) {
      return &mirror;
    }
  }
  return nullptr;
}

void ProductEspNowRuntime::prune_mirrors_(uint64_t now_ms) {
  mirrors_.erase(
      std::remove_if(mirrors_.begin(), mirrors_.end(), [&](const CandidateMirror &mirror) {
        const uint64_t observed_at_ms = mirror.record.observation.observed_at_ms;
        return now_ms < observed_at_ms ||
               now_ms - observed_at_ms > candidate_policy_.observation_ttl_ms;
      }),
      mirrors_.end());
}

void ProductEspNowRuntime::mirror_observation_(
    const RelayCandidateObservation &observation) {
  CandidateMirror *existing = find_mirror_(observation.source_mac);
  if (existing != nullptr) {
    const bool identity_changed =
        existing->record.observation.gateway_id != observation.gateway_id;
    existing->record.observation = observation;
    if (identity_changed) {
      existing->record.eligibility = RelayCandidateEligibility{};
      existing->record.has_eligibility = false;
    }
    return;
  }
  if (mirrors_.size() >= candidate_policy_.capacity) return;
  CandidateMirror mirror;
  mirror.record.observation = observation;
  mirrors_.push_back(mirror);
}

void ProductEspNowRuntime::mirror_eligibility_(
    const MacAddress &source_mac,
    const RelayCandidateEligibility &eligibility) {
  CandidateMirror *mirror = find_mirror_(source_mac);
  if (mirror == nullptr) return;
  mirror->record.eligibility = eligibility;
  mirror->record.has_eligibility = true;
}

ProductRuntimeError ProductEspNowRuntime::apply_manager_eligibility(
    const MacAddress &source_mac,
    const std::string &gateway_id,
    const RelayCandidateEligibility &eligibility) {
  if (!started_) return ProductRuntimeError::NOT_READY;
  const uint64_t now_ms = clock_->now_ms();
  orchestration_.maintenance(now_ms);
  prune_mirrors_(now_ms);
  const ProductCoreError error = orchestration_.apply_manager_eligibility(
      source_mac, gateway_id, eligibility);
  if (error != ProductCoreError::NONE) return ProductRuntimeError::CORE_ERROR;
  mirror_eligibility_(source_mac, eligibility);
  next_candidate_select_ms_ = now_ms;
  return maybe_select_candidate_(now_ms);
}

ProductRuntimeError ProductEspNowRuntime::maybe_select_candidate_(uint64_t now_ms) {
  if (!scan_active_ || now_ms < next_candidate_select_ms_) {
    return ProductRuntimeError::NONE;
  }
  next_candidate_select_ms_ = now_ms + runtime_policy_.candidate_select_interval_ms;
  const ProductCoreError selected = orchestration_.select_candidate(now_ms);
  if (selected == ProductCoreError::NOT_FOUND) return ProductRuntimeError::NONE;
  if (selected != ProductCoreError::NONE) return ProductRuntimeError::CORE_ERROR;
  if (!orchestration_.selected_mac().has_value()) {
    return fail_pending_authorization_(now_ms);
  }
  const CandidateMirror *mirror = find_mirror_(*orchestration_.selected_mac());
  if (mirror == nullptr || !mirror->record.has_eligibility) {
    return fail_pending_authorization_(now_ms);
  }
  pending_authorization_mac_ = mirror->record.observation.source_mac;
  stop_scan_();
  if (radio_->set_channel(mirror->record.observation.channel) != DriverError::NONE) {
    const ProductRuntimeError recovery = fail_pending_authorization_(now_ms);
    return recovery == ProductRuntimeError::NONE ? ProductRuntimeError::RADIO_ERROR : recovery;
  }
  if (events_ != nullptr) events_->on_authorization_needed(mirror->record);
  return ProductRuntimeError::NONE;
}

bool ProductEspNowRuntime::material_matches_pending_(
    const RuntimePeerMaterial &material,
    uint64_t now_ms) const {
  if (!pending_authorization_mac_.has_value() || !material.authorization.valid_shape() ||
      !material.authorization.manager_authorized || !material.authorization.same_system ||
      !nonzero_key_(material.lmk) || now_ms < material.authorization.issued_at_ms ||
      now_ms >= material.authorization.expires_at_ms) {
    return false;
  }
  const CandidateMirror *mirror = find_mirror_(*pending_authorization_mac_);
  if (mirror == nullptr || !mirror->record.has_eligibility ||
      !mirror->record.eligibility.eligible_at(now_ms)) {
    return false;
  }
  return material.authorization.gateway_id == mirror->record.observation.gateway_id &&
         greenhouse_n3w_product_core::same_mac(
             material.authorization.peer_mac, mirror->record.observation.source_mac) &&
         material.authorization.channel == mirror->record.observation.channel &&
         material.authorization.relay_credential_generation ==
             mirror->record.eligibility.credential_generation;
}

ProductRuntimeError ProductEspNowRuntime::install_authorized_peer(
    const RuntimePeerMaterial &material) {
  if (!started_) return ProductRuntimeError::NOT_READY;
  const uint64_t now_ms = clock_->now_ms();
  if (orchestration_.path_state() != AutoPathState::RELAY_AUTH ||
      !material_matches_pending_(material, now_ms)) {
    return ProductRuntimeError::STATE_REJECTED;
  }
  if (radio_->set_channel(material.authorization.channel) != DriverError::NONE) {
    const ProductRuntimeError recovery = fail_pending_authorization_(now_ms);
    return recovery == ProductRuntimeError::NONE ? ProductRuntimeError::RADIO_ERROR : recovery;
  }
  if (radio_->add_encrypted_peer(
          material.authorization.peer_mac, material.lmk, material.authorization.channel) !=
      DriverError::NONE) {
    const ProductRuntimeError recovery = fail_pending_authorization_(now_ms);
    return recovery == ProductRuntimeError::NONE ? ProductRuntimeError::RADIO_ERROR : recovery;
  }
  const ProductCoreError accepted =
      orchestration_.accept_peer_authorization(material.authorization, now_ms);
  if (accepted != ProductCoreError::NONE) {
    (void) radio_->remove_peer(material.authorization.peer_mac);
    const ProductRuntimeError recovery = fail_pending_authorization_(now_ms);
    return recovery == ProductRuntimeError::NONE ? ProductRuntimeError::CORE_ERROR : recovery;
  }
  active_peer_mac_ = material.authorization.peer_mac;
  pending_authorization_mac_.reset();
  stop_scan_();
  if (events_ != nullptr) events_->on_peer_active(material.authorization);
  return ProductRuntimeError::NONE;
}

ProductRuntimeError ProductEspNowRuntime::fail_pending_authorization_(uint64_t now_ms) {
  pending_authorization_mac_.reset();
  if (orchestration_.path_state() == AutoPathState::RELAY_AUTH) {
    const ProductCoreError rejected = orchestration_.reject_peer_authorization();
    if (rejected != ProductCoreError::NONE) return ProductRuntimeError::CORE_ERROR;
  }
  return begin_scan_(now_ms);
}

ProductRuntimeError ProductEspNowRuntime::reject_peer_authorization() {
  if (!started_) return ProductRuntimeError::NOT_READY;
  const uint64_t now_ms = clock_->now_ms();
  if (orchestration_.path_state() != AutoPathState::RELAY_AUTH) {
    return ProductRuntimeError::STATE_REJECTED;
  }
  const ProductCoreError rejected = orchestration_.reject_peer_authorization();
  if (rejected != ProductCoreError::NONE) return ProductRuntimeError::CORE_ERROR;
  pending_authorization_mac_.reset();
  return begin_scan_(now_ms);
}

ProductRuntimeError ProductEspNowRuntime::release_active_peer_() {
  if (!active_peer_mac_.has_value()) return ProductRuntimeError::NONE;
  const MacAddress released = *active_peer_mac_;
  const DriverError radio_error = radio_->remove_peer(released);
  active_peer_mac_.reset();
  if (events_ != nullptr) events_->on_peer_released(released);
  return radio_error == DriverError::NONE ? ProductRuntimeError::NONE
                                          : ProductRuntimeError::RADIO_ERROR;
}

ProductRuntimeError ProductEspNowRuntime::handle_path_state_(uint64_t now_ms) {
  const AutoPathState state = orchestration_.path_state();
  if (state == AutoPathState::DISCOVERY || state == AutoPathState::REDISCOVERY) {
    const ProductRuntimeError released = release_active_peer_();
    const ProductRuntimeError scan = begin_scan_(now_ms);
    if (scan != ProductRuntimeError::NONE) return scan;
    return released;
  }
  if (state == AutoPathState::RELAY_AUTH || state == AutoPathState::RELAY_ACTIVE ||
      state == AutoPathState::DIRECT_RECOVERY || state == AutoPathState::DIRECT_DEGRADED) {
    stop_scan_();
    return ProductRuntimeError::NONE;
  }
  if (state == AutoPathState::DIRECT) {
    stop_scan_();
    pending_authorization_mac_.reset();
    return release_active_peer_();
  }
  return ProductRuntimeError::STATE_REJECTED;
}

ProductRuntimeError ProductEspNowRuntime::note_relay_result(bool success) {
  if (!started_) return ProductRuntimeError::NOT_READY;
  const uint64_t now_ms = clock_->now_ms();
  const ProductCoreError error = orchestration_.note_relay_result(success, now_ms);
  if (error != ProductCoreError::NONE) return ProductRuntimeError::CORE_ERROR;
  return handle_path_state_(now_ms);
}

bool ProductEspNowRuntime::relay_telemetry_ready() const {
  return started_ && active_peer_mac_.has_value() &&
         orchestration_.relay_telemetry_ready(clock_->now_ms());
}

ProductRuntimeError ProductEspNowRuntime::send_active_peer(
    const uint8_t *data,
    std::size_t size) {
  if (!started_) return ProductRuntimeError::NOT_READY;
  if (!relay_telemetry_ready() || data == nullptr || size == 0 ||
      size > greenhouse_n3w_core::kEspNowDatagramLimit) {
    return ProductRuntimeError::STATE_REJECTED;
  }
  return radio_->send_peer(*active_peer_mac_, data, size) == DriverError::NONE
             ? ProductRuntimeError::NONE
             : ProductRuntimeError::RADIO_ERROR;
}

ProductRuntimeError ProductEspNowRuntime::maybe_send_advertisement_(uint64_t now_ms) {
  if (!local_advertisement_.enabled || orchestration_.path_state() != AutoPathState::DIRECT ||
      now_ms < next_advertisement_ms_) {
    return ProductRuntimeError::NONE;
  }
  if (!local_advertisement_.valid() || last_direct_channel_ == 0 ||
      local_advertisement_.channel != last_direct_channel_) {
    return ProductRuntimeError::STATE_REJECTED;
  }
  next_advertisement_ms_ = now_ms + runtime_policy_.advertisement_interval_ms;
  ProductDiscoveryAdvertisement advertisement;
  advertisement.gateway_id = local_advertisement_.gateway_id;
  advertisement.channel = local_advertisement_.channel;
  advertisement.advertisement_generation = local_advertisement_.advertisement_generation;
  std::vector<uint8_t> encoded;
  if (!encode_product_discovery_advertisement(advertisement, &encoded)) {
    return ProductRuntimeError::PACKET_REJECTED;
  }
  if (radio_->prepare_broadcast_peer(advertisement.channel) != DriverError::NONE ||
      radio_->send_broadcast(encoded.data(), encoded.size()) != DriverError::NONE) {
    return ProductRuntimeError::RADIO_ERROR;
  }
  if (events_ != nullptr) events_->on_advertisement_sent(advertisement);
  return ProductRuntimeError::NONE;
}

ProductRuntimeError ProductEspNowRuntime::tick() {
  if (!started_) return ProductRuntimeError::NOT_READY;
  const uint64_t now_ms = clock_->now_ms();
  orchestration_.maintenance(now_ms);
  prune_mirrors_(now_ms);
  ProductRuntimeError state_error = handle_path_state_(now_ms);
  if (state_error != ProductRuntimeError::NONE) return state_error;
  if (scan_active_) {
    ProductRuntimeError error = advance_scan_(now_ms);
    if (error != ProductRuntimeError::NONE) return error;
    error = maybe_select_candidate_(now_ms);
    if (error != ProductRuntimeError::NONE) return error;
  }
  return maybe_send_advertisement_(now_ms);
}

void ProductEspNowRuntime::on_espnow_receive(
    const MacAddress &source,
    const uint8_t *data,
    std::size_t size) {
  EspNowReceiveMetadata metadata;
  metadata.channel = scan_active_ ? scan_plan_.current() : 0;
  on_espnow_receive_with_metadata(source, data, size, metadata);
}

void ProductEspNowRuntime::on_espnow_receive_with_metadata(
    const MacAddress &source,
    const uint8_t *data,
    std::size_t size,
    const EspNowReceiveMetadata &metadata) {
  if (!started_ || !scan_active_ || !valid_unicast_mac_(source)) return;
  ProductDiscoveryAdvertisement advertisement;
  if (!decode_product_discovery_advertisement(data, size, &advertisement)) return;
  const uint8_t current_channel = scan_plan_.current();
  if (advertisement.channel != current_channel ||
      (metadata.channel != 0 && metadata.channel != advertisement.channel) ||
      metadata.rssi_dbm < -127 || metadata.rssi_dbm > 0) {
    return;
  }
  const uint64_t now_ms = clock_->now_ms();
  orchestration_.maintenance(now_ms);
  prune_mirrors_(now_ms);
  RelayCandidateObservation observation;
  observation.gateway_id = advertisement.gateway_id;
  observation.source_mac = source;
  observation.channel = advertisement.channel;
  observation.rssi_dbm = metadata.rssi_dbm;
  observation.advertisement_generation = advertisement.advertisement_generation;
  observation.observed_at_ms = now_ms;
  const ProductCoreError observed = orchestration_.observe_candidate(observation);
  if (observed != ProductCoreError::NONE) return;
  mirror_observation_(observation);
  if (events_ != nullptr) events_->on_candidate_observed(observation);
}

void ProductEspNowRuntime::on_espnow_send_result(
    const MacAddress &destination,
    bool success) {
  (void) destination;
  (void) success;
  // Link-layer send completion is intentionally not treated as end-to-end
  // relay success. Existing N3-W ReceiptAck/retry semantics remain authoritative.
}

}  // namespace esphome::greenhouse_n3w_product_runtime
