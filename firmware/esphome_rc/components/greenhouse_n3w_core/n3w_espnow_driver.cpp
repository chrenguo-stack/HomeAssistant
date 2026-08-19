#include "n3w_espnow_driver.h"

#include <algorithm>
#include <cstring>

#include "esphome/core/log.h"

#ifdef USE_ESP32
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_wifi.h"
#endif

namespace esphome::greenhouse_n3w_core {

namespace {
static const char *const TAG = "n3w_espnow_driver";
constexpr uint8_t kDiagnosticLogLimit = 8;
}

#ifdef USE_ESP32
EspNowDriver *EspNowDriver::active_ = nullptr;
#endif

#ifdef USE_ESP32
DriverError EspNowDriver::start_wifi_() {
  wifi_mode_t mode{};
  const esp_err_t mode_error = esp_wifi_get_mode(&mode);
  if (mode_error == ESP_OK) {
    uint8_t channel = 0;
    wifi_second_chan_t secondary = WIFI_SECOND_CHAN_NONE;
    return esp_wifi_get_channel(&channel, &secondary) == ESP_OK
               ? DriverError::NONE
               : DriverError::WIFI_START_FAILED;
  }
  if (mode_error != ESP_ERR_WIFI_NOT_INIT) {
    return DriverError::WIFI_INIT_FAILED;
  }

  const esp_err_t netif_error = esp_netif_init();
  if (netif_error != ESP_OK && netif_error != ESP_ERR_INVALID_STATE) {
    return DriverError::WIFI_INIT_FAILED;
  }
  const esp_err_t event_error = esp_event_loop_create_default();
  if (event_error != ESP_OK && event_error != ESP_ERR_INVALID_STATE) {
    return DriverError::WIFI_INIT_FAILED;
  }

  wifi_init_config_t config = WIFI_INIT_CONFIG_DEFAULT();
  if (esp_wifi_init(&config) != ESP_OK) {
    return DriverError::WIFI_INIT_FAILED;
  }
  wifi_owned_ = true;
  if (esp_wifi_set_storage(WIFI_STORAGE_RAM) != ESP_OK ||
      esp_wifi_set_mode(WIFI_MODE_STA) != ESP_OK ||
      esp_wifi_start() != ESP_OK) {
    stop_owned_wifi_();
    return DriverError::WIFI_START_FAILED;
  }
  return DriverError::NONE;
}

void EspNowDriver::stop_owned_wifi_() {
  if (!wifi_owned_) return;
  (void) esp_wifi_stop();
  (void) esp_wifi_deinit();
  wifi_owned_ = false;
}
#endif

DriverError EspNowDriver::initialize(EspNowEventSink *sink, const LinkKey &pmk) {
#ifndef USE_ESP32
  (void) sink;
  (void) pmk;
  return DriverError::ESPNOW_INIT_FAILED;
#else
  if (sink == nullptr || std::all_of(pmk.begin(), pmk.end(), [](uint8_t b) { return b == 0; })) {
    return DriverError::INVALID_ARGUMENT;
  }
  if (initialized_ || active_ != nullptr) {
    return DriverError::ALREADY_INITIALIZED;
  }
  const DriverError wifi_error = start_wifi_();
  if (wifi_error != DriverError::NONE) {
    return wifi_error;
  }
  if (esp_now_init() != ESP_OK) {
    stop_owned_wifi_();
    return DriverError::ESPNOW_INIT_FAILED;
  }
  if (esp_now_set_pmk(pmk.data()) != ESP_OK) {
    esp_now_deinit();
    stop_owned_wifi_();
    return DriverError::ESPNOW_PMK_FAILED;
  }
  active_ = this;
  sink_ = sink;
  diagnostic_receive_logs_.store(0, std::memory_order_relaxed);
  diagnostic_broadcast_logs_.store(0, std::memory_order_relaxed);
  if (esp_now_register_recv_cb(&EspNowDriver::recv_cb_) != ESP_OK ||
      esp_now_register_send_cb(&EspNowDriver::send_cb_) != ESP_OK) {
    esp_now_unregister_recv_cb();
    esp_now_unregister_send_cb();
    active_ = nullptr;
    sink_ = nullptr;
    esp_now_deinit();
    stop_owned_wifi_();
    return DriverError::ESPNOW_CALLBACK_FAILED;
  }
  initialized_ = true;
  return DriverError::NONE;
#endif
}

void EspNowDriver::shutdown() {
#ifdef USE_ESP32
  if (initialized_) {
    esp_now_unregister_recv_cb();
    esp_now_unregister_send_cb();
    esp_now_deinit();
  }
  if (active_ == this) {
    active_ = nullptr;
  }
  stop_owned_wifi_();
#endif
  sink_ = nullptr;
  initialized_ = false;
}

DriverError EspNowDriver::set_channel(uint8_t channel) {
#ifndef USE_ESP32
  (void) channel;
  return DriverError::NOT_INITIALIZED;
#else
  if (!initialized_) {
    return DriverError::NOT_INITIALIZED;
  }
  if (!valid_radio_channel(channel)) {
    return DriverError::INVALID_ARGUMENT;
  }
  return esp_wifi_set_channel(channel, WIFI_SECOND_CHAN_NONE) == ESP_OK
             ? DriverError::NONE
             : DriverError::WIFI_CHANNEL_FAILED;
#endif
}

DriverError EspNowDriver::prepare_broadcast_peer(uint8_t channel) {
#ifndef USE_ESP32
  (void) channel;
  return DriverError::NOT_INITIALIZED;
#else
  if (!initialized_) {
    return DriverError::NOT_INITIALIZED;
  }
  if (!valid_radio_channel(channel)) {
    return DriverError::INVALID_ARGUMENT;
  }
  esp_now_peer_info_t peer{};
  std::memcpy(peer.peer_addr, kEspNowBroadcastMac.data(), kEspNowBroadcastMac.size());
  peer.channel = channel;
  peer.ifidx = WIFI_IF_STA;
  peer.encrypt = false;
  esp_err_t err = ESP_OK;
  if (esp_now_is_peer_exist(peer.peer_addr)) {
    err = esp_now_mod_peer(&peer);
  } else {
    err = esp_now_add_peer(&peer);
  }
  return err == ESP_OK ? DriverError::NONE : DriverError::PEER_CONFIG_FAILED;
#endif
}

DriverError EspNowDriver::add_encrypted_peer(
    const MacAddress &peer_mac,
    const LinkKey &lmk,
    uint8_t channel) {
#ifndef USE_ESP32
  (void) peer_mac;
  (void) lmk;
  (void) channel;
  return DriverError::NOT_INITIALIZED;
#else
  if (!initialized_) {
    return DriverError::NOT_INITIALIZED;
  }
  RelayPeerBinding validation;
  validation.gateway_id = "binding_check";
  validation.peer_mac = peer_mac;
  validation.lmk = lmk;
  validation.preferred_channel = channel;
  if (!validation.valid() || !valid_radio_channel(channel)) {
    return DriverError::INVALID_ARGUMENT;
  }
  static_assert(ESP_NOW_KEY_LEN == kEspNowLinkKeyBytes, "unexpected ESP-NOW LMK length");
  esp_now_peer_info_t peer{};
  std::memcpy(peer.peer_addr, peer_mac.data(), peer_mac.size());
  std::memcpy(peer.lmk, lmk.data(), lmk.size());
  peer.channel = channel;
  peer.ifidx = WIFI_IF_STA;
  peer.encrypt = true;
  esp_err_t err = ESP_OK;
  if (esp_now_is_peer_exist(peer.peer_addr)) {
    err = esp_now_mod_peer(&peer);
  } else {
    err = esp_now_add_peer(&peer);
  }
  return err == ESP_OK ? DriverError::NONE : DriverError::PEER_CONFIG_FAILED;
#endif
}

DriverError EspNowDriver::remove_peer(const MacAddress &peer_mac) {
#ifndef USE_ESP32
  (void) peer_mac;
  return DriverError::NOT_INITIALIZED;
#else
  if (!initialized_) {
    return DriverError::NOT_INITIALIZED;
  }
  const esp_err_t err = esp_now_del_peer(peer_mac.data());
  if (err == ESP_OK || err == ESP_ERR_ESPNOW_NOT_FOUND) {
    return DriverError::NONE;
  }
  return DriverError::PEER_CONFIG_FAILED;
#endif
}

DriverError EspNowDriver::send(
    const MacAddress &peer_mac,
    const uint8_t *data,
    std::size_t size) {
#ifndef USE_ESP32
  (void) peer_mac;
  (void) data;
  (void) size;
  return DriverError::NOT_INITIALIZED;
#else
  if (!initialized_) {
    return DriverError::NOT_INITIALIZED;
  }
  if (data == nullptr || size == 0 || size > kEspNowPhysicalDatagramLimit ||
      !esp_now_is_peer_exist(peer_mac.data())) {
    return DriverError::INVALID_ARGUMENT;
  }
  return esp_now_send(peer_mac.data(), data, size) == ESP_OK
             ? DriverError::NONE
             : DriverError::SEND_FAILED;
#endif
}

DriverError EspNowDriver::send_broadcast(
    const uint8_t *data,
    std::size_t size) {
#ifndef USE_ESP32
  (void) data;
  (void) size;
  return DriverError::NOT_INITIALIZED;
#else
  if (!initialized_) {
    return DriverError::NOT_INITIALIZED;
  }
  if (data == nullptr || size == 0 || size > kEspNowPhysicalDatagramLimit ||
      !esp_now_is_peer_exist(kEspNowBroadcastMac.data())) {
    return DriverError::INVALID_ARGUMENT;
  }
  return esp_now_send(kEspNowBroadcastMac.data(), data, size) == ESP_OK
             ? DriverError::NONE
             : DriverError::SEND_FAILED;
#endif
}

#ifdef USE_ESP32
void EspNowDriver::recv_cb_(
    const esp_now_recv_info_t *info,
    const uint8_t *data,
    int data_len) {
  if (active_ == nullptr || active_->sink_ == nullptr || info == nullptr ||
      info->src_addr == nullptr || data == nullptr || data_len <= 0 ||
      static_cast<std::size_t>(data_len) > kEspNowPhysicalDatagramLimit) {
    return;
  }
  MacAddress source{};
  std::copy_n(info->src_addr, source.size(), source.begin());
  EspNowReceiveMetadata metadata{};
  if (info->rx_ctrl != nullptr) {
    metadata.rssi_dbm = static_cast<int16_t>(info->rx_ctrl->rssi);
    metadata.channel = static_cast<uint8_t>(info->rx_ctrl->channel);
  }
  const uint8_t receive_index = active_->diagnostic_receive_logs_.fetch_add(
      1, std::memory_order_relaxed);
  if (receive_index < kDiagnosticLogLimit) {
    ESP_LOGI(TAG, "ESP-NOW diagnostic receive count=%u size=%d channel=%u",
             static_cast<unsigned>(receive_index + 1), data_len,
             static_cast<unsigned>(metadata.channel));
  }
  active_->sink_->on_espnow_receive_with_metadata(
      source, data, static_cast<std::size_t>(data_len), metadata);
}

#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 5, 0)
void EspNowDriver::send_cb_(
    const esp_now_send_info_t *info,
    esp_now_send_status_t status) {
  if (active_ == nullptr || active_->sink_ == nullptr || info == nullptr ||
      info->des_addr == nullptr) {
    return;
  }
  MacAddress destination{};
  std::copy_n(info->des_addr, destination.size(), destination.begin());
  if (destination == kEspNowBroadcastMac) {
    const uint8_t send_index = active_->diagnostic_broadcast_logs_.fetch_add(
        1, std::memory_order_relaxed);
    if (send_index < kDiagnosticLogLimit) {
      ESP_LOGI(TAG, "ESP-NOW diagnostic broadcast completion count=%u success=%s",
               static_cast<unsigned>(send_index + 1),
               status == ESP_NOW_SEND_SUCCESS ? "true" : "false");
    }
  }
  active_->sink_->on_espnow_send_result(
      destination, status == ESP_NOW_SEND_SUCCESS);
}
#else
void EspNowDriver::send_cb_(
    const uint8_t *mac_addr,
    esp_now_send_status_t status) {
  if (active_ == nullptr || active_->sink_ == nullptr || mac_addr == nullptr) {
    return;
  }
  MacAddress destination{};
  std::copy_n(mac_addr, destination.size(), destination.begin());
  if (destination == kEspNowBroadcastMac) {
    const uint8_t send_index = active_->diagnostic_broadcast_logs_.fetch_add(
        1, std::memory_order_relaxed);
    if (send_index < kDiagnosticLogLimit) {
      ESP_LOGI(TAG, "ESP-NOW diagnostic broadcast completion count=%u success=%s",
               static_cast<unsigned>(send_index + 1),
               status == ESP_NOW_SEND_SUCCESS ? "true" : "false");
    }
  }
  active_->sink_->on_espnow_send_result(
      destination, status == ESP_NOW_SEND_SUCCESS);
}
#endif
#endif

}  // namespace esphome::greenhouse_n3w_core
