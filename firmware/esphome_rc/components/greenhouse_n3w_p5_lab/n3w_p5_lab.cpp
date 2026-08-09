#include "n3w_p5_lab.h"

#include <algorithm>
#include <cctype>
#include <cstdio>
#include <cstring>

#include "esphome/components/mqtt/mqtt_client.h"
#include "esphome/core/log.h"

#ifdef USE_ESP32
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#endif

namespace esphome::greenhouse_n3w_p5_lab {
namespace {

static const char *const TAG = "n3w_p5_lab";
constexpr uint64_t kRadioRetryIntervalMs = 1000;

uint8_t hex_nibble(char value) {
  if (value >= '0' && value <= '9') return static_cast<uint8_t>(value - '0');
  if (value >= 'a' && value <= 'f') return static_cast<uint8_t>(value - 'a' + 10);
  if (value >= 'A' && value <= 'F') return static_cast<uint8_t>(value - 'A' + 10);
  return 0xff;
}

std::string upper_trim(std::string value) {
  while (!value.empty() && std::isspace(static_cast<unsigned char>(value.front()))) value.erase(value.begin());
  while (!value.empty() && std::isspace(static_cast<unsigned char>(value.back()))) value.pop_back();
  std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) {
    return static_cast<char>(std::toupper(c));
  });
  return value;
}

}  // namespace

float GreenhouseN3wP5Lab::get_setup_priority() const { return setup_priority::AFTER_WIFI; }

void GreenhouseN3wP5Lab::setup() {
  ESP_LOGI(TAG, "P5 lab setup role=%s execution_enabled=%s", role_.c_str(), execution_enabled_ ? "true" : "false");
  if (!parse_configuration_()) {
    ESP_LOGE(TAG, "P5 lab configuration rejected");
    this->mark_failed();
    return;
  }
  if (!execution_enabled_) {
    ESP_LOGI(TAG, "Compile-only target is inert; no radio or MQTT traffic is started");
    return;
  }
#ifdef USE_ESP32
  rx_queue_ = xQueueCreate(8, sizeof(RxEvent));
  tx_queue_ = xQueueCreate(8, sizeof(TxEvent));
  if (rx_queue_ == nullptr || tx_queue_ == nullptr) {
    ESP_LOGE(TAG, "Unable to allocate bounded ESP-NOW event queues");
    this->mark_failed();
    return;
  }
#endif
  if (is_child_ && !initialize_child_session_()) {
    this->mark_failed();
    return;
  }
}

void GreenhouseN3wP5Lab::dump_config() {
  ESP_LOGCONFIG(TAG, "N3-W P5 isolated lab component");
  ESP_LOGCONFIG(TAG, "  role: %s", role_.c_str());
  ESP_LOGCONFIG(TAG, "  execution enabled: %s", execution_enabled_ ? "true" : "false");
  ESP_LOGCONFIG(TAG, "  system_id: %s", system_id_.c_str());
  ESP_LOGCONFIG(TAG, "  node_id: %s", node_id_.c_str());
  ESP_LOGCONFIG(TAG, "  gateway_id: %s", gateway_id_.c_str());
  ESP_LOGCONFIG(TAG, "  application key bytes logged: false");
  ESP_LOGCONFIG(TAG, "  PMK/LMK bytes logged: false");
}

bool GreenhouseN3wP5Lab::parse_hex_(const std::string &value, uint8_t *output, std::size_t bytes) {
  if (output == nullptr || value.size() != bytes * 2) return false;
  uint8_t aggregate = 0;
  for (std::size_t i = 0; i < bytes; ++i) {
    const uint8_t hi = hex_nibble(value[i * 2]);
    const uint8_t lo = hex_nibble(value[i * 2 + 1]);
    if (hi == 0xff || lo == 0xff) return false;
    output[i] = static_cast<uint8_t>((hi << 4U) | lo);
    aggregate |= output[i];
  }
  return aggregate != 0;
}

