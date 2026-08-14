#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "mbedtls/md.h"
#include "esphome/components/greenhouse_n3w_product_runtime/n3w_product_s5_peer_coordinator.h"

using namespace esphome::greenhouse_n3w_core;
using namespace esphome::greenhouse_n3w_product_core;
using namespace esphome::greenhouse_n3w_product_runtime;

namespace {

constexpr const char *kAuthorizationId = "11111111-2222-3333-4444-555555555555";

class FakeClock final : public ProductRuntimeClock {
 public:
  uint64_t now_ms() const override { return now; }
  uint64_t now{1786689000000ULL};
};

class DeterministicRandom final : public ProductS5RandomSource {
 public:
  DeterministicRandom(uint64_t token, uint8_t seed) : token_(token), seed_(seed) {}

  bool fill32(ProductPeerKey *value) override {
    if (value == nullptr) return false;
    const uint8_t start = static_cast<uint8_t>(seed_ + calls_ * 0x20U);
    ++calls_;
    for (std::size_t index = 0; index < value->size(); ++index)
      (*value)[index] = static_cast<uint8_t>(start + index);
    return true;
  }

  uint64_t session_token() override { return token_ + token_calls_++; }

 private:
  uint64_t token_{0};
  uint8_t seed_{0};
  uint32_t calls_{0};
  uint64_t token_calls_{0};
};

class FakeHealth final : public ProductS5RelayHealthProvider {
 public:
  bool read_health(uint64_t now_ms, ProductRelayHealth *health) override {
    if (health == nullptr) return false;
    health->observed_at_ms = now_ms;
    health->relay_capable = true;
    health->low_battery = false;
    health->overloaded = false;
    return true;
  }
};

class NetworkRadio final : public ProductRuntimeRadioPort {
 public:
  explicit NetworkRadio(MacAddress mac) : mac_(mac) {}

  void connect(NetworkRadio *peer) { peer_ = peer; }

  DriverError initialize(EspNowEventSink *sink, const LinkKey &) override {
    sink_ = sink;
    initialized = true;
    return DriverError::NONE;
  }
  void shutdown() override { initialized = false; }
  DriverError set_channel(uint8_t channel) override {
    channel_ = channel;
    return DriverError::NONE;
  }
  DriverError prepare_broadcast_peer(uint8_t channel) override {
    channel_ = channel;
    return DriverError::NONE;
  }
  DriverError add_encrypted_peer(
      const MacAddress &peer_mac,
      const LinkKey &lmk,
      uint8_t channel) override {
    ++add_peer_count;
    peer_mac_ = peer_mac;
    lmk_ = lmk;
    channel_ = channel;
    encrypted_peer = true;
    return DriverError::NONE;
  }
  DriverError remove_peer(const MacAddress &peer_mac) override {
    if (encrypted_peer && peer_mac == peer_mac_) {
      encrypted_peer = false;
      ++remove_peer_count;
      lmk_.fill(0);
    }
    return DriverError::NONE;
  }
  DriverError send_peer(
      const MacAddress &peer_mac,
      const uint8_t *data,
      std::size_t size) override {
    if (!encrypted_peer || peer_mac != peer_mac_ || data == nullptr || size == 0)
      return DriverError::SEND_FAILED;
    return deliver_(data, size);
  }
  DriverError send_broadcast(const uint8_t *data, std::size_t size) override {
    if (data == nullptr || size == 0) return DriverError::SEND_FAILED;
    return deliver_(data, size);
  }

  DriverError deliver_(const uint8_t *data, std::size_t size) {
    if (peer_ == nullptr || peer_->sink_ == nullptr || peer_->channel_ != channel_)
      return DriverError::SEND_FAILED;
    EspNowReceiveMetadata metadata;
    metadata.channel = channel_;
    metadata.rssi_dbm = -48;
    peer_->sink_->on_espnow_receive_with_metadata(mac_, data, size, metadata);
    return DriverError::NONE;
  }

