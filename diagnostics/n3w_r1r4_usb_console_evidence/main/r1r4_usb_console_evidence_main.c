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
#include "r1r4_operation_state.h"

#define R1R3_HOME_CHANNEL 1
#define R1R3_TARGET_CHANNEL 6
#define R1R3_ROC_WAIT_MS 3000
#define R1R3_SWITCH_TX_WAIT_MS 200
#define R1R3_MAGIC 0x4E335233u
#define R1R3_HELLO_RETRY_MS 500
#define R1R3_CONTROL_PROBE_DELAY_MS 350
#define R1R3_ROC_PROBE_WAIT_MS 1500
#define R1R3_HOME_RECOVERY_TIMEOUT_MS 5000
#define R1R3_INITIAL_ASSOC_MAX_ATTEMPTS 3
#define R1R3_INITIAL_ASSOC_TIMEOUT_MS 15000
#define R1R3_INITIAL_ASSOC_ATTEMPT_WAIT_MS 5000
#define R1R3_BASELINE_TIMEOUT_MS 15000
#define R1R3_OFFCHANNEL_START_TIMEOUT_MS 15000

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
static bool s_home_recovery_ok;
static bool s_home_ack_ok;
static bool s_home_ack_received;
static volatile bool s_initial_assoc_active;
static volatile uint8_t s_initial_assoc_last_disconnect_reason;
static uint8_t s_initial_assoc_attempts;
static esp_err_t s_initial_assoc_last_result = ESP_FAIL;

typedef enum {
    R1R4_OP_EVENT_ACTION_TX = 1,
    R1R4_OP_EVENT_ROC_DONE = 2,
} r1r4_op_event_kind_t;

typedef struct {
    r1r4_op_event_kind_t kind;
    uint8_t op_id;
    uint8_t channel;
    uint8_t status;
} r1r4_op_event_t;

typedef enum {
    R1R4_ASYNC_UNKNOWN = 0,
    R1R4_ASYNC_PASS,
    R1R4_ASYNC_FAIL,
} r1r4_async_result_t;

static QueueHandle_t s_op_event_queue;
static volatile bool s_op_event_queue_overflow;
static bool s_control_tx_done;
static bool s_control_tx_failed;
static bool s_control_tx_duration_complete;
static bool s_control_tx_cancelled;
static uint8_t s_control_tx_driver_op_id;
static uint8_t s_control_tx_request_op_id;
static bool s_control_home_channel_api_ok;
static uint8_t s_control_home_channel;
static bool s_control_home_ap_link;
static bool s_control_home_return;
static bool s_roc_natural_complete;
static bool s_roc_cancel_requested;
static bool s_roc_cancel_api_ok;
static bool s_roc_termination_observed;
static bool s_roc_termination_wait_ok;
static uint8_t s_roc_request_op_id;
static uint8_t s_roc_driver_op_id;
static uint8_t s_roc_completion_status;
static bool s_home_ack_api_ok;
static r1r4_async_result_t s_home_ack_send_callback = R1R4_ASYNC_UNKNOWN;
static volatile bool s_home_ack_callback_waiting;
static volatile bool s_home_ack_callback_seen;
static volatile bool s_home_ack_callback_ambiguous;
static volatile uint32_t s_non_home_send_callbacks_pending;

