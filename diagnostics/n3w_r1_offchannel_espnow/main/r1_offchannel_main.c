#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_wifi.h"

#define R1_HOME_CHANNEL 1
#define R1_TARGET_CHANNEL 6
#define R1_OFFCHANNEL_WAIT_MS 700
#define R1_SWITCH_TX_WAIT_MS 200
#define R1_MAGIC 0x4E335231u
#define R1_READY_RETRY_MS 500
#define R1_RESULT_SETTLE_MS 1200

static const char *TAG = "n3w_r1_offchan";
static const char *R1_AP_SSID = "N3W-R1-OFFCHAN";
static const char *R1_AP_PASS = "n3w-r1-test";
static const uint8_t kBroadcast[ESP_NOW_ETH_ALEN] = {0xff, 0xff, 0xff, 0xff, 0xff, 0xff};

#if CONFIG_R1_ROLE_CONTROL
#define R1_LOCAL_ROLE "CONTROL"
#define R1_IFIDX WIFI_IF_AP
#else
#define R1_LOCAL_ROLE "DUT"
#define R1_IFIDX WIFI_IF_STA
#endif

typedef enum {
    R1_MSG_READY = 1,
    R1_MSG_BASELINE_ACK = 2,
    R1_MSG_ARM_B = 3,
    R1_MSG_PROBE_B = 4,
    R1_MSG_ARM_C = 5,
    R1_MSG_PROBE_C = 6,
} r1_msg_type_t;

typedef struct __attribute__((packed)) {
    uint32_t magic;
    uint8_t type;
    uint8_t seq;
    uint16_t reserved;
} r1_msg_t;

typedef struct {
    uint8_t src[ESP_NOW_ETH_ALEN];
    r1_msg_t msg;
    uint8_t rx_channel;
} r1_rx_event_t;

static QueueHandle_t s_rx_queue;
static EventGroupHandle_t s_events;
static uint8_t s_peer_mac[ESP_NOW_ETH_ALEN];
static bool s_peer_known;
static uint32_t s_wifi_disconnect_count;
static uint8_t s_home_channel_before;
static uint8_t s_home_channel_after;
static bool s_r1a_pass;
static bool s_r1b_pass;
static bool s_r1c_pass;
static bool s_r1d_pass;

#define EV_WIFI_LINK BIT0
#define EV_BASELINE BIT1
#define EV_R1B_RX BIT2
#define EV_R1C_RX BIT3

