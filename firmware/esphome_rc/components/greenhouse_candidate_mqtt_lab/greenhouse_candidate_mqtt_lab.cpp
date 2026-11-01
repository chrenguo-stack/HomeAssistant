#include "greenhouse_candidate_mqtt_lab.h"

#include <algorithm>
#include <cstring>
#include <utility>

#include "esphome/core/hal.h"
#include "esphome/core/log.h"

namespace esphome::greenhouse_candidate_mqtt_lab {
namespace {

static const char *const TAG = "gh_candidate_mqtt_lab";

void secure_clear(std::string *value) {
  if (value == nullptr)
    return;
  std::fill(value->begin(), value->end(), '\0');
  value->clear();
  value->shrink_to_fit();
}

}  // namespace

EspIdfCandidateMqttTransport::~EspIdfCandidateMqttTransport() { this->destroy(); }

bool EspIdfCandidateMqttTransport::create(
    const CandidateMqttProfile &profile,
    const CandidateMqttProbeExchange &exchange) {
  if (this->client_ != nullptr || !profile.valid() || !exchange.valid())
    return false;

  this->broker_host_ = profile.broker_host;
  this->broker_port_ = profile.broker_port;
  this->ca_pem_ = profile.ca_pem;
  this->mqtt_username_ = profile.mqtt_username;
  this->mqtt_client_id_ = profile.mqtt_client_id;
  this->mqtt_password_ = profile.mqtt_password;
  this->exchange_.publish_topic = exchange.publish_topic;
  this->exchange_.subscribe_topic = exchange.subscribe_topic;
  this->exchange_.request_payload = exchange.request_payload;
  this->exchange_.expected_payload = exchange.expected_payload;

  esp_mqtt_client_config_t config{};
  config.broker.address.hostname = this->broker_host_.c_str();
  config.broker.address.port = this->broker_port_;
  config.broker.address.transport = MQTT_TRANSPORT_OVER_SSL;
  config.broker.verification.certificate = this->ca_pem_.c_str();
  config.credentials.username = this->mqtt_username_.c_str();
  config.credentials.client_id = this->mqtt_client_id_.c_str();
  config.credentials.authentication.password = this->mqtt_password_.c_str();
  config.session.keepalive = 15;
  config.network.timeout_ms = 5000;

  this->client_ = esp_mqtt_client_init(&config);
  if (this->client_ == nullptr) {
    this->clear_material_();
    return false;
  }
  if (esp_mqtt_client_register_event(this->client_, MQTT_EVENT_ANY,
                                     &EspIdfCandidateMqttTransport::event_handler_,
                                     this) != ESP_OK) {
    esp_mqtt_client_destroy(this->client_);
    this->client_ = nullptr;
    this->clear_material_();
    return false;
  }
  return true;
}

bool EspIdfCandidateMqttTransport::start() {
  if (this->client_ == nullptr || this->started_)
    return false;
  if (esp_mqtt_client_start(this->client_) != ESP_OK)
    return false;
  this->started_ = true;
  return true;
}

bool EspIdfCandidateMqttTransport::poll(
    CandidateMqttTransportObservation *output) {
  if (output == nullptr || this->client_ == nullptr)
    return false;
  output->client_created = true;
  output->connected = this->connected_.load();
  output->authenticated = this->authenticated_.load();
  output->subscribe_ready = this->subscribe_ready_.load();
  output->telemetry_round_trip = this->telemetry_round_trip_.load();
  output->terminal_failure = this->terminal_failure_.load();
  output->failure = static_cast<CandidateMqttProbeFailure>(this->failure_.load());
  return true;
}

void EspIdfCandidateMqttTransport::event_handler_(void *handler_args,
                                                  esp_event_base_t,
                                                  int32_t,
                                                  void *event_data) {
  auto *self = static_cast<EspIdfCandidateMqttTransport *>(handler_args);
  if (self == nullptr || event_data == nullptr)
    return;
  self->handle_event_(static_cast<esp_mqtt_event_handle_t>(event_data));
}

void EspIdfCandidateMqttTransport::handle_event_(esp_mqtt_event_handle_t event) {
  if (event == nullptr || this->terminal_failure_.load())
    return;
  switch (static_cast<esp_mqtt_event_id_t>(event->event_id)) {
    case MQTT_EVENT_CONNECTED: {
      this->connected_.store(true);
      this->authenticated_.store(true);
      this->subscribe_message_id_ = esp_mqtt_client_subscribe(
          this->client_, this->exchange_.subscribe_topic.c_str(), 1);
      if (this->subscribe_message_id_ < 0)
        this->fail_(CandidateMqttProbeFailure::SUBSCRIBE_FAILED);
      break;
    }
    case MQTT_EVENT_SUBSCRIBED: {
      if (event->msg_id != this->subscribe_message_id_)
        break;
      this->subscribe_ready_.store(true);
      const int message_id = esp_mqtt_client_publish(
          this->client_, this->exchange_.publish_topic.c_str(),
          this->exchange_.request_payload.c_str(),
          static_cast<int>(this->exchange_.request_payload.size()), 1, 0);
      if (message_id < 0)
        this->fail_(CandidateMqttProbeFailure::PUBLISH_FAILED);
      break;
    }
    case MQTT_EVENT_DATA: {
      const bool topic_matches =
          event->topic_len == static_cast<int>(this->exchange_.subscribe_topic.size()) &&
          std::memcmp(event->topic, this->exchange_.subscribe_topic.data(),
                      this->exchange_.subscribe_topic.size()) == 0;
      if (!topic_matches)
        break;
      const bool payload_matches =
          event->data_len == static_cast<int>(this->exchange_.expected_payload.size()) &&
          std::memcmp(event->data, this->exchange_.expected_payload.data(),
                      this->exchange_.expected_payload.size()) == 0;
      if (!payload_matches) {
        this->fail_(CandidateMqttProbeFailure::ROUND_TRIP_MISMATCH);
        break;
      }
      this->telemetry_round_trip_.store(true);
      break;
    }
    case MQTT_EVENT_ERROR:
      this->fail_(this->authenticated_.load()
                      ? CandidateMqttProbeFailure::TRANSPORT_ERROR
                      : CandidateMqttProbeFailure::AUTHENTICATION_FAILED);
      break;
    case MQTT_EVENT_DISCONNECTED:
      this->connected_.store(false);
      if (!this->telemetry_round_trip_.load())
        this->fail_(this->authenticated_.load()
                        ? CandidateMqttProbeFailure::TRANSPORT_ERROR
                        : CandidateMqttProbeFailure::AUTHENTICATION_FAILED);
      break;
    default:
      break;
  }
}

void EspIdfCandidateMqttTransport::fail_(CandidateMqttProbeFailure failure) {
  this->failure_.store(static_cast<uint8_t>(failure));
  this->terminal_failure_.store(true);
}

void EspIdfCandidateMqttTransport::destroy() {
  if (this->client_ != nullptr) {
    if (this->started_)
      esp_mqtt_client_stop(this->client_);
    esp_mqtt_client_destroy(this->client_);
  }
  this->client_ = nullptr;
  this->started_ = false;
  this->subscribe_message_id_ = -1;
  this->connected_.store(false);
  this->authenticated_.store(false);
  this->subscribe_ready_.store(false);
  this->telemetry_round_trip_.store(false);
  this->terminal_failure_.store(false);
  this->failure_.store(static_cast<uint8_t>(CandidateMqttProbeFailure::NONE));
  this->clear_material_();
}

void EspIdfCandidateMqttTransport::clear_material_() {
  secure_clear(&this->broker_host_);
  secure_clear(&this->ca_pem_);
  secure_clear(&this->mqtt_username_);
  secure_clear(&this->mqtt_client_id_);
  secure_clear(&this->mqtt_password_);
  this->exchange_.clear();
  this->broker_port_ = 0;
}

void GreenhouseCandidateMqttLab::setup() {
  // Compile-only laboratory wrapper. Setup does not read NVS, obtain credentials,
  // start Wi-Fi, create an MQTT client, or contact a Broker.
  this->validator_.configure(0, this->probe_timeout_ms_);
}

void GreenhouseCandidateMqttLab::loop() {
  if (!this->probe_running_)
    return;
  const uint32_t elapsed_ms = millis() - this->probe_started_ms_;
  const bool progressed = this->validator_.poll(&this->transport_, elapsed_ms);
  const auto phase = this->validator_.snapshot().phase;
  if (!progressed || phase == greenhouse_pairing_client::CandidateMqttProbePhase::VERIFIED ||
      phase == greenhouse_pairing_client::CandidateMqttProbePhase::FAILED ||
      phase == greenhouse_pairing_client::CandidateMqttProbePhase::CANCELLED)
    this->probe_running_ = false;
}

bool GreenhouseCandidateMqttLab::begin_for_lab(
    RamCredentialBundle *credentials, uint32_t active_generation,
    const std::string &nonce_hex) {
  if (credentials == nullptr || !credentials->valid() || this->probe_running_ ||
      this->transport_.live())
    return false;

  CandidateMqttProfile profile;
  profile.system_id = credentials->system_id;
  profile.node_id = credentials->node_id;
  profile.broker_host = credentials->broker_host;
  profile.broker_port = credentials->broker_port;
  profile.broker_tls_server_name = credentials->broker_tls_server_name;
  profile.ca_pem = credentials->ca_pem;
  profile.mqtt_username = credentials->mqtt_username;
  profile.mqtt_client_id = credentials->mqtt_client_id;
  profile.credential_generation = credentials->credential_generation;
  profile.mqtt_password = credentials->mqtt_password;
  credentials->clear();

  if (!this->validator_.configure(active_generation, this->probe_timeout_ms_) ||
      !this->validator_.stage(std::move(profile), nonce_hex) ||
      !this->validator_.begin(&this->transport_))
    return false;
  this->probe_started_ms_ = millis();
  this->probe_running_ = true;
  return true;
}

bool GreenhouseCandidateMqttLab::cancel_for_lab() {
  const bool result = this->validator_.cancel(&this->transport_);
  this->probe_running_ = false;
  return result;
}

const char *GreenhouseCandidateMqttLab::phase_name() const {
  return CandidateMqttProfileValidator::phase_name(this->validator_.snapshot().phase);
}

const char *GreenhouseCandidateMqttLab::failure_name() const {
  return CandidateMqttProfileValidator::failure_name(this->validator_.snapshot().failure);
}

bool GreenhouseCandidateMqttLab::active_profile_unchanged() const {
  return this->validator_.snapshot().active_profile_unchanged;
}

bool GreenhouseCandidateMqttLab::candidate_client_live() const {
  return this->transport_.live();
}

void GreenhouseCandidateMqttLab::dump_config() {
  ESP_LOGCONFIG(TAG, "Candidate MQTT profile validator laboratory wrapper");
  ESP_LOGCONFIG(TAG, "  Auto-start: disabled");
  ESP_LOGCONFIG(TAG, "  Production MQTT mutation: disabled");
  ESP_LOGCONFIG(TAG, "  Probe timeout: %u ms", this->probe_timeout_ms_);
}

float GreenhouseCandidateMqttLab::get_setup_priority() const {
  return setup_priority::LATE;
}

}  // namespace esphome::greenhouse_candidate_mqtt_lab
