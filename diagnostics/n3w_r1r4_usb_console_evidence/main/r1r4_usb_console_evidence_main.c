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

#define R1R3_HOME_CHANNEL 1
#define R1R3_TARGET_CHANNEL 6
#define R1R3_ROC_WAIT_MS 3000
#define R1R3_SWITCH_TX_WAIT_MS 200
#define R1R3_MAGIC 0x4E335233u
#define R1R3_HELLO_RETRY_MS 500
#define R1R3_CONTROL_PROBE_DELAY_MS 350
#define R1R3_ROC_PROBE_WAIT_MS 1500
#define R1R3_HOME_RECOVERY_TIMEOUT_MS 5000
#define R1R3_ROC_OP_ID 77

static const char *TAG = "n3w_r1r4_usb";
static const char *R1R3_AP_SSID = "N3W-R1R3-ROC";
static const char *R1R3_AP_PASS = "n3w-r1r3-test";
static const uint8_t kBroadcast[ESP_NOW_ETH_ALEN] = {0xff, 0xff, 0xff, 0xff, 0xff, 0xff};

#if CONFIG_R1R4_ROLE_CONTROL
#define R1R3_LOCAL_ROLE "CONTROL"
#define R1R3_IFIDX WIFI_IF_AP
#else
#define R1R3_LOCAL_ROLE "DUT"
#define R1R3_IFIDX WIFI_IF_STA
#endif

typedef enum {
    R1R3_MSG_HELLO = 1,
    R1R3_MSG_HELLO_ACK = 2,
    R1R3_MSG_START_ROC = 3,
    R1R3_MSG_ROC_ARMED = 4,
    R1R3_MSG_OFFCHANNEL_PROBE = 5,
    R1R3_MSG_HOME_ACK = 6,
    R1R4_MSG_CAPTURE_READY = 7,
} r1r3_msg_type_t;

typedef struct __attribute__((packed)) {
    uint32_t magic;
    uint8_t type;
    uint8_t seq;
    uint16_t reserved;
} r1r3_msg_t;

typedef struct {
    uint8_t src[ESP_NOW_ETH_ALEN];
    r1r3_msg_t msg;
    uint8_t rx_channel;
} r1r3_rx_event_t;

static QueueHandle_t s_rx_queue;
static EventGroupHandle_t s_events;
static uint8_t s_peer_mac[ESP_NOW_ETH_ALEN];
static bool s_peer_known;
static volatile bool s_roc_active;
static volatile bool s_roc_cancel_complete;
static uint32_t s_wifi_disconnect_count;
static bool s_baseline_pass;
static bool s_roc_req_ok;
static bool s_probe_rx_ok;
static bool s_roc_cancel_ok;
static bool s_home_recovery_ok;
static bool s_home_ack_ok;

#define EV_WIFI_LINK BIT0
#define EV_BASELINE BIT1
#define EV_START_ROC BIT2
#define EV_ROC_ARMED BIT3
#define EV_PROBE_RX BIT4
#define EV_HOME_ACK BIT5
#define EV_CAPTURE_ARMED BIT6
#define EV_DUT_CAPTURE_READY BIT7

#define R1R4_CAPTURE_HEARTBEAT_INTERVAL_MS 250
#define R1R4_CAPTURE_ARM_DELAY_MS 5000
#define R1R4_CAPTURE_READY_INTERVAL_MS 500

