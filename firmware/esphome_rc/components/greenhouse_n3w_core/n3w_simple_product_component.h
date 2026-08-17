#pragma once

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <string>

#include "esphome/core/component.h"

#include "n3w_esp32_pairing_nvs.h"
#include "n3w_esp32_runtime_nvs.h"
#include "n3w_espnow_driver.h"
#include "n3w_simple_pairing_client.h"
#include "n3w_simple_product_runtime.h"

namespace esphome::greenhouse_n3w_core {

class SimpleProductComponent : public Component,
                               public EspNowEventSink,
                               public SimpleProductPort,
                               public SimpleProductClock,
                               public SimpleProductRandom,
                               public SimplePairingClientNetwork,
                               public SimplePairingClientRandom {
 public:
  SimpleProductComponent();

  void set_activation_enabled(bool enabled) { activation_enabled_ = enabled; }
  void setup() override;
  void loop() override;
  float get_setup_priority() const override;

  bool send_telemetry_json(
      const std::string &telemetry_json,
      const std::string &boot_id,
      uint32_t seq);

  bool provisioned() const { return pairing_client_.provisioned(); }
  bool runtime_ready() const { return runtime_ready_; }
  LocalPathState path_state() const { return runtime_.path_state(); }
  const std::string &hardware_id() const { return pairing_client_.hardware_id(); }
  const std::string &pairing_id() const { return pairing_client_.pairing_id(); }
  const std::string &node_id() const { return peer_state_.node_id; }
  std::string pairing_qr_payload() const { return pairing_client_.pairing_qr_payload(); }

  // EspNowEventSink. Receive work is copied into a bounded SPSC ring and
  // processed from loop(), never from the high-priority Wi-Fi callback.
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

  // SimpleProductPort.
  bool set_radio_channel(uint8_t channel) override;
  bool broadcast_control(const uint8_t *data, std::size_t size) override;
  bool install_encrypted_peer(
      const MacAddress &peer_mac,
      const LinkKey &lmk,
      uint8_t channel) override;
  bool remove_peer(const MacAddress &peer_mac) override;
  bool send_encrypted_peer(
      const MacAddress &peer_mac,
      const uint8_t *data,
      std::size_t size) override;
  bool publish_direct(const std::string &topic, const std::string &payload) override;
  bool publish_relay(const std::string &topic, const std::string &payload) override;

  // Clocks/randomness.
  uint64_t now_ms() const override;
  bool fill(uint8_t *data, std::size_t size) override;
  bool fill_pairing_random(uint8_t *data, std::size_t size) override;

  // Simplified bootstrap network.
  bool discover_manager(
      const std::string &request_json,
      std::string *response_json) override;
  bool post_json(
      const SimpleManagerCandidateV2 &candidate,
      const std::string &path,
      const std::string &request_json,
      int *status_code,
      std::string *response_json) override;
  bool post_json(
      const PendingPairingAckV2 &pending,
      const std::string &path,
      const std::string &request_json,
      int *status_code,
      std::string *response_json) override;

 protected:
  struct RxSlot {
    MacAddress source{};
    uint16_t size{0};
    uint8_t channel{0};
    std::array<uint8_t, kEspNowPhysicalDatagramLimit> data{};
  };

  bool read_local_mac_();
  bool load_runtime_state_();
  bool configure_mqtt_();
  bool start_runtime_if_ready_();
  bool derive_pmk_(LinkKey *pmk) const;
  void drain_radio_();
  void advance_pairing_();
  void advance_recovery_();
  bool http_post_(
      const std::string &host,
      uint16_t port,
      const std::string &path,
      const std::string &request_json,
      int *status_code,
      std::string *response_json);

  static constexpr std::size_t kRxRingSlots = 4;
  static constexpr uint32_t kPairingRetryMs = 5000;
  static constexpr uint32_t kRecoveryProbeMs = 2000;
  static constexpr uint16_t kDiscoveryPort = 47111;

  bool activation_enabled_{false};
  bool runtime_state_loaded_{false};
  bool mqtt_configured_{false};
  bool runtime_ready_{false};
  bool radio_attempted_{false};
  uint64_t next_pairing_attempt_ms_{0};
  uint64_t next_recovery_probe_ms_{0};
  uint64_t last_radio_attempt_ms_{0};
  MacAddress local_mac_{};
  ProvisionedPeerStateV2 peer_state_{};
  ProvisionedBrokerStateV2 broker_state_{};
  EspNowDriver radio_{};
  SimpleProductRuntime runtime_;
  NvsSetupSecretStore setup_secret_store_{};
  NvsProvisionedPeerStoreV2 peer_store_{};
  NvsProvisionedBrokerStoreV2 broker_store_{};
  NvsPendingPairingAckStoreV2 ack_store_{};
  SimplePairingClient pairing_client_;
  std::array<RxSlot, kRxRingSlots> rx_ring_{};
  std::atomic<uint8_t> rx_write_{0};
  std::atomic<uint8_t> rx_read_{0};
  std::atomic<uint32_t> rx_dropped_{0};
};

}  // namespace esphome::greenhouse_n3w_core