bool GreenhouseN3wP5Lab::parse_mac_(const std::string &value, MacAddress *output) {
  if (output == nullptr || value.size() != 17) return false;
  for (std::size_t i = 0; i < output->size(); ++i) {
    const std::size_t offset = i * 3;
    const uint8_t hi = hex_nibble(value[offset]);
    const uint8_t lo = hex_nibble(value[offset + 1]);
    if (hi == 0xff || lo == 0xff) return false;
    (*output)[i] = static_cast<uint8_t>((hi << 4U) | lo);
    if (i != output->size() - 1 && value[offset + 2] != ':') return false;
  }
  uint8_t aggregate = 0;
  for (uint8_t byte : *output) aggregate |= byte;
  return aggregate != 0 && (((*output)[0] & 0x01U) == 0);
}

bool GreenhouseN3wP5Lab::parse_configuration_() {
  is_child_ = role_ == "child";
  if (!is_child_ && role_ != "relay") return false;
  if (!greenhouse_n3w_core::valid_identity(system_id_) ||
      !greenhouse_n3w_core::valid_identity(node_id_) ||
      !greenhouse_n3w_core::valid_identity(gateway_id_)) return false;
  if (!parse_mac_(peer_mac_text_, &peer_mac_)) return false;
  if (!parse_hex_(pmk_hex_, pmk_.data(), pmk_.size()) ||
      !parse_hex_(lmk_hex_, lmk_.data(), lmk_.size())) return false;
  if (publish_interval_ms_ < 1000 || session_floor_ == 0) return false;

  relay_binding_.gateway_id = gateway_id_;
  relay_binding_.peer_mac = peer_mac_;
  relay_binding_.lmk = lmk_;
  child_binding_.node_id = node_id_;
  child_binding_.peer_mac = peer_mac_;
  child_binding_.lmk = lmk_;

  if (is_child_) {
    if (!parse_hex_(app_key_epoch1_hex_, key_epoch1_.key.data(), key_epoch1_.key.size()) ||
        !parse_hex_(app_key_epoch2_hex_, key_epoch2_.key.data(), key_epoch2_.key.size())) return false;
    key_epoch1_.lifecycle = greenhouse_n3w_core::KeyLifecycle::ACTIVE;
    key_epoch1_.key_epoch = 1;
    key_epoch1_.session_floor = session_floor_;
    key_epoch2_.lifecycle = greenhouse_n3w_core::KeyLifecycle::ACTIVE;
    key_epoch2_.key_epoch = 2;
    key_epoch2_.session_floor = session_floor_;
  } else if (!app_key_epoch1_hex_.empty() || !app_key_epoch2_hex_.empty()) {
    ESP_LOGE(TAG, "Relay must not receive Child application key material");
    return false;
  }
  return relay_binding_.valid() && child_binding_.valid();
}

bool GreenhouseN3wP5Lab::initialize_child_session_() {
  auto error = boot_.begin(&boot_store_, session_floor_);
  if (error == greenhouse_n3w_core::CoreError::STORE_MISSING) {
    error = boot_.provision_recovery_floor(&boot_store_, session_floor_);
    if (error == greenhouse_n3w_core::CoreError::NONE)
      error = boot_.begin(&boot_store_, session_floor_);
  }
  if (error != greenhouse_n3w_core::CoreError::NONE) {
    ESP_LOGE(TAG, "Boot-session persistence fail closed error=%u", static_cast<unsigned>(error));
    return false;
  }
  ESP_LOGI(TAG, "Child boot session ready boot_id=%s", boot_.boot_id().c_str());
  return true;
}

uint64_t GreenhouseN3wP5Lab::now_ms_() {
#ifdef USE_ESP32
  return static_cast<uint64_t>(esp_timer_get_time() / 1000ULL);
#else
  return 0;
#endif
}