  MacAddress mac_{};
  NetworkRadio *peer_{nullptr};
  EspNowEventSink *sink_{nullptr};
  uint8_t channel_{0};
  bool initialized{false};
  bool encrypted_peer{false};
  int add_peer_count{0};
  int remove_peer_count{0};
  MacAddress peer_mac_{};
  LinkKey lmk_{};
};

ProductPeerProof grant_mac(
    const ProductPeerGrant &grant,
    const ProductPeerKey &relay_auth_key) {
  std::string binding;
  assert(ProductPeerSecurity::grant_binding(grant, &binding));
  std::string message("gh.n3w-product/peer-grant/1");
  message.push_back('\0');
  message.append(grant.role == ProductPeerRole::CHILD ? "child" : "relay");
  message.push_back('\0');
  message.append(binding);
  ProductPeerProof result{};
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  assert(info != nullptr);
  assert(mbedtls_md_hmac(
             info,
             relay_auth_key.data(),
             relay_auth_key.size(),
             reinterpret_cast<const unsigned char *>(message.data()),
             message.size(),
             result.data()) == 0);
  return result;
}

class FakeManager final : public ProductS5ManagerPort {
 public:
  FakeManager(
      FakeClock *clock,
      ProductS5NodeCredentials child,
      ProductS5NodeCredentials relay)
      : clock_(clock), child_(std::move(child)), relay_(std::move(relay)) {}

  bool submit_peer_authorization(const ProductPeerRequest &request) override {
    assert(request.valid_shape(true));
    request_ = request;
    submitted = true;
    return true;
  }

  void attach(ProductS5PeerCoordinator *relay_coordinator) {
    relay_coordinator_ = relay_coordinator;
  }

  std::pair<ProductPeerGrant, ProductPeerGrant> grants() const {
    assert(submitted && request_.has_value());
    ProductPeerGrant child_grant = base_grant_(ProductPeerRole::CHILD);
    ProductPeerGrant relay_grant = base_grant_(ProductPeerRole::RELAY);
    ProductPeerKey child_auth{};
    ProductPeerKey relay_auth{};
    assert(ProductPeerSecurity::derive_relay_auth_key(
        child_.application_key,
        child_.system_id,
        child_.node_id,
        child_.credential_generation,
        child_.key_epoch,
        &child_auth));
    assert(ProductPeerSecurity::derive_relay_auth_key(
        relay_.application_key,
        relay_.system_id,
        relay_.node_id,
        relay_.credential_generation,
        relay_.key_epoch,
        &relay_auth));
    child_grant.grant_mac = grant_mac(child_grant, child_auth);
    relay_grant.grant_mac = grant_mac(relay_grant, relay_auth);
    return {child_grant, relay_grant};
  }

  void deliver() {
    assert(relay_coordinator_ != nullptr);
    auto pair = grants();
    assert(relay_coordinator_->accept_manager_authorization(pair.first, pair.second) ==
           ProductS5CoordinatorError::NONE);
  }

  ProductPeerGrant base_grant_(ProductPeerRole role) const {
    const ProductPeerRequest &request = *request_;
    ProductPeerGrant grant;
    grant.role = role;
    grant.authorization_id = kAuthorizationId;
    grant.system_id = request.system_id;
    grant.session_id = request.session_id;
    grant.child_node_id = request.child.node_id;
    grant.relay_node_id = request.relay.node_id;
    grant.child_credential_generation = request.child.credential_generation;
    grant.relay_credential_generation = request.relay.credential_generation;
    grant.child_key_epoch = request.child.key_epoch;
    grant.relay_key_epoch = request.relay.key_epoch;
    grant.child_ephemeral_public_key = request.child.ephemeral_public_key;
    grant.relay_ephemeral_public_key = request.relay.ephemeral_public_key;
    grant.child_nonce = request.child.nonce;
    grant.relay_nonce = request.relay.nonce;
    grant.issued_at_ms = clock_->now;
    grant.expires_at_ms = clock_->now + 30000;
    grant.authorization_epoch = 1;
    return grant;
  }

