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
  void shutdown();

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
      std::size_t size);
  DriverError send_broadcast(
      const uint8_t *data,
      std::size_t size);

  bool initialized() const { return initialized_; }

 protected:
#ifdef USE_ESP32
  DriverError start_wifi_();
  void stop_owned_wifi_();

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
  static EspNowDriver *active_;
  bool wifi_owned_{false};
  std::atomic<uint8_t> diagnostic_receive_logs_{0};
  std::atomic<uint8_t> diagnostic_broadcast_logs_{0};
#endif

  EspNowEventSink *sink_{nullptr};
  bool initialized_{false};
};

}  // namespace esphome::greenhouse_n3w_core
