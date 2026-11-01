#pragma once
#include <cstddef>
#include <cstdint>
#include "esp_wifi.h"

constexpr esp_err_t ESP_ERR_ESPNOW_NOT_INIT = 0x3065;
constexpr esp_err_t ESP_ERR_ESPNOW_NOT_FOUND = 0x3066;
constexpr esp_err_t ESP_ERR_ESPNOW_INTERNAL = 0x3067;
constexpr esp_err_t ESP_ERR_ESPNOW_ARG = 0x3068;
constexpr int ESP_NOW_KEY_LEN = 16;
#define ESP_NOW_MAX_DATA_LEN_V2 1470

enum esp_now_send_status_t : int {
  ESP_NOW_SEND_SUCCESS = 0,
  ESP_NOW_SEND_FAIL = 1,
};

struct esp_now_recv_info_t {
  const uint8_t *src_addr{nullptr};
  wifi_pkt_rx_ctrl_t *rx_ctrl{nullptr};
};

struct esp_now_send_info_t {
  const uint8_t *des_addr{nullptr};
};

using esp_now_recv_cb_t =
    void (*)(const esp_now_recv_info_t *, const uint8_t *, int);
using esp_now_send_cb_t =
    void (*)(const esp_now_send_info_t *, esp_now_send_status_t);

struct esp_now_peer_info_t {
  uint8_t peer_addr[6]{};
  uint8_t lmk[16]{};
  uint8_t channel{0};
  wifi_interface_t ifidx{WIFI_IF_STA};
  bool encrypt{false};
};

constexpr uint8_t WIFI_OFFCHAN_TX_REQ = 1;

struct esp_now_switch_channel_t {
  uint8_t type{0};
  uint8_t channel{0};
  wifi_second_chan_t sec_channel{WIFI_SECOND_CHAN_NONE};
  uint32_t wait_time_ms{0};
  uint8_t dest_mac[6]{};
  uint16_t data_len{0};
  uint32_t op_id{0};
  uint8_t data[1]{};
};

esp_err_t esp_now_init();
esp_err_t esp_now_deinit();
esp_err_t esp_now_set_pmk(const uint8_t *pmk);
esp_err_t esp_now_register_recv_cb(esp_now_recv_cb_t cb);
esp_err_t esp_now_register_send_cb(esp_now_send_cb_t cb);
esp_err_t esp_now_unregister_recv_cb();
esp_err_t esp_now_unregister_send_cb();
bool esp_now_is_peer_exist(const uint8_t *peer_addr);
esp_err_t esp_now_add_peer(const esp_now_peer_info_t *peer);
esp_err_t esp_now_mod_peer(const esp_now_peer_info_t *peer);
esp_err_t esp_now_del_peer(const uint8_t *peer_addr);
esp_err_t esp_now_get_peer(const uint8_t *peer_addr, esp_now_peer_info_t *peer);
esp_err_t esp_now_send(const uint8_t *peer_addr, const uint8_t *data, size_t len);
esp_err_t esp_now_switch_channel_tx(esp_now_switch_channel_t *config);
