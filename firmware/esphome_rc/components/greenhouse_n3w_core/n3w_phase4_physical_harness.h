#pragma once

#include <cstddef>
#include <cstdint>

#include "n3w_compact_telemetry.h"
#include "n3w_esp32_simple_nvs.h"
#include "n3w_espnow_driver.h"
#include "n3w_radio.h"
#include "n3w_simple_runtime.h"

namespace esphome::greenhouse_n3w_core {

// Source-only Phase 4 adapter. Constructing or preparing this object performs no
// board, NVS, Wi-Fi, or ESP-NOW I/O. Physical methods remain explicit so a later
// authorization can bind the exact same generic firmware code to an isolated lab.
class Phase4PhysicalHarness : public EspNowEventSink {
 public:
  bool prepare_source_only();
  bool source_contract_ready() const;

  SimpleNvsStatus load_or_create_setup_secret(SetupSecret *secret);
  SimpleNvsStatus load_provisioned_state(ProvisionedPeerStateV2 *state);
  SimpleNvsStatus save_provisioned_state(const ProvisionedPeerStateV2 &state);
  SimpleNvsStatus erase_setup_secret();

  LocalPathState path_state() const { return path_.state(); }
  RadioError note_direct_result(bool success) { return path_.note_direct_result(success); }
  RadioError note_authenticated_relay_ready(bool ready) {
    return path_.note_authenticated_relay_ready(ready);
  }
  RadioError note_relay_result(bool success) { return path_.note_relay_result(success); }
  RadioError note_direct_recovery_probe(bool success) {
    return path_.note_direct_recovery_probe(success);
  }

  DriverError activate_radio(const LinkKey &pmk, uint8_t channel);
  void shutdown_radio();
  DriverError install_authenticated_peer(
      const MacAddress &peer_mac,
      const LinkKey &pair_lmk,
      uint8_t channel);
  DriverError send_peer_control_broadcast(const uint8_t *data, std::size_t size);
  DriverError send_compact_unicast(
      const MacAddress &peer_mac,
      const uint8_t *data,
      std::size_t size);

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

  std::size_t receive_count() const { return receive_count_; }
  std::size_t send_completion_count() const { return send_completion_count_; }
  const MacAddress &last_source() const { return last_source_; }
  std::size_t last_receive_size() const { return last_receive_size_; }
  const EspNowReceiveMetadata &last_receive_metadata() const {
    return last_receive_metadata_;
  }

 private:
  bool source_only_prepared_{false};
  EspNowDriver radio_{};
  LocalPathController path_{LocalPathPolicy{}};
  NvsSetupSecretStore setup_secret_store_{};
  NvsProvisionedPeerStoreV2 peer_store_{};
  std::size_t receive_count_{0};
  std::size_t send_completion_count_{0};
  MacAddress last_source_{};
  MacAddress last_destination_{};
  std::size_t last_receive_size_{0};
  EspNowReceiveMetadata last_receive_metadata_{};
  bool last_send_success_{false};
};

}  // namespace esphome::greenhouse_n3w_core
