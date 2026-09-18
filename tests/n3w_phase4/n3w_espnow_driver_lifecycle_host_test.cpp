#include <cassert>
#include <cstddef>
#include <cstdint>

#include "n3w_espnow_driver.h"

using esphome::greenhouse_n3w_core::DriverError;
using esphome::greenhouse_n3w_core::EspNowDriver;
using esphome::greenhouse_n3w_core::EspNowEventSink;
using esphome::greenhouse_n3w_core::LinkKey;
using esphome::greenhouse_n3w_core::MacAddress;

namespace {

struct FakeSdk {
  esp_err_t init_result{ESP_OK};
  esp_err_t pmk_result{ESP_OK};
  esp_err_t recv_register_result{ESP_OK};
  esp_err_t send_register_result{ESP_OK};
  esp_err_t deinit_results[8]{ESP_OK, ESP_OK, ESP_OK, ESP_OK,
                              ESP_OK, ESP_OK, ESP_OK, ESP_OK};
  int init_calls{0};
  int deinit_calls{0};
  int recv_unregister_calls{0};
  int send_unregister_calls{0};
};

FakeSdk sdk;

void reset_sdk() {
  sdk = FakeSdk{};
}

void set_deinit_results(
    esp_err_t first,
    esp_err_t second = ESP_OK,
    esp_err_t third = ESP_OK,
    esp_err_t fourth = ESP_OK) {
  sdk.deinit_results[0] = first;
  sdk.deinit_results[1] = second;
  sdk.deinit_results[2] = third;
  sdk.deinit_results[3] = fourth;
}

class Sink final : public EspNowEventSink {
 public:
  void on_espnow_receive(
      const MacAddress &, const uint8_t *, std::size_t) override {}
  void on_espnow_send_result(const MacAddress &, bool) override {}
};

LinkKey valid_pmk() {
  LinkKey pmk{};
  pmk.fill(0x42);
  return pmk;
}

}  // namespace

esp_err_t esp_event_loop_create_default() { return ESP_OK; }
esp_err_t esp_netif_init() { return ESP_OK; }

esp_err_t esp_wifi_get_mode(wifi_mode_t *mode) {
  if (mode != nullptr) *mode = WIFI_MODE_STA;
  return ESP_OK;
}
esp_err_t esp_wifi_set_mode(wifi_mode_t) { return ESP_OK; }
esp_err_t esp_wifi_start() { return ESP_OK; }
esp_err_t esp_wifi_stop() { return ESP_OK; }
esp_err_t esp_wifi_init(const wifi_init_config_t *) { return ESP_OK; }
esp_err_t esp_wifi_deinit() { return ESP_OK; }
esp_err_t esp_wifi_set_storage(wifi_storage_t) { return ESP_OK; }
esp_err_t esp_wifi_get_channel(
    uint8_t *primary, wifi_second_chan_t *secondary) {
  if (primary != nullptr) *primary = 6;
  if (secondary != nullptr) *secondary = WIFI_SECOND_CHAN_NONE;
  return ESP_OK;
}
esp_err_t esp_wifi_set_channel(uint8_t, wifi_second_chan_t) { return ESP_OK; }

esp_err_t esp_now_init() {
  ++sdk.init_calls;
  return sdk.init_result;
}
esp_err_t esp_now_deinit() {
  const int index = sdk.deinit_calls++;
  return index < 8 ? sdk.deinit_results[index] : ESP_OK;
}
esp_err_t esp_now_set_pmk(const uint8_t *) { return sdk.pmk_result; }
esp_err_t esp_now_register_recv_cb(esp_now_recv_cb_t) {
  return sdk.recv_register_result;
}
esp_err_t esp_now_register_send_cb(esp_now_send_cb_t) {
  return sdk.send_register_result;
}
esp_err_t esp_now_unregister_recv_cb() {
  ++sdk.recv_unregister_calls;
  return ESP_OK;
}
esp_err_t esp_now_unregister_send_cb() {
  ++sdk.send_unregister_calls;
  return ESP_OK;
}
bool esp_now_is_peer_exist(const uint8_t *) { return true; }
esp_err_t esp_now_add_peer(const esp_now_peer_info_t *) { return ESP_OK; }
esp_err_t esp_now_mod_peer(const esp_now_peer_info_t *) { return ESP_OK; }
esp_err_t esp_now_del_peer(const uint8_t *) { return ESP_OK; }
esp_err_t esp_now_get_peer(const uint8_t *, esp_now_peer_info_t *peer) {
  if (peer != nullptr) peer->channel = 6;
  return ESP_OK;
}
esp_err_t esp_now_send(const uint8_t *, const uint8_t *, size_t) {
  return ESP_OK;
}
esp_err_t esp_now_switch_channel_tx(esp_now_switch_channel_t *) {
  return ESP_OK;
}