#define EV_WIFI_LINK BIT0
#define EV_BASELINE BIT1
#define EV_START_ROC BIT2
#define EV_ROC_ARMED BIT3
#define EV_PROBE_RX BIT4
#define EV_HOME_ACK BIT5
#define EV_CAPTURE_ARMED BIT6
#define EV_DUT_CAPTURE_READY BIT7
#define EV_HOME_ACK_SEND_CALLBACK BIT8

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
            ESP_LOGI(TAG, "R1R4_LOCAL_CAPTURE_ARMED role=%s", R1R3_LOCAL_ROLE);
            next_heartbeat = now + pdMS_TO_TICKS(1000);
        }

        if (now >= next_heartbeat) {
            ESP_LOGI(TAG,
                     "R1R4_CAPTURE_HEARTBEAT role=%s phase=%s seq=%lu",
                     R1R3_LOCAL_ROLE,
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

static const char *action_tx_status_name(uint8_t status) {
    switch ((wifi_action_tx_status_type_t)status) {
        case WIFI_ACTION_TX_DONE: return "TX_DONE";
        case WIFI_ACTION_TX_FAILED: return "TX_FAILED";
        case WIFI_ACTION_TX_DURATION_COMPLETED: return "TX_DURATION_COMPLETED";
        case WIFI_ACTION_TX_OP_CANCELLED: return "TX_OP_CANCELLED";
        default: return "UNKNOWN";
    }
}

static const char *roc_status_name(uint8_t status) {
    switch ((wifi_roc_done_status_t)status) {
        case WIFI_ROC_DONE: return "WIFI_ROC_DONE";
        case WIFI_ROC_FAIL: return "WIFI_ROC_FAIL";
        default: return "UNKNOWN";
    }
}

static const char *async_result_name(r1r4_async_result_t result) {
    switch (result) {
        case R1R4_ASYNC_PASS: return "PASS";
        case R1R4_ASYNC_FAIL: return "FAIL";
        default: return "UNKNOWN";
    }
}

static bool wait_for_action_tx_completion(uint8_t expected_op_id, uint32_t timeout_ms) {
    const TickType_t deadline = xTaskGetTickCount() + pdMS_TO_TICKS(timeout_ms);
    while (xTaskGetTickCount() < deadline) {
        r1r4_op_event_t event = {0};
        const TickType_t remaining = deadline - xTaskGetTickCount();
        if (xQueueReceive(s_op_event_queue, &event, remaining) != pdTRUE) break;
        if (event.kind != R1R4_OP_EVENT_ACTION_TX || event.op_id != expected_op_id) {
            ESP_LOGW(TAG,
                     "R1R4_OP_EVENT_IGNORED role=%s kind=%u expected_op_id=%u event_op_id=%u status=%u",
                     R1R3_LOCAL_ROLE,
                     (unsigned)event.kind,
                     (unsigned)expected_op_id,
                     (unsigned)event.op_id,
                     (unsigned)event.status);
            continue;
        }
        ESP_LOGI(TAG,
                 "R1R4_ACTION_TX_EVENT role=%s op_id=%u channel=%u status=%s",
                 R1R3_LOCAL_ROLE,
                 (unsigned)event.op_id,
                 (unsigned)event.channel,
                 action_tx_status_name(event.status));
        switch ((wifi_action_tx_status_type_t)event.status) {
            case WIFI_ACTION_TX_DONE:
                s_control_tx_done = true;
                break;
            case WIFI_ACTION_TX_FAILED:
                s_control_tx_failed = true;
                s_control_tx_duration_complete = false;
                return false;
            case WIFI_ACTION_TX_DURATION_COMPLETED:
                s_control_tx_duration_complete = !s_op_event_queue_overflow;
                return !s_op_event_queue_overflow;
            case WIFI_ACTION_TX_OP_CANCELLED:
                s_control_tx_cancelled = true;
                return false;
            default:
                break;
        }
    }
    ESP_LOGW(TAG,
             "R1R4_OPERATION_TIMEOUT role=%s kind=ACTION_TX op_id=%u queue_overflow=%s",
             R1R3_LOCAL_ROLE,
             (unsigned)expected_op_id,
             s_op_event_queue_overflow ? "true" : "false");
    return false;
}

static bool wait_for_roc_completion(uint8_t expected_op_id, uint32_t timeout_ms) {
    const TickType_t deadline = xTaskGetTickCount() + pdMS_TO_TICKS(timeout_ms);
    while (xTaskGetTickCount() < deadline) {
        r1r4_op_event_t event = {0};
        const TickType_t remaining = deadline - xTaskGetTickCount();
        if (xQueueReceive(s_op_event_queue, &event, remaining) != pdTRUE) break;
        if (event.kind != R1R4_OP_EVENT_ROC_DONE || event.op_id != expected_op_id) {
            ESP_LOGW(TAG,
                     "R1R4_OP_EVENT_IGNORED role=%s kind=%u expected_op_id=%u event_op_id=%u status=%u",
                     R1R3_LOCAL_ROLE,
                     (unsigned)event.kind,
                     (unsigned)expected_op_id,
                     (unsigned)event.op_id,
                     (unsigned)event.status);
            continue;
        }
        s_roc_completion_status = event.status;
        ESP_LOGI(TAG,
                 "R1R4_ROC_DONE_EVENT role=%s op_id=%u channel=%u status=%s cancel_requested=%s",
                 R1R3_LOCAL_ROLE,
                 (unsigned)event.op_id,
                 (unsigned)event.channel,
                 roc_status_name(event.status),
                 s_roc_cancel_requested ? "true" : "false");
        if (event.status == WIFI_ROC_DONE) {
            s_roc_natural_complete = !s_op_event_queue_overflow;
            s_roc_termination_observed = !s_op_event_queue_overflow;
            s_roc_termination_wait_ok = !s_op_event_queue_overflow;
            return !s_op_event_queue_overflow;
        }
        if (event.status == WIFI_ROC_FAIL) {
            s_roc_termination_observed = !s_op_event_queue_overflow;
            s_roc_termination_wait_ok = !s_op_event_queue_overflow;
            if (s_roc_cancel_requested) {
                s_roc_cancel_complete = !s_op_event_queue_overflow;
            }
            return !s_op_event_queue_overflow;
        }
        s_roc_termination_wait_ok = false;
        return false;
    }
    ESP_LOGW(TAG,
             "R1R4_OPERATION_TIMEOUT role=%s kind=ROC_DONE op_id=%u queue_overflow=%s",
             R1R3_LOCAL_ROLE,
             (unsigned)expected_op_id,
             s_op_event_queue_overflow ? "true" : "false");
    s_roc_termination_wait_ok = false;
    return false;
}

static bool log_home_channel_check(
    const char *step, bool *link_out, uint8_t *channel_out, bool *api_ok_out) {
    uint8_t channel = 0;
    wifi_second_chan_t secondary = WIFI_SECOND_CHAN_NONE;
    const esp_err_t channel_err = esp_wifi_get_channel(&channel, &secondary);
#if CONFIG_R1R4_ROLE_DUT
    const bool link = dut_sta_associated();
#else
    const bool link = (xEventGroupGetBits(s_events) & EV_WIFI_LINK) != 0;
#endif
    if (link_out != NULL) *link_out = link;
    if (channel_out != NULL) *channel_out = channel;
    if (api_ok_out != NULL) *api_ok_out = channel_err == ESP_OK;
    ESP_LOGI(TAG,
             "R1R4_HOME_CHANNEL_CHECK role=%s step=%s get_channel_result=%s channel=%u home_channel=%u link=%s",
             R1R3_LOCAL_ROLE,
             step,
             esp_err_to_name(channel_err),
             (unsigned)channel,
             R1R3_HOME_CHANNEL,
             link ? "true" : "false");
    return channel_err == ESP_OK && channel == R1R3_HOME_CHANNEL && link;
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
    const bool is_home_ack = type == R1R3_MSG_HOME_ACK;
    if (is_home_ack) {
        s_home_ack_callback_waiting = true;
        s_home_ack_callback_seen = false;
        s_home_ack_callback_ambiguous = s_non_home_send_callbacks_pending != 0;
        s_home_ack_send_callback = R1R4_ASYNC_UNKNOWN;
        xEventGroupClearBits(s_events, EV_HOME_ACK_SEND_CALLBACK);
    } else {
        s_non_home_send_callbacks_pending++;
    }
    const esp_err_t err = esp_now_send(dest, (const uint8_t *)&msg, sizeof(msg));
    if (!is_home_ack && err != ESP_OK && s_non_home_send_callbacks_pending > 0) {
        s_non_home_send_callbacks_pending--;
    }
    if (is_home_ack) {
        s_home_ack_api_ok = err == ESP_OK;
        if (err != ESP_OK) s_home_ack_callback_waiting = false;
    }
    ESP_LOGI(TAG,
             "R1R3_NORMAL_TX role=%s type=%u seq=%u home_ack_api=%s result=%s",
             R1R3_LOCAL_ROLE,
             (unsigned)type,
             (unsigned)seq,
             is_home_ack ? (err == ESP_OK ? "PASS" : "FAIL") : "NOT_APPLICABLE",
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
    const uint8_t request_op_id = seq;
    cfg->op_id = request_op_id;
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
    const uint8_t driver_op_id = cfg->op_id;
    s_control_tx_request_op_id = request_op_id;
    s_control_tx_driver_op_id = driver_op_id;
    ESP_LOGI(TAG,
             "R1R3_SWITCH_CHANNEL_TX role=%s target=%u wait_ms=%u application_seq=%u request_op_id=%u driver_op_id=%u result=%s",
             R1R3_LOCAL_ROLE,
             (unsigned)channel,
             (unsigned)cfg->wait_time_ms,
             (unsigned)seq,
             (unsigned)request_op_id,
             (unsigned)driver_op_id,
             esp_err_to_name(err));
    log_state("CONTROL_AFTER_SWITCH_TX_RETURN");
    bool completion_ok = false;
    if (err == ESP_OK) {
        completion_ok = wait_for_action_tx_completion(
            driver_op_id, R1R3_SWITCH_TX_WAIT_MS + 1000);
    }
    ESP_LOGI(TAG,
             "R1R4_ACTION_TX_COMPLETION role=%s driver_op_id=%u tx_done=%s tx_failed=%s duration_complete=%s op_cancelled=%s result=%s",
             R1R3_LOCAL_ROLE,
             (unsigned)driver_op_id,
             s_control_tx_done ? "true" : "false",
             s_control_tx_failed ? "true" : "false",
             s_control_tx_duration_complete ? "true" : "false",
             s_control_tx_cancelled ? "true" : "false",
             completion_ok ? "PASS" : "FAIL");
    log_state("CONTROL_AFTER_SWITCH_TX_SETTLE");
    free(cfg);
    return err;
}

static esp_err_t roc_request(uint8_t channel, uint8_t request_op_id, uint8_t *driver_op_id_out) {
    esp_now_remain_on_channel_t cfg = {
        .type = WIFI_ROC_REQ,
        .channel = channel,
        .sec_channel = WIFI_SECOND_CHAN_NONE,
        .wait_time_ms = R1R3_ROC_WAIT_MS,
        .op_id = request_op_id,
    };
    log_state("DUT_BEFORE_ROC_REQ");
    const esp_err_t err = esp_now_remain_on_channel(&cfg);
    if (driver_op_id_out != NULL) *driver_op_id_out = cfg.op_id;
    ESP_LOGI(TAG,
             "R1R3_ROC_REQ role=DUT target=%u wait_ms=%u request_op_id=%u driver_op_id=%u result=%s",
             (unsigned)channel,
             (unsigned)cfg.wait_time_ms,
             (unsigned)request_op_id,
             (unsigned)cfg.op_id,
             esp_err_to_name(err));
    log_state("DUT_AFTER_ROC_REQ_RETURN");
    return err;
}

static esp_err_t roc_cancel(uint8_t channel, uint8_t request_driver_op_id) {
    esp_now_remain_on_channel_t cfg = {
        .type = WIFI_ROC_CANCEL,
        .channel = channel,
        .sec_channel = WIFI_SECOND_CHAN_NONE,
        .wait_time_ms = 0,
        .op_id = request_driver_op_id,
    };
    log_state("DUT_BEFORE_ROC_CANCEL");
    const esp_err_t err = esp_now_remain_on_channel(&cfg);
    ESP_LOGI(TAG,
             "R1R3_ROC_CANCEL role=DUT target=%u wait_ms=%u cancel_request_driver_op_id=%u cancel_api_returned_op_id=%u result=%s",
             (unsigned)channel,
             (unsigned)cfg.wait_time_ms,
             (unsigned)request_driver_op_id,
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
    const char *purpose = "UNASSOCIATED";
    if (s_home_ack_callback_waiting) {
        purpose = s_home_ack_callback_ambiguous ? "HOME_ACK_UNKNOWN" : "HOME_ACK";
        if (s_home_ack_callback_ambiguous || s_home_ack_callback_seen) {
            s_home_ack_send_callback = R1R4_ASYNC_UNKNOWN;
        } else {
            s_home_ack_callback_seen = true;
            s_home_ack_callback_waiting = false;
            s_home_ack_send_callback =
                status == ESP_NOW_SEND_SUCCESS ? R1R4_ASYNC_PASS : R1R4_ASYNC_FAIL;
        }
        xEventGroupSetBits(s_events, EV_HOME_ACK_SEND_CALLBACK);
    } else if (s_non_home_send_callbacks_pending > 0) {
        s_non_home_send_callbacks_pending--;
    }
    ESP_LOGI(TAG,
             "R1R3_SEND_CB role=%s purpose=%s dest=%02x:%02x:%02x:%02x:%02x:%02x status=%s",
             R1R3_LOCAL_ROLE,
             purpose,
             info->des_addr[0], info->des_addr[1], info->des_addr[2],
             info->des_addr[3], info->des_addr[4], info->des_addr[5],
             status == ESP_NOW_SEND_SUCCESS ? "SUCCESS" : "FAIL");
}

static void wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data) {
    (void)arg;
    (void)base;
    if (id == WIFI_EVENT_ACTION_TX_STATUS && data != NULL) {
        const wifi_event_action_tx_status_t *status = (const wifi_event_action_tx_status_t *)data;
        const r1r4_op_event_t event = {
            .kind = R1R4_OP_EVENT_ACTION_TX,
            .op_id = status->op_id,
            .channel = status->channel,
            .status = (uint8_t)status->status,
        };
        if (s_op_event_queue == NULL || xQueueSend(s_op_event_queue, &event, 0) != pdTRUE) {
            s_op_event_queue_overflow = true;
            ESP_LOGE(TAG,
                     "R1R4_OP_EVENT_QUEUE_OVERFLOW role=%s kind=ACTION_TX op_id=%u status=%u",
                     R1R3_LOCAL_ROLE,
                     (unsigned)event.op_id,
                     (unsigned)event.status);
        }
        return;
    }
    if (id == WIFI_EVENT_ROC_DONE && data != NULL) {
        const wifi_event_roc_done_t *status = (const wifi_event_roc_done_t *)data;
        const r1r4_op_event_t event = {
            .kind = R1R4_OP_EVENT_ROC_DONE,
            .op_id = status->op_id,
            .channel = status->channel,
            .status = (uint8_t)status->status,
        };
        if (s_op_event_queue == NULL || xQueueSend(s_op_event_queue, &event, 0) != pdTRUE) {
            s_op_event_queue_overflow = true;
            ESP_LOGE(TAG,
                     "R1R4_OP_EVENT_QUEUE_OVERFLOW role=%s kind=ROC_DONE op_id=%u status=%u",
                     R1R3_LOCAL_ROLE,
                     (unsigned)event.op_id,
                     (unsigned)event.status);
        }
        return;
    }
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
        uint8_t reason = 0;
        if (data != NULL) {
            reason = ((const wifi_event_sta_disconnected_t *)data)->reason;
        }
        s_initial_assoc_last_disconnect_reason = reason;
        s_wifi_disconnect_count++;
        xEventGroupClearBits(s_events, EV_WIFI_LINK);
        ESP_LOGW(TAG,
                 "R1R3_WIFI_EVENT role=DUT STA_DISCONNECTED reason=%u initial_assoc_active=%s count=%lu roc_active=%s cancel_complete=%s",
                 (unsigned)reason,
                 s_initial_assoc_active ? "true" : "false",
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
                s_home_ack_received = true;
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
    s_control_tx_done = false;
    s_control_tx_failed = false;
    s_control_tx_duration_complete = false;
    s_control_tx_cancelled = false;
    const esp_err_t probe_err = send_offchannel(
        s_peer_mac, R1R3_MSG_OFFCHANNEL_PROBE, 55, R1R3_TARGET_CHANNEL);
    ESP_LOGI(TAG, "R1R3_CONTROL_PROBE_TX result=%s", esp_err_to_name(probe_err));

    s_control_home_return = log_home_channel_check(
        "CONTROL_AFTER_ACTION_TX",
        &s_control_home_ap_link,
        &s_control_home_channel,
        &s_control_home_channel_api_ok);
    if (!s_control_home_return) {
        ESP_LOGW(TAG, "R1R4_CONTROL_HOME_RETURN result=FAIL");
    }

    const EventBits_t home_ack = xEventGroupWaitBits(
        s_events, EV_HOME_ACK, pdFALSE, pdTRUE, pdMS_TO_TICKS(7000));
    log_state("CONTROL_FINAL");
    ESP_LOGI(TAG,
             "R1R3_SUMMARY role=CONTROL baseline=%s probe_tx_api=%s switch_tx_api=%s switch_tx_request_op_id=%u switch_tx_driver_op_id=%u switch_tx_completion=%s switch_tx_status=%s control_home_channel_api=%s control_home_channel=%u control_ap_sta_link=%s control_home_return=%s home_ack_api=NOT_APPLICABLE home_ack_send_callback=NOT_APPLICABLE home_ack_received=%s home_ack=%s",
             s_baseline_pass ? "PASS" : "FAIL",
             probe_err == ESP_OK ? "PASS" : "FAIL",
             probe_err == ESP_OK ? "PASS" : "FAIL",
             (unsigned)s_control_tx_request_op_id,
             (unsigned)s_control_tx_driver_op_id,
             s_control_tx_duration_complete ? "PASS" : "FAIL",
             s_control_tx_duration_complete ? "TX_DURATION_COMPLETED" :
                 (s_control_tx_failed ? "TX_FAILED" :
                  (s_control_tx_cancelled ? "TX_OP_CANCELLED" : "TIMEOUT")),
             s_control_home_channel_api_ok ? "PASS" : "FAIL",
             (unsigned)s_control_home_channel,
             s_control_home_ap_link ? "true" : "false",
             s_control_home_return ? "PASS" : "FAIL",
             (home_ack & EV_HOME_ACK) && s_home_ack_received ? "PASS" : "FAIL",
             (home_ack & EV_HOME_ACK) && s_home_ack_received ? "PASS" : "FAIL");

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

static bool wait_initial_association(void) {
    const TickType_t start = xTaskGetTickCount();
    const TickType_t deadline = start + pdMS_TO_TICKS(R1R3_INITIAL_ASSOC_TIMEOUT_MS);
    s_initial_assoc_active = true;
    s_initial_assoc_attempts = 0;
    s_initial_assoc_last_result = ESP_FAIL;

    while (s_initial_assoc_attempts < R1R3_INITIAL_ASSOC_MAX_ATTEMPTS &&
           xTaskGetTickCount() < deadline) {
        s_initial_assoc_attempts++;
        s_initial_assoc_last_result = esp_wifi_connect();
        ESP_LOGI(TAG,
                 "R1R3_STAGE_ATTEMPT stage=INITIAL_ASSOCIATION attempt=%u/%u api_result=%s disconnect_reason=%u",
                 (unsigned)s_initial_assoc_attempts,
                 (unsigned)R1R3_INITIAL_ASSOC_MAX_ATTEMPTS,
                 esp_err_to_name(s_initial_assoc_last_result),
                 (unsigned)s_initial_assoc_last_disconnect_reason);

        const TickType_t attempt_deadline =
            xTaskGetTickCount() + pdMS_TO_TICKS(R1R3_INITIAL_ASSOC_ATTEMPT_WAIT_MS);
        while ((xEventGroupGetBits(s_events) & EV_WIFI_LINK) == 0 &&
               xTaskGetTickCount() < attempt_deadline &&
               xTaskGetTickCount() < deadline) {
            vTaskDelay(pdMS_TO_TICKS(100));
        }
        if ((xEventGroupGetBits(s_events) & EV_WIFI_LINK) != 0) {
            s_initial_assoc_active = false;
            ESP_LOGI(TAG,
                     "R1R3_STAGE_RESULT stage=INITIAL_ASSOCIATION result=PASS attempts=%u last_api_result=%s disconnect_reason=%u",
                     (unsigned)s_initial_assoc_attempts,
                     esp_err_to_name(s_initial_assoc_last_result),
                     (unsigned)s_initial_assoc_last_disconnect_reason);
            return true;
        }
    }

    s_initial_assoc_active = false;
    ESP_LOGW(TAG,
             "R1R3_STAGE_TIMEOUT stage=INITIAL_ASSOCIATION result=TIMEOUT attempts=%u max_attempts=%u window_ms=%u last_api_result=%s disconnect_reason=%u",
             (unsigned)s_initial_assoc_attempts,
             (unsigned)R1R3_INITIAL_ASSOC_MAX_ATTEMPTS,
             (unsigned)R1R3_INITIAL_ASSOC_TIMEOUT_MS,
             esp_err_to_name(s_initial_assoc_last_result),
             (unsigned)s_initial_assoc_last_disconnect_reason);
    return false;
}

static void dut_experiment_task(void *arg) {
    (void)arg;
    ESP_LOGI(TAG, "R1R3_ROLE=DUT HOME_CHANNEL=%u TARGET_CHANNEL=%u",
             R1R3_HOME_CHANNEL, R1R3_TARGET_CHANNEL);

    if (!wait_initial_association()) {
        ESP_LOGW(TAG, "R1R3_STAGE_NOT_EXECUTED stage=BASELINE reason=INITIAL_ASSOCIATION_TIMEOUT");
        ESP_LOGW(TAG, "R1R3_STAGE_NOT_EXECUTED stage=OFFCHANNEL reason=BASELINE_NOT_REACHED");
        for (;;) vTaskDelay(pdMS_TO_TICKS(1000));
    }

    const EventBits_t baseline = xEventGroupWaitBits(
        s_events, EV_BASELINE, pdFALSE, pdTRUE, pdMS_TO_TICKS(R1R3_BASELINE_TIMEOUT_MS));
    if ((baseline & EV_BASELINE) == 0) {
        ESP_LOGW(TAG,
                 "R1R3_STAGE_TIMEOUT stage=BASELINE result=TIMEOUT window_ms=%u",
                 (unsigned)R1R3_BASELINE_TIMEOUT_MS);
        ESP_LOGW(TAG, "R1R3_STAGE_NOT_EXECUTED stage=OFFCHANNEL reason=BASELINE_TIMEOUT");
        for (;;) vTaskDelay(pdMS_TO_TICKS(1000));
    }
    ESP_LOGI(TAG, "R1R3_STAGE_RESULT stage=BASELINE result=PASS");
    log_state("DUT_BASELINE_ESTABLISHED");
    ESP_LOGI(TAG, "R1R3_BASELINE_RESULT=PASS");

    const EventBits_t start_roc = xEventGroupWaitBits(
        s_events, EV_START_ROC, pdFALSE, pdTRUE, pdMS_TO_TICKS(R1R3_OFFCHANNEL_START_TIMEOUT_MS));
    if ((start_roc & EV_START_ROC) == 0) {
        ESP_LOGW(TAG,
                 "R1R3_STAGE_TIMEOUT stage=OFFCHANNEL result=TIMEOUT window_ms=%u",
                 (unsigned)R1R3_OFFCHANNEL_START_TIMEOUT_MS);
        for (;;) vTaskDelay(pdMS_TO_TICKS(1000));
    }
    ESP_LOGI(TAG, "R1R3_STAGE_RESULT stage=OFFCHANNEL result=EXECUTED");
    log_state("DUT_PRE_ARM");
    const esp_err_t armed_err = send_normal(s_peer_mac, R1R3_MSG_ROC_ARMED, 20);
    ESP_LOGI(TAG, "R1R3_ROC_ARMED_TX result=%s", esp_err_to_name(armed_err));
    vTaskDelay(pdMS_TO_TICKS(100));

    s_roc_active = true;
    s_roc_cancel_complete = false;
    s_roc_natural_complete = false;
    s_roc_cancel_requested = false;
    s_roc_cancel_api_ok = false;
    s_roc_termination_observed = false;
    s_roc_termination_wait_ok = false;
    s_roc_completion_status = 0xff;
    s_roc_request_op_id = 0;
    const uint8_t request_op_id = 0;
    const esp_err_t req_err = roc_request(
        R1R3_TARGET_CHANNEL, request_op_id, &s_roc_driver_op_id);
    s_roc_req_ok = req_err == ESP_OK;
    s_roc_request_op_id = request_op_id;

    const EventBits_t probe = xEventGroupWaitBits(
        s_events, EV_PROBE_RX, pdFALSE, pdTRUE, pdMS_TO_TICKS(R1R3_ROC_PROBE_WAIT_MS));
    ESP_LOGI(TAG,
             "R1R3_PROBE_WAIT_RESULT received=%s",
             (probe & EV_PROBE_RX) && s_probe_rx_ok ? "true" : "false");
    log_state("DUT_BEFORE_EXPLICIT_CANCEL");

    esp_err_t cancel_err = ESP_FAIL;
    if (s_roc_req_ok) {
        cancel_err = roc_cancel(R1R3_TARGET_CHANNEL, s_roc_driver_op_id);
        s_roc_cancel_api_ok = cancel_err == ESP_OK;
        s_roc_cancel_requested = s_roc_cancel_api_ok;
        (void)wait_for_roc_completion(s_roc_driver_op_id, R1R3_HOME_RECOVERY_TIMEOUT_MS);
    } else {
        ESP_LOGW(TAG, "R1R3_ROC_CANCEL skipped=true reason=ROC_REQ_FAILED");
    }
    ESP_LOGI(TAG,
             "R1R4_ROC_COMPLETION role=DUT request_op_id=%u driver_op_id=%u natural_complete=%s cancel_api=%s cancel_complete=%s termination_observed=%s termination_wait=%s status=%s",
             (unsigned)s_roc_request_op_id,
             (unsigned)s_roc_driver_op_id,
             s_roc_natural_complete ? "true" : "false",
             s_roc_cancel_api_ok ? "PASS" : "FAIL",
             s_roc_cancel_complete ? "true" : "false",
             s_roc_termination_observed ? "true" : "false",
             s_roc_termination_wait_ok ? "PASS" : "FAIL",
             roc_status_name(s_roc_completion_status));

    const r1r4_operation_state_t operation_state = {
        .request_ok = s_roc_req_ok,
        .cancel_api_ok = s_roc_cancel_api_ok,
        .termination_observed = s_roc_termination_observed,
        .event_loss = s_op_event_queue_overflow,
        .roc_active = s_roc_active,
    };
    if (!r1r4_should_clear_roc_active(operation_state)) {
        uint8_t observed_channel = 0;
        bool observed_link = false;
        bool observed_api_ok = false;
        (void)log_home_channel_check(
            "DUT_TERMINATION_UNCONFIRMED", &observed_link, &observed_channel, &observed_api_ok);
        ESP_LOGW(TAG,
                 "R1R3_STAGE_NOT_EXECUTED stage=HOME_RECOVERY reason=ROC_TERMINATION_UNCONFIRMED channel_api=%s channel=%u sta_link=%s",
                 observed_api_ok ? "PASS" : "FAIL",
                 (unsigned)observed_channel,
                 observed_link ? "true" : "false");
        ESP_LOGW(TAG,
                 "R1R3_STAGE_NOT_EXECUTED stage=HOME_ACK reason=ROC_TERMINATION_UNCONFIRMED");
        ESP_LOGI(TAG,
                 "R1R3_SUMMARY role=DUT baseline=%s roc_req=%s roc_request_input_op_id=%u roc_driver_op_id=%u roc_natural_complete=%s roc_cancel_api=%s roc_cancel_complete=%s roc_termination_observed=%s roc_termination_wait=%s roc_active=%s roc_completion_status=%s probe_rx=%s home_recovery=NOT_EXECUTED home_channel_api=%s home_channel=%u home_sta_link=%s home_ack_tx=NOT_EXECUTED home_ack_api=NOT_EXECUTED home_ack_send_callback=NOT_EXECUTED home_ack_received=NOT_APPLICABLE disconnect_count=%lu",
                 s_baseline_pass ? "PASS" : "FAIL",
                 s_roc_req_ok ? "PASS" : "FAIL",
                 (unsigned)s_roc_request_op_id,
                 (unsigned)s_roc_driver_op_id,
                 s_roc_natural_complete ? "true" : "false",
                 s_roc_cancel_api_ok ? "PASS" : "FAIL",
                 s_roc_cancel_complete ? "PASS" : "FAIL",
                 s_roc_termination_observed ? "true" : "false",
                 s_roc_termination_wait_ok ? "PASS" : "FAIL",
                 s_roc_active ? "true" : "false",
                 roc_status_name(s_roc_completion_status),
                 s_probe_rx_ok ? "PASS" : "FAIL",
                 observed_api_ok ? "PASS" : "FAIL",
                 (unsigned)observed_channel,
                 observed_link ? "true" : "false",
                 (unsigned long)s_wifi_disconnect_count);
        for (;;) vTaskDelay(pdMS_TO_TICKS(1000));
    }
    s_roc_active = false;

    log_state("DUT_POST_CANCEL_IMMEDIATE");
    vTaskDelay(pdMS_TO_TICKS(100));
    log_state("DUT_POST_CANCEL_100MS");
    vTaskDelay(pdMS_TO_TICKS(400));
    log_state("DUT_POST_CANCEL_500MS");

    const TickType_t deadline = xTaskGetTickCount() + pdMS_TO_TICKS(R1R3_HOME_RECOVERY_TIMEOUT_MS);
    unsigned reconnect_attempt = 0;
    while (xTaskGetTickCount() < deadline) {
        bool home_channel_api_ok = false;
        const bool home_ready = log_home_channel_check(
            "DUT_HOME_RECOVERY_POLL", NULL, NULL, &home_channel_api_ok);
        if (home_ready && home_channel_api_ok) {
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

    bool final_home_link = false;
    uint8_t final_home_channel = 0;
    bool final_home_api_ok = false;
    const bool final_home_return = log_home_channel_check(
        "DUT_HOME_RECOVERY_FINAL",
        &final_home_link,
        &final_home_channel,
        &final_home_api_ok);
    s_home_recovery_ok = final_home_return;
    ESP_LOGI(TAG, "R1R4_DUT_HOME_RETURN result=%s", final_home_return ? "PASS" : "FAIL");
    log_state("DUT_HOME_RECOVERY_FINAL");
    esp_err_t home_ack_err = ESP_FAIL;
    if (r1r4_should_send_home_ack(operation_state, final_home_return)) {
        home_ack_err = send_normal(s_peer_mac, R1R3_MSG_HOME_ACK, 66);
        s_home_ack_ok = home_ack_err == ESP_OK;
        if (s_home_ack_ok) {
            const EventBits_t callback = xEventGroupWaitBits(
                s_events,
                EV_HOME_ACK_SEND_CALLBACK,
                pdFALSE,
                pdTRUE,
                pdMS_TO_TICKS(1000));
            if ((callback & EV_HOME_ACK_SEND_CALLBACK) == 0) {
                s_home_ack_send_callback = R1R4_ASYNC_UNKNOWN;
                ESP_LOGW(TAG, "R1R4_HOME_ACK_CALLBACK_TIMEOUT role=DUT api=PASS");
            }
        }
    }
    ESP_LOGI(TAG, "R1R3_HOME_ACK_TX result=%s", esp_err_to_name(home_ack_err));

    ESP_LOGI(TAG,
             "R1R3_SUMMARY role=DUT baseline=%s roc_req=%s roc_request_input_op_id=%u roc_driver_op_id=%u roc_natural_complete=%s roc_cancel_api=%s roc_cancel_complete=%s roc_termination_observed=%s roc_termination_wait=%s roc_active=%s roc_completion_status=%s probe_rx=%s home_recovery=%s home_channel_api=%s home_channel=%u home_sta_link=%s home_ack_tx=%s home_ack_api=%s home_ack_send_callback=%s home_ack_received=NOT_APPLICABLE disconnect_count=%lu",
             s_baseline_pass ? "PASS" : "FAIL",
             s_roc_req_ok ? "PASS" : "FAIL",
             (unsigned)s_roc_request_op_id,
             (unsigned)s_roc_driver_op_id,
             s_roc_natural_complete ? "true" : "false",
             s_roc_cancel_api_ok ? "PASS" : "FAIL",
             s_roc_cancel_complete ? "PASS" : "FAIL",
             s_roc_termination_observed ? "true" : "false",
             s_roc_termination_wait_ok ? "PASS" : "FAIL",
             s_roc_active ? "true" : "false",
             roc_status_name(s_roc_completion_status),
             s_probe_rx_ok ? "PASS" : "FAIL",
             s_home_recovery_ok ? "PASS" : "FAIL",
             final_home_api_ok ? "PASS" : "FAIL",
             (unsigned)final_home_channel,
             final_home_link ? "true" : "false",
             s_home_ack_ok ? "PASS" : "FAIL",
             s_home_ack_api_ok ? "PASS" : "FAIL",
             async_result_name(s_home_ack_send_callback),
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
    s_op_event_queue = xQueueCreate(16, sizeof(r1r4_op_event_t));
    if (s_events == NULL || s_rx_queue == NULL || s_op_event_queue == NULL) abort();

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