  FakeClock *clock_{nullptr};
  ProductS5NodeCredentials child_{};
  ProductS5NodeCredentials relay_{};
  ProductS5PeerCoordinator *relay_coordinator_{nullptr};
  std::optional<ProductPeerRequest> request_{};
  bool submitted{false};
};

ProductS5NodeCredentials credentials(
    const std::string &node_id,
    uint32_t generation,
    uint32_t epoch,
    uint8_t seed) {
  ProductS5NodeCredentials result;
  result.system_id = "system001";
  result.node_id = node_id;
  result.credential_generation = generation;
  result.key_epoch = epoch;
  for (std::size_t index = 0; index < result.application_key.size(); ++index)
    result.application_key[index] = static_cast<uint8_t>(seed + index);
  assert(result.valid());
  return result;
}

LinkKey pmk(uint8_t seed) {
  LinkKey result{};
  for (std::size_t index = 0; index < result.size(); ++index)
    result[index] = static_cast<uint8_t>(seed + index);
  return result;
}

ProductEspNowRuntime make_runtime(
    ProductRuntimeRadioPort *radio,
    ProductRuntimeClock *clock,
    ProductRuntimeEventSink *events) {
  return ProductEspNowRuntime(
      radio,
      clock,
      events,
      WifiDirectHealthPolicy{1, 3, 3},
      RelayCandidatePolicy{8, 15000, -92, 12, 30000},
      AutoPathPolicy{2},
      ProductRuntimePolicy{{1, 6, 11}, 250, 10, 1000});
}

void enter_discovery(ProductEspNowRuntime *runtime) {
  assert(runtime->note_direct_result(false) == ProductRuntimeError::NONE);
  assert(runtime->note_direct_result(false) == ProductRuntimeError::NONE);
  assert(runtime->note_direct_result(false) == ProductRuntimeError::NONE);
  assert(runtime->path_state() == AutoPathState::DISCOVERY);
  assert(runtime->scan_active());
}

struct Fixture {
  FakeClock clock{};
  MacAddress child_mac{0x02, 0x11, 0x22, 0x33, 0x44, 0x55};
  MacAddress relay_mac{0x02, 0xaa, 0xbb, 0xcc, 0xdd, 0xee};
  ProductS5NodeCredentials child_credentials{credentials("node_child01", 7, 9, 0x81)};
  ProductS5NodeCredentials relay_credentials{credentials("node_relay01", 11, 13, 0xa1)};
  DeterministicRandom child_random{0x0123456789abcdefULL, 0x01};
  DeterministicRandom relay_random{0, 0x11};
  FakeHealth relay_health{};
  FakeManager manager{&clock, child_credentials, relay_credentials};
  ProductS5PeerCoordinator child_coordinator{
      ProductS5Role::CHILD,
      child_mac,
      child_credentials,
      &clock,
      &child_random,
      nullptr,
      nullptr};
  ProductS5PeerCoordinator relay_coordinator{
      ProductS5Role::RELAY,
      relay_mac,
      relay_credentials,
      &clock,
      &relay_random,
      &relay_health,
      &manager};
  NetworkRadio child_inner{child_mac};
  NetworkRadio relay_inner{relay_mac};
  ProductS5RadioMux child_mux{&child_inner, &child_coordinator};
  ProductS5RadioMux relay_mux{&relay_inner, &relay_coordinator};
  ProductEspNowRuntime child_runtime{make_runtime(&child_mux, &clock, &child_coordinator)};
  ProductEspNowRuntime relay_runtime{make_runtime(&relay_mux, &clock, &relay_coordinator)};

  Fixture() {
    manager.attach(&relay_coordinator);
    child_inner.connect(&relay_inner);
    relay_inner.connect(&child_inner);
    assert(child_coordinator.attach(&child_runtime, &child_mux) == ProductS5CoordinatorError::NONE);
    assert(relay_coordinator.attach(&relay_runtime, &relay_mux) == ProductS5CoordinatorError::NONE);
    assert(child_runtime.start(pmk(0x10)) == ProductRuntimeError::NONE);
    assert(relay_runtime.start(pmk(0x30)) == ProductRuntimeError::NONE);
    assert(child_runtime.set_last_direct_channel(6) == ProductRuntimeError::NONE);
    assert(relay_runtime.set_last_direct_channel(6) == ProductRuntimeError::NONE);
    enter_discovery(&child_runtime);
    LocalRelayAdvertisement advertisement;
    advertisement.enabled = true;
    advertisement.gateway_id = relay_credentials.node_id;
    advertisement.channel = 6;
    advertisement.advertisement_generation = 1;
    assert(relay_runtime.set_local_relay_advertisement(advertisement) == ProductRuntimeError::NONE);
  }

