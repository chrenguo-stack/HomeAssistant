#include "n3w_simple_product_component.h"

#include <algorithm>
#include <array>
#include <cstring>
#include <string>
#include <vector>

#ifdef USE_MQTT
#include "esphome/components/mqtt/mqtt_client.h"
#endif
#ifdef USE_WIFI
#include "esphome/components/wifi/wifi_component.h"
#endif
#include "esphome/core/application.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#include "esp_http_client.h"
#include "esp_mac.h"
#include "esp_random.h"
#include "esp_wifi.h"
#include "lwip/inet.h"
#include "lwip/sockets.h"
#include "mbedtls/md.h"

namespace esphome::greenhouse_n3w_core {
namespace {

static const char *const TAG = "n3w_simple_product";
constexpr char kPmkDomain[] = "gh.n3w.espnow-pmk/1";
constexpr std::size_t kHttpResponseMaxBytes = 16 * 1024;
constexpr uint64_t kRadioRetryIntervalMs = 1000;

struct HttpResponseCollector {
  std::string *output{nullptr};
  bool overflow{false};
};

esp_err_t http_event_handler(esp_http_client_event_t *event) {
  if (event == nullptr || event->user_data == nullptr) return ESP_OK;
  auto *collector = static_cast<HttpResponseCollector *>(event->user_data);
  if (event->event_id != HTTP_EVENT_ON_DATA || collector->output == nullptr ||
      event->data == nullptr || event->data_len <= 0) {
    return ESP_OK;
  }
  const std::size_t incoming = static_cast<std::size_t>(event->data_len);
  if (collector->output->size() + incoming > kHttpResponseMaxBytes) {
    collector->overflow = true;
    return ESP_FAIL;
  }
  collector->output->append(static_cast<const char *>(event->data), incoming);
  return ESP_OK;
}

bool mqtt_connected() {
#ifdef USE_MQTT
  return mqtt::global_mqtt_client != nullptr &&
         mqtt::global_mqtt_client->is_connected();
#else
  return false;
#endif
}

bool wifi_connected() {
#ifdef USE_WIFI
  return wifi::global_wifi_component != nullptr &&
         wifi::global_wifi_component->is_connected();
#else
  return false;
#endif
}

}  // namespace

const char *telemetry_submit_disposition_name(
    TelemetrySubmitDisposition disposition) {
  switch (disposition) {
    case TelemetrySubmitDisposition::SUBMITTED:
      return "SUBMITTED";
    case TelemetrySubmitDisposition::BUFFERED:
      return "BUFFERED";
    case TelemetrySubmitDisposition::REJECTED:
    default:
      return "REJECTED";
  }
}

SimpleProductComponent::SimpleProductComponent()
    : direct_ap_hint_policy_(DirectApHintConfig{
          RecoveryExitPolicy::kDirectApHintMaxAgeMs,
          RecoveryExitPolicy::kDirectApHintMissLimit,
          kDirectApHintScanErrorLimit,
      }),
      direct_recovery_attempt_(DirectRecoveryConfig{
          kDirectRecoveryWifiBudgetMs,
          kDirectRecoveryMqttBudgetMs,
          kDirectRecoveryConfirmBudgetMs,
          kNoRelayDirectRecoveryAbsoluteMs,
          kHealthyRelayDirectRecoveryAbsoluteMs,
          kDirectRecoveryConfirmSuccesses,
      }),
      runtime_(this, this, this),
      pairing_client_(
          this,
          this,
          &setup_secret_store_,
          &peer_store_,
          &broker_store_,
          &ack_store_) {}

float SimpleProductComponent::get_setup_priority() const {
  return setup_priority::LATE;
}

void SimpleProductComponent::setup() {
  if (!activation_enabled_) {
    ESP_LOGI(TAG, "Phase 4 simplified product runtime remains source-only disabled");
    return;
  }
  if (!read_local_mac_()) {
    ESP_LOGE(TAG, "Unable to read local ESP32-C6 STA MAC");
    mark_failed();
    return;
  }
  const SimplePairingClientError pairing = pairing_client_.initialize(local_mac_);
  if (pairing == SimplePairingClientError::ALREADY_PROVISIONED) {
    if (!load_runtime_state_() || !configure_mqtt_()) {
      ESP_LOGE(TAG, "Provisioned N3-W state failed validation");
      mark_failed();
      return;
    }
    ESP_LOGI(
        TAG,
        "Provisioned N3-W runtime state loaded for node=%s",
        peer_state_.node_id.c_str());
    return;
  }
  if (pairing != SimplePairingClientError::NONE &&
      pairing != SimplePairingClientError::ACK_PENDING) {
    ESP_LOGE(
        TAG,
        "Simplified pairing bootstrap initialization failed code=%u",
        static_cast<unsigned>(pairing));
    mark_failed();
    return;
  }
  ESP_LOGI(
      TAG,
      "Unprovisioned N3-W node ready for local pairing hardware_id=%s pairing_id=%s",
      pairing_client_.hardware_id().c_str(),
      pairing_client_.pairing_id().c_str());
}

void SimpleProductComponent::loop() {
  if (!activation_enabled_ || is_failed() || safe_reboot_requested_) return;
  const bool recovery_exclusive =
      radio_ownership_ == RadioOwnership::DIRECT_PROBE ||
      radio_ownership_ == RadioOwnership::RELAY_RESTORE;
  if (!recovery_exclusive) {
    drain_send_completions_();
    if (drain_radio_()) return;
  }
  if (!pairing_client_.provisioned()) {
    advance_pairing_();
    if (!pairing_client_.provisioned()) return;
  }
  if (!runtime_state_loaded_ && !load_runtime_state_()) return;
  if (!mqtt_configured_ && !configure_mqtt_()) return;
  if (!runtime_ready_) {
    (void) start_runtime_if_ready_();
    return;
  }
  // A missing ESP-NOW completion must not wait until the next scheduled Direct
  // recovery probe. Evaluate the completion deadline on every component loop.
  if (check_pending_unicast_timeout_()) {
    return;
  }
  diagnostics_.observe_connectivity(
      wifi_connected(), mqtt_connected(), now_ms());
  if (radio_ownership_ == RadioOwnership::DIRECT_WIFI) {
    refresh_direct_ap_hint_();
  }
  if (radio_ownership_ == RadioOwnership::DIRECT_PROBE ||
      radio_ownership_ == RadioOwnership::RELAY_RESTORE) {
    advance_recovery_();
    diagnostics_.observe_runtime(
        static_cast<uint8_t>(runtime_.path_state()),
        runtime_.working_channel(),
        runtime_.direct_channel_hint(),
        static_cast<uint32_t>(runtime_.relay_child_count()),
        runtime_.active_relay().has_value(),
        now_ms());
    diagnostics_.emit_summary(now_ms());
    return;
  }
  runtime_.set_relay_capable(mqtt_connected());
  const bool selection_busy_before_tick =
      runtime_.gateway_selection_busy();
  const SimpleProductError tick_result = runtime_.tick();
  if (consume_gateway_selection_runtime_result_(
          tick_result, selection_busy_before_tick)) {
    return;
  }
  diagnostics_.observe_runtime(
      static_cast<uint8_t>(runtime_.path_state()),
      runtime_.working_channel(),
      runtime_.direct_channel_hint(),
      static_cast<uint32_t>(runtime_.relay_child_count()),
      runtime_.active_relay().has_value(),
      now_ms());
  diagnostics_.emit_summary(now_ms());
  (void) flush_telemetry_queue_(TelemetryPathAccounting::TRANSPORT_ONLY);
  advance_recovery_();
}

TelemetrySubmitDisposition SimpleProductComponent::submit_telemetry_json(
    const std::string &telemetry_json,
    const std::string &boot_id,
    uint32_t seq) {
  if (!runtime_ready_) return TelemetrySubmitDisposition::REJECTED;

  uint64_t boot_session = 0;
  if (telemetry_json.empty() ||
      telemetry_json.size() > kMaxCiphertextBytes ||
      boot_id.empty() ||
      !parse_boot_id(boot_id, &boot_session) ||
      boot_session == 0U) {
    ++telemetry_queue_dropped_;
    ESP_LOGE(
        TAG,
        "N3-W telemetry admission rejected seq=%u size=%u rejected=%u",
        static_cast<unsigned>(seq),
        static_cast<unsigned>(telemetry_json.size()),
        static_cast<unsigned>(telemetry_queue_dropped_));
    return TelemetrySubmitDisposition::REJECTED;
  }

  // Path-health accounting belongs to the newly generated business sample,
  // not to backlog transport polling. In particular, DIRECT without MQTT is
  // not a transport attempt, but each new sample must still advance the
  // Direct-failure hysteresis even when the hold FIFO is already full or a
  // TRANSPORT_ONLY poll recently advanced the queue cooldown.
  const TelemetryAdmissionPlan admission_plan =
      plan_business_telemetry_admission(
          runtime_.path_state(), mqtt_connected());
  if (admission_plan.record_direct_unavailable) {
    const SimpleProductError state_result = runtime_.note_direct_result(false);
    if (state_result != SimpleProductError::NONE &&
        state_result != SimpleProductError::RADIO_FAILED) {
      ++telemetry_invariant_failures_;
      request_safe_reboot_("telemetry Direct admission path-state failure");
      return TelemetrySubmitDisposition::REJECTED;
    }
  }

  const bool queue_was_empty = telemetry_queue_.empty();
  if (!enqueue_telemetry_(telemetry_json, boot_id, seq)) {
    return TelemetrySubmitDisposition::REJECTED;
  }

  // Option B: the queue owns telemetry only while it has not yet received a
  // real transport opportunity. DIRECT/no-MQTT was already accounted exactly
  // once above; backlog draining must remain TRANSPORT_ONLY so the held front
  // sample cannot double-count the same business-cadence failure.
  const TelemetryPathAccounting front_accounting =
      admission_plan.front_accounting;
  const TelemetrySubmitDisposition front_result =
      flush_telemetry_queue_(front_accounting);

  // When older telemetry already owned the FIFO, this new sample is still
  // buffered regardless of the older front item's one-attempt outcome.
  return queue_was_empty
             ? front_result
             : TelemetrySubmitDisposition::BUFFERED;
}

bool SimpleProductComponent::send_telemetry_json(
    const std::string &telemetry_json,
    const std::string &boot_id,
    uint32_t seq) {
  return submit_telemetry_json(telemetry_json, boot_id, seq) !=
         TelemetrySubmitDisposition::REJECTED;
}

bool SimpleProductComponent::read_local_mac_() {
  local_mac_.fill(0);
  return esp_read_mac(local_mac_.data(), ESP_MAC_WIFI_STA) == ESP_OK &&
         std::any_of(
             local_mac_.begin(),
             local_mac_.end(),
             [](uint8_t value) { return value != 0; });
}

bool SimpleProductComponent::load_runtime_state_() {
  ProvisionedPeerStateV2 peer;
  ProvisionedBrokerStateV2 broker;
  if (peer_store_.load(&peer) != SimpleNvsStatus::OK ||
      broker_store_.load(&broker) != SimpleNvsStatus::OK || !peer.valid() ||
      !broker.valid() || peer.system_id != broker.system_id ||
      peer.node_id != broker.node_id) {
    return false;
  }
  peer_state_ = std::move(peer);
  broker_state_ = std::move(broker);
  runtime_state_loaded_ = true;
  return true;
}

bool SimpleProductComponent::configure_mqtt_() {
#ifdef USE_MQTT
  if (!runtime_state_loaded_ || mqtt::global_mqtt_client == nullptr) return false;
  mqtt::global_mqtt_client->set_broker_address(broker_state_.broker_host);
  mqtt::global_mqtt_client->set_broker_port(broker_state_.broker_port);
  mqtt::global_mqtt_client->set_username(broker_state_.mqtt_username);
  mqtt::global_mqtt_client->set_password(broker_state_.mqtt_password);
  mqtt::global_mqtt_client->set_client_id(broker_state_.mqtt_client_id);
  mqtt::global_mqtt_client->set_tls_server_name(
      broker_state_.broker_tls_server_name);
  mqtt::global_mqtt_client->set_ca_certificate(broker_state_.ca_pem.c_str());
  mqtt::global_mqtt_client->set_enable_on_boot(true);
  mqtt::global_mqtt_client->enable();
  mqtt_configured_ = true;
  return true;
#else
  return false;
#endif
}

bool SimpleProductComponent::derive_pmk_(LinkKey *pmk) const {
  if (pmk == nullptr || !peer_state_.valid()) return false;
  std::vector<uint8_t> message;
  message.insert(
      message.end(), std::begin(kPmkDomain), std::end(kPmkDomain) - 1);
  message.push_back(0);
  message.insert(
      message.end(),
      peer_state_.system_id.begin(),
      peer_state_.system_id.end());
  message.push_back(0);
  for (int shift = 56; shift >= 0; shift -= 8) {
    message.push_back(static_cast<uint8_t>(
        (static_cast<uint64_t>(peer_state_.peer_trust_generation) >> shift) &
        0xffU));
  }
  std::array<uint8_t, 32> digest{};
  const mbedtls_md_info_t *info =
      mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if (info == nullptr ||
      mbedtls_md_hmac(
          info,
          peer_state_.system_peer_key.data(),
          peer_state_.system_peer_key.size(),
          message.data(),
          message.size(),
          digest.data()) != 0) {
    return false;
  }
  std::copy_n(digest.begin(), pmk->size(), pmk->begin());
  digest.fill(0);
  return std::any_of(
      pmk->begin(), pmk->end(), [](uint8_t value) { return value != 0; });
}

bool SimpleProductComponent::start_runtime_if_ready_() {
  if (runtime_ready_) return true;
  if (!runtime_state_loaded_ || !mqtt_configured_) {
    return false;
  }

  const uint64_t now = now_ms();
  const bool direct_available = wifi_connected();
  if (!direct_available) {
    if (!runtime_start_grace_started_) {
      runtime_start_grace_started_ = true;
      runtime_start_grace_started_ms_ = now;
      ESP_LOGI(
          TAG,
          "N3-W waiting up to %u ms for preferred Direct Wi-Fi before Relay discovery",
          static_cast<unsigned>(kInitialDirectGraceMs));
      return false;
    }
    if (now - runtime_start_grace_started_ms_ < kInitialDirectGraceMs) {
      return false;
    }
  }

  if (radio_attempted_ &&
      now - last_radio_attempt_ms_ < kRadioRetryIntervalMs) {
    return false;
  }
  radio_attempted_ = true;
  last_radio_attempt_ms_ = now;

  uint8_t channel = 0;
  SimpleProductStartMode start_mode = SimpleProductStartMode::DISCOVERY;
  if (direct_available) {
    wifi_second_chan_t secondary = WIFI_SECOND_CHAN_NONE;
    if (esp_wifi_get_channel(&channel, &secondary) != ESP_OK ||
        !valid_radio_channel(channel)) {
      ESP_LOGW(TAG, "ESP-NOW deferred: connected STA channel is not ready");
      return false;
    }
    start_mode = SimpleProductStartMode::DIRECT;
  }

  LinkKey pmk{};
  if (!derive_pmk_(&pmk)) return false;
  DriverError error = DriverError::WIFI_START_FAILED;
  if (start_mode == SimpleProductStartMode::DISCOVERY) {
#ifdef USE_WIFI
    if (wifi::global_wifi_component == nullptr) {
      pmk.fill(0);
      return false;
    }
    wifi::global_wifi_component->disable();
#endif
    error = radio_.initialize_standalone(this, pmk);
    if (error == DriverError::NONE) {
      radio_ownership_ = RadioOwnership::RELAY_ESPNOW;
    }
  } else {
    error = radio_.initialize(this, pmk);
    if (error == DriverError::NONE) {
      radio_ownership_ = RadioOwnership::DIRECT_WIFI;
    }
  }
  pmk.fill(0);
  if (error != DriverError::NONE) {
    ESP_LOGW(
        TAG,
        "ESP-NOW initialization failed error=%u teardown_confirmed=%s",
        static_cast<unsigned>(error),
        radio_.teardown_confirmed() ? "true" : "false");
    if (error == DriverError::ESPNOW_TEARDOWN_UNCONFIRMED ||
        !radio_.teardown_confirmed()) {
      request_safe_reboot_(
          "ESP-NOW runtime start cannot continue with unconfirmed teardown");
      return false;
    }
#ifdef USE_WIFI
    if (start_mode == SimpleProductStartMode::DISCOVERY &&
        wifi::global_wifi_component != nullptr) {
      wifi::global_wifi_component->enable();
    }
#endif
    radio_ownership_ = RadioOwnership::DIRECT_WIFI;
    return false;
  }

  if (start_mode == SimpleProductStartMode::DIRECT) {
    // Wi-Fi owns the channel while STA is associated. ESP-NOW shares the
    // already-observed channel; do not call esp_wifi_set_channel here.
    error = radio_.prepare_broadcast_peer(channel);
    if (error != DriverError::NONE) {
      ESP_LOGW(
          TAG,
          "ESP-NOW broadcast peer configuration failed error=%u",
          static_cast<unsigned>(error));
      if (!radio_.shutdown()) {
        request_safe_reboot_(
            "ESP-NOW broadcast-peer failure left teardown unconfirmed");
      }
      return false;
    }
  }

  diagnostics_.begin_boot_session();
  const SimpleProductError runtime_error =
      runtime_.start(peer_state_, local_mac_, channel, start_mode);
  if (runtime_error != SimpleProductError::NONE) {
    ESP_LOGW(
        TAG,
        "Simplified N3-W runtime start failed error=%u",
        static_cast<unsigned>(runtime_error));
    if (!radio_.shutdown()) {
      request_safe_reboot_(
          "N3-W runtime start failure left ESP-NOW teardown unconfirmed");
      return false;
    }
#ifdef USE_WIFI
    if (start_mode == SimpleProductStartMode::DISCOVERY &&
        wifi::global_wifi_component != nullptr) {
      wifi::global_wifi_component->enable();
    }
#endif
    radio_ownership_ = RadioOwnership::DIRECT_WIFI;
    return false;
  }
  runtime_.set_relay_capable(mqtt_connected());
  runtime_ready_ = true;
  recovery_schedule_.reset(now);
  diagnostics_.note_recovery_schedule(
      recovery_schedule_.next_presence_ms(),
      recovery_schedule_.next_full_verify_ms());
  next_recovery_probe_ms_ = now + kRecoveryProbeMs;
  if (start_mode == SimpleProductStartMode::DIRECT) {
    refresh_direct_ap_hint_();
  }
  ESP_LOGI(
      TAG,
      "Simplified N3-W product runtime active node=%s mode=%s direct_channel=%u",
      peer_state_.node_id.c_str(),
      start_mode == SimpleProductStartMode::DIRECT ? "direct" : "discovery",
      static_cast<unsigned>(channel));
  return true;
}

void SimpleProductComponent::advance_pairing_() {
  if (!wifi_connected()) return;
  const uint64_t now = now_ms();
  if (now < next_pairing_attempt_ms_) return;
  next_pairing_attempt_ms_ = now + kPairingRetryMs;
  const SimplePairingClientError result = pairing_client_.run_once(now);
  if (result == SimplePairingClientError::NONE ||
      result == SimplePairingClientError::ALREADY_PROVISIONED) {
    if (pairing_client_.provisioned()) {
      ESP_LOGI(
          TAG,
          "Simplified pairing committed; loading product runtime state");
      (void) load_runtime_state_();
      (void) configure_mqtt_();
    }
    return;
  }
  if (result == SimplePairingClientError::NOT_READY ||
      result == SimplePairingClientError::DISCOVERY_FAILED ||
      result == SimplePairingClientError::TRANSACTION_RENEWED ||
      result == SimplePairingClientError::ACK_PENDING) {
    ESP_LOGD(
        TAG,
        "Simplified pairing waiting code=%u",
        static_cast<unsigned>(result));
    return;
  }
  ESP_LOGW(
      TAG,
      "Simplified pairing attempt failed code=%u",
      static_cast<unsigned>(result));
}

void SimpleProductComponent::advance_recovery_() {
  if (!runtime_ready_ || runtime_.path_state() == LocalPathState::DIRECT) return;
  const uint64_t now = now_ms();

  if (radio_ownership_ == RadioOwnership::RELAY_RESTORE) {
    advance_relay_restore_();
    return;
  }

  if (radio_ownership_ == RadioOwnership::RELAY_ESPNOW) {
    if (direct_ap_bssid_valid_ &&
        valid_radio_channel(direct_ap_channel_) &&
        direct_ap_hint_policy_.expired(now)) {
      release_direct_ap_hint_authority_();
      pending_hint_release_acceleration_ = true;
      recovery_schedule_.request_full_verify(now);
      recovery_schedule_.defer_presence(now, 0);
    }

    if (runtime_.gateway_selection_busy()) return;

    if (runtime_.path_state() != LocalPathState::RELAY_ACTIVE &&
        recovery_schedule_.full_verify_backoff_ms() >
            kRecoveryProbeIntervalMs) {
      recovery_schedule_.accelerate_to_initial(now);
    }

    if (direct_ap_bssid_valid_ &&
        valid_radio_channel(direct_ap_channel_) &&
        recovery_schedule_.presence_due(now)) {
      if (runtime_.path_state() == LocalPathState::RELAY_ACTIVE &&
          last_relay_telemetry_ms_ != 0 &&
          now - last_relay_telemetry_ms_ <
              kDirectPresenceProbeQuietGuardMs) {
        recovery_schedule_.defer_presence(
            now, kDirectPresenceProbeQuietGuardMs);
        diagnostics_.note_recovery_probe_deferral(1U);
        diagnostics_.note_recovery_schedule(
            recovery_schedule_.next_presence_ms(),
            recovery_schedule_.next_full_verify_ms());
        return;
      }

      if (radio_.pending_unicast_sends() != 0U) {
        recovery_schedule_.defer_presence(
            now, kPendingUnicastDrainRetryMs);
        diagnostics_.note_recovery_probe_deferral(2U);
        diagnostics_.note_recovery_schedule(
            recovery_schedule_.next_presence_ms(),
            recovery_schedule_.next_full_verify_ms());
        return;
      }
      drain_send_completions_();

      const uint64_t presence_started_ms = now_ms();
      const DirectPresenceProbeResult presence =
          probe_direct_ap_presence_();
      const uint64_t presence_finished_ms = now_ms();
      diagnostics_.note_presence_probe(
          presence_started_ms,
          static_cast<uint32_t>(
              presence_finished_ms >= presence_started_ms
                  ? presence_finished_ms - presence_started_ms
                  : 0U),
          static_cast<uint8_t>(presence));

      if (presence == DirectPresenceProbeResult::RESTORE_FAILED) {
        recovery_schedule_.note_presence_error(now);
        diagnostics_.note_recovery_schedule(
            recovery_schedule_.next_presence_ms(),
            recovery_schedule_.next_full_verify_ms());
        begin_relay_restore_(RelayRestoreCause::PRESENCE_SCAN);
        advance_relay_restore_();
        return;
      }

      DirectApScanResult scan_result = DirectApScanResult::ERROR;
      if (presence == DirectPresenceProbeResult::FOUND) {
        scan_result = DirectApScanResult::FOUND;
      } else if (presence == DirectPresenceProbeResult::NOT_FOUND) {
        scan_result = DirectApScanResult::NOT_FOUND;
      }

      DirectApHintDecision hint_decision{};
      const bool hint_was_active = direct_ap_hint_policy_.active();
      if (hint_was_active) {
        hint_decision =
            direct_ap_hint_policy_.assess(now, scan_result);
      }

      if (presence == DirectPresenceProbeResult::FOUND) {
        direct_ap_hint_lease_.note_found(now);
        if (recovery_schedule_.note_presence(now, true)) {
          pending_ap_visible_acceleration_ = true;
        }
      } else if (presence == DirectPresenceProbeResult::NOT_FOUND) {
        (void) direct_ap_hint_lease_.note_not_found(now);
        (void) recovery_schedule_.note_presence(now, false);
      } else {
        recovery_schedule_.note_presence_error(now);
      }

      if (hint_was_active &&
          hint_decision.allow_configured_full_direct) {
        ESP_LOGW(
            TAG,
            "N3-W Direct AP hint authority released misses=%u scan_errors=%u locked=%s; retaining scan locator",
            static_cast<unsigned>(hint_decision.misses),
            static_cast<unsigned>(hint_decision.scan_errors),
            hint_decision.explicit_bssid_lock_preserved ? "true" : "false");
        release_direct_ap_hint_authority_();
        pending_hint_release_acceleration_ = true;
        recovery_schedule_.request_full_verify(now);
      }

      diagnostics_.note_recovery_schedule(
          recovery_schedule_.next_presence_ms(),
          recovery_schedule_.next_full_verify_ms());
    }

    const bool healthy_relay =
        runtime_.path_state() == LocalPathState::RELAY_ACTIVE;
    const bool locator_can_gate_full_verify =
        healthy_relay &&
        direct_ap_bssid_valid_ &&
        valid_radio_channel(direct_ap_channel_) &&
        direct_ap_hint_policy_.active();

    if (locator_can_gate_full_verify &&
        recovery_schedule_.presence_state() !=
            RelayDirectPresenceState::VISIBLE &&
        !pending_hint_release_acceleration_) {
      return;
    }

    if (!recovery_schedule_.full_verify_due(now)) return;

    if (healthy_relay &&
        last_relay_telemetry_ms_ != 0 &&
        now - last_relay_telemetry_ms_ <
            kDirectPresenceProbeQuietGuardMs) {
      recovery_schedule_.defer_full_verify(
          now, kDirectPresenceProbeQuietGuardMs);
      diagnostics_.note_recovery_probe_deferral(3U);
      diagnostics_.note_recovery_schedule(
          recovery_schedule_.next_presence_ms(),
          recovery_schedule_.next_full_verify_ms());
      return;
    }

    if (radio_.pending_unicast_sends() != 0U) {
      recovery_schedule_.defer_full_verify(
          now, kPendingUnicastDrainRetryMs);
      diagnostics_.note_recovery_probe_deferral(4U);
      diagnostics_.note_recovery_schedule(
          recovery_schedule_.next_presence_ms(),
          recovery_schedule_.next_full_verify_ms());
      return;
    }
    drain_send_completions_();

    if (healthy_relay && !telemetry_queue_.empty()) {
      recovery_schedule_.defer_full_verify(
          now, kDirectFullVerifyBacklogRetryMs);
      diagnostics_.note_recovery_probe_deferral(5U);
      diagnostics_.note_recovery_schedule(
          recovery_schedule_.next_presence_ms(),
          recovery_schedule_.next_full_verify_ms());
      return;
    }

    DirectFullVerifyTrigger trigger =
        healthy_relay ? DirectFullVerifyTrigger::BACKOFF
                      : DirectFullVerifyTrigger::NO_RELAY;
    if (pending_ap_visible_acceleration_) {
      trigger = DirectFullVerifyTrigger::AP_BECAME_VISIBLE;
    } else if (pending_hint_release_acceleration_) {
      trigger = DirectFullVerifyTrigger::HINT_RELEASED;
    }

    if (begin_direct_probe_(trigger)) {
      pending_ap_visible_acceleration_ = false;
      pending_hint_release_acceleration_ = false;
      return;
    }

    recovery_schedule_.defer_full_verify(
        now, kPendingUnicastDrainRetryMs);
    diagnostics_.note_recovery_probe_deferral(6U);
    diagnostics_.note_recovery_schedule(
        recovery_schedule_.next_presence_ms(),
        recovery_schedule_.next_full_verify_ms());
    return;
  }

  if (radio_ownership_ != RadioOwnership::DIRECT_PROBE) return;
  if (now < next_recovery_probe_ms_) return;
  next_recovery_probe_ms_ = now + kRecoveryProbeMs;

  const bool wifi_ready = wifi_connected();
  const bool mqtt_ready = wifi_ready && mqtt_connected();
  bool direct_check_success = false;
  if (wifi_ready && mqtt_ready) {
    direct_check_success = prepare_direct_probe_radio_();
  }

  const DirectRecoveryDecision decision =
      direct_recovery_attempt_.observe(DirectRecoveryObservation{
          now, wifi_ready, mqtt_ready, direct_check_success});

  if (decision.action ==
      DirectRecoveryAction::REQUEST_CONCRETE_DIRECT_RESTORE) {
    const DirectRecoveryCommitResult commit =
        runtime_.commit_direct_recovery_before(decision.absolute_deadline_ms);
    const DirectRecoveryDecision final_decision =
        direct_recovery_attempt_.on_concrete_direct_restore(
            commit.committed, commit.completed_at_ms);
    if (commit.committed &&
        final_decision.action == DirectRecoveryAction::COMMIT_DIRECT) {
      radio_ownership_ = RadioOwnership::DIRECT_WIFI;
      recovery_schedule_.note_full_verify_success(commit.completed_at_ms);
      diagnostics_.note_full_verify_terminal(
          static_cast<uint8_t>(DirectRecoveryTerminalReason::SUCCEEDED),
          static_cast<uint8_t>(
              std::min<std::size_t>(telemetry_queue_.size(), 255U)),
          telemetry_queue_dropped_,
          telemetry_attempt_failed_dropped_);
      diagnostics_.note_recovery_schedule(
          recovery_schedule_.next_presence_ms(),
          recovery_schedule_.next_full_verify_ms());
      refresh_direct_ap_hint_();
      ESP_LOGI(TAG, "N3-W Direct recovery committed; Wi-Fi owns radio");
      return;
    }
    diagnostics_.note_full_verify_terminal(
          static_cast<uint8_t>(final_decision.terminal_reason),
          static_cast<uint8_t>(
              std::min<std::size_t>(telemetry_queue_.size(), 255U)),
          telemetry_queue_dropped_,
          telemetry_attempt_failed_dropped_);
    begin_relay_restore_(RelayRestoreCause::FULL_DIRECT_VERIFY);
    advance_relay_restore_();
    return;
  }

  if (decision.phase == DirectRecoveryPhase::DIRECT_CONFIRM) {
    (void) runtime_.note_direct_recovery_probe(direct_check_success);
  } else {
    (void) runtime_.note_direct_recovery_probe(false);
  }

  if (decision.terminal) {
    diagnostics_.note_full_verify_terminal(
          static_cast<uint8_t>(decision.terminal_reason),
          static_cast<uint8_t>(
              std::min<std::size_t>(telemetry_queue_.size(), 255U)),
          telemetry_queue_dropped_,
          telemetry_attempt_failed_dropped_);
    begin_relay_restore_(RelayRestoreCause::FULL_DIRECT_VERIFY);
    advance_relay_restore_();
  }
}

bool SimpleProductComponent::claim_relay_radio_() {
  if ((radio_ownership_ == RadioOwnership::RELAY_ESPNOW ||
       radio_ownership_ == RadioOwnership::RELAY_RESTORE) &&
      radio_.initialized()) return true;
  LinkKey pmk{};
  if (!derive_pmk_(&pmk)) return false;
  if (!radio_.shutdown()) {
    pmk.fill(0);
    request_safe_reboot_("ESP-NOW teardown unconfirmed before Relay claim");
    return false;
  }
#ifdef USE_WIFI
  if (wifi::global_wifi_component == nullptr) {
    pmk.fill(0);
    return false;
  }
  wifi::global_wifi_component->disable();
#endif
  const DriverError error = radio_.initialize_standalone(this, pmk);
  pmk.fill(0);
  if (error != DriverError::NONE) {
    ESP_LOGW(
        TAG,
        "N3-W failed to claim standalone ESP-NOW radio error=%u",
        static_cast<unsigned>(error));
#ifdef USE_WIFI
    wifi::global_wifi_component->enable();
#endif
    radio_ownership_ = RadioOwnership::DIRECT_WIFI;
    return false;
  }
  radio_ownership_ = RadioOwnership::RELAY_ESPNOW;
  recovery_schedule_.reset(now_ms());
  pending_ap_visible_acceleration_ = false;
  pending_hint_release_acceleration_ = false;
  diagnostics_.note_recovery_schedule(
      recovery_schedule_.next_presence_ms(),
      recovery_schedule_.next_full_verify_ms());
  ESP_LOGI(TAG, "N3-W claimed exclusive standalone ESP-NOW radio ownership");
  return true;
}

bool SimpleProductComponent::begin_direct_probe_(
    DirectFullVerifyTrigger trigger) {
  if (radio_ownership_ != RadioOwnership::RELAY_ESPNOW ||
      runtime_.path_state() == LocalPathState::DIRECT ||
      runtime_.gateway_selection_busy() ||
      radio_.pending_unicast_sends() != 0U) return false;
#ifdef USE_WIFI
  if (wifi::global_wifi_component == nullptr) return false;
#endif
  const DirectRecoveryMode mode =
      runtime_.path_state() == LocalPathState::RELAY_ACTIVE
          ? DirectRecoveryMode::HEALTHY_RELAY
          : DirectRecoveryMode::NO_RELAY;
  if (!radio_.shutdown()) {
    request_safe_reboot_("ESP-NOW teardown unconfirmed before Direct probe");
    return false;
  }
#ifdef USE_WIFI
  wifi::global_wifi_component->enable();
#endif
  radio_ownership_ = RadioOwnership::DIRECT_PROBE;
  const uint64_t now = now_ms();
  active_full_verify_trigger_ = trigger;
  recovery_schedule_.note_full_verify_start(now);
  diagnostics_.note_full_verify_start(
      static_cast<uint8_t>(trigger),
      now,
      static_cast<uint8_t>(
          std::min<std::size_t>(telemetry_queue_.size(), 255U)),
      telemetry_queue_dropped_,
      telemetry_attempt_failed_dropped_);
  diagnostics_.note_recovery_schedule(
      recovery_schedule_.next_presence_ms(),
      recovery_schedule_.next_full_verify_ms());
  (void) runtime_.note_direct_recovery_probe(false);
  (void) direct_recovery_attempt_.begin(mode, now);
  next_recovery_probe_ms_ = now;
  ESP_LOGI(
      TAG,
      "N3-W opened phased Direct recovery mode=%u trigger=%u",
      static_cast<unsigned>(mode),
      static_cast<unsigned>(trigger));
  return true;
}

bool SimpleProductComponent::prepare_direct_probe_radio_() {
  uint8_t channel = 0;
  wifi_second_chan_t secondary = WIFI_SECOND_CHAN_NONE;
  if (esp_wifi_get_channel(&channel, &secondary) != ESP_OK ||
      !valid_radio_channel(channel)) {
    return false;
  }
  if (!radio_.initialized()) {
    LinkKey pmk{};
    if (!derive_pmk_(&pmk)) return false;
    const DriverError error = radio_.initialize(this, pmk);
    pmk.fill(0);
    if (error != DriverError::NONE) return false;
  }
  return radio_.prepare_broadcast_peer(channel) == DriverError::NONE &&
         runtime_.update_direct_channel_hint(channel);
}

bool SimpleProductComponent::explicit_bssid_lock_active_() const {
#ifdef USE_WIFI
  if (wifi::global_wifi_component == nullptr) {
    return true;
  }
  // Read the selected ESPHome Wi-Fi configuration, not the current IDF STA
  // connection parameters. ESPHome's scan-connect path copies the chosen scan
  // result BSSID into temporary connection parameters, so IDF bssid_set does
  // not prove the user configured a BSSID restriction.
  return wifi::global_wifi_component->get_sta().has_bssid();
#else
  return true;
#endif
}

void SimpleProductComponent::release_direct_ap_hint_authority_() {
  direct_ap_hint_lease_.clear();
  direct_ap_hint_policy_.clear();
}

void SimpleProductComponent::refresh_direct_ap_hint_() {
#ifdef USE_WIFI
  if (radio_ownership_ != RadioOwnership::DIRECT_WIFI || !wifi_connected()) {
    return;
  }
  wifi_ap_record_t ap{};
  if (esp_wifi_sta_get_ap_info(&ap) != ESP_OK ||
      !valid_radio_channel(ap.primary)) {
    return;
  }
  std::copy_n(ap.bssid, direct_ap_bssid_.size(), direct_ap_bssid_.begin());
  direct_ap_bssid_valid_ = std::any_of(
      direct_ap_bssid_.begin(),
      direct_ap_bssid_.end(),
      [](uint8_t value) { return value != 0; });
  if (!direct_ap_bssid_valid_) return;
  direct_ap_channel_ = ap.primary;
  const bool explicitly_locked = explicit_bssid_lock_active_();
  const uint64_t now = now_ms();
  direct_ap_hint_lease_.observe(now, explicitly_locked);
  direct_ap_hint_policy_.observe(now, explicitly_locked);
  (void) runtime_.update_direct_channel_hint(ap.primary);
#endif
}

SimpleProductComponent::DirectPresenceProbeResult
SimpleProductComponent::probe_direct_ap_presence_() {
#ifdef USE_WIFI
  if (radio_ownership_ != RadioOwnership::RELAY_ESPNOW ||
      !radio_.initialized() || !direct_ap_bssid_valid_ ||
      !valid_radio_channel(direct_ap_channel_)) {
    return DirectPresenceProbeResult::ERROR;
  }

  const uint8_t relay_channel = runtime_.working_channel();
  if (!valid_radio_channel(relay_channel)) {
    return DirectPresenceProbeResult::RESTORE_FAILED;
  }

  const auto scan_for_bound_bssid =
      [this](uint8_t channel, wifi_ap_record_t *record)
          -> DirectPresenceProbeResult {
    if (record == nullptr) return DirectPresenceProbeResult::ERROR;

    wifi_scan_config_t scan{};
    scan.bssid = direct_ap_bssid_.data();
    scan.channel = channel;
    scan.show_hidden = true;
    scan.scan_type = WIFI_SCAN_TYPE_PASSIVE;
    scan.scan_time.passive = kDirectPresenceProbePassiveMs;

    const uint64_t scan_started_ms = now_ms();
    const esp_err_t scan_result = esp_wifi_scan_start(&scan, true);
    const uint64_t scan_elapsed_ms = now_ms() - scan_started_ms;
    ESP_LOGI(
        TAG,
        "N3-W Direct AP presence scan channel=%u elapsed_ms=%llu result=%ld",
        static_cast<unsigned>(channel),
        static_cast<unsigned long long>(scan_elapsed_ms),
        static_cast<long>(scan_result));
    if (scan_result != ESP_OK) {
      return DirectPresenceProbeResult::ERROR;
    }

    uint16_t found_count = 0;
    const esp_err_t count_result = esp_wifi_scan_get_ap_num(&found_count);
    if (count_result != ESP_OK) {
      (void) esp_wifi_clear_ap_list();
      return DirectPresenceProbeResult::ERROR;
    }
    if (found_count == 0U) {
      (void) esp_wifi_clear_ap_list();
      return DirectPresenceProbeResult::NOT_FOUND;
    }

    wifi_ap_record_t candidate{};
    uint16_t capacity = 1;
    const esp_err_t records_result =
        esp_wifi_scan_get_ap_records(&capacity, &candidate);
    if (records_result != ESP_OK || capacity != 1U ||
        !std::equal(
            direct_ap_bssid_.begin(),
            direct_ap_bssid_.end(),
            candidate.bssid)) {
      (void) esp_wifi_clear_ap_list();
      return records_result == ESP_OK
                 ? DirectPresenceProbeResult::NOT_FOUND
                 : DirectPresenceProbeResult::ERROR;
    }
    *record = candidate;
    return DirectPresenceProbeResult::FOUND;
  };

  // First borrow only the previously associated AP channel. If that misses,
  // immediately widen the same recovery check to all allowed channels using
  // the exact remembered BSSID. AP channel changes therefore cost one bounded
  // scan cycle, not several exponentially-backed-off recovery intervals.
  wifi_ap_record_t record{};
  DirectPresenceProbeResult result =
      scan_for_bound_bssid(direct_ap_channel_, &record);
  if (result == DirectPresenceProbeResult::NOT_FOUND) {
    result = scan_for_bound_bssid(0, &record);
  }
  if (result == DirectPresenceProbeResult::FOUND &&
      valid_radio_channel(record.primary)) {
    direct_ap_channel_ = record.primary;
    (void) runtime_.update_direct_channel_hint(record.primary);
  }

  // Scanning is a short, planned loan of the radio. Relay ownership is not
  // considered restored until the driver verifies the concrete channel again.
  // Feed that concrete readback into the same diagnostic oracle used by normal
  // runtime channel commits so physical evidence cannot fall back to a logical
  // requested/working channel.
  const DriverError restore_result = radio_.set_channel(relay_channel);
  last_channel_observed_ = radio_.last_channel_observed();
  last_channel_error_raw_ = radio_.last_channel_error_raw();
  diagnostics_.note_channel_result(
      relay_channel,
      restore_result == DriverError::NONE,
      last_channel_observed_,
      last_channel_error_raw_,
      now_ms());
  if (restore_result != DriverError::NONE) {
    return DirectPresenceProbeResult::RESTORE_FAILED;
  }
  return result;
#else
  return DirectPresenceProbeResult::ERROR;
#endif
}

void SimpleProductComponent::schedule_full_direct_verify_(
    bool increase_backoff) {
  const uint64_t now = now_ms();
  recovery_schedule_.note_full_verify_failure(now, increase_backoff);
  diagnostics_.note_recovery_schedule(
      recovery_schedule_.next_presence_ms(),
      recovery_schedule_.next_full_verify_ms());
}

void SimpleProductComponent::begin_relay_restore_(
    RelayRestoreCause cause,
    uint32_t initial_delay_ms) {
  const uint64_t now = now_ms();
  radio_ownership_ = RadioOwnership::RELAY_RESTORE;
  relay_restore_cause_ = cause;
  relay_restore_budget_.start(now);
  diagnostics_.note_relay_restore(static_cast<uint8_t>(cause), 0U);
  next_relay_restore_attempt_ms_ = now + initial_delay_ms;
}

void SimpleProductComponent::begin_direct_probe_after_restore_exit_(
    uint64_t now) {
  if (!radio_.shutdown()) {
    request_safe_reboot_("ESP-NOW teardown unconfirmed after Relay restore exhaustion");
    return;
  }
#ifdef USE_WIFI
  if (wifi::global_wifi_component != nullptr) wifi::global_wifi_component->enable();
#endif
  radio_ownership_ = RadioOwnership::DIRECT_PROBE;
  active_full_verify_trigger_ = DirectFullVerifyTrigger::NO_RELAY;
  recovery_schedule_.note_full_verify_start(now);
  diagnostics_.note_full_verify_start(
      static_cast<uint8_t>(DirectFullVerifyTrigger::NO_RELAY),
      now,
      static_cast<uint8_t>(
          std::min<std::size_t>(telemetry_queue_.size(), 255U)),
      telemetry_queue_dropped_,
      telemetry_attempt_failed_dropped_);
  (void) runtime_.note_direct_recovery_probe(false);
  (void) direct_recovery_attempt_.begin(DirectRecoveryMode::NO_RELAY, now);
  next_recovery_probe_ms_ = now;
  relay_restore_cause_ = RelayRestoreCause::NONE;
  ESP_LOGW(
      TAG,
      "N3-W Relay restore budget exhausted; opened phased Direct recovery from Discovery");
}

void SimpleProductComponent::exit_relay_restore_failure_(uint64_t now) {
  ++relay_restore_exhausted_count_;
  const uint64_t elapsed =
      now >= relay_restore_budget_.started_ms()
          ? now - relay_restore_budget_.started_ms()
          : 0U;
  ESP_LOGE(
      TAG,
      "N3-W Relay restore budget exhausted attempts=%u elapsed_ms=%llu count=%u; abandoning stale Relay binding",
      static_cast<unsigned>(relay_restore_budget_.attempts()),
      static_cast<unsigned long long>(elapsed),
      static_cast<unsigned>(relay_restore_exhausted_count_));

  // End the failed ESP-NOW session first. An unconfirmed teardown must not
  // hand the same boot to another radio owner.
  if (!radio_.shutdown()) {
    request_safe_reboot_("ESP-NOW teardown unconfirmed after Relay restore exhaustion");
    return;
  }
  pending_unicast_deadline_.on_drained();
  clear_tx_completion_ring_();
  const SimpleProductError reset_result =
      runtime_.reset_to_discovery_after_radio_fault();
  if (reset_result != SimpleProductError::NONE) {
    ESP_LOGE(
        TAG,
        "N3-W failed to reset logical path to Discovery after Relay restore exhaustion code=%u",
        static_cast<unsigned>(reset_result));
  }
  relay_restore_budget_.clear();
  begin_direct_probe_after_restore_exit_(now);
}

void SimpleProductComponent::advance_relay_restore_() {
  if (radio_ownership_ != RadioOwnership::RELAY_RESTORE) return;
  const uint64_t now = now_ms();
  if (now < next_relay_restore_attempt_ms_) return;

  // A Relay restore may follow a clean Direct probe, or an abnormal teardown.
  // The abnormal case is never allowed to poll callbacks forever or re-use an
  // unconfirmed old event source.
  const CallbackQuiesceAction quiesce = callback_quiesce_action(
      radio_.callbacks_idle(),
      radio_.teardown_confirmed(),
      relay_restore_budget_,
      now);
  if (quiesce == CallbackQuiesceAction::WAIT) {
    next_relay_restore_attempt_ms_ =
        now + kPendingUnicastDrainRetryMs;
    return;
  }
  if (quiesce == CallbackQuiesceAction::REBOOT) {
    request_safe_reboot_(
        radio_.teardown_confirmed()
            ? "ESP-NOW callback quiesce exceeded Relay restore budget"
            : "ESP-NOW old event source stop could not be confirmed");
    return;
  }
  clear_tx_completion_ring_();
  if (relay_restore_cause_ ==
      RelayRestoreCause::GATEWAY_SELECTION_LOCAL_FAULT) {
    clear_rx_ring_();
  }

  if (restore_relay_radio_()) {
    const RelayRestoreCause completed_cause = relay_restore_cause_;
    diagnostics_.note_relay_restore(
        static_cast<uint8_t>(completed_cause), 1U);
    relay_restore_cause_ = RelayRestoreCause::NONE;
    relay_restore_budget_.clear();
    if (completed_cause == RelayRestoreCause::FULL_DIRECT_VERIFY) {
      schedule_full_direct_verify_(
          runtime_.path_state() == LocalPathState::RELAY_ACTIVE);
    } else {
      diagnostics_.note_recovery_schedule(
          recovery_schedule_.next_presence_ms(),
          recovery_schedule_.next_full_verify_ms());
    }
    ESP_LOGI(
        TAG,
        "N3-W Relay radio restored after recovery cause=%u",
        static_cast<unsigned>(completed_cause));
    return;
  }

  relay_restore_budget_.note_failure();
  diagnostics_.note_relay_restore(
      static_cast<uint8_t>(relay_restore_cause_), 2U);
  if (relay_restore_budget_.exhausted(now)) {
    diagnostics_.note_relay_restore(
        static_cast<uint8_t>(relay_restore_cause_), 3U);
    exit_relay_restore_failure_(now);
    return;
  }

  const uint32_t retry_ms =
      relay_restore_budget_.attempts() <= kRelayRestoreFastAttempts
          ? kRelayRestoreRetryFastMs
          : kRelayRestoreRetrySlowMs;
  next_relay_restore_attempt_ms_ = now + retry_ms;
  ESP_LOGW(
      TAG,
      "N3-W Relay restore retry deferred attempt=%u delay_ms=%u",
      static_cast<unsigned>(relay_restore_budget_.attempts()),
      static_cast<unsigned>(retry_ms));
}

bool SimpleProductComponent::enqueue_telemetry_(
    const std::string &telemetry_json,
    const std::string &boot_id,
    uint32_t seq) {
  if (telemetry_json.empty() || boot_id.empty()) return false;
  if (telemetry_queue_.size() >= kTelemetryQueueCapacity) {
    ++telemetry_queue_dropped_;
    ESP_LOGW(
        TAG,
        "N3-W telemetry hold buffer overflow; rejecting newest seq=%u depth=%u rejected=%u",
        static_cast<unsigned>(seq),
        static_cast<unsigned>(telemetry_queue_.size()),
        static_cast<unsigned>(telemetry_queue_dropped_));
    return false;
  }
  telemetry_queue_.push_back(PendingTelemetry{
      telemetry_json,
      boot_id,
      seq,
      PendingTelemetryState::QUEUED,
      {},
      TelemetryPathAccounting::TRANSPORT_ONLY,
      0,
  });
  ESP_LOGI(
      TAG,
      "N3-W telemetry held seq=%u depth=%u path=%u ownership=%u",
      static_cast<unsigned>(seq),
      static_cast<unsigned>(telemetry_queue_.size()),
      static_cast<unsigned>(runtime_.path_state()),
      static_cast<unsigned>(radio_ownership_));
  return true;
}

TelemetrySubmitDisposition SimpleProductComponent::flush_telemetry_queue_(
    TelemetryPathAccounting accounting) {
  if (telemetry_queue_.empty() || safe_reboot_requested_) {
    return TelemetrySubmitDisposition::BUFFERED;
  }
  if (radio_ownership_ == RadioOwnership::DIRECT_PROBE ||
      radio_ownership_ == RadioOwnership::RELAY_RESTORE) {
    return TelemetrySubmitDisposition::BUFFERED;
  }

  const uint64_t now = now_ms();
  if (now < next_telemetry_flush_ms_) {
    return TelemetrySubmitDisposition::BUFFERED;
  }

  if (telemetry_queue_.front().state ==
      PendingTelemetryState::RELAY_IN_FLIGHT) {
    return TelemetrySubmitDisposition::BUFFERED;
  }

  const LocalPathState current_path = runtime_.path_state();
  if (current_path != LocalPathState::DIRECT &&
      current_path != LocalPathState::RELAY_ACTIVE) {
    next_telemetry_flush_ms_ = now + kTelemetryHoldPollMs;
    return TelemetrySubmitDisposition::BUFFERED;
  }

  // DIRECT without a connected MQTT client is not a transport attempt.
  // Keep the oldest sample held. A newly generated business sample may still
  // record one path-health failure so failover can progress to Discovery.
  if (current_path == LocalPathState::DIRECT && !mqtt_connected()) {
    SimpleProductError state_result = SimpleProductError::NONE;
    if (accounting == TelemetryPathAccounting::RECORD_PATH_RESULT) {
      state_result = runtime_.note_direct_result(false);
    }
    ESP_LOGI(
        TAG,
        "N3-W telemetry held without Direct MQTT opportunity seq=%u depth=%u state_result=%u",
        static_cast<unsigned>(telemetry_queue_.front().seq),
        static_cast<unsigned>(telemetry_queue_.size()),
        static_cast<unsigned>(state_result));
    next_telemetry_flush_ms_ = now + kTelemetryHoldPollMs;
    if (state_result != SimpleProductError::NONE &&
        state_result != SimpleProductError::RADIO_FAILED) {
      ++telemetry_invariant_failures_;
      request_safe_reboot_("telemetry Direct hold path-state failure");
      return TelemetrySubmitDisposition::REJECTED;
    }
    return TelemetrySubmitDisposition::BUFFERED;
  }

  // ESP-IDF recommends waiting for the previous ESP-NOW send callback before
  // submitting the next frame. Synchronous submit success is only an
  // in-flight state; MAC completion is the end of the single Relay attempt.
  if (current_path == LocalPathState::RELAY_ACTIVE) {
    if (radio_.pending_unicast_sends() != 0U) {
      next_telemetry_flush_ms_ = now + kPendingUnicastDrainRetryMs;
      return TelemetrySubmitDisposition::BUFFERED;
    }
    drain_send_completions_();
    if (safe_reboot_requested_ || telemetry_queue_.empty()) {
      return safe_reboot_requested_
                 ? TelemetrySubmitDisposition::REJECTED
                 : TelemetrySubmitDisposition::BUFFERED;
    }
    if (now_ms() < next_telemetry_flush_ms_) {
      return TelemetrySubmitDisposition::BUFFERED;
    }
    if (telemetry_queue_.front().state ==
        PendingTelemetryState::RELAY_IN_FLIGHT) {
      return TelemetrySubmitDisposition::BUFFERED;
    }
    if (runtime_.path_state() != LocalPathState::RELAY_ACTIVE) {
      next_telemetry_flush_ms_ = now + kTelemetryHoldPollMs;
      return TelemetrySubmitDisposition::BUFFERED;
    }
  }

  PendingTelemetry &item = telemetry_queue_.front();
  const LocalPathState path_before = runtime_.path_state();
  const SimpleProductError result =
      runtime_.send_telemetry(
          item.telemetry_json, item.boot_id, item.seq, accounting);
  ++item.submit_count;

  if (result == SimpleProductError::NONE) {
    if (path_before == LocalPathState::RELAY_ACTIVE) {
      const auto &active_relay = runtime_.active_relay();
      if (!active_relay.has_value()) {
        ++telemetry_invariant_failures_;
        ESP_LOGE(
            TAG,
            "N3-W telemetry invariant failure after Relay submit seq=%u failures=%u",
            static_cast<unsigned>(item.seq),
            static_cast<unsigned>(telemetry_invariant_failures_));
        request_safe_reboot_("telemetry relay submit lost active peer");
        return TelemetrySubmitDisposition::REJECTED;
      }
      item.state = PendingTelemetryState::RELAY_IN_FLIGHT;
      item.relay_destination = active_relay->mac;
      item.in_flight_accounting = accounting;
      last_relay_telemetry_ms_ = now;
      ESP_LOGI(
          TAG,
          "N3-W telemetry Relay single attempt in-flight seq=%u depth=%u",
          static_cast<unsigned>(item.seq),
          static_cast<unsigned>(telemetry_queue_.size()));
      return TelemetrySubmitDisposition::SUBMITTED;
    }

    ESP_LOGI(
        TAG,
        "N3-W telemetry Direct single attempt submitted seq=%u depth_after=%u",
        static_cast<unsigned>(item.seq),
        static_cast<unsigned>(telemetry_queue_.size() - 1U));
    telemetry_queue_.pop_front();
    next_telemetry_flush_ms_ = now + kTelemetryFlushSpacingMs;
    return TelemetrySubmitDisposition::SUBMITTED;
  }

  // NOT_READY means the runtime did not obtain a real transport opportunity.
  // Preserve the sample for a later path rather than converting it into a
  // resend after a failed transport attempt.
  if (result == SimpleProductError::NOT_READY) {
    next_telemetry_flush_ms_ = now + kTelemetryHoldPollMs;
    return TelemetrySubmitDisposition::BUFFERED;
  }

  // Under the accepted latest-state contract, a real Direct/Relay transport
  // attempt is performed at most once per ordinary periodic sample.
  if (result == SimpleProductError::MQTT_FAILED ||
      result == SimpleProductError::RADIO_FAILED) {
    const uint32_t failed_seq = item.seq;
    ++telemetry_attempt_failed_dropped_;
    telemetry_queue_.pop_front();
    next_telemetry_flush_ms_ = now + kTelemetryFlushSpacingMs;
    ESP_LOGW(
        TAG,
        "N3-W telemetry single attempt failed; not resending seq=%u error=%u dropped=%u",
        static_cast<unsigned>(failed_seq),
        static_cast<unsigned>(result),
        static_cast<unsigned>(telemetry_attempt_failed_dropped_));
    return TelemetrySubmitDisposition::REJECTED;
  }

  ++telemetry_invariant_failures_;
  ESP_LOGE(
      TAG,
      "N3-W telemetry permanent/invariant failure retained seq=%u error=%u depth=%u failures=%u",
      static_cast<unsigned>(item.seq),
      static_cast<unsigned>(result),
      static_cast<unsigned>(telemetry_queue_.size()),
      static_cast<unsigned>(telemetry_invariant_failures_));
  request_safe_reboot_("telemetry permanent/invariant failure");
  return TelemetrySubmitDisposition::REJECTED;
}

bool SimpleProductComponent::restore_relay_radio_() {
  if (!radio_.shutdown()) {
    return false;
  }
#ifdef USE_WIFI
  if (wifi::global_wifi_component == nullptr) return false;
  wifi::global_wifi_component->disable();
#endif
  LinkKey pmk{};
  if (!derive_pmk_(&pmk)) return false;
  const DriverError error = radio_.initialize_standalone(this, pmk);
  pmk.fill(0);
  if (error != DriverError::NONE) {
    ESP_LOGW(
        TAG,
        "N3-W failed to restore standalone ESP-NOW radio error=%u",
        static_cast<unsigned>(error));
    return false;
  }
  if (runtime_.rebind_radio_state() != SimpleProductError::NONE) {
    radio_.shutdown();
    return false;
  }
  radio_ownership_ = RadioOwnership::RELAY_ESPNOW;
  ESP_LOGI(TAG, "N3-W restored Relay ESP-NOW channel and encrypted peer");
  return true;
}

void SimpleProductComponent::drain_send_completions_() {
  if (!runtime_ready_) return;
  while (true) {
    const uint8_t read =
        tx_completion_read_.load(std::memory_order_relaxed);
    const uint8_t write =
        tx_completion_write_.load(std::memory_order_acquire);
    if (read == write) break;

    const TxCompletionSlot slot = tx_completion_ring_[read];
    tx_completion_read_.store(
        static_cast<uint8_t>((read + 1U) % kTxCompletionRingSlots),
        std::memory_order_release);

    if (telemetry_queue_.empty() ||
        telemetry_queue_.front().state !=
            PendingTelemetryState::RELAY_IN_FLIGHT ||
        telemetry_queue_.front().relay_destination != slot.destination) {
      ++telemetry_invariant_failures_;
      ESP_LOGE(
          TAG,
          "N3-W telemetry completion ownership mismatch success=%s depth=%u failures=%u",
          slot.success ? "true" : "false",
          static_cast<unsigned>(telemetry_queue_.size()),
          static_cast<unsigned>(telemetry_invariant_failures_));
      request_safe_reboot_("telemetry completion ownership mismatch");
      break;
    }

    PendingTelemetry &item = telemetry_queue_.front();
    const uint32_t completed_seq = item.seq;
    SimpleProductError state_result = SimpleProductError::NONE;
    if (item.in_flight_accounting ==
        TelemetryPathAccounting::RECORD_PATH_RESULT) {
      state_result =
          runtime_.note_relay_delivery_result(slot.destination, slot.success);
    }

    if (slot.success) {
      ESP_LOGI(
          TAG,
          "N3-W telemetry Relay single attempt completed seq=%u depth_after=%u",
          static_cast<unsigned>(completed_seq),
          static_cast<unsigned>(telemetry_queue_.size() - 1U));
    } else {
      ++telemetry_completion_failures_;
      ++telemetry_attempt_failed_dropped_;
      ESP_LOGW(
          TAG,
          "N3-W telemetry Relay single attempt failed; not resending seq=%u state_error=%u dropped=%u",
          static_cast<unsigned>(completed_seq),
          static_cast<unsigned>(state_result),
          static_cast<unsigned>(telemetry_attempt_failed_dropped_));
    }

    // Either completion outcome ends this ordinary periodic sample's one Relay
    // transport attempt. Do not convert MAC failure into application resend.
    telemetry_queue_.pop_front();
    next_telemetry_flush_ms_ = now_ms() + kTelemetryFlushSpacingMs;

    // A RADIO_FAILED result can be produced while Relay failure accounting
    // moves the path into Discovery and its first channel setup also fails.
    // Recovery owns that fault. Other state errors are invariants.
    if (state_result != SimpleProductError::NONE &&
        state_result != SimpleProductError::RADIO_FAILED) {
      ++telemetry_invariant_failures_;
      ESP_LOGE(
          TAG,
          "N3-W telemetry completion state failure seq=%u error=%u failures=%u",
          static_cast<unsigned>(completed_seq),
          static_cast<unsigned>(state_result),
          static_cast<unsigned>(telemetry_invariant_failures_));
      request_safe_reboot_("telemetry completion state failure");
      break;
    }
  }

  if (radio_.pending_unicast_sends() == 0U) {
    pending_unicast_deadline_.on_drained();
    if (!safe_reboot_requested_ &&
        !telemetry_queue_.empty() &&
        telemetry_queue_.front().state ==
            PendingTelemetryState::RELAY_IN_FLIGHT) {
      ++telemetry_invariant_failures_;
      ESP_LOGE(
          TAG,
          "N3-W telemetry completion missing for in-flight seq=%u failures=%u",
          static_cast<unsigned>(telemetry_queue_.front().seq),
          static_cast<unsigned>(telemetry_invariant_failures_));
      request_safe_reboot_("telemetry completion missing");
    }
  }
}

bool SimpleProductComponent::check_pending_unicast_timeout_() {
  if (radio_.pending_unicast_sends() == 0U) {
    pending_unicast_deadline_.on_drained();
    return false;
  }
  const uint64_t now = now_ms();
  if (!pending_unicast_deadline_.timed_out(now)) {
    return false;
  }
  // The callback runs on the Wi-Fi task. Recheck after the deadline decision
  // so a completion racing with this loop is not unnecessarily converted into
  // a session abort.
  if (radio_.pending_unicast_sends() == 0U) {
    drain_send_completions_();
    pending_unicast_deadline_.on_drained();
    return false;
  }
  handle_pending_unicast_timeout_(now);
  return true;
}

void SimpleProductComponent::clear_tx_completion_ring_() {
  const uint8_t write =
      tx_completion_write_.load(std::memory_order_acquire);
  tx_completion_read_.store(write, std::memory_order_release);
}

void SimpleProductComponent::handle_pending_unicast_timeout_(uint64_t now) {
  ++pending_unicast_timeout_count_;
  ESP_LOGE(
      TAG,
      "N3-W ESP-NOW unicast completion timeout pending=%u count=%u; fencing old ESP-NOW session and rebooting",
      static_cast<unsigned>(radio_.pending_unicast_sends()),
      static_cast<unsigned>(pending_unicast_timeout_count_));

  // ESP-IDF 5.5.4 exposes unregister/deinit but does not publish a guarantee
  // that a send event already queued below the user callback boundary cannot
  // enter after a later same-boot re-registration. Therefore a missing
  // completion is not recovered by reusing the same ESP-NOW session object.
  // Detach/unregister/deinit first, then cross a reboot boundary before any new
  // session can exist.
  const bool teardown_confirmed = radio_.shutdown();
  pending_unicast_deadline_.on_drained();
  clear_tx_completion_ring_();
  ESP_LOGW(
      TAG,
      "N3-W timed-out ESP-NOW teardown_confirmed=%s uptime_ms=%llu",
      teardown_confirmed ? "true" : "false",
      static_cast<unsigned long long>(now));
  request_safe_reboot_(
      teardown_confirmed
          ? "ESP-NOW completion timeout requires fresh boot session"
          : "ESP-NOW completion timeout teardown unconfirmed");
}

void SimpleProductComponent::request_safe_reboot_(const char *reason) {
  if (safe_reboot_requested_) return;
  safe_reboot_requested_ = true;
  ESP_LOGE(
      TAG,
      "N3-W fail-safe reboot requested reason=%s",
      reason != nullptr ? reason : "unspecified");
  App.safe_reboot();
}

bool SimpleProductComponent::drain_radio_() {
  if (!runtime_ready_) return false;
  while (true) {
    const uint8_t read = rx_read_.load(std::memory_order_relaxed);
    const uint8_t write = rx_write_.load(std::memory_order_acquire);
    if (read == write) break;
    const RxSlot &slot = rx_ring_[read];
    const bool selection_busy_before =
        runtime_.gateway_selection_busy();
    const SimpleProductError result = runtime_.on_radio_receive(
        slot.source,
        slot.data.data(),
        slot.size,
        slot.channel,
        slot.rssi_dbm);
    rx_read_.store(
        static_cast<uint8_t>((read + 1U) % kRxRingSlots),
        std::memory_order_release);
    if (consume_gateway_selection_runtime_result_(
            result, selection_busy_before)) {
      return true;
    }
  }
  return false;
}

void SimpleProductComponent::clear_rx_ring_() {
  rx_read_.store(
      rx_write_.load(std::memory_order_acquire),
      std::memory_order_release);
}

bool SimpleProductComponent::consume_gateway_selection_runtime_result_(
    SimpleProductError result,
    bool selection_busy_before) {
  const bool selection_busy_after =
      runtime_.gateway_selection_busy();
  if (!gateway_selection_local_fault_requires_restore(
          result,
          selection_busy_before,
          selection_busy_after)) {
    return false;
  }

  if (radio_ownership_ != RadioOwnership::RELAY_ESPNOW ||
      runtime_.path_state() != LocalPathState::DISCOVERY) {
    ESP_LOGE(
        TAG,
        "N3-W Gateway selection local fault escaped expected ownership/state result=%u ownership=%u path=%u",
        static_cast<unsigned>(result),
        static_cast<unsigned>(radio_ownership_),
        static_cast<unsigned>(runtime_.path_state()));
    request_safe_reboot_(
        "Gateway selection local fault escaped Relay Discovery ownership");
    return true;
  }

  ESP_LOGE(
      TAG,
      "N3-W Gateway selection local fault entering bounded Relay restore result=%u",
      static_cast<unsigned>(result));

  // Existing Relay-restore quiesce logic assumes the old ESP-NOW event source
  // has already been stopped. Gateway-selection faults happen while Relay
  // ownership is still live, so establish the same teardown precondition
  // before entering RELAY_RESTORE.
  if (!radio_.shutdown()) {
    request_safe_reboot_(
        "ESP-NOW teardown unconfirmed after Gateway selection local fault");
    return true;
  }
  clear_rx_ring_();
  begin_relay_restore_(
      RelayRestoreCause::GATEWAY_SELECTION_LOCAL_FAULT,
      0);
  return true;
}

void SimpleProductComponent::on_espnow_receive(
    const MacAddress &source,
    const uint8_t *data,
    std::size_t size) {
  EspNowReceiveMetadata metadata{};
  on_espnow_receive_with_metadata(source, data, size, metadata);
}

void SimpleProductComponent::on_espnow_receive_with_metadata(
    const MacAddress &source,
    const uint8_t *data,
    std::size_t size,
    const EspNowReceiveMetadata &metadata) {
  if (data == nullptr || size == 0 || size > kEspNowPhysicalDatagramLimit) {
    return;
  }
  const uint8_t write = rx_write_.load(std::memory_order_relaxed);
  const uint8_t next = static_cast<uint8_t>((write + 1U) % kRxRingSlots);
  if (next == rx_read_.load(std::memory_order_acquire)) {
    rx_dropped_.fetch_add(1, std::memory_order_relaxed);
    return;
  }
  RxSlot &slot = rx_ring_[write];
  slot.source = source;
  slot.size = static_cast<uint16_t>(size);
  slot.rssi_dbm = metadata.rssi_dbm;
  slot.channel = metadata.channel;
  std::copy_n(data, size, slot.data.begin());
  rx_write_.store(next, std::memory_order_release);
}

void SimpleProductComponent::on_espnow_send_result(
    const MacAddress &destination,
    bool success) {
  if (destination == kEspNowBroadcastMac) {
    return;
  }

  // ESP-NOW send callbacks run from the Wi-Fi task. Enqueue only bounded
  // completion metadata here; path state is owned by the normal component loop.
  const uint8_t write =
      tx_completion_write_.load(std::memory_order_relaxed);
  const uint8_t next =
      static_cast<uint8_t>((write + 1U) % kTxCompletionRingSlots);
  if (next == tx_completion_read_.load(std::memory_order_acquire)) {
    tx_completion_dropped_.fetch_add(1, std::memory_order_relaxed);
    return;
  }
  TxCompletionSlot &slot = tx_completion_ring_[write];
  slot.destination = destination;
  slot.success = success;
  tx_completion_write_.store(next, std::memory_order_release);
}

bool SimpleProductComponent::set_radio_channel(uint8_t channel) {
  if (!valid_radio_channel(channel)) {
    last_channel_observed_ = 0;
    last_channel_error_raw_ = -1;
    diagnostics_.note_channel_result(channel, false, 0, -1, now_ms());
    return false;
  }

  // While STA is associated, ESP-NOW must share the channel already owned by
  // Wi-Fi. Treat an idempotent request for that channel as success without
  // calling esp_wifi_set_channel(); reject any attempt to move an associated
  // STA to a different channel. N3-W may call the official channel setter only
  // after claim_relay_radio_() has stopped ESPHome's reconnect state machine.
  if (radio_ownership_ == RadioOwnership::DIRECT_PROBE &&
      !wifi_connected()) {
    last_channel_observed_ = 0;
    last_channel_error_raw_ = -2;
    diagnostics_.note_channel_result(channel, false, 0, -2, now_ms());
    return false;
  }

  // A Direct publish can fail while the STA is still associated (for example,
  // when only the broker path is unavailable). Once the runtime has entered
  // Discovery, do not let that association retain channel ownership: stop the
  // reconnect state machine and hand the radio to standalone ESP-NOW before
  // the first scan/channel operation.
  if (radio_ownership_ == RadioOwnership::DIRECT_WIFI &&
      runtime_.path_state() != LocalPathState::DIRECT &&
      !claim_relay_radio_()) {
    last_channel_observed_ = 0;
    last_channel_error_raw_ = -3;
    diagnostics_.note_channel_result(channel, false, 0, -3, now_ms());
    return false;
  }

  if ((radio_ownership_ == RadioOwnership::DIRECT_WIFI ||
       radio_ownership_ == RadioOwnership::DIRECT_PROBE) &&
      wifi_connected()) {
    uint8_t current_channel = 0;
    wifi_second_chan_t secondary = WIFI_SECOND_CHAN_NONE;
    const esp_err_t get_result = esp_wifi_get_channel(&current_channel, &secondary);
    last_channel_observed_ = current_channel;
    last_channel_error_raw_ = static_cast<int32_t>(get_result);
    if (get_result != ESP_OK || !valid_radio_channel(current_channel)) {
      diagnostics_.note_channel_result(
          channel, false, current_channel, static_cast<int32_t>(get_result), now_ms());
      return false;
    }
    diagnostics_.note_channel_result(
        channel, current_channel == channel, current_channel, 0, now_ms());
    return current_channel == channel;
  }

  if (!claim_relay_radio_()) {
    last_channel_observed_ = 0;
    last_channel_error_raw_ = -3;
    diagnostics_.note_channel_result(channel, false, 0, -3, now_ms());
    return false;
  }

  const DriverError set_result = radio_.set_channel(channel);
  const bool success =
      set_result == DriverError::NONE &&
      radio_.prepare_broadcast_peer(channel) == DriverError::NONE;
  last_channel_observed_ = radio_.last_channel_observed();
  last_channel_error_raw_ = radio_.last_channel_error_raw();
  diagnostics_.note_channel_result(
      channel,
      success,
      radio_.last_channel_observed(),
      radio_.last_channel_error_raw(),
      now_ms());
  return success;
}

bool SimpleProductComponent::broadcast_control(
    const uint8_t *data,
    std::size_t size) {
  return radio_.send_broadcast(data, size) == DriverError::NONE;
}

bool SimpleProductComponent::install_encrypted_peer(
    const MacAddress &peer_mac,
    const LinkKey &lmk,
    uint8_t channel) {
  return radio_.add_encrypted_peer(peer_mac, lmk, channel) ==
         DriverError::NONE;
}

bool SimpleProductComponent::remove_peer(const MacAddress &peer_mac) {
  return radio_.remove_peer(peer_mac) == DriverError::NONE;
}

bool SimpleProductComponent::send_encrypted_peer(
    const MacAddress &peer_mac,
    const uint8_t *data,
    std::size_t size) {
  const uint64_t submit_ms = now_ms();
  const DriverError result = radio_.send(peer_mac, data, size);
  const bool success = result == DriverError::NONE;
  if (success) {
    pending_unicast_deadline_.on_submit(submit_ms);
  }
  return success;
}

bool SimpleProductComponent::publish_direct(
    const std::string &topic,
    const std::string &payload) {
#ifdef USE_MQTT
  return mqtt_connected() &&
         mqtt::global_mqtt_client->publish(topic, payload, 1, false);
#else
  (void) topic;
  (void) payload;
  return false;
#endif
}

bool SimpleProductComponent::publish_relay(
    const std::string &topic,
    const std::string &payload) {
#ifdef USE_MQTT
  return mqtt_connected() &&
         mqtt::global_mqtt_client->publish(topic, payload, 1, false);
#else
  (void) topic;
  (void) payload;
  return false;
#endif
}

uint64_t SimpleProductComponent::now_ms() const {
  return static_cast<uint64_t>(millis());
}

bool SimpleProductComponent::fill(uint8_t *data, std::size_t size) {
  return fill_pairing_random(data, size);
}

bool SimpleProductComponent::fill_pairing_random(
    uint8_t *data,
    std::size_t size) {
  if (data == nullptr || size == 0) return false;
  esp_fill_random(data, size);
  return std::any_of(
      data, data + size, [](uint8_t value) { return value != 0; });
}

bool SimpleProductComponent::discover_manager(
    const std::string &request_json,
    std::string *response_json) {
  if (request_json.empty() || response_json == nullptr) return false;
  response_json->clear();
  const int fd = ::socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
  if (fd < 0) return false;
  int broadcast = 1;
  timeval timeout{};
  timeout.tv_sec = 1;
  timeout.tv_usec = 0;
  bool ok =
      ::setsockopt(
          fd, SOL_SOCKET, SO_BROADCAST, &broadcast, sizeof(broadcast)) == 0 &&
      ::setsockopt(
          fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) == 0;
  sockaddr_in target{};
  target.sin_family = AF_INET;
  target.sin_port = htons(kDiscoveryPort);
  target.sin_addr.s_addr = htonl(INADDR_BROADCAST);
  if (ok) {
    ok = ::sendto(
             fd,
             request_json.data(),
             request_json.size(),
             0,
             reinterpret_cast<sockaddr *>(&target),
             sizeof(target)) ==
         static_cast<ssize_t>(request_json.size());
  }
  if (ok) {
    std::array<char, 1401> buffer{};
    const ssize_t received =
        ::recv(fd, buffer.data(), buffer.size() - 1U, 0);
    if (received > 0) {
      response_json->assign(
          buffer.data(), static_cast<std::size_t>(received));
    } else {
      ok = false;
    }
  }
  ::close(fd);
  return ok && !response_json->empty();
}

bool SimpleProductComponent::http_post_(
    const std::string &host,
    uint16_t port,
    const std::string &path,
    const std::string &request_json,
    int *status_code,
    std::string *response_json) {
  if (host.empty() || port == 0 || path.empty() || path.front() != '/' ||
      request_json.empty() || status_code == nullptr ||
      response_json == nullptr) {
    return false;
  }
  response_json->clear();
  const std::string url =
      "http://" + host + ":" + std::to_string(port) + path;
  HttpResponseCollector collector{response_json, false};
  esp_http_client_config_t config{};
  config.url = url.c_str();
  config.event_handler = http_event_handler;
  config.user_data = &collector;
  config.timeout_ms = 4000;
  esp_http_client_handle_t client = esp_http_client_init(&config);
  if (client == nullptr) return false;
  esp_http_client_set_method(client, HTTP_METHOD_POST);
  esp_http_client_set_header(client, "Content-Type", "application/json");
  esp_http_client_set_header(client, "Cache-Control", "no-store");
  esp_http_client_set_post_field(
      client,
      request_json.data(),
      static_cast<int>(request_json.size()));
  const esp_err_t result = esp_http_client_perform(client);
  *status_code = esp_http_client_get_status_code(client);
  esp_http_client_cleanup(client);
  return result == ESP_OK && !collector.overflow;
}

bool SimpleProductComponent::post_json(
    const SimpleManagerCandidateV2 &candidate,
    const std::string &path,
    const std::string &request_json,
    int *status_code,
    std::string *response_json) {
  return candidate.valid() &&
         http_post_(
             candidate.host,
             candidate.port,
             path,
             request_json,
             status_code,
             response_json);
}

bool SimpleProductComponent::post_json(
    const PendingPairingAckV2 &pending,
    const std::string &path,
    const std::string &request_json,
    int *status_code,
    std::string *response_json) {
  return pending.valid() &&
         http_post_(
             pending.manager_host,
             pending.manager_port,
             path,
             request_json,
             status_code,
             response_json);
}

}  // namespace esphome::greenhouse_n3w_core