bool GreenhouseN3wP5Lab::ensure_radio_ready_() {
  if (!execution_enabled_) return false;
  if (radio_ready_) return true;
#ifdef USE_ESP32
  const uint64_t now = now_ms_();
  if (radio_attempted_ && now - last_radio_attempt_ms_ < kRadioRetryIntervalMs) return false;
  radio_attempted_ = true;
  last_radio_attempt_ms_ = now;

  uint8_t primary = 0;
  wifi_second_chan_t secondary = WIFI_SECOND_CHAN_NONE;
  if (esp_wifi_get_channel(&primary, &secondary) != ESP_OK ||
      !greenhouse_n3w_core::valid_radio_channel(primary)) {
    ESP_LOGW(TAG, "ESP-NOW deferred: connected STA channel is not ready");
    return false;
  }
  relay_binding_.preferred_channel = primary;
  const auto init_error = driver_.initialize(this, pmk_);
  if (init_error != greenhouse_n3w_core::DriverError::NONE) {
    ESP_LOGW(TAG, "ESP-NOW initialization failed error=%u", static_cast<unsigned>(init_error));
    return false;
  }

  // Wi-Fi owns the channel while STA is associated. ESP-NOW shares that
  // already-observed channel; calling esp_wifi_set_channel here is rejected by
  // ESP-IDF on a connected STA and previously caused an init/deinit loop.
  const auto peer_error = driver_.add_encrypted_peer(peer_mac_, lmk_, primary);
  if (peer_error != greenhouse_n3w_core::DriverError::NONE) {
    driver_.shutdown();
    ESP_LOGW(TAG, "ESP-NOW peer configuration failed error=%u", static_cast<unsigned>(peer_error));
    return false;
  }
  radio_ready_ = true;
  ESP_LOGI(TAG, "ESP-NOW ready role=%s channel=%u", role_.c_str(), primary);
  return true;
#else
  return false;
#endif
}

void GreenhouseN3wP5Lab::loop() {
  if (!execution_enabled_ || this->is_failed()) return;
  ensure_radio_ready_();
  process_rx_();
  process_tx_();
  if (!is_child_) return;
  maybe_probe_();
  flush_relay_cache_();
  maybe_publish_();
}

void GreenhouseN3wP5Lab::on_espnow_receive(
    const MacAddress &source,
    const uint8_t *data,
    std::size_t size) {
#ifdef USE_ESP32
  if (rx_queue_ == nullptr || data == nullptr || size == 0 || size > greenhouse_n3w_core::kEspNowDatagramLimit) {
    ++rx_dropped_;
    return;
  }
  RxEvent event{};
  event.source = source;
  event.size = static_cast<uint16_t>(size);
  std::memcpy(event.data.data(), data, size);
  if (xQueueSend(rx_queue_, &event, 0) != pdTRUE) ++rx_dropped_;
#else
  (void) source;
  (void) data;
  (void) size;
#endif
}

void GreenhouseN3wP5Lab::on_espnow_send_result(
    const MacAddress &destination,
    bool success) {
  (void) destination;
#ifdef USE_ESP32
  if (success || tx_queue_ == nullptr) return;
  TxEvent event{};
  xQueueSend(tx_queue_, &event, 0);
#else
  (void) success;
#endif
}

void GreenhouseN3wP5Lab::process_rx_() {
#ifdef USE_ESP32
  if (rx_queue_ == nullptr) return;
  RxEvent event{};
  while (xQueueReceive(rx_queue_, &event, 0) == pdTRUE) {
    if (!greenhouse_n3w_core::same_mac(event.source, peer_mac_)) continue;
    if (is_child_) process_child_packet_(event);
    else process_relay_packet_(event);
  }
#endif
}

void GreenhouseN3wP5Lab::process_tx_() {
#ifdef USE_ESP32
  if (tx_queue_ == nullptr) return;
  TxEvent event{};
  while (xQueueReceive(tx_queue_, &event, 0) == pdTRUE) {
    if (event.success) continue;
    ++send_failures_;
    ESP_LOGW(TAG, "ESP-NOW delivery callback failed total=%u", static_cast<unsigned>(send_failures_));
  }
#endif
}

