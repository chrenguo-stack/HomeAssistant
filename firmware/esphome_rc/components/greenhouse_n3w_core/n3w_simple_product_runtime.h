#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "n3w_compact_telemetry.h"
#include "n3w_esp32_simple_nvs.h"
#include "n3w_radio.h"
#include "n3w_simple_runtime.h"

namespace esphome::greenhouse_n3w_core {

enum class SimpleProductError : uint8_t {
  NONE = 0,
  INVALID_ARGUMENT,
  NOT_READY,
  RADIO_FAILED,
  MQTT_FAILED,
  CRYPTO_FAILED,
  PACKET_REJECTED,
  STATE_REJECTED,
};

struct SimpleProductPolicy {
  LocalPathPolicy path{};
  std::vector<uint8_t> allowed_channels{1, 6, 11};
  uint32_t scan_dwell_ms{250};
  uint32_t challenge_timeout_ms{1500};
  uint32_t relay_advertisement_interval_ms{2000};
  std::size_t max_relay_children{8};

  bool valid() const;
};

class SimpleProductClock {
 public:
  virtual ~SimpleProductClock() = default;
  virtual uint64_t now_ms() const = 0;
};

class SimpleProductRandom {
 public:
  virtual ~SimpleProductRandom() = default;
  virtual bool fill(uint8_t *data, std::size_t size) = 0;
};

class SimpleProductPort {
 public:
  virtual ~SimpleProductPort() = default;
  virtual bool set_radio_channel(uint8_t channel) = 0;
  virtual bool broadcast_control(const uint8_t *data, std::size_t size) = 0;
  virtual bool install_encrypted_peer(
      const MacAddress &peer_mac,
      const LinkKey &lmk,
      uint8_t channel) = 0;
  virtual bool remove_peer(const MacAddress &peer_mac) = 0;
  virtual bool send_encrypted_peer(
      const MacAddress &peer_mac,
      const uint8_t *data,
      std::size_t size) = 0;
  virtual bool publish_direct(const std::string &topic, const std::string &payload) = 0;
  virtual bool publish_relay(const std::string &topic, const std::string &payload) = 0;
};

struct SimpleProductRelayPeer {
  std::string node_id;
  MacAddress mac{};
  LinkKey lmk{};
  uint8_t channel{0};

  bool valid() const;
};

class SimpleProductRuntime {
 public:
  SimpleProductRuntime(
      SimpleProductPort *port,
      SimpleProductClock *clock,
      SimpleProductRandom *random,
      SimpleProductPolicy policy = {});

  SimpleProductError start(
      const ProvisionedPeerStateV2 &state,
      const MacAddress &local_mac,
      uint8_t direct_channel);
  void stop();
  SimpleProductError tick();

  SimpleProductError note_direct_result(bool success);
  SimpleProductError note_direct_recovery_probe(bool success);
  bool update_direct_channel_hint(uint8_t channel);
  SimpleProductError send_telemetry(
      const std::string &telemetry_json,
      const std::string &boot_id,
      uint32_t seq);

  SimpleProductError on_radio_receive(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size,
      uint8_t channel);

  void set_relay_capable(bool value) { relay_capable_ = value; }
  bool started() const { return started_; }
  LocalPathState path_state() const { return path_.state(); }
  uint8_t direct_channel_hint() const { return direct_channel_; }
  const std::optional<SimpleProductRelayPeer> &active_relay() const {
    return active_relay_;
  }
  std::size_t relay_child_count() const { return relay_children_.size(); }
  const ProvisionedPeerStateV2 &provisioned_state() const { return state_; }

 private:
  friend struct SimpleProductRelayPeer;

  struct PendingChallenge {
    std::string relay_node_id;
    MacAddress relay_mac{};
    HandshakeNonce challenge_nonce{};
    uint8_t channel{0};
    uint64_t expires_at_ms{0};
  };

  SimpleProductError begin_discovery_();
  SimpleProductError leave_relay_for_discovery_();
  SimpleProductError restore_direct_();
  SimpleProductError handle_discovery_(
      const MacAddress &source,
      const SimpleRelayDiscovery &packet,
      uint8_t channel);
  SimpleProductError handle_challenge_(
      const MacAddress &source,
      const SimplePeerChallenge &packet,
      uint8_t channel);
  SimpleProductError handle_accept_(
      const MacAddress &source,
      const SimplePeerAccept &packet,
      uint8_t channel);
  SimpleProductError handle_compact_(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size);
  SimpleProductError maybe_advertise_relay_(uint64_t now_ms);
  SimpleProductError maybe_advance_scan_(uint64_t now_ms);
  SimpleProductRelayPeer *find_relay_child_(const MacAddress &mac);
  bool fill_nonce_(HandshakeNonce *nonce);
  static bool valid_unicast_mac_(const MacAddress &mac);
  static LinkKey as_link_key_(const SimpleLmk &lmk);

  SimpleProductPort *port_{nullptr};
  SimpleProductClock *clock_{nullptr};
  SimpleProductRandom *random_{nullptr};
  SimpleProductPolicy policy_{};
  LocalPathController path_;
  ChannelScanPlan scan_{};
  ProvisionedPeerStateV2 state_{};
  SystemPeerCredentialV2 peer_credential_{};
  ApplicationKeyState application_key_{};
  PeerEndpointV2 local_endpoint_{};
  HandshakeNonce local_boot_nonce_{};
  uint8_t direct_channel_{0};
  uint64_t next_scan_switch_ms_{0};
  uint64_t next_advertisement_ms_{0};
  bool started_{false};
  bool relay_capable_{true};
  std::optional<PendingChallenge> pending_challenge_{};
  std::optional<SimpleProductRelayPeer> active_relay_{};
  std::vector<SimpleProductRelayPeer> relay_children_{};
};

}  // namespace esphome::greenhouse_n3w_core