static void log_mac(const char *label, const uint8_t *mac) {
    ESP_LOGI(TAG, "%s=%02x:%02x:%02x:%02x:%02x:%02x",
             label,
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}

static bool get_current_channel(uint8_t *out) {
    wifi_second_chan_t second = WIFI_SECOND_CHAN_NONE;
    uint8_t primary = 0;
    if (esp_wifi_get_channel(&primary, &second) != ESP_OK) {
        return false;
    }
    if (out != NULL) *out = primary;
    return true;
}

static bool dut_sta_associated(void) {
#if CONFIG_R1_ROLE_DUT
    wifi_ap_record_t ap = {0};
    return esp_wifi_sta_get_ap_info(&ap) == ESP_OK;
#else
    return true;
#endif
}

static esp_err_t add_peer(const uint8_t *mac, wifi_interface_t ifidx, uint8_t channel) {
    esp_now_peer_info_t peer = {0};
    memcpy(peer.peer_addr, mac, ESP_NOW_ETH_ALEN);
    peer.channel = channel;
    peer.ifidx = ifidx;
    peer.encrypt = false;
    if (esp_now_is_peer_exist(mac)) {
        return esp_now_mod_peer(&peer);
    }
    return esp_now_add_peer(&peer);
}

static esp_err_t send_normal(const uint8_t *dest, r1_msg_type_t type, uint8_t seq) {
    r1_msg_t msg = {
        .magic = R1_MAGIC,
        .type = (uint8_t)type,
        .seq = seq,
        .reserved = 0,
    };
    return esp_now_send(dest, (const uint8_t *)&msg, sizeof(msg));
}

static esp_err_t send_offchannel(const uint8_t *dest, r1_msg_type_t type, uint8_t seq, uint8_t channel) {
    const size_t payload_len = sizeof(r1_msg_t);
    const size_t total = sizeof(esp_now_switch_channel_t) + payload_len;
    esp_now_switch_channel_t *cfg = calloc(1, total);
    if (cfg == NULL) return ESP_ERR_NO_MEM;

    cfg->type = WIFI_OFFCHAN_TX_REQ;
    cfg->channel = channel;
    cfg->sec_channel = WIFI_SECOND_CHAN_NONE;
    cfg->wait_time_ms = R1_SWITCH_TX_WAIT_MS;
    cfg->op_id = seq;
    memcpy(cfg->dest_mac, dest, ESP_NOW_ETH_ALEN);
    cfg->data_len = payload_len;

    r1_msg_t msg = {
        .magic = R1_MAGIC,
        .type = (uint8_t)type,
        .seq = seq,
        .reserved = 0,
    };
    memcpy(cfg->data, &msg, payload_len);

    const esp_err_t err = esp_now_switch_channel_tx(cfg);
    ESP_LOGI(TAG,
             "R1_SWITCH_CHANNEL_TX role=%s type=%u target=%u wait_ms=%u result=%s",
             R1_LOCAL_ROLE,
             (unsigned)type,
             (unsigned)channel,
             (unsigned)cfg->wait_time_ms,
             esp_err_to_name(err));
    vTaskDelay(pdMS_TO_TICKS(R1_SWITCH_TX_WAIT_MS + 100));
    free(cfg);
    return err;
}

static esp_err_t remain_on_channel(uint8_t channel, uint8_t op_id) {
    esp_now_remain_on_channel_t cfg = {
        .type = WIFI_ROC_REQ,
        .channel = channel,
        .sec_channel = WIFI_SECOND_CHAN_NONE,
        .wait_time_ms = R1_OFFCHANNEL_WAIT_MS,
        .op_id = op_id,
    };
    const esp_err_t err = esp_now_remain_on_channel(&cfg);
    ESP_LOGI(TAG,
             "R1_REMAIN_ON_CHANNEL role=%s target=%u wait_ms=%u result=%s",
             R1_LOCAL_ROLE,
             (unsigned)channel,
             (unsigned)cfg.wait_time_ms,
             esp_err_to_name(err));
    return err;
}

static void recv_cb(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
    if (info == NULL || info->src_addr == NULL || data == NULL || len != (int)sizeof(r1_msg_t)) {
        return;
    }
    r1_msg_t msg;
    memcpy(&msg, data, sizeof(msg));
    if (msg.magic != R1_MAGIC) return;

    r1_rx_event_t evt = {0};
    memcpy(evt.src, info->src_addr, ESP_NOW_ETH_ALEN);
    evt.msg = msg;
    if (info->rx_ctrl != NULL) {
        evt.rx_channel = (uint8_t)info->rx_ctrl->channel;
    }
    (void)xQueueSend(s_rx_queue, &evt, 0);
}

static void send_cb(const esp_now_send_info_t *info, esp_now_send_status_t status) {
    if (info == NULL || info->des_addr == NULL) return;
    ESP_LOGI(TAG,
             "R1_SEND_CB role=%s dest=%02x:%02x:%02x:%02x:%02x:%02x status=%s",
             R1_LOCAL_ROLE,
             info->des_addr[0], info->des_addr[1], info->des_addr[2],
             info->des_addr[3], info->des_addr[4], info->des_addr[5],
             status == ESP_NOW_SEND_SUCCESS ? "SUCCESS" : "FAIL");
}

static void wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data) {
    (void)arg;
    (void)base;
    (void)data;
#if CONFIG_R1_ROLE_CONTROL
    if (id == WIFI_EVENT_AP_STACONNECTED) {
        xEventGroupSetBits(s_events, EV_WIFI_LINK);
        ESP_LOGI(TAG, "R1_WIFI_EVENT role=CONTROL AP_STA_CONNECTED");
    } else if (id == WIFI_EVENT_AP_STADISCONNECTED) {
        xEventGroupClearBits(s_events, EV_WIFI_LINK);
        ESP_LOGW(TAG, "R1_WIFI_EVENT role=CONTROL AP_STA_DISCONNECTED");
    }
#else
    if (id == WIFI_EVENT_STA_CONNECTED) {
        xEventGroupSetBits(s_events, EV_WIFI_LINK);
        ESP_LOGI(TAG, "R1_WIFI_EVENT role=DUT STA_CONNECTED");
    } else if (id == WIFI_EVENT_STA_DISCONNECTED) {
        s_wifi_disconnect_count++;
        xEventGroupClearBits(s_events, EV_WIFI_LINK);
        ESP_LOGW(TAG, "R1_WIFI_EVENT role=DUT STA_DISCONNECTED count=%lu",
                 (unsigned long)s_wifi_disconnect_count);
        (void)esp_wifi_connect();
    }
#endif
}