namespace esphome::greenhouse_n3w_core {

bool valid_radio_channel(uint8_t channel) {
  return channel >= 1 && channel <= 14;
}

bool RelayPeerBinding::valid() const {
  return true;
}

}  // namespace esphome::greenhouse_n3w_core

int main() {
  Sink sink;
  const LinkKey pmk = valid_pmk();

  // A1 regression: PMK failure after esp_now_init(), followed by failed
  // rollback deinit, must retain "SDK started" state. Repeated shutdown must
  // retry deinit, and initialize must stay fenced until deinit succeeds.
  {
    reset_sdk();
    sdk.pmk_result = ESP_FAIL;
    set_deinit_results(ESP_FAIL, ESP_FAIL, ESP_OK, ESP_OK);

    EspNowDriver driver;
    assert(driver.initialize(&sink, pmk) == DriverError::ESPNOW_PMK_FAILED);
    assert(!driver.initialized());
    assert(driver.espnow_started());
    assert(!driver.teardown_confirmed());
    assert(sdk.init_calls == 1);
    assert(sdk.deinit_calls == 1);

    assert(!driver.shutdown());
    assert(driver.espnow_started());
    assert(!driver.teardown_confirmed());
    assert(sdk.deinit_calls == 2);

    assert(driver.initialize(&sink, pmk) ==
           DriverError::ESPNOW_TEARDOWN_UNCONFIRMED);
    assert(sdk.init_calls == 1);

    assert(driver.shutdown());
    assert(!driver.espnow_started());
    assert(driver.teardown_confirmed());
    assert(sdk.deinit_calls == 3);

    sdk.pmk_result = ESP_OK;
    assert(driver.initialize(&sink, pmk) == DriverError::NONE);
    assert(sdk.init_calls == 2);
    assert(driver.initialized());
    assert(driver.espnow_started());
    assert(driver.shutdown());
  }

  // A1 regression: callback-registration failure has the same partial-init
  // obligation and must not be "washed clean" by a shutdown that skips deinit.
  {
    reset_sdk();
    sdk.send_register_result = ESP_FAIL;
    set_deinit_results(ESP_FAIL, ESP_FAIL, ESP_OK, ESP_OK);

    EspNowDriver driver;
    assert(driver.initialize(&sink, pmk) ==
           DriverError::ESPNOW_CALLBACK_FAILED);
    assert(!driver.initialized());
    assert(driver.espnow_started());
    assert(!driver.teardown_confirmed());
    assert(sdk.init_calls == 1);
    assert(sdk.deinit_calls == 1);
    assert(sdk.recv_unregister_calls == 1);
    assert(sdk.send_unregister_calls == 1);

    assert(!driver.shutdown());
    assert(driver.espnow_started());
    assert(sdk.deinit_calls == 2);
    assert(driver.initialize(&sink, pmk) ==
           DriverError::ESPNOW_TEARDOWN_UNCONFIRMED);
    assert(sdk.init_calls == 1);

    assert(driver.shutdown());
    assert(!driver.espnow_started());
    assert(driver.teardown_confirmed());
    assert(sdk.deinit_calls == 3);

    sdk.send_register_result = ESP_OK;
    assert(driver.initialize(&sink, pmk) == DriverError::NONE);
    assert(sdk.init_calls == 2);
    assert(driver.shutdown());
  }

  // Fully initialized sessions also keep their teardown obligation when
  // deinit fails, then recover only after a later successful deinit.
  {
    reset_sdk();
    set_deinit_results(ESP_FAIL, ESP_OK);

    EspNowDriver driver;
    assert(driver.initialize(&sink, pmk) == DriverError::NONE);
    assert(driver.initialized());
    assert(driver.espnow_started());

    assert(!driver.shutdown());
    assert(driver.initialized());
    assert(driver.espnow_started());
    assert(!driver.teardown_confirmed());

    assert(driver.initialize(&sink, pmk) ==
           DriverError::ESPNOW_TEARDOWN_UNCONFIRMED);
    assert(sdk.init_calls == 1);

    assert(driver.shutdown());
    assert(!driver.initialized());
    assert(!driver.espnow_started());
    assert(driver.teardown_confirmed());
  }

  return 0;
}