void GreenhouseN3wP5Lab::process_child_packet_(const RxEvent &event) {
  greenhouse_n3w_core::ProbeAckPacket probe{};
  if (greenhouse_n3w_core::decode_authenticated_probe_ack(
          event.data.data(), event.size, lmk_, &probe) == greenhouse_n3w_core::RadioError::NONE) {
    if (probe.accepted && probe.challenge == probe_challenge_) {
      relay_authenticated_ = true;
      ESP_LOGI(TAG, "Authenticated Relay probe accepted");
    }
    return;
  }
  ReceiptAckPacket receipt{};
  if (greenhouse_n3w_core::decode_authenticated_receipt_ack(
          event.data.data(), event.size, lmk_, &receipt) == greenhouse_n3w_core::RadioError::NONE) {
    const bool removed = cache_.acknowledge(receipt);
    ESP_LOGI(TAG, "Relay receipt status=%u removed=%s", static_cast<unsigned>(receipt.status), removed ? "true" : "false");
  }
}

void GreenhouseN3wP5Lab::process_relay_packet_(const RxEvent &event) {
  greenhouse_n3w_core::ProbePacket probe{};
  if (greenhouse_n3w_core::decode_authenticated_probe(
          event.data.data(), event.size, gateway_id_, child_binding_, &probe) == greenhouse_n3w_core::RadioError::NONE) {
    std::vector<uint8_t> reply;
    if (greenhouse_n3w_core::encode_authenticated_probe_ack(lmk_, probe.challenge, true, &reply) ==
        greenhouse_n3w_core::RadioError::NONE)
      driver_.send(peer_mac_, reply.data(), reply.size());
    return;
  }

  ReceiptAckPacket receipt{};
  bool receipt_ready = false;
  const auto error = relay_ingress_.accept_fragment(
      event.data.data(), event.size, gateway_id_, node_id_, &receipt, &receipt_ready);
  const bool completed_receipt =
      receipt_ready ||
      (error == greenhouse_n3w_core::RadioError::NONE && receipt.boot_session != 0);
  if (completed_receipt) {
    std::vector<uint8_t> reply;
    if (greenhouse_n3w_core::encode_authenticated_receipt_ack(
            lmk_, receipt.boot_session, receipt.seq, receipt.status, &reply) == greenhouse_n3w_core::RadioError::NONE)
      driver_.send(peer_mac_, reply.data(), reply.size());
  } else if (error != greenhouse_n3w_core::RadioError::NONE &&
             error != greenhouse_n3w_core::RadioError::DUPLICATE_FRAGMENT) {
    ESP_LOGW(TAG, "Relay fragment rejected error=%u", static_cast<unsigned>(error));
  }
}

bool GreenhouseN3wP5Lab::accept_for_forwarding(const RelayFrame &frame) {
  if (is_child_ || mqtt::global_mqtt_client == nullptr || !mqtt::global_mqtt_client->is_connected()) return false;
  std::string payload;
  if (greenhouse_n3w_core::serialize_relay_frame_json(frame, &payload) != greenhouse_n3w_core::CoreError::NONE)
    return false;
  const std::string topic = "gh/v1/" + system_id_ + "/ingress/gateway/" + gateway_id_ + "/" + node_id_ + "/frame";
  return mqtt::global_mqtt_client->publish(topic, payload, 1, false);
}

void GreenhouseN3wP5Lab::maybe_probe_() {
  if (desired_path_ != DesiredPath::RELAY || relay_authenticated_ || !radio_ready_) return;
  const uint64_t now = now_ms_();
  if (now - last_probe_ms_ < 2000) return;
  last_probe_ms_ = now;
  send_probe_();
}

bool GreenhouseN3wP5Lab::send_probe_() {
  std::vector<uint8_t> packet;
  if (greenhouse_n3w_core::encode_authenticated_probe(relay_binding_, node_id_, probe_challenge_, &packet) !=
      greenhouse_n3w_core::RadioError::NONE)
    return false;
  return driver_.send(peer_mac_, packet.data(), packet.size()) == greenhouse_n3w_core::DriverError::NONE;
}