static void wifi_init_control(void) {
    esp_netif_create_default_wifi_ap();
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));

    wifi_config_t ap = {0};
    strncpy((char *)ap.ap.ssid, R1_AP_SSID, sizeof(ap.ap.ssid) - 1);
    ap.ap.ssid_len = strlen(R1_AP_SSID);
    strncpy((char *)ap.ap.password, R1_AP_PASS, sizeof(ap.ap.password) - 1);
    ap.ap.channel = R1_HOME_CHANNEL;
    ap.ap.authmode = WIFI_AUTH_WPA2_PSK;
    ap.ap.max_connection = 1;
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap));
    ESP_ERROR_CHECK(esp_wifi_start());
}

static void wifi_init_dut(void) {
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));

    wifi_config_t sta = {0};
    strncpy((char *)sta.sta.ssid, R1_AP_SSID, sizeof(sta.sta.ssid) - 1);
    strncpy((char *)sta.sta.password, R1_AP_PASS, sizeof(sta.sta.password) - 1);
    sta.sta.scan_method = WIFI_FAST_SCAN;
    sta.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &sta));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_connect());
}

static void espnow_init_common(void) {
    ESP_ERROR_CHECK(esp_now_init());
    ESP_ERROR_CHECK(esp_now_register_recv_cb(recv_cb));
    ESP_ERROR_CHECK(esp_now_register_send_cb(send_cb));
    ESP_ERROR_CHECK(add_peer(kBroadcast, R1_IFIDX, R1_HOME_CHANNEL));
}

static void control_task(void *arg) {
    (void)arg;
    ESP_LOGI(TAG, "R1_ROLE=CONTROL HOME_CHANNEL=%u TARGET_CHANNEL=%u",
             R1_HOME_CHANNEL, R1_TARGET_CHANNEL);

    uint8_t ready_seq = 0;
    while ((xEventGroupGetBits(s_events) & EV_BASELINE) == 0) {
        if ((xEventGroupGetBits(s_events) & EV_WIFI_LINK) != 0) {
            const esp_err_t err = send_normal(kBroadcast, R1_MSG_READY, ready_seq++);
            ESP_LOGI(TAG, "R1A_READY_BROADCAST result=%s", esp_err_to_name(err));
        }
        vTaskDelay(pdMS_TO_TICKS(R1_READY_RETRY_MS));
    }

    s_r1a_pass = true;
    ESP_LOGI(TAG, "R1A_RESULT=PASS");
    vTaskDelay(pdMS_TO_TICKS(400));

    ESP_ERROR_CHECK(add_peer(s_peer_mac, WIFI_IF_AP, R1_HOME_CHANNEL));
    ESP_LOGI(TAG, "R1B_ARM_SEND");
    ESP_ERROR_CHECK(send_normal(s_peer_mac, R1_MSG_ARM_B, 1));
    vTaskDelay(pdMS_TO_TICKS(100));
    const esp_err_t roc_b = remain_on_channel(R1_TARGET_CHANNEL, 11);
    vTaskDelay(pdMS_TO_TICKS(R1_RESULT_SETTLE_MS));
    s_r1b_pass = (roc_b == ESP_OK) && ((xEventGroupGetBits(s_events) & EV_R1B_RX) != 0);
    ESP_LOGI(TAG, "R1B_RESULT=%s", s_r1b_pass ? "PASS" : "FAIL");

    vTaskDelay(pdMS_TO_TICKS(500));
    ESP_LOGI(TAG, "R1C_ARM_SEND");
    ESP_ERROR_CHECK(send_normal(s_peer_mac, R1_MSG_ARM_C, 2));
    vTaskDelay(pdMS_TO_TICKS(250));
    const esp_err_t tx_c = send_offchannel(s_peer_mac, R1_MSG_PROBE_C, 22, R1_TARGET_CHANNEL);
    vTaskDelay(pdMS_TO_TICKS(R1_RESULT_SETTLE_MS));
    s_r1c_pass = tx_c == ESP_OK;
    ESP_LOGI(TAG, "R1C_CONTROL_TX_RESULT=%s", s_r1c_pass ? "PASS" : "FAIL");

    vTaskDelay(pdMS_TO_TICKS(1200));
    s_r1d_pass = get_current_channel(&s_home_channel_after) &&
                   s_home_channel_after == R1_HOME_CHANNEL;
    ESP_LOGI(TAG,
             "R1D_RESULT role=CONTROL home_before=%u home_after=%u wifi_link=%s result=%s",
             (unsigned)s_home_channel_before,
             (unsigned)s_home_channel_after,
             (xEventGroupGetBits(s_events) & EV_WIFI_LINK) ? "true" : "false",
             s_r1d_pass ? "PASS" : "FAIL");

    ESP_LOGI(TAG,
             "R1_SUMMARY role=CONTROL R1A=%s R1B=%s R1C_TX=%s R1D=%s",
             s_r1a_pass ? "PASS" : "FAIL",
             s_r1b_pass ? "PASS" : "FAIL",
             s_r1c_pass ? "PASS" : "FAIL",
             s_r1d_pass ? "PASS" : "FAIL");

    for (;;) vTaskDelay(pdMS_TO_TICKS(1000));
}

