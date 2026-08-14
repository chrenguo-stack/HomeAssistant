#include "n3w_product_s5_peer_coordinator.h"

#include <algorithm>
#include <utility>

namespace esphome::greenhouse_n3w_product_runtime {

bool ProductS5NodeCredentials::valid() const {
  return ProductPeerSecurity::valid_identifier_(system_id) &&
         ProductPeerSecurity::valid_identifier_(node_id) && credential_generation > 0 && key_epoch > 0 &&
         ProductPeerSecurity::nonzero_(application_key.data(), application_key.size());
}

bool ProductS5CryptoRandomSource::fill32(ProductPeerKey *value) {
  return ProductPeerSecurity::random_private_key(value);
}

uint64_t ProductS5CryptoRandomSource::session_token() {
  ProductPeerKey random{};
  if (!ProductPeerSecurity::random_private_key(&random)) return 0;
  uint64_t token = 0;
  for (std::size_t index = 0; index < 8; ++index) {
    token = (token << 8U) | random[index];
  }
  std::fill(random.begin(), random.end(), 0);
  return token;
}

ProductS5PeerCoordinator::ProductS5PeerCoordinator(
    ProductS5Role role,
    const MacAddress &local_mac,
    ProductS5NodeCredentials credentials,
    ProductRuntimeClock *clock,
    ProductS5RandomSource *random,
    ProductS5RelayHealthProvider *relay_health,
    ProductS5ManagerPort *manager,
    ProductS5CoordinatorPolicy policy)
    : role_(role),
      local_mac_(local_mac),
      credentials_(std::move(credentials)),
      clock_(clock),
      random_(random),
      relay_health_(relay_health),
      manager_(manager),
      policy_(policy) {
  if (credentials_.valid()) {
    (void) ProductPeerSecurity::derive_relay_auth_key(
        credentials_.application_key,
        credentials_.system_id,
        credentials_.node_id,
        credentials_.credential_generation,
        credentials_.key_epoch,
        &relay_auth_key_);
  }
}

ProductS5PeerCoordinator::~ProductS5PeerCoordinator() {
  reset();
  zeroize_(relay_auth_key_.data(), relay_auth_key_.size());
  zeroize_(credentials_.application_key.data(), credentials_.application_key.size());
}

bool ProductS5PeerCoordinator::valid_unicast_mac_(const MacAddress &mac) {
  uint8_t aggregate = 0;
  for (uint8_t value : mac) aggregate |= value;
  return aggregate != 0 && (mac[0] & 0x01U) == 0;
}

bool ProductS5PeerCoordinator::same_mac_(const MacAddress &left, const MacAddress &right) {
  return std::equal(left.begin(), left.end(), right.begin());
}

void ProductS5PeerCoordinator::zeroize_(void *data, std::size_t length) {
  if (data == nullptr) return;
  volatile uint8_t *cursor = static_cast<volatile uint8_t *>(data);
  while (length-- > 0) *cursor++ = 0;
}

ProductS5CoordinatorError ProductS5PeerCoordinator::attach(
    ProductEspNowRuntime *runtime,
    ProductRuntimeRadioPort *radio) {
  if (runtime_ != nullptr || radio_ != nullptr || runtime == nullptr || radio == nullptr ||
      clock_ == nullptr || random_ == nullptr || !policy_.valid() || !credentials_.valid() ||
      !valid_unicast_mac_(local_mac_) ||
      !ProductPeerSecurity::nonzero_(relay_auth_key_.data(), relay_auth_key_.size()) ||
      (role_ == ProductS5Role::RELAY && (relay_health_ == nullptr || manager_ == nullptr))) {
    return ProductS5CoordinatorError::INVALID_ARGUMENT;
  }
  runtime_ = runtime;
  radio_ = radio;
  return ProductS5CoordinatorError::NONE;
}

bool ProductS5PeerCoordinator::provisional_channel_locked() const {
  return role_ == ProductS5Role::CHILD &&
         (state_ == ProductS5PeerState::CHILD_WAIT_CHALLENGE ||
          state_ == ProductS5PeerState::CHILD_WAIT_GRANT ||
          state_ == ProductS5PeerState::CHILD_WAIT_RUNTIME_INSTALL);
}

void ProductS5PeerCoordinator::clear_ephemeral_() {
  zeroize_(local_ephemeral_private_.data(), local_ephemeral_private_.size());
}

void ProductS5PeerCoordinator::clear_cached_runtime_material_() {
  if (cached_runtime_material_.has_value()) {
    zeroize_(cached_runtime_material_->lmk.data(), cached_runtime_material_->lmk.size());
    cached_runtime_material_.reset();
  }
}

void ProductS5PeerCoordinator::clear_pending_(bool remove_relay_peer) {
  if (remove_relay_peer && radio_ != nullptr && relay_active_child_mac_.has_value()) {
    (void) radio_->remove_peer(*relay_active_child_mac_);
  }
  clear_ephemeral_();
  pending_request_.reset();
  child_candidate_.reset();
  relay_pending_child_mac_.reset();
  relay_active_child_mac_.reset();
  clear_cached_runtime_material_();
  pending_channel_ = 0;
  session_token_ = 0;
  deadline_ms_ = 0;
  active_expires_at_ms_ = 0;
  state_ = ProductS5PeerState::IDLE;
}

void ProductS5PeerCoordinator::reset() {
  clear_pending_(role_ == ProductS5Role::RELAY);
}

void ProductS5PeerCoordinator::expire_pending_(uint64_t now_ms) {
  if (state_ == ProductS5PeerState::RELAY_ACTIVE && active_expires_at_ms_ != 0 &&
      now_ms >= active_expires_at_ms_) {
    clear_pending_(true);
    return;
  }
  if (deadline_ms_ != 0 && now_ms >= deadline_ms_ &&
      state_ != ProductS5PeerState::CHILD_ACTIVE && state_ != ProductS5PeerState::RELAY_ACTIVE) {
    if (role_ == ProductS5Role::CHILD && runtime_ != nullptr &&
        runtime_->path_state() == AutoPathState::RELAY_AUTH) {
      (void) runtime_->reject_peer_authorization();
    }
    clear_pending_(false);
  }
}

ProductS5CoordinatorError ProductS5PeerCoordinator::tick() {
  if (runtime_ == nullptr || radio_ == nullptr || clock_ == nullptr) {
    return ProductS5CoordinatorError::NOT_READY;
  }
  const uint64_t now_ms = clock_->now_ms();
  expire_pending_(now_ms);
  if (provisional_channel_locked()) return ProductS5CoordinatorError::NONE;
  const ProductRuntimeError result = runtime_->tick();
  return result == ProductRuntimeError::NONE ? ProductS5CoordinatorError::NONE
                                             : ProductS5CoordinatorError::RUNTIME_FAILED;
}

ProductS5CoordinatorError ProductS5PeerCoordinator::send_broadcast_(
    uint8_t channel,
    const std::vector<uint8_t> &packet) {
  if (radio_ == nullptr || !greenhouse_n3w_core::valid_radio_channel(channel) || packet.empty() ||
      packet.size() > greenhouse_n3w_core::kEspNowDatagramLimit) {
    return ProductS5CoordinatorError::INVALID_ARGUMENT;
  }
  if (radio_->set_channel(channel) != DriverError::NONE ||
      radio_->prepare_broadcast_peer(channel) != DriverError::NONE ||
      radio_->send_broadcast(packet.data(), packet.size()) != DriverError::NONE) {
    return ProductS5CoordinatorError::RADIO_FAILED;
  }
  return ProductS5CoordinatorError::NONE;
}

ProductS5CoordinatorError ProductS5PeerCoordinator::start_child_provisional_(
    const RelayCandidateObservation &observation) {
  if (role_ != ProductS5Role::CHILD || state_ != ProductS5PeerState::IDLE || runtime_ == nullptr ||
      radio_ == nullptr || clock_ == nullptr || random_ == nullptr || !observation.valid() ||
      observation.gateway_id == credentials_.node_id || !runtime_->scan_active()) {
    return ProductS5CoordinatorError::STATE_REJECTED;
  }

  ProductPeerKey child_private{};
  ProductPeerKey child_public{};
  ProductPeerKey nonce{};
  const uint64_t token = random_->session_token();
  if (token == 0 || !random_->fill32(&child_private) || !random_->fill32(&nonce)) {
    zeroize_(child_private.data(), child_private.size());
    zeroize_(nonce.data(), nonce.size());
    return ProductS5CoordinatorError::RANDOM_FAILED;
  }
  if (!ProductPeerSecurity::x25519_public_key(child_private, &child_public)) {
    zeroize_(child_private.data(), child_private.size());
    zeroize_(nonce.data(), nonce.size());
    return ProductS5CoordinatorError::CRYPTO_FAILED;
  }

  ProductChildAuthInit init;
  init.session_token = token;
  init.child_node_id = credentials_.node_id;
  init.target_relay_node_id = observation.gateway_id;
  init.child_credential_generation = credentials_.credential_generation;
  init.child_key_epoch = credentials_.key_epoch;
  init.child_ephemeral_public_key = child_public;
  init.child_nonce = nonce;
  std::vector<uint8_t> encoded;
  if (!encode_child_auth_init(init, &encoded)) {
    zeroize_(child_private.data(), child_private.size());
    zeroize_(nonce.data(), nonce.size());
    return ProductS5CoordinatorError::PACKET_REJECTED;
  }

  ProductPeerRequest request;
  request.system_id = credentials_.system_id;
  request.session_id = product_session_id(token);
  request.child.node_id = credentials_.node_id;
  request.child.credential_generation = credentials_.credential_generation;
  request.child.key_epoch = credentials_.key_epoch;
  request.child.ephemeral_public_key = child_public;
  request.child.nonce = nonce;

  session_token_ = token;
  local_ephemeral_private_ = child_private;
  child_candidate_ = observation;
  pending_channel_ = observation.channel;
  pending_request_ = request;
  state_ = ProductS5PeerState::CHILD_WAIT_CHALLENGE;
  deadline_ms_ = clock_->now_ms() + policy_.peer_handshake_timeout_ms;
  const ProductS5CoordinatorError sent = send_broadcast_(observation.channel, encoded);
  if (sent != ProductS5CoordinatorError::NONE) clear_pending_(false);
  zeroize_(child_private.data(), child_private.size());
  zeroize_(nonce.data(), nonce.size());
  return sent;
}

void ProductS5PeerCoordinator::on_candidate_observed(
    const RelayCandidateObservation &observation) {
  if (role_ == ProductS5Role::CHILD && state_ == ProductS5PeerState::IDLE) {
    (void) start_child_provisional_(observation);
  }
}

ProductS5CoordinatorError ProductS5PeerCoordinator::accept_child_auth_init_(
    const MacAddress &source,
    const ProductChildAuthInit &init,
    const EspNowReceiveMetadata &metadata) {
  if (role_ != ProductS5Role::RELAY || state_ != ProductS5PeerState::IDLE || runtime_ == nullptr ||
      runtime_->path_state() != AutoPathState::DIRECT || !valid_unicast_mac_(source) ||
      !init.valid() || init.target_relay_node_id != credentials_.node_id ||
      init.child_node_id == credentials_.node_id ||
      !greenhouse_n3w_core::valid_radio_channel(metadata.channel)) {
    return ProductS5CoordinatorError::STATE_REJECTED;
  }

  ProductPeerKey relay_private{};
  ProductPeerKey relay_public{};
  ProductPeerKey relay_nonce{};
  if (!random_->fill32(&relay_private) || !random_->fill32(&relay_nonce)) {
    zeroize_(relay_private.data(), relay_private.size());
    zeroize_(relay_nonce.data(), relay_nonce.size());
    return ProductS5CoordinatorError::RANDOM_FAILED;
  }
  if (!ProductPeerSecurity::x25519_public_key(relay_private, &relay_public)) {
    zeroize_(relay_private.data(), relay_private.size());
    zeroize_(relay_nonce.data(), relay_nonce.size());
    return ProductS5CoordinatorError::CRYPTO_FAILED;
  }

  const uint64_t now_ms = clock_->now_ms();
  ProductRelayHealth health;
  if (relay_health_ == nullptr || !relay_health_->read_health(now_ms, &health) ||
      health.observed_at_ms == 0) {
    zeroize_(relay_private.data(), relay_private.size());
    zeroize_(relay_nonce.data(), relay_nonce.size());
    return ProductS5CoordinatorError::STATE_REJECTED;
  }

  ProductPeerRequest request;
  request.system_id = credentials_.system_id;
  request.session_id = product_session_id(init.session_token);
  request.requested_at_ms = now_ms;
  request.child.node_id = init.child_node_id;
  request.child.credential_generation = init.child_credential_generation;
  request.child.key_epoch = init.child_key_epoch;
  request.child.ephemeral_public_key = init.child_ephemeral_public_key;
  request.child.nonce = init.child_nonce;
  request.relay.node_id = credentials_.node_id;
  request.relay.credential_generation = credentials_.credential_generation;
  request.relay.key_epoch = credentials_.key_epoch;
  request.relay.ephemeral_public_key = relay_public;
  request.relay.nonce = relay_nonce;
  request.relay_health = health;
  if (!request.valid_shape(false)) {
    zeroize_(relay_private.data(), relay_private.size());
    zeroize_(relay_nonce.data(), relay_nonce.size());
    return ProductS5CoordinatorError::PACKET_REJECTED;
  }

  ProductRelayChallenge challenge;
  challenge.session_token = init.session_token;
  challenge.target_child_mac = source;
  challenge.relay_node_id = credentials_.node_id;
  challenge.relay_credential_generation = credentials_.credential_generation;
  challenge.relay_key_epoch = credentials_.key_epoch;
  challenge.relay_ephemeral_public_key = relay_public;
  challenge.relay_nonce = relay_nonce;
  challenge.requested_at_ms = now_ms;
  challenge.relay_health = health;
  std::vector<uint8_t> encoded;
  if (!encode_relay_challenge(challenge, &encoded)) {
    zeroize_(relay_private.data(), relay_private.size());
    zeroize_(relay_nonce.data(), relay_nonce.size());
    return ProductS5CoordinatorError::PACKET_REJECTED;
  }

  session_token_ = init.session_token;
  local_ephemeral_private_ = relay_private;
  relay_pending_child_mac_ = source;
  pending_channel_ = metadata.channel;
  pending_request_ = request;
  state_ = ProductS5PeerState::RELAY_WAIT_CHILD_PROOF;
  deadline_ms_ = now_ms + policy_.peer_handshake_timeout_ms;
  const ProductS5CoordinatorError sent = send_broadcast_(metadata.channel, encoded);
  if (sent != ProductS5CoordinatorError::NONE) clear_pending_(false);
  zeroize_(relay_private.data(), relay_private.size());
  zeroize_(relay_nonce.data(), relay_nonce.size());
  return sent;
}

ProductS5CoordinatorError ProductS5PeerCoordinator::accept_relay_challenge_(
    const MacAddress &source,
    const ProductRelayChallenge &challenge,
    const EspNowReceiveMetadata &metadata) {
  if (role_ != ProductS5Role::CHILD || state_ != ProductS5PeerState::CHILD_WAIT_CHALLENGE ||
      !pending_request_.has_value() || !child_candidate_.has_value() ||
      challenge.session_token != session_token_ || !same_mac_(source, child_candidate_->source_mac) ||
      !same_mac_(challenge.target_child_mac, local_mac_) ||
      challenge.relay_node_id != child_candidate_->gateway_id ||
      metadata.channel != child_candidate_->channel || !challenge.valid()) {
    return ProductS5CoordinatorError::STATE_REJECTED;
  }

  ProductPeerRequest request = *pending_request_;
  request.requested_at_ms = challenge.requested_at_ms;
  request.relay.node_id = challenge.relay_node_id;
  request.relay.credential_generation = challenge.relay_credential_generation;
  request.relay.key_epoch = challenge.relay_key_epoch;
  request.relay.ephemeral_public_key = challenge.relay_ephemeral_public_key;
  request.relay.nonce = challenge.relay_nonce;
  request.relay_health = challenge.relay_health;
  if (!request.valid_shape(false)) return ProductS5CoordinatorError::PACKET_REJECTED;
  if (!ProductPeerSecurity::build_endpoint_proof(
          request, ProductPeerRole::CHILD, relay_auth_key_, &request.child.proof)) {
    return ProductS5CoordinatorError::CRYPTO_FAILED;
  }

  ProductChildProofPacket packet;
  packet.session_token = session_token_;
  packet.target_relay_mac = source;
  packet.child_proof = request.child.proof;
  std::vector<uint8_t> encoded;
  if (!encode_child_proof_packet(packet, &encoded)) return ProductS5CoordinatorError::PACKET_REJECTED;
  pending_request_ = request;
  state_ = ProductS5PeerState::CHILD_WAIT_GRANT;
  deadline_ms_ = clock_->now_ms() + policy_.manager_timeout_ms + policy_.peer_handshake_timeout_ms;
  const ProductS5CoordinatorError sent = send_broadcast_(metadata.channel, encoded);
  if (sent != ProductS5CoordinatorError::NONE) clear_pending_(false);
  return sent;
}

ProductS5CoordinatorError ProductS5PeerCoordinator::accept_child_proof_(
    const MacAddress &source,
    const ProductChildProofPacket &packet,
    const EspNowReceiveMetadata &metadata) {
  if (role_ != ProductS5Role::RELAY || state_ != ProductS5PeerState::RELAY_WAIT_CHILD_PROOF ||
      !pending_request_.has_value() || !relay_pending_child_mac_.has_value() ||
      packet.session_token != session_token_ || !same_mac_(source, *relay_pending_child_mac_) ||
      !same_mac_(packet.target_relay_mac, local_mac_) || metadata.channel != pending_channel_ ||
      !packet.valid()) {
    return ProductS5CoordinatorError::STATE_REJECTED;
  }

  ProductPeerRequest request = *pending_request_;
  request.child.proof = packet.child_proof;
  if (!ProductPeerSecurity::build_endpoint_proof(
          request, ProductPeerRole::RELAY, relay_auth_key_, &request.relay.proof) ||
      !request.valid_shape(true)) {
    return ProductS5CoordinatorError::CRYPTO_FAILED;
  }
  if (manager_ == nullptr || !manager_->submit_peer_authorization(request)) {
    return ProductS5CoordinatorError::MANAGER_FAILED;
  }
  pending_request_ = request;
  state_ = ProductS5PeerState::RELAY_WAIT_MANAGER;
  deadline_ms_ = clock_->now_ms() + policy_.manager_timeout_ms;
  return ProductS5CoordinatorError::NONE;
}

bool ProductS5PeerCoordinator::grant_matches_pending_(
    const ProductPeerGrant &grant,
    ProductPeerRole expected_role) const {
  if (!pending_request_.has_value() || !grant.valid_shape() || grant.role != expected_role) return false;
  const ProductPeerRequest &request = *pending_request_;
  return grant.system_id == request.system_id && grant.session_id == request.session_id &&
         grant.child_node_id == request.child.node_id && grant.relay_node_id == request.relay.node_id &&
         grant.child_credential_generation == request.child.credential_generation &&
         grant.relay_credential_generation == request.relay.credential_generation &&
         grant.child_key_epoch == request.child.key_epoch && grant.relay_key_epoch == request.relay.key_epoch &&
         grant.child_ephemeral_public_key == request.child.ephemeral_public_key &&
         grant.relay_ephemeral_public_key == request.relay.ephemeral_public_key &&
         grant.child_nonce == request.child.nonce && grant.relay_nonce == request.relay.nonce;
}

ProductS5CoordinatorError ProductS5PeerCoordinator::accept_manager_authorization(
    const ProductPeerGrant &child_grant,
    const ProductPeerGrant &relay_grant) {
  if (role_ != ProductS5Role::RELAY || state_ != ProductS5PeerState::RELAY_WAIT_MANAGER ||
      !grant_matches_pending_(child_grant, ProductPeerRole::CHILD) ||
      !grant_matches_pending_(relay_grant, ProductPeerRole::RELAY) ||
      child_grant.authorization_id != relay_grant.authorization_id ||
      child_grant.issued_at_ms != relay_grant.issued_at_ms ||
      child_grant.expires_at_ms != relay_grant.expires_at_ms ||
      child_grant.authorization_epoch != relay_grant.authorization_epoch) {
    return ProductS5CoordinatorError::STATE_REJECTED;
  }
  const uint64_t now_ms = clock_->now_ms();
  if (!ProductPeerSecurity::verify_endpoint_grant(relay_grant, relay_auth_key_, now_ms)) {
    return ProductS5CoordinatorError::CRYPTO_FAILED;
  }
  return install_relay_peer_and_forward_child_grant_(child_grant, relay_grant, now_ms);
}

ProductS5CoordinatorError ProductS5PeerCoordinator::install_relay_peer_and_forward_child_grant_(
    const ProductPeerGrant &child_grant,
    const ProductPeerGrant &relay_grant,
    uint64_t now_ms) {
  if (!pending_request_.has_value() || !relay_pending_child_mac_.has_value() || radio_ == nullptr ||
      now_ms < relay_grant.issued_at_ms || now_ms >= relay_grant.expires_at_ms) {
    return ProductS5CoordinatorError::STATE_REJECTED;
  }
  LinkKey lmk{};
  if (!ProductPeerSecurity::derive_pair_lmk(
          local_ephemeral_private_, pending_request_->child.ephemeral_public_key, relay_grant, &lmk)) {
    return ProductS5CoordinatorError::CRYPTO_FAILED;
  }
  const MacAddress child_mac = *relay_pending_child_mac_;
  if (radio_->add_encrypted_peer(child_mac, lmk, pending_channel_) != DriverError::NONE) {
    zeroize_(lmk.data(), lmk.size());
    return ProductS5CoordinatorError::RADIO_FAILED;
  }
  zeroize_(lmk.data(), lmk.size());

  ProductChildGrantPacket compact;
  compact.session_token = session_token_;
  compact.target_child_mac = child_mac;
  if (!parse_authorization_uuid(child_grant.authorization_id, &compact.authorization_uuid)) {
    (void) radio_->remove_peer(child_mac);
    return ProductS5CoordinatorError::PACKET_REJECTED;
  }
  compact.issued_at_ms = child_grant.issued_at_ms;
  compact.expires_at_ms = child_grant.expires_at_ms;
  compact.authorization_epoch = child_grant.authorization_epoch;
  compact.child_grant_mac = child_grant.grant_mac;
  std::vector<uint8_t> encoded;
  if (!encode_child_grant_packet(compact, &encoded) ||
      send_broadcast_(pending_channel_, encoded) != ProductS5CoordinatorError::NONE) {
    (void) radio_->remove_peer(child_mac);
    return ProductS5CoordinatorError::RADIO_FAILED;
  }

  relay_active_child_mac_ = child_mac;
  relay_pending_child_mac_.reset();
  active_expires_at_ms_ = relay_grant.expires_at_ms;
  deadline_ms_ = 0;
  state_ = ProductS5PeerState::RELAY_ACTIVE;
  clear_ephemeral_();
  pending_request_.reset();
  session_token_ = 0;
  return ProductS5CoordinatorError::NONE;
}

RelayCandidateEligibility ProductS5PeerCoordinator::eligibility_from_grant_(
    const ProductPeerGrant &grant) const {
  RelayCandidateEligibility eligibility;
  eligibility.manager_verified = true;
  eligibility.registered = true;
  eligibility.same_system = true;
  eligibility.wifi_up = true;
  eligibility.uplink_available = true;
  eligibility.direct_uplink = true;
  eligibility.relay_capable = pending_request_.has_value() && pending_request_->relay_health.relay_capable;
  eligibility.low_battery = !pending_request_.has_value() || pending_request_->relay_health.low_battery;
  eligibility.overloaded = !pending_request_.has_value() || pending_request_->relay_health.overloaded;
  eligibility.retired = false;
  eligibility.revoked = false;
  eligibility.uplink_quality_pct = 100;
  eligibility.load_pct = eligibility.overloaded ? 100 : 0;
  eligibility.battery_pct = eligibility.low_battery ? 1 : 100;
  eligibility.credential_generation = grant.relay_credential_generation;
  eligibility.verified_at_ms = grant.issued_at_ms;
  eligibility.valid_until_ms = grant.expires_at_ms;
  return eligibility;
}

RuntimePeerMaterial ProductS5PeerCoordinator::runtime_material_from_grant_(
    const ProductPeerGrant &grant,
    const LinkKey &lmk) const {
  RuntimePeerMaterial material;
  if (!child_candidate_.has_value()) return material;
  material.authorization.authorization_id = grant.authorization_id;
  material.authorization.gateway_id = grant.relay_node_id;
  material.authorization.peer_mac = child_candidate_->source_mac;
  material.authorization.channel = child_candidate_->channel;
  material.authorization.relay_credential_generation = grant.relay_credential_generation;
  material.authorization.issued_at_ms = grant.issued_at_ms;
  material.authorization.expires_at_ms = grant.expires_at_ms;
  material.authorization.manager_authorized = true;
  material.authorization.same_system = true;
  material.lmk = lmk;
  return material;
}

ProductS5CoordinatorError ProductS5PeerCoordinator::install_child_runtime_peer_(
    const ProductPeerGrant &child_grant,
    uint64_t now_ms) {
  if (role_ != ProductS5Role::CHILD || !pending_request_.has_value() ||
      !child_candidate_.has_value() || runtime_ == nullptr ||
      now_ms < child_grant.issued_at_ms || now_ms >= child_grant.expires_at_ms) {
    return ProductS5CoordinatorError::STATE_REJECTED;
  }
  LinkKey lmk{};
  if (!ProductPeerSecurity::derive_pair_lmk(
          local_ephemeral_private_, pending_request_->relay.ephemeral_public_key, child_grant, &lmk)) {
    return ProductS5CoordinatorError::CRYPTO_FAILED;
  }
  cached_runtime_material_ = runtime_material_from_grant_(child_grant, lmk);
  zeroize_(lmk.data(), lmk.size());
  const RelayCandidateEligibility eligibility = eligibility_from_grant_(child_grant);
  if (!eligibility.valid_shape() || !eligibility.eligible_at(now_ms)) {
    clear_cached_runtime_material_();
    return ProductS5CoordinatorError::STATE_REJECTED;
  }
  state_ = ProductS5PeerState::CHILD_WAIT_RUNTIME_INSTALL;
  active_expires_at_ms_ = child_grant.expires_at_ms;
  const ProductRuntimeError result = runtime_->apply_manager_eligibility(
      child_candidate_->source_mac, child_candidate_->gateway_id, eligibility);
  if (result != ProductRuntimeError::NONE || state_ != ProductS5PeerState::CHILD_ACTIVE) {
    (void) runtime_->reject_peer_authorization();
    clear_pending_(false);
    return ProductS5CoordinatorError::RUNTIME_FAILED;
  }
  return ProductS5CoordinatorError::NONE;
}

ProductS5CoordinatorError ProductS5PeerCoordinator::accept_child_grant_(
    const MacAddress &source,
    const ProductChildGrantPacket &packet,
    const EspNowReceiveMetadata &metadata) {
  if (role_ != ProductS5Role::CHILD || state_ != ProductS5PeerState::CHILD_WAIT_GRANT ||
      !pending_request_.has_value() || !child_candidate_.has_value() ||
      packet.session_token != session_token_ || !same_mac_(source, child_candidate_->source_mac) ||
      !same_mac_(packet.target_child_mac, local_mac_) || metadata.channel != pending_channel_ ||
      !packet.valid()) {
    return ProductS5CoordinatorError::STATE_REJECTED;
  }

  ProductPeerGrant grant;
  grant.role = ProductPeerRole::CHILD;
  grant.authorization_id = packet.authorization_id();
  grant.system_id = pending_request_->system_id;
  grant.session_id = pending_request_->session_id;
  grant.child_node_id = pending_request_->child.node_id;
  grant.relay_node_id = pending_request_->relay.node_id;
  grant.child_credential_generation = pending_request_->child.credential_generation;
  grant.relay_credential_generation = pending_request_->relay.credential_generation;
  grant.child_key_epoch = pending_request_->child.key_epoch;
  grant.relay_key_epoch = pending_request_->relay.key_epoch;
  grant.child_ephemeral_public_key = pending_request_->child.ephemeral_public_key;
  grant.relay_ephemeral_public_key = pending_request_->relay.ephemeral_public_key;
  grant.child_nonce = pending_request_->child.nonce;
  grant.relay_nonce = pending_request_->relay.nonce;
  grant.issued_at_ms = packet.issued_at_ms;
  grant.expires_at_ms = packet.expires_at_ms;
  grant.authorization_epoch = packet.authorization_epoch;
  grant.grant_mac = packet.child_grant_mac;
  const uint64_t now_ms = clock_->now_ms();
  if (!grant_matches_pending_(grant, ProductPeerRole::CHILD) ||
      !ProductPeerSecurity::verify_endpoint_grant(grant, relay_auth_key_, now_ms)) {
    return ProductS5CoordinatorError::CRYPTO_FAILED;
  }
  return install_child_runtime_peer_(grant, now_ms);
}

void ProductS5PeerCoordinator::on_authorization_needed(
    const RelayCandidateRecord &candidate) {
  if (role_ != ProductS5Role::CHILD || state_ != ProductS5PeerState::CHILD_WAIT_RUNTIME_INSTALL ||
      !cached_runtime_material_.has_value() || !child_candidate_.has_value() || runtime_ == nullptr ||
      candidate.observation.gateway_id != child_candidate_->gateway_id ||
      !same_mac_(candidate.observation.source_mac, child_candidate_->source_mac)) {
    if (role_ == ProductS5Role::CHILD && runtime_ != nullptr &&
        runtime_->path_state() == AutoPathState::RELAY_AUTH) {
      (void) runtime_->reject_peer_authorization();
    }
    return;
  }
  const ProductRuntimeError result = runtime_->install_authorized_peer(*cached_runtime_material_);
  if (result != ProductRuntimeError::NONE) {
    clear_pending_(false);
    return;
  }
  state_ = ProductS5PeerState::CHILD_ACTIVE;
  deadline_ms_ = 0;
  clear_cached_runtime_material_();
  clear_ephemeral_();
  pending_request_.reset();
  child_candidate_.reset();
  session_token_ = 0;
}

void ProductS5PeerCoordinator::on_peer_active(
    const DynamicPeerAuthorization &authorization) {
  if (role_ == ProductS5Role::CHILD && state_ == ProductS5PeerState::CHILD_WAIT_RUNTIME_INSTALL &&
      authorization.manager_authorized && authorization.same_system) {
    state_ = ProductS5PeerState::CHILD_ACTIVE;
  }
}

void ProductS5PeerCoordinator::on_peer_released(const MacAddress &peer_mac) {
  (void) peer_mac;
  if (role_ == ProductS5Role::CHILD && state_ == ProductS5PeerState::CHILD_ACTIVE) {
    clear_pending_(false);
  }
}

void ProductS5PeerCoordinator::on_s5_datagram(
    const MacAddress &source,
    const uint8_t *data,
    std::size_t size,
    const EspNowReceiveMetadata &metadata) {
  if (data == nullptr || size < 4 || size > greenhouse_n3w_core::kEspNowDatagramLimit ||
      data[0] != 'G' || data[1] != 'P' || data[2] != kProductPeerHandshakeWireVersion) {
    return;
  }
  const auto type = static_cast<ProductPeerHandshakeType>(data[3]);
  if (role_ == ProductS5Role::CHILD) {
    if (type == ProductPeerHandshakeType::RELAY_CHALLENGE) {
      ProductRelayChallenge challenge;
      if (decode_relay_challenge(data, size, &challenge))
        (void) accept_relay_challenge_(source, challenge, metadata);
      return;
    }
    if (type == ProductPeerHandshakeType::CHILD_GRANT) {
      ProductChildGrantPacket grant;
      if (decode_child_grant_packet(data, size, &grant))
        (void) accept_child_grant_(source, grant, metadata);
      return;
    }
    return;
  }

  if (type == ProductPeerHandshakeType::CHILD_AUTH_INIT) {
    ProductChildAuthInit init;
    if (decode_child_auth_init(data, size, &init))
      (void) accept_child_auth_init_(source, init, metadata);
    return;
  }
  if (type == ProductPeerHandshakeType::CHILD_PROOF) {
    ProductChildProofPacket proof;
    if (decode_child_proof_packet(data, size, &proof))
      (void) accept_child_proof_(source, proof, metadata);
  }
}

}  // namespace esphome::greenhouse_n3w_product_runtime
