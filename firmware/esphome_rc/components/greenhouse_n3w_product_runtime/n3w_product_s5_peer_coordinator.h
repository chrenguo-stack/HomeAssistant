#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>

#include "n3w_product_peer_handshake_wire.h"
#include "n3w_product_peer_security.h"
#include "n3w_product_runtime.h"
#include "n3w_product_s5_radio_mux.h"

namespace esphome::greenhouse_n3w_product_runtime {

enum class ProductS5Role : uint8_t {
  CHILD = 0,
  RELAY = 1,
};

enum class ProductS5PeerState : uint8_t {
  IDLE = 0,
  CHILD_WAIT_CHALLENGE,
  CHILD_WAIT_GRANT,
  CHILD_WAIT_RUNTIME_INSTALL,
  CHILD_ACTIVE,
  RELAY_WAIT_CHILD_PROOF,
  RELAY_WAIT_MANAGER,
  RELAY_ACTIVE,
};

enum class ProductS5CoordinatorError : uint8_t {
  NONE = 0,
  INVALID_ARGUMENT,
  NOT_READY,
  STATE_REJECTED,
  RANDOM_FAILED,
  CRYPTO_FAILED,
  RADIO_FAILED,
  MANAGER_FAILED,
  RUNTIME_FAILED,
  PACKET_REJECTED,
  EXPIRED,
};

struct ProductS5NodeCredentials {
  std::string system_id;
  std::string node_id;
  uint32_t credential_generation{0};
  uint32_t key_epoch{0};
  ProductPeerKey application_key{};

  bool valid() const;
};

struct ProductS5CoordinatorPolicy {
  uint32_t peer_handshake_timeout_ms{10000};
  uint32_t manager_timeout_ms{10000};

