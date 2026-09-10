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

enum class SimpleProductStartMode : uint8_t {
  DIRECT = 0,
  DISCOVERY,
};

enum class DiscoveryRejectReason : uint8_t {
  NONE = 0,
  STATE_NOT_DISCOVERY = 1,
  PENDING_CHALLENGE = 2,
  PACKET_INVALID = 3,
  TRUST_GENERATION_MISMATCH = 4,
  SELF_RELAY = 5,
  CHANNEL_MISMATCH = 6,
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
  virtual uint8_t last_channel_observed() const { return 0; }
  virtual int32_t last_channel_error_raw() const { return 0; }
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

class SimpleProductDiagnosticSink {
 public:
  virtual ~SimpleProductDiagnosticSink() = default;
  virtual void on_runtime_start(uint8_t mode, uint8_t path_state) = 0;
  virtual void on_scan_attempt(uint8_t requested, uint64_t now_ms) = 0;
  virtual void on_scan_result(
      uint8_t requested,
      bool success,
      uint8_t observed,
      int32_t raw_error,
      uint64_t now_ms) = 0;
  virtual void on_discovery_rx(bool accepted, uint64_t now_ms) = 0;
  virtual void on_discovery_rejected(
      DiscoveryRejectReason reason,
      uint8_t packet_channel,
      uint8_t rx_channel,
      uint64_t now_ms) {
    (void) reason;
    (void) packet_channel;
    (void) rx_channel;
    (void) now_ms;
  }
  virtual void on_challenge_tx(bool success, uint64_t now_ms) = 0;
  virtual void on_challenge_rx(bool verified, uint64_t now_ms) = 0;
  virtual void on_accept_tx(bool success, uint64_t now_ms) = 0;
  virtual void on_accept_rx(bool verified, uint64_t now_ms) = 0;
  virtual void on_relay_active(uint64_t now_ms) = 0;
  virtual void on_relay_telemetry(bool success, uint64_t now_ms) = 0;
  virtual void on_relay_advertisement(bool submitted, uint64_t now_ms) = 0;
  virtual void on_broadcast_completion(bool success, uint64_t now_ms) = 0;
  // Send callbacks run from the Wi-Fi task. Implementations must only enqueue
  // atomic state here; durable persistence belongs to the normal loop.
  virtual void on_unicast_completion(bool success, uint64_t now_ms) {
    (void) success;
    (void) now_ms;
  }
  virtual void on_compact_rx(uint64_t now_ms) { (void) now_ms; }
  virtual void on_compact_state_rejected(uint64_t now_ms) { (void) now_ms; }
  virtual void on_compact_child_binding_failure(uint64_t now_ms) { (void) now_ms; }
  virtual void on_compact_decode(bool success, uint64_t now_ms) {
    (void) success;
    (void) now_ms;
  }
  virtual void on_compact_wrap_failure(uint64_t now_ms) { (void) now_ms; }
  virtual void on_compact_forward_attempt(uint64_t now_ms) { (void) now_ms; }
  virtual void on_compact_forward_submit(bool success, uint64_t now_ms) {
    (void) success;
    (void) now_ms;
  }
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
      uint8_t direct_channel,
      SimpleProductStartMode start_mode = SimpleProductStartMode::DIRECT);
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
  void set_diagnostic_sink(SimpleProductDiagnosticSink *sink) {
    diagnostic_sink_ = sink;
  }
  bool started() const { return started_; }
  LocalPathState path_state() const { return path_.state(); }
  uint8_t direct_channel_hint() const { return direct_channel_; }
  uint8_t working_channel() const;
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
  SimpleProductDiagnosticSink *diagnostic_sink_{nullptr};
};

}  // namespace esphome::greenhouse_n3w_core
