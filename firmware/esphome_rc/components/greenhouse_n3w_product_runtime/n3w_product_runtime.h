#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "esphome/components/greenhouse_n3w_core/n3w_espnow_driver.h"
#include "esphome/components/greenhouse_n3w_core/n3w_radio.h"
#include "esphome/components/greenhouse_n3w_product_core/n3w_product_core.h"

namespace esphome::greenhouse_n3w_product_runtime {

using greenhouse_n3w_core::ChannelScanPlan;
using greenhouse_n3w_core::DriverError;
using greenhouse_n3w_core::EspNowDriver;
using greenhouse_n3w_core::EspNowEventSink;
using greenhouse_n3w_core::EspNowReceiveMetadata;
using greenhouse_n3w_core::LinkKey;
using greenhouse_n3w_core::MacAddress;
using greenhouse_n3w_product_core::AutoPathPolicy;
using greenhouse_n3w_product_core::AutoPathState;
using greenhouse_n3w_product_core::DynamicPeerAuthorization;
using greenhouse_n3w_product_core::ProductCoreError;
using greenhouse_n3w_product_core::RelayCandidateEligibility;
using greenhouse_n3w_product_core::RelayCandidateObservation;
using greenhouse_n3w_product_core::RelayCandidatePolicy;
using greenhouse_n3w_product_core::RelayCandidateRecord;
using greenhouse_n3w_product_core::RelayOrchestrationCore;
using greenhouse_n3w_product_core::WifiDirectHealthPolicy;

constexpr uint8_t kProductDiscoveryWireVersion = 1;
constexpr uint8_t kProductDiscoveryWireType = 1;
constexpr std::size_t kProductDiscoveryMaxIdentityBytes = 96;

struct ProductDiscoveryAdvertisement {
  std::string gateway_id;
  uint8_t channel{0};
  uint32_t advertisement_generation{0};

  bool valid() const;
};

bool encode_product_discovery_advertisement(
    const ProductDiscoveryAdvertisement &advertisement,
    std::vector<uint8_t> *encoded);
bool decode_product_discovery_advertisement(
    const uint8_t *data,
    std::size_t size,
    ProductDiscoveryAdvertisement *advertisement);

enum class ProductRuntimeError : uint8_t {
  NONE = 0,
  INVALID_ARGUMENT,
  POLICY_INVALID,
  NOT_READY,
  STATE_REJECTED,
  PACKET_REJECTED,
  RADIO_ERROR,
  CORE_ERROR,
};

struct ProductRuntimePolicy {
  std::vector<uint8_t> allowed_channels{1, 6, 11};
  uint32_t scan_dwell_ms{250};
  uint32_t candidate_select_interval_ms{500};
  uint32_t advertisement_interval_ms{2000};

  bool valid() const;
};

struct LocalRelayAdvertisement {
  bool enabled{false};
  std::string gateway_id;
  uint8_t channel{0};
  uint32_t advertisement_generation{0};

  bool valid() const;
};

struct RuntimePeerMaterial {
  DynamicPeerAuthorization authorization{};
  LinkKey lmk{};
};

class ProductRuntimeClock {
 public:
  virtual ~ProductRuntimeClock() = default;
  virtual uint64_t now_ms() const = 0;
};

class ProductRuntimeRadioPort {
 public:
  virtual ~ProductRuntimeRadioPort() = default;
  virtual DriverError initialize(EspNowEventSink *sink, const LinkKey &pmk) = 0;
  virtual void shutdown() = 0;
  virtual DriverError set_channel(uint8_t channel) = 0;
  virtual DriverError prepare_broadcast_peer(uint8_t channel) = 0;
  virtual DriverError add_encrypted_peer(
      const MacAddress &peer_mac,
      const LinkKey &lmk,
      uint8_t channel) = 0;
  virtual DriverError remove_peer(const MacAddress &peer_mac) = 0;
  virtual DriverError send_peer(
      const MacAddress &peer_mac,
      const uint8_t *data,
      std::size_t size) = 0;
  virtual DriverError send_broadcast(
      const uint8_t *data,
      std::size_t size) = 0;
};

class EspNowDriverRuntimePort final : public ProductRuntimeRadioPort {
 public:
  DriverError initialize(EspNowEventSink *sink, const LinkKey &pmk) override;
  void shutdown() override;
  DriverError set_channel(uint8_t channel) override;
  DriverError prepare_broadcast_peer(uint8_t channel) override;
  DriverError add_encrypted_peer(
      const MacAddress &peer_mac,
      const LinkKey &lmk,
      uint8_t channel) override;
  DriverError remove_peer(const MacAddress &peer_mac) override;
  DriverError send_peer(
      const MacAddress &peer_mac,
      const uint8_t *data,
      std::size_t size) override;
  DriverError send_broadcast(
      const uint8_t *data,
      std::size_t size) override;

  EspNowDriver &driver() { return driver_; }