static void dut_task(void *arg) {
    (void)arg;
    ESP_LOGI(TAG, "R1_ROLE=DUT HOME_CHANNEL=%u TARGET_CHANNEL=%u",
             R1_HOME_CHANNEL, R1_TARGET_CHANNEL);

    for (;;) {
        r1_rx_event_t evt;
        if (xQueueReceive(s_rx_queue, &evt, portMAX_DELAY) != pdTRUE) continue;

        if (evt.msg.type == R1_MSG_READY) {
            if (!s_peer_known) {
                memcpy(s_peer_mac, evt.src, ESP_NOW_ETH_ALEN);
                s_peer_known = true;
                log_mac("R1_DUT_CONTROL_MAC", s_peer_mac);
                ESP_ERROR_CHECK(add_peer(s_peer_mac, WIFI_IF_STA, R1_HOME_CHANNEL));
            }
            if ((xEventGroupGetBits(s_events) & EV_BASELINE) == 0) {
                const esp_err_t err = send_normal(s_peer_mac, R1_MSG_BASELINE_ACK, evt.msg.seq);
                ESP_LOGI(TAG, "R1A_BASELINE_ACK result=%s rx_channel=%u",
                         esp_err_to_name(err), (unsigned)evt.rx_channel);
                if (err == ESP_OK) {
                    xEventGroupSetBits(s_events, EV_BASELINE);
                    s_r1a_pass = true;
                    ESP_LOGI(TAG, "R1A_RESULT=PASS");
                }
            }
        } else if (evt.msg.type == R1_MSG_ARM_B) {
            ESP_LOGI(TAG, "R1B_ARM_RX rx_channel=%u", (unsigned)evt.rx_channel);
            vTaskDelay(pdMS_TO_TICKS(250));
            const esp_err_t err = send_offchannel(evt.src, R1_MSG_PROBE_B, 33, R1_TARGET_CHANNEL);
            ESP_LOGI(TAG, "R1B_DUT_TX_RESULT=%s", err == ESP_OK ? "PASS" : "FAIL");
        } else if (evt.msg.type == R1_MSG_ARM_C) {
            ESP_LOGI(TAG, "R1C_ARM_RX rx_channel=%u", (unsigned)evt.rx_channel);
            vTaskDelay(pdMS_TO_TICKS(100));
            const esp_err_t err = remain_on_channel(R1_TARGET_CHANNEL, 44);
            ESP_LOGI(TAG, "R1C_DUT_ROC_RESULT=%s", err == ESP_OK ? "PASS" : "FAIL");
        } else if (evt.msg.type == R1_MSG_PROBE_C) {
            ESP_LOGI(TAG, "R1C_PROBE_RX rx_channel=%u seq=%u",
                     (unsigned)evt.rx_channel, (unsigned)evt.msg.seq);
            if (evt.rx_channel == R1_TARGET_CHANNEL) {
                xEventGroupSetBits(s_events, EV_R1C_RX);
                s_r1c_pass = true;
            }

            vTaskDelay(pdMS_TO_TICKS(1200));
            s_r1d_pass = get_current_channel(&s_home_channel_after) &&
                           s_home_channel_after == R1_HOME_CHANNEL &&
                           dut_sta_associated();
            ESP_LOGI(TAG,
                     "R1D_RESULT role=DUT home_before=%u home_after=%u sta_associated=%s disconnect_count=%lu result=%s",
                     (unsigned)s_home_channel_before,
                     (unsigned)s_home_channel_after,
                     dut_sta_associated() ? "true" : "false",
                     (unsigned long)s_wifi_disconnect_count,
                     s_r1d_pass ? "PASS" : "FAIL");
            ESP_LOGI(TAG,
                     "R1_SUMMARY role=DUT R1A=%s R1B_TX=OBSERVED_IN_LOG R1C_RX=%s R1D=%s",
                     s_r1a_pass ? "PASS" : "FAIL",
                     s_r1c_pass ? "PASS" : "FAIL",
                     s_r1d_pass ? "PASS" : "FAIL");
        }
    }
}

