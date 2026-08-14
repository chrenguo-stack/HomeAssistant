#include "n3w_espnow_driver.h"

#include <algorithm>
#include <cstring>

#ifdef USE_ESP32
#include "esp_now.h"
#include "esp_wifi.h"
#endif

namespace esphome::greenhouse_n3w_core {

#ifdef USE_ESP32
EspNowDriver *EspNowDriver::active_ = nullptr;
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
  if (esp_now_init() != ESP_OK) {
    return DriverError::ESPNOW_INIT_FAILED;
  }
  if (esp_now_set_pmk(pmk.data()) != ESP_OK) {
    esp_now_deinit();
    return DriverError::ESPNOW_PMK_FAILED;
  }
  active_ = this;
  sink_ = sink;
  if (esp_now_register_recv_cb(&EspNowDriver::recv_cb_) != ESP_OK ||
      esp_now_register_send_cb(&EspNowDriver::send_cb_) != ESP_OK) {
    esp_now_unregister_recv_cb();
    esp_now_unregister_send_cb();
    active_ = nullptr;
    sink_ = nullptr;
    esp_now_deinit();
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
  if (data == nullptr || size == 0 || size > kEspNowDatagramLimit ||
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
  if (data == nullptr || size == 0 || size > kEspNowDatagramLimit ||
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
      static_cast<std::size_t>(data_len) > kEspNowDatagramLimit) {
    return;
  }
  MacAddress source{};
  std::copy_n(info->src_addr, source.size(), source.begin());
  EspNowReceiveMetadata metadata{};
  if (info->rx_ctrl != nullptr) {
    metadata.rssi_dbm = static_cast<int16_t>(info->rx_ctrl->rssi);
    metadata.channel = static_cast<uint8_t>(info->rx_ctrl->channel);
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
  active_->sink_->on_espnow_send_result(
      destination, status == ESP_NOW_SEND_SUCCESS);
}
#endif
#endif

}  // namespace esphome::greenhouse_n3w_core
