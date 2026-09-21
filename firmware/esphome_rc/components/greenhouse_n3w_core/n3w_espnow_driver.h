#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>

#include "n3w_radio.h"

#ifdef USE_ESP32
#include "esp_idf_version.h"
#include "esp_now.h"
#endif

namespace esphome::greenhouse_n3w_core {

// Keep kEspNowDatagramLimit=240 in n3w_radio.h as the legacy control and
// fragmentation contract. The concrete ESP-NOW v2 driver must also be able to
// carry the new single-frame N3W2 telemetry payload (maximum 1072 bytes).
constexpr std::size_t kEspNowPhysicalDatagramLimit = 1470;

#ifdef USE_ESP32
#ifdef ESP_NOW_MAX_DATA_LEN_V2
static_assert(kEspNowPhysicalDatagramLimit <= ESP_NOW_MAX_DATA_LEN_V2,
              "configured ESP-NOW physical datagram limit exceeds ESP-IDF v2 limit");
#endif
#endif

constexpr MacAddress kEspNowBroadcastMac{
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff};

enum class DriverError : uint8_t {
  NONE = 0,
  INVALID_ARGUMENT,
  NOT_INITIALIZED,
  ALREADY_INITIALIZED,
  WIFI_INIT_FAILED,
  WIFI_START_FAILED,
  WIFI_CHANNEL_FAILED,
  ESPNOW_INIT_FAILED,
  ESPNOW_CALLBACK_FAILED,
  ESPNOW_TEARDOWN_UNCONFIRMED,
  ESPNOW_PMK_FAILED,
  PEER_CONFIG_FAILED,
  SEND_FAILED,
};

struct EspNowReceiveMetadata {
  int16_t rssi_dbm{-127};
  uint8_t channel{0};
};

class EspNowEventSink {
 public:
  virtual ~EspNowEventSink() = default;
  // ESP-IDF invokes these from a high-priority Wi-Fi task. Implementations must
  // copy/queue minimal metadata and return immediately.
  virtual void on_espnow_receive(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size) = 0;
  // Metadata-aware receive is backward-compatible with existing sinks. New
  // product runtimes use RSSI/channel for disconnected candidate collection.
  virtual void on_espnow_receive_with_metadata(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size,
      const EspNowReceiveMetadata &metadata) {
    (void) metadata;
    on_espnow_receive(source, data, size);
  }
  virtual void on_espnow_send_result(
      const MacAddress &destination,
      bool success) = 0;
};

class EspNowDriver {
 public:
  DriverError initialize(EspNowEventSink *sink, const LinkKey &pmk);
  // Starts Wi-Fi in STA-only mode when ESPHome has deliberately stopped its
  // reconnect state machine. The driver stops only what it starts and leaves
  // ESPHome's Wi-Fi initialization intact for a later Direct recovery probe.
  DriverError initialize_standalone(EspNowEventSink *sink, const LinkKey &pmk);
  bool shutdown();
  bool teardown_confirmed() const { return teardown_confirmed_; }

  DriverError set_channel(uint8_t channel);
  DriverError prepare_broadcast_peer(uint8_t channel);
  DriverError add_encrypted_peer(
      const MacAddress &peer_mac,
      const LinkKey &lmk,
      uint8_t channel);
  DriverError remove_peer(const MacAddress &peer_mac);
  DriverError send(
      const MacAddress &peer_mac,
      const uint8_t *data,
      std::size_t size,
      bool observe_context = false);
  DriverError send_broadcast(
      const uint8_t *data,
      std::size_t size);
  DriverError send_broadcast_on_channel(
      uint8_t channel,
      const uint8_t *data,
      std::size_t size,
      uint32_t wait_time_ms);

  int32_t last_channel_error_raw() const { return last_channel_error_raw_; }
  uint8_t last_channel_observed() const { return last_channel_observed_; }
  DriverError last_broadcast_send_error() const {
    return last_broadcast_send_error_;
  }
  int32_t last_broadcast_send_error_raw() const {
    return last_broadcast_send_error_raw_;
  }
  DriverError last_unicast_send_error() const {
    return last_unicast_send_error_;
  }
  int32_t last_unicast_send_error_raw() const {
    return last_unicast_send_error_raw_;
  }
  uint8_t last_unicast_current_channel() const {
    return last_unicast_current_channel_;
  }
  uint8_t last_unicast_peer_channel() const {
    return last_unicast_peer_channel_;
  }

  bool initialized() const { return initialized_; }
  bool espnow_started() const { return espnow_started_; }
  uint16_t pending_unicast_sends() const {
    return pending_unicast_sends_.load(std::memory_order_acquire);
  }
  bool callbacks_idle() const {
    return callbacks_inflight_.load(std::memory_order_acquire) == 0U;
  }

 protected:
#ifdef USE_ESP32
  DriverError initialize_(
      EspNowEventSink *sink,
      const LinkKey &pmk,
      bool start_standalone_wifi);
  DriverError start_wifi_(bool start_standalone_wifi);
  bool stop_owned_wifi_();
  void complete_unicast_send_();

  static void recv_cb_(
      const esp_now_recv_info_t *info,
      const uint8_t *data,
      int data_len);
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 5, 0)
  static void send_cb_(
      const esp_now_send_info_t *info,
      esp_now_send_status_t status);
#else
  static void send_cb_(
      const uint8_t *mac_addr,
      esp_now_send_status_t status);
#endif
  static std::atomic<EspNowDriver *> active_;
  bool wifi_initialized_by_driver_{false};
  bool wifi_started_by_driver_{false};
#ifdef GREENHOUSE_N3W_ENABLE_PHASE4_LAB
  std::atomic<uint8_t> diagnostic_receive_logs_{0};
  std::atomic<uint8_t> diagnostic_broadcast_logs_{0};
#endif
#endif

  std::atomic<EspNowEventSink *> sink_{nullptr};
  static std::atomic<uint16_t> callbacks_inflight_;
  bool initialized_{false};
  // Tracks whether esp_now_init() succeeded and a matching successful
  // esp_now_deinit() is still required. This is intentionally independent of
  // initialized_, which means the full driver setup completed.
  bool espnow_started_{false};
  bool teardown_confirmed_{true};
  int32_t last_channel_error_raw_{0};
  uint8_t last_channel_observed_{0};
  DriverError last_broadcast_send_error_{DriverError::NONE};
  int32_t last_broadcast_send_error_raw_{0};
  DriverError last_unicast_send_error_{DriverError::NONE};
  int32_t last_unicast_send_error_raw_{0};
  uint8_t last_unicast_current_channel_{0};
  uint8_t last_unicast_peer_channel_{0};
  std::atomic<uint16_t> pending_unicast_sends_{0};
};

}  // namespace esphome::greenhouse_n3w_core