static void capture_evidence_task(void *arg) {
    (void)arg;
    uint32_t seq = 0;
    bool armed = false;
    TickType_t next_heartbeat = xTaskGetTickCount();
    const TickType_t deadline = next_heartbeat + pdMS_TO_TICKS(R1R4_CAPTURE_ARM_DELAY_MS);

    for (;;) {
        const TickType_t now = xTaskGetTickCount();
        if (!armed && now >= deadline) {
            armed = true;
            xEventGroupSetBits(s_events, EV_CAPTURE_ARMED);
            ESP_LOGI(TAG, "R1R4_LOCAL_CAPTURE_ARMED role=%s", R1R4_LOCAL_ROLE);
            next_heartbeat = now + pdMS_TO_TICKS(1000);
        }

        if (now >= next_heartbeat) {
            ESP_LOGI(TAG,
                     "R1R4_CAPTURE_HEARTBEAT role=%s phase=%s seq=%lu",
                     R1R4_LOCAL_ROLE,
                     armed ? "ARMED" : "PRE_ARM",
                     (unsigned long)seq++);
            next_heartbeat = now + pdMS_TO_TICKS(armed ? 1000 : R1R4_CAPTURE_HEARTBEAT_INTERVAL_MS);
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}

static void log_mac(const char *label, const uint8_t *mac) {
    ESP_LOGI(TAG, "%s=%02x:%02x:%02x:%02x:%02x:%02x",
             label,
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}

static bool get_current_channel(uint8_t *out) {
    uint8_t primary = 0;
    wifi_second_chan_t secondary = WIFI_SECOND_CHAN_NONE;
    const esp_err_t err = esp_wifi_get_channel(&primary, &secondary);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "R1R3_GET_CHANNEL role=%s result=%s", R1R3_LOCAL_ROLE, esp_err_to_name(err));
        return false;
    }
    if (out != NULL) *out = primary;
    return true;
}

static bool dut_sta_associated(void) {
#if CONFIG_R1R4_ROLE_DUT
    wifi_ap_record_t ap = {0};
    return esp_wifi_sta_get_ap_info(&ap) == ESP_OK;
#else
    return true;
#endif
}

static void log_state(const char *step) {
    uint8_t channel = 0;
    const bool channel_ok = get_current_channel(&channel);
#if CONFIG_R1R4_ROLE_DUT
    const bool associated = dut_sta_associated();
    ESP_LOGI(TAG,
             "R1R3_STATE role=DUT step=%s channel_ok=%s channel=%u associated=%s wifi_link=%s roc_active=%s cancel_complete=%s disconnect_count=%lu",
             step,
             channel_ok ? "true" : "false",
             (unsigned)channel,
             associated ? "true" : "false",
             (xEventGroupGetBits(s_events) & EV_WIFI_LINK) ? "true" : "false",
             s_roc_active ? "true" : "false",
             s_roc_cancel_complete ? "true" : "false",
             (unsigned long)s_wifi_disconnect_count);
#else
    ESP_LOGI(TAG,
             "R1R3_STATE role=CONTROL step=%s channel_ok=%s channel=%u ap_sta_link=%s",
             step,
             channel_ok ? "true" : "false",
             (unsigned)channel,
             (xEventGroupGetBits(s_events) & EV_WIFI_LINK) ? "true" : "false");
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

static esp_err_t send_normal(const uint8_t *dest, r1r3_msg_type_t type, uint8_t seq) {
    const r1r3_msg_t msg = {
        .magic = R1R3_MAGIC,
        .type = (uint8_t)type,
        .seq = seq,
        .reserved = 0,
    };
    const esp_err_t err = esp_now_send(dest, (const uint8_t *)&msg, sizeof(msg));
    ESP_LOGI(TAG,
             "R1R3_NORMAL_TX role=%s type=%u seq=%u result=%s",
             R1R3_LOCAL_ROLE,
             (unsigned)type,
             (unsigned)seq,
             esp_err_to_name(err));
    return err;
}

#if CONFIG_R1R4_ROLE_DUT
static esp_err_t send_capture_ready(uint8_t seq) {
    const esp_err_t err = send_normal(kBroadcast, R1R4_MSG_CAPTURE_READY, seq);
    ESP_LOGI(TAG,
             "R1R4_CAPTURE_READY_TX role=DUT seq=%u result=%s",
             (unsigned)seq,
             esp_err_to_name(err));
    return err;
}

static void capture_ready_task(void *arg) {
    (void)arg;
    uint8_t seq = 0;
    (void)xEventGroupWaitBits(s_events, EV_CAPTURE_ARMED, pdFALSE, pdTRUE, portMAX_DELAY);
    while ((xEventGroupGetBits(s_events) & EV_BASELINE) == 0) {
        (void)send_capture_ready(seq++);
        vTaskDelay(pdMS_TO_TICKS(R1R4_CAPTURE_READY_INTERVAL_MS));
    }
    vTaskDelete(NULL);
}
#endif

static esp_err_t send_offchannel(const uint8_t *dest, r1r3_msg_type_t type, uint8_t seq, uint8_t channel) {
    const size_t payload_len = sizeof(r1r3_msg_t);
    const size_t total_len = sizeof(esp_now_switch_channel_t) + payload_len;
    esp_now_switch_channel_t *cfg = calloc(1, total_len);
    if (cfg == NULL) return ESP_ERR_NO_MEM;

    cfg->type = WIFI_OFFCHAN_TX_REQ;
    cfg->channel = channel;
    cfg->sec_channel = WIFI_SECOND_CHAN_NONE;
    cfg->wait_time_ms = R1R3_SWITCH_TX_WAIT_MS;
    cfg->op_id = seq;
    memcpy(cfg->dest_mac, dest, ESP_NOW_ETH_ALEN);
    cfg->data_len = payload_len;

    const r1r3_msg_t msg = {
        .magic = R1R3_MAGIC,
        .type = (uint8_t)type,
        .seq = seq,
        .reserved = 0,
    };
    memcpy(cfg->data, &msg, payload_len);

    log_state("CONTROL_BEFORE_SWITCH_TX");
    const esp_err_t err = esp_now_switch_channel_tx(cfg);
    ESP_LOGI(TAG,
             "R1R3_SWITCH_CHANNEL_TX role=%s target=%u wait_ms=%u op_id=%u result=%s",
             R1R3_LOCAL_ROLE,
             (unsigned)channel,
             (unsigned)cfg->wait_time_ms,
             (unsigned)cfg->op_id,
             esp_err_to_name(err));
    log_state("CONTROL_AFTER_SWITCH_TX_RETURN");
    vTaskDelay(pdMS_TO_TICKS(R1R3_SWITCH_TX_WAIT_MS + 100));
    log_state("CONTROL_AFTER_SWITCH_TX_SETTLE");
    free(cfg);
    return err;
}

static esp_err_t roc_request(uint8_t channel, uint8_t op_id) {
    esp_now_remain_on_channel_t cfg = {
        .type = WIFI_ROC_REQ,
        .channel = channel,
        .sec_channel = WIFI_SECOND_CHAN_NONE,
        .wait_time_ms = R1R3_ROC_WAIT_MS,
        .op_id = op_id,
    };
    log_state("DUT_BEFORE_ROC_REQ");
    const esp_err_t err = esp_now_remain_on_channel(&cfg);
    ESP_LOGI(TAG,
             "R1R3_ROC_REQ role=DUT target=%u wait_ms=%u op_id=%u result=%s",
             (unsigned)channel,
             (unsigned)cfg.wait_time_ms,
             (unsigned)cfg.op_id,
             esp_err_to_name(err));
    log_state("DUT_AFTER_ROC_REQ_RETURN");
    return err;
}

static esp_err_t roc_cancel(uint8_t channel, uint8_t op_id) {
    esp_now_remain_on_channel_t cfg = {
        .type = WIFI_ROC_CANCEL,
        .channel = channel,
        .sec_channel = WIFI_SECOND_CHAN_NONE,
        .wait_time_ms = 0,
        .op_id = op_id,
    };
    log_state("DUT_BEFORE_ROC_CANCEL");
    const esp_err_t err = esp_now_remain_on_channel(&cfg);
    ESP_LOGI(TAG,
             "R1R3_ROC_CANCEL role=DUT target=%u wait_ms=%u op_id=%u result=%s",
             (unsigned)channel,
             (unsigned)cfg.wait_time_ms,
             (unsigned)cfg.op_id,
             esp_err_to_name(err));
    log_state("DUT_AFTER_ROC_CANCEL_RETURN");
    return err;
}

static void recv_cb(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
    if (info == NULL || info->src_addr == NULL || data == NULL || len != (int)sizeof(r1r3_msg_t)) {
        return;
    }
    r1r3_msg_t msg;
    memcpy(&msg, data, sizeof(msg));
    if (msg.magic != R1R3_MAGIC) return;

    r1r3_rx_event_t event = {0};
    memcpy(event.src, info->src_addr, ESP_NOW_ETH_ALEN);
    event.msg = msg;
    if (info->rx_ctrl != NULL) {
        event.rx_channel = (uint8_t)info->rx_ctrl->channel;
    }
    (void)xQueueSend(s_rx_queue, &event, 0);
}

static void send_cb(const esp_now_send_info_t *info, esp_now_send_status_t status) {
    if (info == NULL || info->des_addr == NULL) return;
    ESP_LOGI(TAG,
             "R1R3_SEND_CB role=%s dest=%02x:%02x:%02x:%02x:%02x:%02x status=%s",
             R1R3_LOCAL_ROLE,
             info->des_addr[0], info->des_addr[1], info->des_addr[2],
             info->des_addr[3], info->des_addr[4], info->des_addr[5],
             status == ESP_NOW_SEND_SUCCESS ? "SUCCESS" : "FAIL");
}

static void wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data) {
    (void)arg;
    (void)base;
    (void)data;
#if CONFIG_R1R4_ROLE_CONTROL
    if (id == WIFI_EVENT_AP_STACONNECTED) {
        xEventGroupSetBits(s_events, EV_WIFI_LINK);
        ESP_LOGI(TAG, "R1R3_WIFI_EVENT role=CONTROL AP_STA_CONNECTED");
    } else if (id == WIFI_EVENT_AP_STADISCONNECTED) {
        xEventGroupClearBits(s_events, EV_WIFI_LINK);
        ESP_LOGW(TAG, "R1R3_WIFI_EVENT role=CONTROL AP_STA_DISCONNECTED");
    }
#else
    if (id == WIFI_EVENT_STA_CONNECTED) {
        xEventGroupSetBits(s_events, EV_WIFI_LINK);
        ESP_LOGI(TAG, "R1R3_WIFI_EVENT role=DUT STA_CONNECTED");
    } else if (id == WIFI_EVENT_STA_DISCONNECTED) {
        s_wifi_disconnect_count++;
        xEventGroupClearBits(s_events, EV_WIFI_LINK);
        ESP_LOGW(TAG,
                 "R1R3_WIFI_EVENT role=DUT STA_DISCONNECTED count=%lu roc_active=%s cancel_complete=%s",
                 (unsigned long)s_wifi_disconnect_count,
                 s_roc_active ? "true" : "false",
                 s_roc_cancel_complete ? "true" : "false");
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
    strncpy((char *)ap.ap.ssid, R1R3_AP_SSID, sizeof(ap.ap.ssid) - 1);
    ap.ap.ssid_len = strlen(R1R3_AP_SSID);
    strncpy((char *)ap.ap.password, R1R3_AP_PASS, sizeof(ap.ap.password) - 1);
    ap.ap.channel = R1R3_HOME_CHANNEL;
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
    strncpy((char *)sta.sta.ssid, R1R3_AP_SSID, sizeof(sta.sta.ssid) - 1);
    strncpy((char *)sta.sta.password, R1R3_AP_PASS, sizeof(sta.sta.password) - 1);
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
    ESP_ERROR_CHECK(add_peer(kBroadcast, R1R3_IFIDX, R1R3_HOME_CHANNEL));
}

#if CONFIG_R1R4_ROLE_CONTROL
static void control_rx_task(void *arg) {
    (void)arg;
    for (;;) {
        r1r3_rx_event_t event;
        if (xQueueReceive(s_rx_queue, &event, portMAX_DELAY) != pdTRUE) continue;

        if (event.msg.type == R1R3_MSG_HELLO_ACK) {
            if (!s_peer_known) {
                memcpy(s_peer_mac, event.src, ESP_NOW_ETH_ALEN);
                s_peer_known = true;
                log_mac("R1R3_CONTROL_DUT_MAC", s_peer_mac);
                const esp_err_t peer_err = add_peer(s_peer_mac, WIFI_IF_AP, R1R3_HOME_CHANNEL);
                ESP_LOGI(TAG, "R1R3_CONTROL_ADD_DUT_PEER result=%s", esp_err_to_name(peer_err));
            }
            ESP_LOGI(TAG, "R1R3_BASELINE_ACK_RX channel=%u seq=%u",
                     (unsigned)event.rx_channel, (unsigned)event.msg.seq);
            if (event.rx_channel == R1R3_HOME_CHANNEL) {
                s_baseline_pass = true;
                xEventGroupSetBits(s_events, EV_BASELINE);
            }
        } else if (event.msg.type == R1R3_MSG_ROC_ARMED) {
            ESP_LOGI(TAG, "R1R3_ROC_ARMED_RX channel=%u seq=%u",
                     (unsigned)event.rx_channel, (unsigned)event.msg.seq);
            xEventGroupSetBits(s_events, EV_ROC_ARMED);
        } else if (event.msg.type == R1R3_MSG_HOME_ACK) {
            ESP_LOGI(TAG, "R1R3_HOME_ACK_RX channel=%u seq=%u",
                     (unsigned)event.rx_channel, (unsigned)event.msg.seq);
            if (event.rx_channel == R1R3_HOME_CHANNEL) {
                s_home_ack_ok = true;
                xEventGroupSetBits(s_events, EV_HOME_ACK);
            }
        } else if (event.msg.type == R1R4_MSG_CAPTURE_READY) {
            ESP_LOGI(TAG,
                     "R1R4_CAPTURE_READY_RX role=CONTROL channel=%u seq=%u",
                     (unsigned)event.rx_channel,
                     (unsigned)event.msg.seq);
            if (event.rx_channel == R1R3_HOME_CHANNEL) {
                xEventGroupSetBits(s_events, EV_DUT_CAPTURE_READY);
            }
        }
    }
}

static void control_task(void *arg) {
    (void)arg;
    ESP_LOGI(TAG, "R1R3_ROLE=CONTROL HOME_CHANNEL=%u TARGET_CHANNEL=%u",
             R1R3_HOME_CHANNEL, R1R3_TARGET_CHANNEL);

    (void)xEventGroupWaitBits(
        s_events,
        EV_CAPTURE_ARMED | EV_DUT_CAPTURE_READY,
        pdFALSE,
        pdTRUE,
        portMAX_DELAY);
    ESP_LOGI(TAG,
             "R1R4_LIFECYCLE_GATE_OPEN control_capture_armed=true dut_capture_ready=true");

    uint8_t hello_seq = 0;
    while ((xEventGroupGetBits(s_events) & EV_BASELINE) == 0) {
        if ((xEventGroupGetBits(s_events) & EV_WIFI_LINK) != 0) {
            (void)send_normal(kBroadcast, R1R3_MSG_HELLO, hello_seq++);
        }
        vTaskDelay(pdMS_TO_TICKS(R1R3_HELLO_RETRY_MS));
    }

    log_state("CONTROL_BASELINE_ESTABLISHED");
    ESP_LOGI(TAG, "R1R3_BASELINE_RESULT=PASS");
    vTaskDelay(pdMS_TO_TICKS(300));

    const esp_err_t start_err = send_normal(s_peer_mac, R1R3_MSG_START_ROC, 10);
    ESP_LOGI(TAG, "R1R3_START_ROC_TX result=%s", esp_err_to_name(start_err));

    const EventBits_t armed = xEventGroupWaitBits(
        s_events, EV_ROC_ARMED, pdFALSE, pdTRUE, pdMS_TO_TICKS(3000));
    if ((armed & EV_ROC_ARMED) == 0) {
        ESP_LOGE(TAG, "R1R3_CONTROL_STOP reason=ROC_ARMED_NOT_RECEIVED");
        log_state("CONTROL_STOP_NO_ARM");
        for (;;) vTaskDelay(pdMS_TO_TICKS(1000));
    }

    vTaskDelay(pdMS_TO_TICKS(R1R3_CONTROL_PROBE_DELAY_MS));
    const esp_err_t probe_err = send_offchannel(
        s_peer_mac, R1R3_MSG_OFFCHANNEL_PROBE, 55, R1R3_TARGET_CHANNEL);
    ESP_LOGI(TAG, "R1R3_CONTROL_PROBE_TX result=%s", esp_err_to_name(probe_err));

    const EventBits_t home_ack = xEventGroupWaitBits(
        s_events, EV_HOME_ACK, pdFALSE, pdTRUE, pdMS_TO_TICKS(7000));
    log_state("CONTROL_FINAL");
    ESP_LOGI(TAG,
             "R1R3_SUMMARY role=CONTROL baseline=%s probe_tx_api=%s home_ack=%s",
             s_baseline_pass ? "PASS" : "FAIL",
             probe_err == ESP_OK ? "PASS" : "FAIL",
             (home_ack & EV_HOME_ACK) && s_home_ack_ok ? "PASS" : "FAIL");

    for (;;) vTaskDelay(pdMS_TO_TICKS(1000));
}
#else
static void dut_rx_task(void *arg) {
    (void)arg;
    for (;;) {
        r1r3_rx_event_t event;
        if (xQueueReceive(s_rx_queue, &event, portMAX_DELAY) != pdTRUE) continue;

        if (event.msg.type == R1R3_MSG_HELLO) {
            if (!s_peer_known) {
                memcpy(s_peer_mac, event.src, ESP_NOW_ETH_ALEN);
                s_peer_known = true;
                log_mac("R1R3_DUT_CONTROL_MAC", s_peer_mac);
                const esp_err_t peer_err = add_peer(s_peer_mac, WIFI_IF_STA, R1R3_HOME_CHANNEL);
                ESP_LOGI(TAG, "R1R3_DUT_ADD_CONTROL_PEER result=%s", esp_err_to_name(peer_err));
            }
            (void)xEventGroupWaitBits(s_events, EV_CAPTURE_ARMED, pdFALSE, pdTRUE, portMAX_DELAY);
            ESP_LOGI(TAG,
                     "R1R4_LIFECYCLE_GATE_OPEN role=DUT local_capture_armed=true baseline_control_seen=true");
            const esp_err_t ack_err = send_normal(
                s_peer_mac, R1R3_MSG_HELLO_ACK, event.msg.seq);
            ESP_LOGI(TAG, "R1R3_BASELINE_ACK_TX channel=%u result=%s",
                     (unsigned)event.rx_channel, esp_err_to_name(ack_err));
            if (ack_err == ESP_OK && event.rx_channel == R1R3_HOME_CHANNEL) {
                s_baseline_pass = true;
                xEventGroupSetBits(s_events, EV_BASELINE);
            }
        } else if (event.msg.type == R1R3_MSG_START_ROC) {
            ESP_LOGI(TAG, "R1R3_START_ROC_RX channel=%u seq=%u",
                     (unsigned)event.rx_channel, (unsigned)event.msg.seq);
            xEventGroupSetBits(s_events, EV_START_ROC);
        } else if (event.msg.type == R1R3_MSG_OFFCHANNEL_PROBE) {
            ESP_LOGI(TAG, "R1R3_OFFCHANNEL_PROBE_RX channel=%u seq=%u",
                     (unsigned)event.rx_channel, (unsigned)event.msg.seq);
            if (event.rx_channel == R1R3_TARGET_CHANNEL) {
                s_probe_rx_ok = true;
                xEventGroupSetBits(s_events, EV_PROBE_RX);
            }
        }
    }
}

static void dut_experiment_task(void *arg) {
    (void)arg;
    ESP_LOGI(TAG, "R1R3_ROLE=DUT HOME_CHANNEL=%u TARGET_CHANNEL=%u",
             R1R3_HOME_CHANNEL, R1R3_TARGET_CHANNEL);

    (void)xEventGroupWaitBits(s_events, EV_BASELINE, pdFALSE, pdTRUE, portMAX_DELAY);
    log_state("DUT_BASELINE_ESTABLISHED");
    ESP_LOGI(TAG, "R1R3_BASELINE_RESULT=PASS");

    (void)xEventGroupWaitBits(s_events, EV_START_ROC, pdFALSE, pdTRUE, portMAX_DELAY);
    log_state("DUT_PRE_ARM");
    const esp_err_t armed_err = send_normal(s_peer_mac, R1R3_MSG_ROC_ARMED, 20);
    ESP_LOGI(TAG, "R1R3_ROC_ARMED_TX result=%s", esp_err_to_name(armed_err));
    vTaskDelay(pdMS_TO_TICKS(100));

    s_roc_active = true;
    s_roc_cancel_complete = false;
    const esp_err_t req_err = roc_request(R1R3_TARGET_CHANNEL, R1R3_ROC_OP_ID);
    s_roc_req_ok = req_err == ESP_OK;

    const EventBits_t probe = xEventGroupWaitBits(
        s_events, EV_PROBE_RX, pdFALSE, pdTRUE, pdMS_TO_TICKS(R1R3_ROC_PROBE_WAIT_MS));
    ESP_LOGI(TAG,
             "R1R3_PROBE_WAIT_RESULT received=%s",
             (probe & EV_PROBE_RX) && s_probe_rx_ok ? "true" : "false");
    log_state("DUT_BEFORE_EXPLICIT_CANCEL");

    esp_err_t cancel_err = ESP_FAIL;
    if (s_roc_req_ok) {
        cancel_err = roc_cancel(R1R3_TARGET_CHANNEL, R1R3_ROC_OP_ID);
        s_roc_cancel_ok = cancel_err == ESP_OK;
    } else {
        ESP_LOGW(TAG, "R1R3_ROC_CANCEL skipped=true reason=ROC_REQ_FAILED");
    }
    s_roc_active = false;
    s_roc_cancel_complete = true;

    log_state("DUT_POST_CANCEL_IMMEDIATE");
    vTaskDelay(pdMS_TO_TICKS(100));
    log_state("DUT_POST_CANCEL_100MS");
    vTaskDelay(pdMS_TO_TICKS(400));
    log_state("DUT_POST_CANCEL_500MS");

    const TickType_t deadline = xTaskGetTickCount() + pdMS_TO_TICKS(R1R3_HOME_RECOVERY_TIMEOUT_MS);
    unsigned reconnect_attempt = 0;
    while (xTaskGetTickCount() < deadline) {
        uint8_t channel = 0;
        const bool channel_ok = get_current_channel(&channel);
        const bool associated = dut_sta_associated();
        if (channel_ok && channel == R1R3_HOME_CHANNEL && associated) {
            s_home_recovery_ok = true;
            break;
        }
        reconnect_attempt++;
        const esp_err_t reconnect_err = esp_wifi_connect();
        ESP_LOGI(TAG,
                 "R1R3_RECONNECT_REQUEST attempt=%u result=%s",
                 reconnect_attempt,
                 esp_err_to_name(reconnect_err));
        vTaskDelay(pdMS_TO_TICKS(500));
    }

    log_state("DUT_HOME_RECOVERY_FINAL");
    esp_err_t home_ack_err = ESP_FAIL;
    if (s_home_recovery_ok) {
        home_ack_err = send_normal(s_peer_mac, R1R3_MSG_HOME_ACK, 66);
        s_home_ack_ok = home_ack_err == ESP_OK;
    }
    ESP_LOGI(TAG, "R1R3_HOME_ACK_TX result=%s", esp_err_to_name(home_ack_err));

    ESP_LOGI(TAG,
             "R1R3_SUMMARY role=DUT baseline=%s roc_req=%s probe_rx=%s roc_cancel=%s home_recovery=%s home_ack_tx=%s disconnect_count=%lu",
             s_baseline_pass ? "PASS" : "FAIL",
             s_roc_req_ok ? "PASS" : "FAIL",
             s_probe_rx_ok ? "PASS" : "FAIL",
             s_roc_cancel_ok ? "PASS" : "FAIL",
             s_home_recovery_ok ? "PASS" : "FAIL",
             s_home_ack_ok ? "PASS" : "FAIL",
             (unsigned long)s_wifi_disconnect_count);

    for (;;) vTaskDelay(pdMS_TO_TICKS(1000));
}
#endif

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
    s_rx_queue = xQueueCreate(16, sizeof(r1r3_rx_event_t));
    if (s_events == NULL || s_rx_queue == NULL) abort();

#if CONFIG_R1R4_ROLE_CONTROL
    wifi_init_control();
#else
    wifi_init_dut();
#endif
    espnow_init_common();

    uint8_t own_mac[ESP_NOW_ETH_ALEN] = {0};
#if CONFIG_R1R4_ROLE_CONTROL
    ESP_ERROR_CHECK(esp_read_mac(own_mac, ESP_MAC_WIFI_SOFTAP));
#else
    ESP_ERROR_CHECK(esp_read_mac(own_mac, ESP_MAC_WIFI_STA));
#endif
    log_mac("R1R3_LOCAL_MAC", own_mac);
    log_state("BOOT");

    xTaskCreate(capture_evidence_task, "r1r4_capture", 3072, NULL, 3, NULL);

#if CONFIG_R1R4_ROLE_CONTROL
    xTaskCreate(control_rx_task, "r1r3_control_rx", 4096, NULL, 5, NULL);
    xTaskCreate(control_task, "r1r3_control", 6144, NULL, 4, NULL);
#else
    xTaskCreate(dut_rx_task, "r1r3_dut_rx", 4096, NULL, 5, NULL);
    xTaskCreate(dut_experiment_task, "r1r3_dut_exp", 6144, NULL, 4, NULL);
    xTaskCreate(capture_ready_task, "r1r4_ready", 3072, NULL, 4, NULL);
#endif
}
