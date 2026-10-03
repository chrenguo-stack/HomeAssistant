#include "n3w_simple_product_component.h"

#include <algorithm>
#include <array>
#include <cstdio>
#include <utility>

#ifdef USE_MQTT
#include "esphome/components/mqtt/mqtt_client.h"
#endif
#ifdef USE_WIFI
#include "esphome/components/wifi/wifi_component.h"
#endif
#include "esphome/core/log.h"
#include "esp_netif.h"
#include "esp_netif_ip_addr.h"

namespace esphome::greenhouse_n3w_core {
namespace {

static const char *const TAG = "n3w_broker_relocation";

bool broker_mqtt_connected() {
#ifdef USE_MQTT
  return mqtt::global_mqtt_client != nullptr &&
         mqtt::global_mqtt_client->is_connected();
#else
  return false;
#endif
}

bool broker_wifi_connected() {
#ifdef USE_WIFI
  return wifi::global_wifi_component != nullptr &&
         wifi::global_wifi_component->is_connected();
#else
  return false;
#endif
}

}

bool SimpleProductComponent::current_wifi_ipv4_(
    std::string *local_ipv4,
    std::string *subnet_mask) const {
  if (local_ipv4 == nullptr || subnet_mask == nullptr) return false;
  esp_netif_t *netif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
  if (netif == nullptr) return false;
  esp_netif_ip_info_t info{};
  if (esp_netif_get_ip_info(netif, &info) != ESP_OK ||
      info.ip.addr == 0U || info.netmask.addr == 0U) {
    return false;
  }
  std::array<char, IP4ADDR_STRLEN_MAX> ip_text{};
  std::array<char, IP4ADDR_STRLEN_MAX> mask_text{};
  const int ip_written = std::snprintf(
      ip_text.data(), ip_text.size(), IPSTR, IP2STR(&info.ip));
  const int mask_written = std::snprintf(
      mask_text.data(), mask_text.size(), IPSTR, IP2STR(&info.netmask));
  if (ip_written <= 0 || mask_written <= 0 ||
      static_cast<std::size_t>(ip_written) >= ip_text.size() ||
      static_cast<std::size_t>(mask_written) >= mask_text.size()) {
    return false;
  }
  *local_ipv4 = ip_text.data();
  *subnet_mask = mask_text.data();
  return true;
}

void SimpleProductComponent::reset_broker_relocation_attempt_() {
  broker_discovery_session_.reset();
  broker_discovery_attempted_ = false;
  broker_candidate_active_ = false;
  broker_candidate_verified_ = false;
  broker_mqtt_failure_started_ms_ = 0;
  broker_candidate_started_ms_ = 0;
  broker_candidate_deadline_ms_ = 0;
  broker_discovery_completed_ms_ = 0;
  pending_broker_candidate_host_.clear();
  broker_discovery_request_id_.clear();
  broker_discovery_nonce_.clear();
  broker_discovery_local_ipv4_.clear();
  broker_discovery_subnet_mask_.clear();
  broker_relocation_targets_.clear();
  broker_relocation_target_index_ = 0;
  if (!broker_relocation_initialized_ && broker_state_.valid()) {
    stable_runtime_broker_host_ = broker_state_.broker_host;
    broker_relocation_initialized_ = true;
  }
}

bool SimpleProductComponent::retarget_runtime_broker_(
    const std::string &host,
    bool reconnect) {
#ifdef USE_MQTT
  if (host.empty() || !broker_state_.valid() ||
      mqtt::global_mqtt_client == nullptr) {
    return false;
  }
  auto *client = mqtt::global_mqtt_client;
  if (!client->n3w_runtime_retarget_server(
          host, broker_state_.broker_port)) {
    return false;
  }
  if (!reconnect) return true;

  client->n3w_runtime_fence_old_events();
  if (client->n3w_runtime_request_reconnect()) return true;

  if (!stable_runtime_broker_host_.empty() &&
      client->n3w_runtime_retarget_server(
          stable_runtime_broker_host_, broker_state_.broker_port)) {
    client->n3w_runtime_fence_old_events();
    if (!client->n3w_runtime_request_reconnect()) {
      (void) client->n3w_runtime_request_disconnect();
    }
  }
  return false;
#else
  (void) host;
  (void) reconnect;
  return false;
#endif
}

void SimpleProductComponent::rollback_broker_candidate_() {
  broker_discovery_session_.reset();
  const bool had_candidate =
      broker_candidate_active_ ||
      !pending_broker_candidate_host_.empty() ||
      broker_relocation_target_index_ != 0U;
  bool restored = true;
#ifdef USE_MQTT
  if (had_candidate && broker_relocation_initialized_ &&
      !stable_runtime_broker_host_.empty() && broker_state_.valid() &&
      mqtt::global_mqtt_client != nullptr) {
    auto *client = mqtt::global_mqtt_client;
    restored = client->n3w_runtime_retarget_server(
        stable_runtime_broker_host_, broker_state_.broker_port);
    if (restored) {
      client->n3w_runtime_fence_old_events();
      if (!client->n3w_runtime_request_reconnect()) {
        (void) client->n3w_runtime_request_disconnect();
      }
    }
  }
#endif
  if (had_candidate) {
    ESP_LOGI(
        TAG,
        "N3-W Broker candidate rolled back restored=%s",
        restored ? "true" : "false");
  }
  broker_candidate_active_ = false;
  broker_candidate_verified_ = false;
  broker_candidate_started_ms_ = 0;
  broker_candidate_deadline_ms_ = 0;
  pending_broker_candidate_host_.clear();
}

bool SimpleProductComponent::start_broker_discovery_() {
  if (!pairing_client_.provisioned() || !peer_state_.valid() ||
      !broker_state_.valid() || !broker_wifi_connected() ||
      broker_mqtt_connected()) {
    return false;
  }
  std::string local_ipv4;
  std::string subnet_mask;
  if (!current_wifi_ipv4_(&local_ipv4, &subnet_mask)) return false;

  std::array<uint8_t, 16> request_random{};
  std::array<uint8_t, 32> nonce_random{};
  if (!broker_discovery_random_.fill_discovery_random(
          request_random.data(), request_random.size()) ||
      !broker_discovery_random_.fill_discovery_random(
          nonce_random.data(), nonce_random.size())) {
    return false;
  }

  std::string request_json;
  if (!build_simple_discovery_query(
          pairing_client_.hardware_id(),
          request_random,
          nonce_random,
          &broker_discovery_request_id_,
          &broker_discovery_nonce_,
          &request_json)) {
    return false;
  }

  const uint64_t now = now_ms();
  if (!broker_discovery_session_.begin(request_json, now)) return false;
  broker_discovery_attempted_ = true;
  broker_discovery_ever_started_ = true;
  last_broker_discovery_started_ms_ = now;
  broker_discovery_local_ipv4_ = std::move(local_ipv4);
  broker_discovery_subnet_mask_ = std::move(subnet_mask);
  ESP_LOGI(TAG, "N3-W Broker relocation discovery started");
  return true;
}

bool SimpleProductComponent::finish_broker_discovery_() {
  const SimpleDiscoveryFilterContext context{
      peer_state_.system_id,
      broker_discovery_local_ipv4_,
      broker_discovery_subnet_mask_,
  };
  const auto candidates = parse_filter_simple_discovery_datagrams(
      broker_discovery_session_.datagrams(),
      broker_discovery_request_id_,
      broker_discovery_nonce_,
      context);
  broker_relocation_targets_ =
      make_simple_broker_recovery_targets(candidates, broker_state_.broker_port);
  broker_relocation_targets_.erase(
      std::remove_if(
          broker_relocation_targets_.begin(),
          broker_relocation_targets_.end(),
          [&](const SimpleBrokerRecoveryTarget &target) {
            return target.host == stable_runtime_broker_host_;
          }),
      broker_relocation_targets_.end());
  broker_relocation_target_index_ = 0;
  broker_discovery_completed_ms_ = now_ms();
  broker_discovery_session_.reset();
  ESP_LOGI(
      TAG,
      "N3-W Broker relocation discovery retained=%u",
      static_cast<unsigned>(broker_relocation_targets_.size()));
  return !broker_relocation_targets_.empty();
}

bool SimpleProductComponent::start_next_broker_candidate_() {
  const uint64_t now = now_ms();
  const uint64_t deadline = broker_relocation_candidate_deadline(
      now,
      direct_recovery_attempt_.phase_deadline_ms(),
      direct_recovery_attempt_.absolute_deadline_ms(),
      kDirectRecoveryConfirmBudgetMs);
  if (deadline == 0U) return false;

  std::string current_ipv4;
  std::string current_mask;
  if (!current_wifi_ipv4_(&current_ipv4, &current_mask) ||
      current_ipv4 != broker_discovery_local_ipv4_ ||
      current_mask != broker_discovery_subnet_mask_) {
    broker_relocation_target_index_ = broker_relocation_targets_.size();
    ESP_LOGW(TAG, "N3-W Broker relocation network changed after discovery");
    return false;
  }

  while (broker_relocation_target_index_ < broker_relocation_targets_.size()) {
    const SimpleBrokerRecoveryTarget target =
        broker_relocation_targets_[broker_relocation_target_index_++];
    if (target.host.empty() || target.host == stable_runtime_broker_host_ ||
        target.ttl_s == 0U) {
      continue;
    }
    const uint64_t ttl_ms = static_cast<uint64_t>(target.ttl_s) * 1000U;
    if (broker_discovery_completed_ms_ == 0U ||
        now < broker_discovery_completed_ms_ ||
        now - broker_discovery_completed_ms_ >= ttl_ms) {
      continue;
    }
    if (!retarget_runtime_broker_(target.host, true)) {
      broker_relocation_target_index_ = broker_relocation_targets_.size();
      ESP_LOGW(TAG, "N3-W Broker candidate bounded reconnect request failed");
      return false;
    }
    pending_broker_candidate_host_ = target.host;
    broker_candidate_active_ = true;
    broker_candidate_verified_ = false;
    broker_candidate_started_ms_ = now;
    broker_candidate_deadline_ms_ = deadline;
    ESP_LOGI(TAG, "N3-W Broker relocation candidate attempt started");
    return true;
  }
  return false;
}

void SimpleProductComponent::advance_broker_relocation_() {
  if (!broker_wifi_connected() || broker_mqtt_connected() ||
      direct_recovery_attempt_.phase() != DirectRecoveryPhase::MQTT_RECOVERY) {
    return;
  }

  const uint64_t now = now_ms();
  if (broker_mqtt_failure_started_ms_ == 0U) {
    broker_mqtt_failure_started_ms_ = now;
    return;
  }

  if (broker_candidate_active_) {
    if (broker_candidate_deadline_ms_ != 0U &&
        now >= broker_candidate_deadline_ms_) {
      broker_candidate_active_ = false;
      broker_candidate_verified_ = false;
      broker_candidate_started_ms_ = 0;
      broker_candidate_deadline_ms_ = 0;
      pending_broker_candidate_host_.clear();
      if (!start_next_broker_candidate_()) {
        rollback_broker_candidate_();
      }
    }
    return;
  }

  if (broker_discovery_session_.active()) {
    const Esp32ManagerDiscoverySessionStatus status =
        broker_discovery_session_.poll(now);
    if (status == Esp32ManagerDiscoverySessionStatus::IN_PROGRESS) return;
    if (status == Esp32ManagerDiscoverySessionStatus::COMPLETE &&
        finish_broker_discovery_()) {
      if (start_next_broker_candidate_()) return;
      rollback_broker_candidate_();
      return;
    }
    broker_discovery_session_.reset();
    return;
  }

  if (broker_discovery_attempted_ ||
      !broker_relocation_trigger_due(broker_mqtt_failure_started_ms_, now)) {
    return;
  }
  if (broker_discovery_ever_started_ &&
      (now < last_broker_discovery_started_ms_ ||
       now - last_broker_discovery_started_ms_ <
           kBrokerRelocationDiscoveryMinIntervalMs)) {
    return;
  }
  if (!broker_relocation_discovery_can_start(
          now,
          direct_recovery_attempt_.phase_deadline_ms(),
          direct_recovery_attempt_.absolute_deadline_ms(),
          kDirectRecoveryConfirmBudgetMs)) {
    return;
  }
  (void) start_broker_discovery_();
}

void SimpleProductComponent::on_direct_recovery_probe_tick(bool success) {
  if (!runtime_ready_ || radio_ownership_ != RadioOwnership::DIRECT_PROBE ||
      !broker_state_.valid()) {
    return;
  }
  if (!broker_relocation_initialized_) {
    stable_runtime_broker_host_ = broker_state_.broker_host;
    broker_relocation_initialized_ = true;
  }

  const DirectRecoveryPhase phase = direct_recovery_attempt_.phase();
  if (phase == DirectRecoveryPhase::IDLE) {
    reset_broker_relocation_attempt_();
    return;
  }
  if (phase == DirectRecoveryPhase::FAILED) {
    rollback_broker_candidate_();
    return;
  }
  if (broker_candidate_active_ && broker_mqtt_connected()) {
    broker_candidate_verified_ = true;
  }
  if (phase == DirectRecoveryPhase::MQTT_RECOVERY && !success) {
    advance_broker_relocation_();
  }
}

void SimpleProductComponent::on_direct_recovery_commit_result(bool committed) {
  if (!broker_relocation_initialized_) return;
  if (!committed) {
    rollback_broker_candidate_();
    return;
  }
  if (broker_candidate_active_ && broker_candidate_verified_ &&
      !pending_broker_candidate_host_.empty()) {
    stable_runtime_broker_host_ = pending_broker_candidate_host_;
    ESP_LOGI(TAG, "N3-W Broker relocation candidate promoted for this boot");
  }
  reset_broker_relocation_attempt_();
}

}  // namespace esphome::greenhouse_n3w_core
