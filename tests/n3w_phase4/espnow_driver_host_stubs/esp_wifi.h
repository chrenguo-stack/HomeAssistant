#pragma once
#include <cstdint>

using esp_err_t = int;
constexpr esp_err_t ESP_OK = 0;
constexpr esp_err_t ESP_FAIL = -1;
constexpr esp_err_t ESP_ERR_INVALID_STATE = 0x103;
constexpr esp_err_t ESP_ERR_NO_MEM = 0x101;
constexpr esp_err_t ESP_ERR_NOT_SUPPORTED = 0x106;
constexpr esp_err_t ESP_ERR_WIFI_NOT_INIT = 0x3001;

enum wifi_mode_t : int {
  WIFI_MODE_NULL = 0,
  WIFI_MODE_STA = 1,
};
enum wifi_second_chan_t : int {
  WIFI_SECOND_CHAN_NONE = 0,
};
enum wifi_storage_t : int {
  WIFI_STORAGE_RAM = 0,
};
enum wifi_interface_t : int {
  WIFI_IF_STA = 0,
};

struct wifi_pkt_rx_ctrl_t {
  int rssi{0};
  int channel{0};
};

struct wifi_init_config_t {
  int dummy{0};
};

#define WIFI_INIT_CONFIG_DEFAULT() wifi_init_config_t{}

esp_err_t esp_wifi_get_mode(wifi_mode_t *mode);
esp_err_t esp_wifi_set_mode(wifi_mode_t mode);
esp_err_t esp_wifi_start();
esp_err_t esp_wifi_stop();
esp_err_t esp_wifi_init(const wifi_init_config_t *config);
esp_err_t esp_wifi_deinit();
esp_err_t esp_wifi_set_storage(wifi_storage_t storage);
esp_err_t esp_wifi_get_channel(uint8_t *primary, wifi_second_chan_t *secondary);
esp_err_t esp_wifi_set_channel(uint8_t primary, wifi_second_chan_t secondary);
