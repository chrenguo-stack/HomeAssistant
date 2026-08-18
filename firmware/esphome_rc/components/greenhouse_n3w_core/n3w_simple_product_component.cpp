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

SimpleProductComponent::SimpleProductComponent()
    : runtime_(this, this, this),
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
  if (!activation_enabled_ || is_failed()) return;
  drain_radio_();
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
  runtime_.set_relay_capable(mqtt_connected());
  (void) runtime_.tick();
  advance_recovery_();
}

bool SimpleProductComponent::send_telemetry_json(
    const std::string &telemetry_json,
    const std::string &boot_id,
    uint32_t seq) {
  if (!runtime_ready_) return false;
  return runtime_.send_telemetry(telemetry_json, boot_id, seq) ==
         SimpleProductError::NONE;
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
  if (!runtime_state_loaded_ || !mqtt_configured_ || !wifi_connected()) {
    return false;
  }
  const uint64_t now = now_ms();
  if (radio_attempted_ &&
      now - last_radio_attempt_ms_ < kRadioRetryIntervalMs) {
    return false;
  }
  radio_attempted_ = true;
  last_radio_attempt_ms_ = now;

  uint8_t channel = 0;
  wifi_second_chan_t secondary = WIFI_SECOND_CHAN_NONE;
  if (esp_wifi_get_channel(&channel, &secondary) != ESP_OK ||
      !valid_radio_channel(channel)) {
    ESP_LOGW(TAG, "ESP-NOW deferred: connected STA channel is not ready");
    return false;
  }
  LinkKey pmk{};
  if (!derive_pmk_(&pmk)) return false;
  DriverError error = radio_.initialize(this, pmk);
  pmk.fill(0);
  if (error != DriverError::NONE) {
    ESP_LOGW(
        TAG,
        "ESP-NOW initialization failed error=%u",
        static_cast<unsigned>(error));
    return false;
  }

  // Wi-Fi owns the channel while STA is associated. ESP-NOW shares the
  // already-observed channel; do not call esp_wifi_set_channel here.
  error = radio_.prepare_broadcast_peer(channel);
  if (error != DriverError::NONE) {
    ESP_LOGW(
        TAG,
        "ESP-NOW broadcast peer configuration failed error=%u",
        static_cast<unsigned>(error));
    radio_.shutdown();
    return false;
  }
  const SimpleProductError runtime_error =
      runtime_.start(peer_state_, local_mac_, channel);
  if (runtime_error != SimpleProductError::NONE) {
    ESP_LOGW(
        TAG,
        "Simplified N3-W runtime start failed error=%u",
        static_cast<unsigned>(runtime_error));
    radio_.shutdown();
    return false;
  }
  runtime_.set_relay_capable(mqtt_connected());
  runtime_ready_ = true;
  next_recovery_probe_ms_ = now + kRecoveryProbeMs;
  ESP_LOGI(
      TAG,
      "Simplified N3-W product runtime active node=%s channel=%u",
      peer_state_.node_id.c_str(),
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
  if (now < next_recovery_probe_ms_) return;
  next_recovery_probe_ms_ = now + kRecoveryProbeMs;
  bool direct_ready = wifi_connected() && mqtt_connected();
  if (direct_ready) {
    uint8_t channel = 0;
    wifi_second_chan_t secondary = WIFI_SECOND_CHAN_NONE;
    if (esp_wifi_get_channel(&channel, &secondary) != ESP_OK ||
        !valid_radio_channel(channel) ||
        !runtime_.update_direct_channel_hint(channel)) {
      direct_ready = false;
    }
  }
  (void) runtime_.note_direct_recovery_probe(direct_ready);
}

void SimpleProductComponent::drain_radio_() {
  if (!runtime_ready_) return;
  while (true) {
    const uint8_t read = rx_read_.load(std::memory_order_relaxed);
    const uint8_t write = rx_write_.load(std::memory_order_acquire);
    if (read == write) break;
    const RxSlot &slot = rx_ring_[read];
    (void) runtime_.on_radio_receive(
        slot.source, slot.data.data(), slot.size, slot.channel);
    rx_read_.store(
        static_cast<uint8_t>((read + 1U) % kRxRingSlots),
        std::memory_order_release);
  }
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
  slot.channel = metadata.channel;
  std::copy_n(data, size, slot.data.begin());
  rx_write_.store(next, std::memory_order_release);
}

void SimpleProductComponent::on_espnow_send_result(
    const MacAddress &destination,
    bool success) {
  (void) destination;
  (void) success;
}

bool SimpleProductComponent::set_radio_channel(uint8_t channel) {
  if (!valid_radio_channel(channel)) return false;

  // While STA is associated, ESP-NOW must share the channel already owned by
  // Wi-Fi. Treat an idempotent request for that channel as success without
  // calling esp_wifi_set_channel(); reject any attempt to move an associated
  // STA to a different channel. Once STA is disconnected, the ESP-NOW runtime
  // may control the radio channel for discovery/relay scanning as before.
  if (wifi_connected()) {
    uint8_t current_channel = 0;
    wifi_second_chan_t secondary = WIFI_SECOND_CHAN_NONE;
    if (esp_wifi_get_channel(&current_channel, &secondary) != ESP_OK ||
        !valid_radio_channel(current_channel)) {
      return false;
    }
    return current_channel == channel;
  }

  return radio_.set_channel(channel) == DriverError::NONE;
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
  return radio_.send(peer_mac, data, size) == DriverError::NONE;
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