void GreenhouseN3wP5Lab::maybe_publish_() {
  const uint64_t now = now_ms_();
  if (now - last_publish_ms_ < publish_interval_ms_) return;
  if (desired_path_ == DesiredPath::RELAY &&
      (!relay_authenticated_ || !radio_ready_ || cache_.full()))
    return;
  if (desired_path_ == DesiredPath::DIRECT &&
      (mqtt::global_mqtt_client == nullptr || !mqtt::global_mqtt_client->is_connected()))
    return;
  uint32_t seq = 0;
  if (boot_.take_sequence(&seq) != greenhouse_n3w_core::CoreError::NONE) {
    ESP_LOGE(TAG, "Sequence exhausted or boot session unavailable");
    this->mark_failed();
    return;
  }
  last_publish_ms_ = now;
  const std::string telemetry = build_telemetry_(seq);
  if (desired_path_ == DesiredPath::DIRECT)
    publish_direct_(seq, telemetry);
  else
    publish_relay_(seq, telemetry);
}

std::string GreenhouseN3wP5Lab::build_telemetry_(uint32_t seq) const {
  char buffer[768];
  std::snprintf(
      buffer,
      sizeof(buffer),
      "{\"schema\":\"gh.telemetry/1\",\"node_id\":\"%s\",\"boot_id\":\"%s\",\"seq\":%u,\"uptime_ms\":%llu,\"cap_hash\":\"n3wp5lab01\",\"fw_version\":\"N3W-P5-LAB\",\"measurements\":{\"air_temperature_c\":25.0},\"quality\":{\"air_temperature_c\":\"ok\"},\"power\":{\"source\":\"main\",\"low\":false}}",
      node_id_.c_str(),
      boot_.boot_id().c_str(),
      static_cast<unsigned>(seq),
      static_cast<unsigned long long>(now_ms_()));
  return std::string(buffer);
}

bool GreenhouseN3wP5Lab::publish_direct_(uint32_t seq, const std::string &telemetry) {
  (void) seq;
  if (mqtt::global_mqtt_client == nullptr || !mqtt::global_mqtt_client->is_connected()) return false;
  const std::string topic = "gh/v1/" + system_id_ + "/ingress/node/" + node_id_ + "/telemetry";
  return mqtt::global_mqtt_client->publish(topic, telemetry, 1, false);
}

ApplicationKeyState *GreenhouseN3wP5Lab::active_key_() {
  return selected_key_epoch_ == 2 ? &key_epoch2_ : &key_epoch1_;
}

bool GreenhouseN3wP5Lab::publish_relay_(uint32_t seq, const std::string &telemetry) {
  if (!radio_ready_ || !relay_authenticated_) return false;
  greenhouse_n3w_core::RelayHeader header{};
  header.gateway_id = gateway_id_;
  header.node_id = node_id_;
  header.key_epoch = selected_key_epoch_;
  header.boot_id = boot_.boot_id();
  header.seq = seq;
  RelayFrame frame{};
  if (greenhouse_n3w_core::build_relay_frame(header, *active_key_(), telemetry, &frame) !=
      greenhouse_n3w_core::CoreError::NONE)
    return false;
  std::vector<std::vector<uint8_t>> datagrams;
  if (greenhouse_n3w_core::fragment_relay_frame(frame, &datagrams) != greenhouse_n3w_core::RadioError::NONE)
    return false;
  last_datagrams_ = datagrams;
  if (cache_.enqueue(frame, now_ms_()) != greenhouse_n3w_core::RadioError::NONE) return false;
  flush_relay_cache_();
  return true;
}

