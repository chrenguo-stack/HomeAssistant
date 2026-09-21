#include "n3w_espnow_driver.h"
#include "n3w_recovery_exit_policy.h"

#include <algorithm>
#include <cstdlib>
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
}

std::atomic<uint16_t> EspNowDriver::callbacks_inflight_{0};

#ifdef USE_ESP32
std::atomic<EspNowDriver *> EspNowDriver::active_{nullptr};
#endif

#ifdef USE_ESP32
DriverError EspNowDriver::start_wifi_(bool start_standalone_wifi) {
  wifi_mode_t mode{};
  const esp_err_t mode_error = esp_wifi_get_mode(&mode);
  if (mode_error == ESP_OK) {
    if (start_standalone_wifi) {
      if (esp_wifi_set_mode(WIFI_MODE_STA) != ESP_OK ||
          esp_wifi_start() != ESP_OK) {
        return DriverError::WIFI_START_FAILED;
      }
      wifi_started_by_driver_ = true;
      return DriverError::NONE;
    }
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
  wifi_initialized_by_driver_ = true;
  if (esp_wifi_set_storage(WIFI_STORAGE_RAM) != ESP_OK ||
      esp_wifi_set_mode(WIFI_MODE_STA) != ESP_OK ||
      esp_wifi_start() != ESP_OK) {
    teardown_confirmed_ = stop_owned_wifi_();
    return DriverError::WIFI_START_FAILED;
  }
  wifi_started_by_driver_ = true;
  return DriverError::NONE;
}

bool EspNowDriver::stop_owned_wifi_() {
  bool stopped = true;
  if (wifi_started_by_driver_) {
    const esp_err_t result = esp_wifi_stop();
    const bool ok = result == ESP_OK || result == ESP_ERR_WIFI_NOT_INIT;
    stopped = stopped && ok;
    if (ok) wifi_started_by_driver_ = false;
  }
  if (wifi_initialized_by_driver_) {
    const esp_err_t result = esp_wifi_deinit();
    const bool ok = result == ESP_OK || result == ESP_ERR_WIFI_NOT_INIT;
    stopped = stopped && ok;
    if (ok) wifi_initialized_by_driver_ = false;
  }
  return stopped;
}
#endif

DriverError EspNowDriver::initialize(EspNowEventSink *sink, const LinkKey &pmk) {
#ifdef USE_ESP32
  return initialize_(sink, pmk, false);
#else
  (void) sink;
  (void) pmk;
  return DriverError::ESPNOW_INIT_FAILED;
#endif
}

DriverError EspNowDriver::initialize_standalone(
    EspNowEventSink *sink,
    const LinkKey &pmk) {
#ifdef USE_ESP32
  return initialize_(sink, pmk, true);
#else
  (void) sink;
  (void) pmk;
  return DriverError::ESPNOW_INIT_FAILED;
#endif
}

#ifdef USE_ESP32
DriverError EspNowDriver::initialize_(
    EspNowEventSink *sink,
    const LinkKey &pmk,
    bool start_standalone_wifi) {
  if (sink == nullptr || std::all_of(pmk.begin(), pmk.end(), [](uint8_t b) { return b == 0; })) {
    return DriverError::INVALID_ARGUMENT;
  }
  if (!teardown_confirmed_) {
    return DriverError::ESPNOW_TEARDOWN_UNCONFIRMED;
  }
  if (initialized_ || espnow_started_ ||
      active_.load(std::memory_order_acquire) != nullptr ||
      !callbacks_idle()) {
    return DriverError::ALREADY_INITIALIZED;
  }
  const DriverError wifi_error = start_wifi_(start_standalone_wifi);
  if (wifi_error != DriverError::NONE) {
    return wifi_error;
  }
  if (esp_now_init() != ESP_OK) {
    teardown_confirmed_ = stop_owned_wifi_();
    return DriverError::ESPNOW_INIT_FAILED;
  }
  espnow_started_ = true;

  if (esp_now_set_pmk(pmk.data()) != ESP_OK) {
    const bool espnow_stopped = esp_now_deinit() == ESP_OK;
    if (espnow_stopped) {
      espnow_started_ = false;
    }
    const bool wifi_stopped = stop_owned_wifi_();
    const EspNowTeardownDecision decision =
        assess_espnow_teardown(
            espnow_stopped,
            wifi_stopped,
            callbacks_idle());
    teardown_confirmed_ = decision.confirmed;
    espnow_started_ = decision.keep_espnow_started;
    return DriverError::ESPNOW_PMK_FAILED;
  }
  sink_.store(sink, std::memory_order_release);
  active_.store(this, std::memory_order_release);
  last_channel_error_raw_ = 0;
  last_channel_observed_ = 0;
  last_broadcast_send_error_ = DriverError::NONE;
  last_broadcast_send_error_raw_ = 0;
  last_unicast_send_error_ = DriverError::NONE;
  last_unicast_send_error_raw_ = 0;
  pending_unicast_sends_.store(0, std::memory_order_release);
  if (esp_now_register_recv_cb(&EspNowDriver::recv_cb_) != ESP_OK ||
      esp_now_register_send_cb(&EspNowDriver::send_cb_) != ESP_OK) {
    esp_now_unregister_recv_cb();
    esp_now_unregister_send_cb();
    active_.store(nullptr, std::memory_order_release);
    sink_.store(nullptr, std::memory_order_release);
    const bool espnow_stopped = esp_now_deinit() == ESP_OK;
    if (espnow_stopped) {
      espnow_started_ = false;
    }
    const bool wifi_stopped = stop_owned_wifi_();
    const EspNowTeardownDecision decision =
        assess_espnow_teardown(
            espnow_stopped,
            wifi_stopped,
            callbacks_idle());
    teardown_confirmed_ = decision.confirmed;
    espnow_started_ = decision.keep_espnow_started;
    return DriverError::ESPNOW_CALLBACK_FAILED;
  }
  initialized_ = true;
  teardown_confirmed_ = true;
  return DriverError::NONE;
}
#endif

bool EspNowDriver::shutdown() {
#ifdef USE_ESP32
  const uint16_t pending =
      pending_unicast_sends_.load(std::memory_order_acquire);
  if (pending != 0U) {
    ESP_LOGW(
        TAG,
        "ESP-NOW shutdown with pending unicast completions count=%u",
        static_cast<unsigned>(pending));
  }

  // Detach the global callback target first. Any callback that begins after
  // this store observes no active driver. A callback that already captured
  // this driver is tracked by callbacks_inflight_ and must drain before a new
  // ESP-NOW session may initialize.
  EspNowDriver *expected = this;
  (void) active_.compare_exchange_strong(
      expected,
      nullptr,
      std::memory_order_acq_rel,
      std::memory_order_acquire);
  sink_.store(nullptr, std::memory_order_release);

  if (initialized_) {
    const esp_err_t send_unregister = esp_now_unregister_send_cb();
    const esp_err_t recv_unregister = esp_now_unregister_recv_cb();
    if ((send_unregister != ESP_OK &&
         send_unregister != ESP_ERR_ESPNOW_NOT_INIT) ||
        (recv_unregister != ESP_OK &&
         recv_unregister != ESP_ERR_ESPNOW_NOT_INIT)) {
      ESP_LOGW(
          TAG,
          "ESP-NOW callback unregister status send_cb=%ld recv_cb=%ld",
          static_cast<long>(send_unregister),
          static_cast<long>(recv_unregister));
    }
  }

  bool espnow_stopped = !espnow_started_;
  if (espnow_started_) {
    const esp_err_t deinit = esp_now_deinit();
    espnow_stopped = deinit == ESP_OK;
    if (espnow_stopped) {
      espnow_started_ = false;
      initialized_ = false;
    } else {
      ESP_LOGE(
          TAG,
          "ESP-NOW shutdown could not confirm SDK deinit result=%ld",
          static_cast<long>(deinit));
    }
  }

  const bool wifi_stopped = stop_owned_wifi_();
  const EspNowTeardownDecision decision =
      assess_espnow_teardown(
          espnow_stopped,
          wifi_stopped,
          callbacks_idle());
  teardown_confirmed_ = decision.confirmed;
  espnow_started_ = decision.keep_espnow_started;
#else
  teardown_confirmed_ = true;
  espnow_started_ = false;
  initialized_ = false;
#endif
  sink_.store(nullptr, std::memory_order_release);
  if (teardown_confirmed_) {
    initialized_ = false;
    pending_unicast_sends_.store(0, std::memory_order_release);
  }
  return teardown_confirmed_;
}

void EspNowDriver::complete_unicast_send_() {
  uint16_t pending =
      pending_unicast_sends_.load(std::memory_order_acquire);
  while (pending != 0U &&
         !pending_unicast_sends_.compare_exchange_weak(
             pending,
             static_cast<uint16_t>(pending - 1U),
             std::memory_order_acq_rel,
             std::memory_order_acquire)) {
  }
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
  last_channel_observed_ = 0;
  const esp_err_t set_result =
      esp_wifi_set_channel(channel, WIFI_SECOND_CHAN_NONE);
  if (set_result != ESP_OK) {
    last_channel_error_raw_ = static_cast<int32_t>(set_result);
    return DriverError::WIFI_CHANNEL_FAILED;
  }

  wifi_second_chan_t secondary = WIFI_SECOND_CHAN_NONE;
  uint8_t observed = 0;
  const esp_err_t get_result = esp_wifi_get_channel(&observed, &secondary);
  if (get_result != ESP_OK) {
    last_channel_error_raw_ = static_cast<int32_t>(get_result);
    return DriverError::WIFI_CHANNEL_FAILED;
  }
  last_channel_observed_ = observed;
  if (observed != channel) {
    last_channel_error_raw_ = static_cast<int32_t>(ESP_FAIL);
    return DriverError::WIFI_CHANNEL_FAILED;
  }
  last_channel_error_raw_ = 0;
  return DriverError::NONE;
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
  last_unicast_send_error_ = DriverError::NONE;
  last_unicast_send_error_raw_ = 0;
#ifndef USE_ESP32
  (void) peer_mac;
  (void) data;
  (void) size;
  last_unicast_send_error_ = DriverError::NOT_INITIALIZED;
  return last_unicast_send_error_;
#else
  if (!initialized_) {
    last_unicast_send_error_ = DriverError::NOT_INITIALIZED;
    return last_unicast_send_error_;
  }
  if (data == nullptr || size == 0 || size > kEspNowPhysicalDatagramLimit ||
      !esp_now_is_peer_exist(peer_mac.data())) {
    last_unicast_send_error_ = DriverError::INVALID_ARGUMENT;
    return last_unicast_send_error_;
  }

  // Increment before esp_now_send(): the Wi-Fi task may run the completion
  // callback before this function returns. Synchronous submission failures are
  // the only path that removes the reservation here.
  pending_unicast_sends_.fetch_add(1U, std::memory_order_acq_rel);
  const esp_err_t send_result = esp_now_send(peer_mac.data(), data, size);
  if (send_result != ESP_OK) {
    complete_unicast_send_();
  }
  last_unicast_send_error_raw_ = static_cast<int32_t>(send_result);
  last_unicast_send_error_ =
      send_result == ESP_OK ? DriverError::NONE : DriverError::SEND_FAILED;
  return last_unicast_send_error_;
#endif
}

DriverError EspNowDriver::send_broadcast(
    const uint8_t *data,
    std::size_t size) {
  last_broadcast_send_error_ = DriverError::NONE;
  last_broadcast_send_error_raw_ = 0;
#ifndef USE_ESP32
  (void) data;
  (void) size;
  last_broadcast_send_error_ = DriverError::NOT_INITIALIZED;
  return last_broadcast_send_error_;
#else
  if (!initialized_) {
    last_broadcast_send_error_ = DriverError::NOT_INITIALIZED;
    return last_broadcast_send_error_;
  }
  if (data == nullptr || size == 0 || size > kEspNowPhysicalDatagramLimit ||
      !esp_now_is_peer_exist(kEspNowBroadcastMac.data())) {
    last_broadcast_send_error_ = DriverError::INVALID_ARGUMENT;
    return last_broadcast_send_error_;
  }
  const esp_err_t send_result =
      esp_now_send(kEspNowBroadcastMac.data(), data, size);
  last_broadcast_send_error_raw_ = static_cast<int32_t>(send_result);
  last_broadcast_send_error_ =
      send_result == ESP_OK ? DriverError::NONE : DriverError::SEND_FAILED;
  return last_broadcast_send_error_;
#endif
}


DriverError EspNowDriver::send_broadcast_on_channel(
    uint8_t channel,
    const uint8_t *data,
    std::size_t size,
    uint32_t wait_time_ms) {
  last_broadcast_send_error_ = DriverError::NONE;
  last_broadcast_send_error_raw_ = 0;
#ifndef USE_ESP32
  (void) channel;
  (void) data;
  (void) size;
  (void) wait_time_ms;
  last_broadcast_send_error_ = DriverError::NOT_INITIALIZED;
  return last_broadcast_send_error_;
#else
  if (!initialized_) {
    last_broadcast_send_error_ = DriverError::NOT_INITIALIZED;
    return last_broadcast_send_error_;
  }
  if (!valid_radio_channel(channel) || data == nullptr || size == 0 ||
      size > kEspNowPhysicalDatagramLimit || wait_time_ms == 0 ||
      !esp_now_is_peer_exist(kEspNowBroadcastMac.data())) {
    last_broadcast_send_error_ = DriverError::INVALID_ARGUMENT;
    return last_broadcast_send_error_;
  }

#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 5, 0)
  const std::size_t allocation_size =
      sizeof(esp_now_switch_channel_t) + size;
  auto *config = static_cast<esp_now_switch_channel_t *>(
      std::calloc(1, allocation_size));
  if (config == nullptr) {
    last_broadcast_send_error_ = DriverError::SEND_FAILED;
    last_broadcast_send_error_raw_ = static_cast<int32_t>(ESP_ERR_NO_MEM);
    return last_broadcast_send_error_;
  }

  config->type = WIFI_OFFCHAN_TX_REQ;
  config->channel = channel;
  config->sec_channel = WIFI_SECOND_CHAN_NONE;
  config->wait_time_ms = wait_time_ms;
  std::memcpy(
      config->dest_mac,
      kEspNowBroadcastMac.data(),
      kEspNowBroadcastMac.size());
  config->data_len = static_cast<uint16_t>(size);
  std::memcpy(config->data, data, size);

  // op_id is intentionally left zero-initialized. ESP-IDF supplies the
  // operation identifier; this path does not issue an explicit cancellation.
  const esp_err_t send_result = esp_now_switch_channel_tx(config);
  std::free(config);

  last_broadcast_send_error_raw_ = static_cast<int32_t>(send_result);
  last_broadcast_send_error_ =
      send_result == ESP_OK ? DriverError::NONE : DriverError::SEND_FAILED;
  return last_broadcast_send_error_;
#else
  last_broadcast_send_error_ = DriverError::SEND_FAILED;
  last_broadcast_send_error_raw_ =
      static_cast<int32_t>(ESP_ERR_NOT_SUPPORTED);
  return last_broadcast_send_error_;
#endif
#endif
}

#ifdef USE_ESP32
void EspNowDriver::recv_cb_(
    const esp_now_recv_info_t *info,
    const uint8_t *data,
    int data_len) {
  if (info == nullptr || info->src_addr == nullptr || data == nullptr ||
      data_len <= 0 ||
      static_cast<std::size_t>(data_len) > kEspNowPhysicalDatagramLimit) {
    return;
  }

  callbacks_inflight_.fetch_add(1U, std::memory_order_acq_rel);
  EspNowDriver *driver = active_.load(std::memory_order_acquire);
  if (driver == nullptr) {
    callbacks_inflight_.fetch_sub(1U, std::memory_order_acq_rel);
    return;
  }
  EspNowEventSink *sink = driver->sink_.load(std::memory_order_acquire);
  if (sink == nullptr) {
    callbacks_inflight_.fetch_sub(1U, std::memory_order_acq_rel);
    return;
  }

  MacAddress source{};
  std::copy_n(info->src_addr, source.size(), source.begin());
  EspNowReceiveMetadata metadata{};
  if (info->rx_ctrl != nullptr) {
    metadata.rssi_dbm = static_cast<int16_t>(info->rx_ctrl->rssi);
    metadata.channel = static_cast<uint8_t>(info->rx_ctrl->channel);
  }
  sink->on_espnow_receive_with_metadata(
      source, data, static_cast<std::size_t>(data_len), metadata);
  callbacks_inflight_.fetch_sub(1U, std::memory_order_acq_rel);
}

#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 5, 0)
void EspNowDriver::send_cb_(
    const esp_now_send_info_t *info,
    esp_now_send_status_t status) {
  if (info == nullptr || info->des_addr == nullptr) return;

  callbacks_inflight_.fetch_add(1U, std::memory_order_acq_rel);
  EspNowDriver *driver = active_.load(std::memory_order_acquire);
  if (driver == nullptr) {
    callbacks_inflight_.fetch_sub(1U, std::memory_order_acq_rel);
    return;
  }
  EspNowEventSink *sink = driver->sink_.load(std::memory_order_acquire);
  if (sink == nullptr) {
    callbacks_inflight_.fetch_sub(1U, std::memory_order_acq_rel);
    return;
  }

  MacAddress destination{};
  std::copy_n(info->des_addr, destination.size(), destination.begin());
  sink->on_espnow_send_result(
      destination, status == ESP_NOW_SEND_SUCCESS);
  // Decrement only after the sink has copied completion metadata into its
  // bounded ring. A zero pending count is therefore safe for the component to
  // use as a radio-transition barrier.
  if (destination != kEspNowBroadcastMac) {
    driver->complete_unicast_send_();
  }
  callbacks_inflight_.fetch_sub(1U, std::memory_order_acq_rel);
}
#else
void EspNowDriver::send_cb_(
    const uint8_t *mac_addr,
    esp_now_send_status_t status) {
  if (mac_addr == nullptr) return;

  callbacks_inflight_.fetch_add(1U, std::memory_order_acq_rel);
  EspNowDriver *driver = active_.load(std::memory_order_acquire);
  if (driver == nullptr) {
    callbacks_inflight_.fetch_sub(1U, std::memory_order_acq_rel);
    return;
  }
  EspNowEventSink *sink = driver->sink_.load(std::memory_order_acquire);
  if (sink == nullptr) {
    callbacks_inflight_.fetch_sub(1U, std::memory_order_acq_rel);
    return;
  }

  MacAddress destination{};
  std::copy_n(mac_addr, destination.size(), destination.begin());
  sink->on_espnow_send_result(
      destination, status == ESP_NOW_SEND_SUCCESS);
  // Decrement only after the sink has copied completion metadata into its
  // bounded ring. A zero pending count is therefore safe for the component to
  // use as a radio-transition barrier.
  if (destination != kEspNowBroadcastMac) {
    driver->complete_unicast_send_();
  }
  callbacks_inflight_.fetch_sub(1U, std::memory_order_acq_rel);
}
#endif
#endif

}  // namespace esphome::greenhouse_n3w_core