 private:
  EspNowDriver driver_{};
};

class ProductRuntimeEventSink {
 public:
  virtual ~ProductRuntimeEventSink() = default;
  virtual void on_candidate_observed(const RelayCandidateObservation &observation) {
    (void) observation;
  }
  virtual void on_authorization_needed(const RelayCandidateRecord &candidate) {
    (void) candidate;
  }
  virtual void on_peer_active(const DynamicPeerAuthorization &authorization) {
    (void) authorization;
  }
  virtual void on_peer_released(const MacAddress &peer_mac) {
    (void) peer_mac;
  }
  virtual void on_advertisement_sent(const ProductDiscoveryAdvertisement &advertisement) {
    (void) advertisement;
  }
};

class ProductEspNowRuntime final : public EspNowEventSink {
 public:
  ProductEspNowRuntime(
      ProductRuntimeRadioPort *radio,
      ProductRuntimeClock *clock,
      ProductRuntimeEventSink *events,
      WifiDirectHealthPolicy direct_policy,
      RelayCandidatePolicy candidate_policy,
      AutoPathPolicy path_policy,
      ProductRuntimePolicy runtime_policy);

  ProductRuntimeError start(const LinkKey &pmk);
  void stop();

  ProductRuntimeError set_last_direct_channel(uint8_t channel);
  ProductRuntimeError set_local_relay_advertisement(
      const LocalRelayAdvertisement &advertisement);
  ProductRuntimeError note_direct_result(bool success);
  ProductRuntimeError note_direct_recovery_probe(bool success);
  ProductRuntimeError apply_manager_eligibility(
      const MacAddress &source_mac,
      const std::string &gateway_id,
      const RelayCandidateEligibility &eligibility);
  ProductRuntimeError reject_peer_authorization();
  ProductRuntimeError install_authorized_peer(const RuntimePeerMaterial &material);
  ProductRuntimeError note_relay_result(bool success);
  ProductRuntimeError send_active_peer(const uint8_t *data, std::size_t size);
  ProductRuntimeError tick();

  bool started() const { return started_; }
  bool scan_active() const { return scan_active_; }
  uint8_t scan_channel() const { return scan_active_ ? scan_plan_.current() : 0; }
  AutoPathState path_state() const { return orchestration_.path_state(); }
  bool relay_telemetry_ready() const;
  const std::optional<MacAddress> &active_peer_mac() const { return active_peer_mac_; }
  const std::optional<MacAddress> &pending_authorization_mac() const {
    return pending_authorization_mac_;
  }

  void on_espnow_receive(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size) override;
  void on_espnow_receive_with_metadata(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size,
      const EspNowReceiveMetadata &metadata) override;
  void on_espnow_send_result(
      const MacAddress &destination,
      bool success) override;

 private:
  struct CandidateMirror {
    RelayCandidateRecord record{};
  };

  ProductRuntimeError begin_scan_(uint64_t now_ms);
  void stop_scan_();
  ProductRuntimeError advance_scan_(uint64_t now_ms);
  ProductRuntimeError maybe_select_candidate_(uint64_t now_ms);
  ProductRuntimeError maybe_send_advertisement_(uint64_t now_ms);
  ProductRuntimeError handle_path_state_(uint64_t now_ms);
  ProductRuntimeError release_active_peer_();
  ProductRuntimeError fail_pending_authorization_(uint64_t now_ms);
  CandidateMirror *find_mirror_(const MacAddress &source_mac);
  const CandidateMirror *find_mirror_(const MacAddress &source_mac) const;
  void mirror_observation_(const RelayCandidateObservation &observation);
  void mirror_eligibility_(
      const MacAddress &source_mac,
      const RelayCandidateEligibility &eligibility);
  bool material_matches_pending_(
      const RuntimePeerMaterial &material,
      uint64_t now_ms) const;
  static bool valid_unicast_mac_(const MacAddress &mac);
  static bool nonzero_key_(const LinkKey &key);

  ProductRuntimeRadioPort *radio_{nullptr};
  ProductRuntimeClock *clock_{nullptr};
  ProductRuntimeEventSink *events_{nullptr};
  ProductRuntimePolicy runtime_policy_{};
  RelayCandidatePolicy candidate_policy_{};
  RelayOrchestrationCore orchestration_;
  ChannelScanPlan scan_plan_{};

  bool started_{false};
  bool scan_active_{false};
  uint8_t last_direct_channel_{0};
  uint64_t next_scan_switch_ms_{0};
  uint64_t next_candidate_select_ms_{0};
  uint64_t next_advertisement_ms_{0};
  LocalRelayAdvertisement local_advertisement_{};
  std::vector<CandidateMirror> mirrors_{};
  std::optional<MacAddress> pending_authorization_mac_{};
  std::optional<MacAddress> active_peer_mac_{};
};

}  // namespace esphome::greenhouse_n3w_product_runtime