void GreenhouseN3wP5Lab::flush_relay_cache_() {
  if (!is_child_ || !radio_ready_ || !relay_authenticated_) return;
  const uint64_t now = now_ms_();
  const auto *entry = cache_.next_due(now);
  if (entry == nullptr) return;
  const uint64_t session = entry->boot_session;
  const uint32_t seq = entry->seq;
  const auto datagrams = entry->datagrams;
  const bool sent = send_datagrams_(datagrams, false);
  const auto attempt = cache_.note_attempt(session, seq, now);
  if (attempt == greenhouse_n3w_core::RadioError::RETRY_EXHAUSTED) {
    const bool discarded = cache_.discard(session, seq);
    ESP_LOGW(TAG, "Relay retry exhausted boot=%llu seq=%u discarded=%s",
             static_cast<unsigned long long>(session), static_cast<unsigned>(seq), discarded ? "true" : "false");
  }
  if (!sent) ESP_LOGW(TAG, "Relay datagram send failed boot=%llu seq=%u", static_cast<unsigned long long>(session), static_cast<unsigned>(seq));
}

bool GreenhouseN3wP5Lab::send_datagrams_(const std::vector<std::vector<uint8_t>> &datagrams, bool reverse) {
  if (!radio_ready_ || datagrams.empty()) return false;
  bool ok = true;
  if (!reverse) {
    for (const auto &packet : datagrams)
      ok = driver_.send(peer_mac_, packet.data(), packet.size()) == greenhouse_n3w_core::DriverError::NONE && ok;
  } else {
    for (auto it = datagrams.rbegin(); it != datagrams.rend(); ++it)
      ok = driver_.send(peer_mac_, it->data(), it->size()) == greenhouse_n3w_core::DriverError::NONE && ok;
  }
  return ok;
}

bool GreenhouseN3wP5Lab::resend_last_datagrams_(bool reverse) {
  const char *command = reverse ? "REORDER" : "RESEND";
  const auto count = static_cast<unsigned>(last_datagrams_.size());
  if (last_datagrams_.empty()) {
    ESP_LOGW(TAG, "Lab cached datagram command=%s result=rejected reason=empty_cache datagrams=0", command);
    return false;
  }
  if (!ensure_radio_ready_()) {
    ESP_LOGW(TAG, "Lab cached datagram command=%s result=rejected reason=radio_not_ready datagrams=%u",
             command, count);
    return false;
  }
  const bool queued = send_datagrams_(last_datagrams_, reverse);
  if (queued) {
    ESP_LOGI(TAG, "Lab cached datagram command=%s result=queued datagrams=%u order=%s",
             command, count, reverse ? "reverse" : "original");
  } else {
    ESP_LOGW(TAG, "Lab cached datagram command=%s result=rejected reason=driver_send datagrams=%u order=%s",
             command, count, reverse ? "reverse" : "original");
  }
  return queued;
}

void GreenhouseN3wP5Lab::handle_lab_command(const std::string &raw) {
  if (!execution_enabled_) return;
  const std::string command = upper_trim(raw);
  if (is_child_ && command == "PATH DIRECT") {
    desired_path_ = DesiredPath::DIRECT;
    relay_authenticated_ = false;
    ESP_LOGI(TAG, "Lab command: PATH DIRECT");
  } else if (is_child_ && command == "PATH RELAY") {
    desired_path_ = DesiredPath::RELAY;
    relay_authenticated_ = false;
    ++probe_challenge_;
    last_probe_ms_ = 0;
    ESP_LOGI(TAG, "Lab command: PATH RELAY");
  } else if (is_child_ && command == "KEY 1") {
    selected_key_epoch_ = 1;
    ESP_LOGI(TAG, "Lab command: KEY epoch 1");
  } else if (is_child_ && command == "KEY 2") {
    selected_key_epoch_ = 2;
    ESP_LOGI(TAG, "Lab command: KEY epoch 2");
  } else if (is_child_ && command == "RESEND") {
    resend_last_datagrams_(false);
  } else if (is_child_ && command == "REORDER") {
    resend_last_datagrams_(true);
  } else if (command == "RESET REASSEMBLY" && !is_child_) {
    relay_ingress_.reset();
  } else if (command == "RESTART") {
#ifdef USE_ESP32
    esp_restart();
#endif
  } else {
    ESP_LOGW(TAG, "Rejected unsupported P5 lab command");
  }
}

}  // namespace esphome::greenhouse_n3w_p5_lab
