#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "esphome/core/component.h"
#include "esphome/components/greenhouse_n3w_core/n3w_core.h"
#include "esphome/components/greenhouse_n3w_core/n3w_esp32_nvs.h"
#include "esphome/components/greenhouse_n3w_core/n3w_espnow_driver.h"
#include "esphome/components/greenhouse_n3w_core/n3w_radio.h"

#ifdef USE_ESP32
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#endif

namespace esphome::greenhouse_n3w_p5_lab {

using greenhouse_n3w_core::ApplicationKeyState;
using greenhouse_n3w_core::BootSessionManager;
using greenhouse_n3w_core::ChildPeerBinding;
using greenhouse_n3w_core::ChildRelayCache;
using greenhouse_n3w_core::EspNowDriver;
using greenhouse_n3w_core::EspNowEventSink;
using greenhouse_n3w_core::LinkKey;
using greenhouse_n3w_core::MacAddress;
using greenhouse_n3w_core::NvsBootSessionStore;
using greenhouse_n3w_core::ReceiptAckPacket;
using greenhouse_n3w_core::RelayForwardSink;
using greenhouse_n3w_core::RelayFrame;
using greenhouse_n3w_core::RelayIngressController;
using greenhouse_n3w_core::RelayPeerBinding;
using greenhouse_n3w_core::RetryPolicy;

class GreenhouseN3wP5Lab final : public Component,
                                 public EspNowEventSink,
                                 public RelayForwardSink {
 public:
  void set_role(const std::string &value) { role_ = value; }
  void set_execution_enabled(bool value) { execution_enabled_ = value; }
  void set_system_id(const std::string &value) { system_id_ = value; }
  void set_node_id(const std::string &value) { node_id_ = value; }
  void set_gateway_id(const std::string &value) { gateway_id_ = value; }
  void set_peer_mac(const std::string &value) { peer_mac_text_ = value; }
  void set_pmk_hex(const std::string &value) { pmk_hex_ = value; }
  void set_lmk_hex(const std::string &value) { lmk_hex_ = value; }
  void set_app_key_epoch1_hex(const std::string &value) { app_key_epoch1_hex_ = value; }
  void set_app_key_epoch2_hex(const std::string &value) { app_key_epoch2_hex_ = value; }
  void set_session_floor(uint64_t value) { session_floor_ = value; }
  void set_publish_interval_ms(uint32_t value) { publish_interval_ms_ = value; }

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override;

  void handle_lab_command(const std::string &command);

  void on_espnow_receive(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size) override;
  void on_espnow_send_result(
      const MacAddress &destination,
      bool success) override;

  bool accept_for_forwarding(const RelayFrame &frame) override;

 protected:
  struct RxEvent {
    MacAddress source{};
    uint16_t size{0};
    std::array<uint8_t, greenhouse_n3w_core::kEspNowDatagramLimit> data{};
  };

  struct TxEvent {
    bool success{false};
  };

  enum class DesiredPath : uint8_t { DIRECT = 0, RELAY = 1 };

  bool parse_configuration_();
  bool ensure_radio_ready_();
  bool read_connected_sta_channel_(uint8_t *primary) const;
  void mark_radio_unavailable_(const char *reason);
  void require_fresh_relay_probe_(const char *reason);
  bool initialize_child_session_();
  void process_rx_();
  void process_tx_();
  void process_child_packet_(const RxEvent &event);
  void process_relay_packet_(const RxEvent &event);
  void invalidate_relay_auth_(const char *reason);
  void maybe_probe_();
  void maybe_publish_();
  bool publish_direct_(uint32_t seq, const std::string &telemetry);
  bool publish_relay_(uint32_t seq, const std::string &telemetry);
  bool build_relay_datagrams_(uint32_t seq, const std::string &telemetry, RelayFrame *frame,
                              std::vector<std::vector<uint8_t>> *datagrams);
  void flush_relay_cache_();
  bool resend_last_datagrams_(bool reverse);
  bool send_datagrams_(const std::vector<std::vector<uint8_t>> &datagrams, bool reverse);
  bool send_probe_();
  std::string build_telemetry_(uint32_t seq) const;
  ApplicationKeyState *active_key_();

  static bool parse_hex_(const std::string &value, uint8_t *output, std::size_t bytes);
  static bool parse_mac_(const std::string &value, MacAddress *output);
  static uint64_t now_ms_();

  std::string role_;
  bool execution_enabled_{false};
  std::string system_id_;
  std::string node_id_;
  std::string gateway_id_;
  std::string peer_mac_text_;
  std::string pmk_hex_;
  std::string lmk_hex_;
  std::string app_key_epoch1_hex_;
  std::string app_key_epoch2_hex_;
  uint64_t session_floor_{1};
  uint32_t publish_interval_ms_{5000};

  bool is_child_{false};
  bool radio_ready_{false};
  bool radio_attempted_{false};
  bool relay_authenticated_{false};
  bool relay_probe_established_since_boot_{false};
  DesiredPath desired_path_{DesiredPath::DIRECT};
  uint32_t selected_key_epoch_{1};
  uint64_t probe_challenge_{0x5045000000000001ULL};
  uint64_t last_probe_ms_{0};
  uint64_t last_publish_ms_{0};
  uint64_t last_radio_attempt_ms_{0};
  uint8_t configured_peer_channel_{0};
  uint8_t pending_peer_channel_{0};
  uint32_t rx_dropped_{0};
  uint32_t send_failures_{0};

  MacAddress peer_mac_{};
  LinkKey pmk_{};
  LinkKey lmk_{};
  ApplicationKeyState key_epoch1_{};
  ApplicationKeyState key_epoch2_{};
  RelayPeerBinding relay_binding_{};
  ChildPeerBinding child_binding_{};

  EspNowDriver driver_{};
  NvsBootSessionStore boot_store_{"gh_n3w_p5", "boot_state"};
  BootSessionManager boot_{};
  ChildRelayCache cache_{4, RetryPolicy{500, 8000, 5}};
  RelayIngressController relay_ingress_{this};
  std::vector<std::vector<uint8_t>> last_datagrams_{};

#ifdef USE_ESP32
  QueueHandle_t rx_queue_{nullptr};
  QueueHandle_t tx_queue_{nullptr};
#endif
};

}  // namespace esphome::greenhouse_n3w_p5_lab