static void control_rx_task(void *arg) {
    (void)arg;
    for (;;) {
        r1_rx_event_t evt;
        if (xQueueReceive(s_rx_queue, &evt, portMAX_DELAY) != pdTRUE) continue;

        if (evt.msg.type == R1_MSG_BASELINE_ACK) {
            if (!s_peer_known) {
                memcpy(s_peer_mac, evt.src, ESP_NOW_ETH_ALEN);
                s_peer_known = true;
                log_mac("R1_CONTROL_DUT_MAC", s_peer_mac);
            }
            ESP_LOGI(TAG, "R1A_BASELINE_ACK_RX channel=%u", (unsigned)evt.rx_channel);
            xEventGroupSetBits(s_events, EV_BASELINE);
        } else if (evt.msg.type == R1_MSG_PROBE_B) {
            ESP_LOGI(TAG, "R1B_PROBE_RX channel=%u seq=%u",
                     (unsigned)evt.rx_channel, (unsigned)evt.msg.seq);
            if (evt.rx_channel == R1_TARGET_CHANNEL) {
                xEventGroupSetBits(s_events, EV_R1B_RX);
            }
        }
    }
}

void app_main(void) {
    esp_err_t nvs = nvs_flash_init();
    if (nvs == ESP_ERR_NVS_NO_FREE_PAGES || nvs == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    } else {
        ESP_ERROR_CHECK(nvs);
    }

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    s_events = xEventGroupCreate();
    s_rx_queue = xQueueCreate(16, sizeof(r1_rx_event_t));
    if (s_events == NULL || s_rx_queue == NULL) {
        abort();
    }

#if CONFIG_R1_ROLE_CONTROL
    wifi_init_control();
#else
    wifi_init_dut();
#endif

    espnow_init_common();
    ESP_ERROR_CHECK(get_current_channel(&s_home_channel_before) ? ESP_OK : ESP_FAIL);

    uint8_t own_mac[ESP_NOW_ETH_ALEN] = {0};
#if CONFIG_R1_ROLE_CONTROL
    ESP_ERROR_CHECK(esp_read_mac(own_mac, ESP_MAC_WIFI_SOFTAP));
#else
    ESP_ERROR_CHECK(esp_read_mac(own_mac, ESP_MAC_WIFI_STA));
#endif
    log_mac("R1_LOCAL_MAC", own_mac);
    ESP_LOGI(TAG,
             "R1_BOOT role=%s home_channel=%u target_channel=%u",
             R1_LOCAL_ROLE,
             (unsigned)R1_HOME_CHANNEL,
             (unsigned)R1_TARGET_CHANNEL);

#if CONFIG_R1_ROLE_CONTROL
    xTaskCreate(control_rx_task, "r1_control_rx", 4096, NULL, 5, NULL);
    xTaskCreate(control_task, "r1_control", 6144, NULL, 4, NULL);
#else
    xTaskCreate(dut_task, "r1_dut", 6144, NULL, 4, NULL);
#endif
}