  bool valid() const {
    return peer_handshake_timeout_ms >= 1000 && peer_handshake_timeout_ms <= 60000 &&
           manager_timeout_ms >= 1000 && manager_timeout_ms <= 60000;
  }
};

class ProductS5RandomSource {
 public:
  virtual ~ProductS5RandomSource() = default;
  virtual bool fill32(ProductPeerKey *value) = 0;
  virtual uint64_t session_token() = 0;
};

class ProductS5CryptoRandomSource final : public ProductS5RandomSource {
 public:
  bool fill32(ProductPeerKey *value) override;
  uint64_t session_token() override;
};

class ProductS5RelayHealthProvider {
 public:
  virtual ~ProductS5RelayHealthProvider() = default;
  virtual bool read_health(uint64_t now_ms, ProductRelayHealth *health) = 0;
};

class ProductS5ManagerPort {
 public:
  virtual ~ProductS5ManagerPort() = default;
  virtual bool submit_peer_authorization(const ProductPeerRequest &request) = 0;
};

class ProductS5PeerCoordinator final : public ProductRuntimeEventSink,
                                       public ProductS5DatagramSink {
 public:
  ProductS5PeerCoordinator(
      ProductS5Role role,
      const MacAddress &local_mac,
      ProductS5NodeCredentials credentials,
      ProductRuntimeClock *clock,
      ProductS5RandomSource *random,
      ProductS5RelayHealthProvider *relay_health,
      ProductS5ManagerPort *manager,
      ProductS5CoordinatorPolicy policy = {});
  ~ProductS5PeerCoordinator() override;

  ProductS5CoordinatorError attach(
      ProductEspNowRuntime *runtime,
      ProductRuntimeRadioPort *radio);
  ProductS5CoordinatorError tick();
  ProductS5CoordinatorError accept_manager_authorization(
      const ProductPeerGrant &child_grant,
      const ProductPeerGrant &relay_grant);
  void reset();

  ProductS5Role role() const { return role_; }
  ProductS5PeerState state() const { return state_; }
  bool provisional_channel_locked() const;
  bool has_pending_request() const { return pending_request_.has_value(); }
  const std::optional<ProductPeerRequest> &pending_request() const {
    return pending_request_;
  }
  const std::optional<MacAddress> &active_relay_child_mac() const {
    return relay_active_child_mac_;
  }

  void on_candidate_observed(const RelayCandidateObservation &observation) override;
  void on_authorization_needed(const RelayCandidateRecord &candidate) override;
  void on_peer_active(const DynamicPeerAuthorization &authorization) override;
  void on_peer_released(const MacAddress &peer_mac) override;
  void on_s5_datagram(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size,
      const EspNowReceiveMetadata &metadata) override;

 private:
  ProductS5CoordinatorError start_child_provisional_(
      const RelayCandidateObservation &observation);
  ProductS5CoordinatorError accept_relay_challenge_(
      const MacAddress &source,
      const ProductRelayChallenge &challenge,
      const EspNowReceiveMetadata &metadata);
  ProductS5CoordinatorError accept_child_grant_(
      const MacAddress &source,
      const ProductChildGrantPacket &packet,
      const EspNowReceiveMetadata &metadata);
  ProductS5CoordinatorError accept_child_auth_init_(
      const MacAddress &source,
      const ProductChildAuthInit &init,
      const EspNowReceiveMetadata &metadata);
  ProductS5CoordinatorError accept_child_proof_(
      const MacAddress &source,
      const ProductChildProofPacket &packet,
      const EspNowReceiveMetadata &metadata);
  ProductS5CoordinatorError install_relay_peer_and_forward_child_grant_(
      const ProductPeerGrant &child_grant,
      const ProductPeerGrant &relay_grant,
      uint64_t now_ms);
  ProductS5CoordinatorError install_child_runtime_peer_(
      const ProductPeerGrant &child_grant,
      uint64_t now_ms);

  bool grant_matches_pending_(
      const ProductPeerGrant &grant,
      ProductPeerRole expected_role) const;
  RelayCandidateEligibility eligibility_from_grant_(
      const ProductPeerGrant &grant) const;
  RuntimePeerMaterial runtime_material_from_grant_(
      const ProductPeerGrant &grant,
      const LinkKey &lmk) const;
  ProductS5CoordinatorError send_broadcast_(
      uint8_t channel,
      const std::vector<uint8_t> &packet);
  void clear_ephemeral_();
  void clear_pending_(bool remove_relay_peer);
  void expire_pending_(uint64_t now_ms);
  static bool valid_unicast_mac_(const MacAddress &mac);
  static bool same_mac_(const MacAddress &left, const MacAddress &right);
  static void zeroize_(void *data, std::size_t length);

  ProductS5Role role_{ProductS5Role::CHILD};
  MacAddress local_mac_{};
  ProductS5NodeCredentials credentials_{};
  ProductPeerKey relay_auth_key_{};
  ProductRuntimeClock *clock_{nullptr};
  ProductS5RandomSource *random_{nullptr};
  ProductS5RelayHealthProvider *relay_health_{nullptr};
  ProductS5ManagerPort *manager_{nullptr};
  ProductS5CoordinatorPolicy policy_{};
  ProductEspNowRuntime *runtime_{nullptr};
  ProductRuntimeRadioPort *radio_{nullptr};

  ProductS5PeerState state_{ProductS5PeerState::IDLE};
  uint64_t deadline_ms_{0};
  uint64_t active_expires_at_ms_{0};
  uint64_t session_token_{0};
  ProductPeerKey local_ephemeral_private_{};
  std::optional<RelayCandidateObservation> child_candidate_{};
  std::optional<MacAddress> relay_pending_child_mac_{};
  std::optional<MacAddress> relay_active_child_mac_{};
  uint8_t pending_channel_{0};
  std::optional<ProductPeerRequest> pending_request_{};
  std::optional<RuntimePeerMaterial> cached_runtime_material_{};
};

}  // namespace esphome::greenhouse_n3w_product_runtime