  ~Fixture() {
    relay_coordinator.reset();
    child_runtime.stop();
    relay_runtime.stop();
    child_coordinator.reset();
  }

  void begin_pairing() {
    assert(relay_coordinator.tick() == ProductS5CoordinatorError::NONE);
    assert(manager.submitted);
    assert(child_coordinator.state() == ProductS5PeerState::CHILD_WAIT_GRANT);
    assert(relay_coordinator.state() == ProductS5PeerState::RELAY_WAIT_MANAGER);
  }

  void assert_pair_active() {
    assert(relay_coordinator.state() == ProductS5PeerState::RELAY_ACTIVE);
    assert(child_coordinator.state() == ProductS5PeerState::CHILD_ACTIVE);
    assert(child_runtime.path_state() == AutoPathState::RELAY_ACTIVE);
    assert(child_runtime.relay_telemetry_ready());
    assert(child_inner.encrypted_peer);
    assert(relay_inner.encrypted_peer);
    assert(child_inner.peer_mac_ == relay_mac);
    assert(relay_inner.peer_mac_ == child_mac);
    assert(child_inner.lmk_ == relay_inner.lmk_);
    LinkKey zero{};
    assert(child_inner.lmk_ != zero);
    assert(child_coordinator.active_authorization_id() == kAuthorizationId);
    assert(relay_coordinator.active_authorization_id() == kAuthorizationId);
    assert(!child_coordinator.ephemeral_private_resident());
    assert(!relay_coordinator.ephemeral_private_resident());
    assert(!child_coordinator.cached_runtime_lmk_resident());
    assert(!relay_coordinator.cached_runtime_lmk_resident());
  }
};

void grant_binding_duplicate_and_revoke_matrix() {
  Fixture fixture;
  fixture.begin_pairing();
  assert(fixture.child_coordinator.ephemeral_private_resident());
  assert(fixture.relay_coordinator.ephemeral_private_resident());
  assert(fixture.child_inner.add_peer_count == 0);
  assert(fixture.relay_inner.add_peer_count == 0);

  auto tampered = fixture.manager.grants();
  ++tampered.first.relay_credential_generation;
  assert(fixture.relay_coordinator.accept_manager_authorization(tampered.first, tampered.second) ==
         ProductS5CoordinatorError::STATE_REJECTED);
  assert(!fixture.child_inner.encrypted_peer);
  assert(!fixture.relay_inner.encrypted_peer);

  fixture.manager.deliver();
  fixture.assert_pair_active();
  const int child_adds = fixture.child_inner.add_peer_count;
  const int relay_adds = fixture.relay_inner.add_peer_count;
  auto duplicate = fixture.manager.grants();
  assert(fixture.relay_coordinator.accept_manager_authorization(duplicate.first, duplicate.second) ==
         ProductS5CoordinatorError::STATE_REJECTED);
  assert(fixture.child_inner.add_peer_count == child_adds);
  assert(fixture.relay_inner.add_peer_count == relay_adds);

  const std::string wrong_authorization = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
  assert(fixture.relay_coordinator.revoke_active_authorization(wrong_authorization) ==
         ProductS5CoordinatorError::STATE_REJECTED);
  assert(fixture.child_coordinator.revoke_active_authorization(wrong_authorization) ==
         ProductS5CoordinatorError::STATE_REJECTED);
  assert(fixture.child_inner.encrypted_peer);
  assert(fixture.relay_inner.encrypted_peer);

  assert(fixture.relay_coordinator.revoke_active_authorization(kAuthorizationId) ==
         ProductS5CoordinatorError::NONE);
  assert(fixture.child_coordinator.revoke_active_authorization(kAuthorizationId) ==
         ProductS5CoordinatorError::NONE);
  assert(!fixture.child_inner.encrypted_peer);
  assert(!fixture.relay_inner.encrypted_peer);
  assert(fixture.child_coordinator.state() == ProductS5PeerState::IDLE);
  assert(fixture.relay_coordinator.state() == ProductS5PeerState::IDLE);
  assert(fixture.child_runtime.path_state() == AutoPathState::REDISCOVERY ||
         fixture.child_runtime.path_state() == AutoPathState::DISCOVERY);
  assert(fixture.child_runtime.scan_active());
  assert(fixture.child_coordinator.active_authorization_id().empty());
  assert(fixture.relay_coordinator.active_authorization_id().empty());
}

void finite_expiry_matrix() {
  Fixture fixture;
  fixture.begin_pairing();
  fixture.manager.deliver();
  fixture.assert_pair_active();
  fixture.clock.now += 30001;
  assert(fixture.relay_coordinator.tick() == ProductS5CoordinatorError::NONE);
  assert(!fixture.relay_inner.encrypted_peer);
  assert(fixture.relay_coordinator.state() == ProductS5PeerState::IDLE);
  assert(fixture.child_coordinator.tick() == ProductS5CoordinatorError::NONE);
  assert(!fixture.child_inner.encrypted_peer);
  assert(fixture.child_coordinator.state() == ProductS5PeerState::IDLE);
  assert(!fixture.child_coordinator.ephemeral_private_resident());
  assert(!fixture.relay_coordinator.ephemeral_private_resident());
  assert(!fixture.child_coordinator.cached_runtime_lmk_resident());
}

void interrupted_handshake_timeout_matrix() {
  Fixture fixture;
  fixture.begin_pairing();
  assert(fixture.child_coordinator.has_pending_request());
  assert(fixture.relay_coordinator.has_pending_request());
  assert(fixture.child_coordinator.ephemeral_private_resident());
  assert(fixture.relay_coordinator.ephemeral_private_resident());
  fixture.clock.now += 20001;
  assert(fixture.relay_coordinator.tick() == ProductS5CoordinatorError::NONE);
  assert(fixture.child_coordinator.tick() == ProductS5CoordinatorError::NONE);
  assert(fixture.child_coordinator.state() == ProductS5PeerState::IDLE);
  assert(fixture.relay_coordinator.state() == ProductS5PeerState::IDLE);
  assert(!fixture.child_coordinator.has_pending_request());
  assert(!fixture.relay_coordinator.has_pending_request());
  assert(!fixture.child_coordinator.ephemeral_private_resident());
  assert(!fixture.relay_coordinator.ephemeral_private_resident());
  assert(!fixture.child_coordinator.cached_runtime_lmk_resident());
  assert(!fixture.relay_coordinator.cached_runtime_lmk_resident());
  assert(!fixture.child_inner.encrypted_peer);
  assert(!fixture.relay_inner.encrypted_peer);
}

void restart_teardown_matrix() {
  Fixture fixture;
  fixture.begin_pairing();
  fixture.manager.deliver();
  fixture.assert_pair_active();

  // Same ordering as board integration destruction: Relay-owned direct peer
  // is removed before radio shutdown; Child runtime then removes its active
  // dynamic peer. No local peer or LMK survives the restart boundary.
  fixture.relay_coordinator.reset();
  fixture.child_runtime.stop();
  fixture.relay_runtime.stop();
  assert(!fixture.relay_inner.encrypted_peer);
  assert(!fixture.child_inner.encrypted_peer);
  assert(fixture.relay_coordinator.state() == ProductS5PeerState::IDLE);
  assert(fixture.child_coordinator.state() == ProductS5PeerState::IDLE);
  assert(!fixture.child_coordinator.ephemeral_private_resident());
  assert(!fixture.relay_coordinator.ephemeral_private_resident());
}

}  // namespace

int main() {
  grant_binding_duplicate_and_revoke_matrix();
  finite_expiry_matrix();
  interrupted_handshake_timeout_matrix();
  restart_teardown_matrix();
  std::cout << "S5_LIFECYCLE_NEGATIVE_PEER_MATRIX=PASS\n";
  return 0;
}
