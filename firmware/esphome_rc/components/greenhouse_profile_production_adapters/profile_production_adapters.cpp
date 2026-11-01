#include "profile_production_adapters.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstring>
#include <utility>

#ifdef USE_ESP32
#include "esp_err.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#endif

namespace esphome::greenhouse_pairing_client {
namespace {

CandidateMqttProfile clone_profile(const CandidateMqttProfile &source) {
  CandidateMqttProfile copy;
  copy.system_id = source.system_id;
  copy.node_id = source.node_id;
  copy.broker_host = source.broker_host;
  copy.broker_port = source.broker_port;
  copy.broker_tls_server_name = source.broker_tls_server_name;
  copy.ca_pem = source.ca_pem;
  copy.mqtt_username = source.mqtt_username;
  copy.mqtt_client_id = source.mqtt_client_id;
  copy.credential_generation = source.credential_generation;
  copy.mqtt_password = source.mqtt_password;
  return copy;
}

CandidateMqttProfile profile_from_bundle(const RamCredentialBundle &credentials) {
  CandidateMqttProfile profile;
  profile.system_id = credentials.system_id;
  profile.node_id = credentials.node_id;
  profile.broker_host = credentials.broker_host;
  profile.broker_port = credentials.broker_port;
  profile.broker_tls_server_name = credentials.broker_tls_server_name;
  profile.ca_pem = credentials.ca_pem;
  profile.mqtt_username = credentials.mqtt_username;
  profile.mqtt_client_id = credentials.mqtt_client_id;
  profile.credential_generation = credentials.credential_generation;
  profile.mqtt_password = credentials.mqtt_password;
  return profile;
}

bool profiles_equal(const CandidateMqttProfile &left,
                    const CandidateMqttProfile &right) {
  return left.system_id == right.system_id && left.node_id == right.node_id &&
         left.broker_host == right.broker_host &&
         left.broker_port == right.broker_port &&
         left.broker_tls_server_name == right.broker_tls_server_name &&
         left.ca_pem == right.ca_pem &&
         left.mqtt_username == right.mqtt_username &&
         left.mqtt_client_id == right.mqtt_client_id &&
         left.credential_generation == right.credential_generation &&
         left.mqtt_password == right.mqtt_password;
}

bool valid_nonce(const std::string &value) {
  if (value.size() < 16 || value.size() > 64 || (value.size() % 2) != 0)
    return false;
  return std::all_of(value.begin(), value.end(), [](char character) {
    return (character >= '0' && character <= '9') ||
           (character >= 'a' && character <= 'f');
  });
}

bool build_exchange(const CandidateMqttProfile &profile,
                    const std::string &nonce_hex,
                    CandidateMqttProbeExchange *exchange) {
  if (exchange == nullptr || !profile.valid() || !valid_nonce(nonce_hex))
    return false;
  exchange->clear();
  const std::string prefix = "gh/v1/" + profile.system_id;
  exchange->publish_topic =
      prefix + "/ingress/node/" + profile.node_id + "/telemetry";
  exchange->subscribe_topic =
      prefix + "/out/node/" + profile.node_id + "/confirm";
  exchange->request_payload =
      "{\"credential_generation\":" +
      std::to_string(profile.credential_generation) + ",\"node_id\":\"" +
      profile.node_id + "\",\"nonce\":\"" + nonce_hex +
      "\",\"schema\":\"gh.telemetry-probe/1\"}";
  exchange->expected_payload =
      "{\"credential_generation\":" +
      std::to_string(profile.credential_generation) + ",\"node_id\":\"" +
      profile.node_id + "\",\"nonce\":\"" + nonce_hex +
      "\",\"schema\":\"gh.telemetry-probe-confirm/1\",\"status\":\"accepted\"}";
  return exchange->valid();
}

}  // namespace

bool ProductionCandidateMqttTransport::configure(
    ProductionMqttSession *session) {
  if (session == nullptr || session->live())
    return false;
  this->session_ = session;
  return true;
}

CandidateMqttProfile ProductionCandidateMqttTransport::clone_profile_(
    const CandidateMqttProfile &source) {
  return clone_profile(source);
}

CandidateMqttProbeFailure ProductionCandidateMqttTransport::map_failure_(
    ProductionMqttSessionFailure failure) {
  switch (failure) {
    case ProductionMqttSessionFailure::NONE:
      return CandidateMqttProbeFailure::NONE;
    case ProductionMqttSessionFailure::INVALID_CONFIGURATION:
      return CandidateMqttProbeFailure::INVALID_PROFILE;
    case ProductionMqttSessionFailure::CREATE_FAILED:
      return CandidateMqttProbeFailure::CREATE_FAILED;
    case ProductionMqttSessionFailure::START_FAILED:
      return CandidateMqttProbeFailure::START_FAILED;
    case ProductionMqttSessionFailure::AUTHENTICATION_FAILED:
      return CandidateMqttProbeFailure::AUTHENTICATION_FAILED;
    case ProductionMqttSessionFailure::SUBSCRIBE_FAILED:
      return CandidateMqttProbeFailure::SUBSCRIBE_FAILED;
    case ProductionMqttSessionFailure::PUBLISH_FAILED:
      return CandidateMqttProbeFailure::PUBLISH_FAILED;
    case ProductionMqttSessionFailure::ROUND_TRIP_MISMATCH:
      return CandidateMqttProbeFailure::ROUND_TRIP_MISMATCH;
    case ProductionMqttSessionFailure::TIMEOUT:
      return CandidateMqttProbeFailure::TIMEOUT;
    case ProductionMqttSessionFailure::TRANSPORT_ERROR:
      return CandidateMqttProbeFailure::TRANSPORT_ERROR;
  }
  return CandidateMqttProbeFailure::TRANSPORT_ERROR;
}

bool ProductionCandidateMqttTransport::create(
    const CandidateMqttProfile &profile,
    const CandidateMqttProbeExchange &exchange) {
  if (this->session_ == nullptr || this->session_->live() || !profile.valid() ||
      !exchange.valid())
    return false;
  return this->session_->configure(clone_profile_(profile), exchange, true);
}

bool ProductionCandidateMqttTransport::start() {
  return this->session_ != nullptr && this->session_->start();
}

bool ProductionCandidateMqttTransport::poll(
    CandidateMqttTransportObservation *output) {
  if (this->session_ == nullptr || output == nullptr)
    return false;
  ProductionMqttSessionObservation observation{};
  if (!this->session_->poll(&observation))
    return false;
  output->client_created = observation.client_created;
  output->connected = observation.connected;
  output->authenticated = observation.authenticated;
  output->subscribe_ready = observation.subscribe_ready;
  output->telemetry_round_trip = observation.round_trip;
  output->terminal_failure = observation.terminal_failure;
  output->failure = map_failure_(observation.failure);
  return true;
}

void ProductionCandidateMqttTransport::destroy() {
  if (this->session_ != nullptr)
    this->session_->destroy();
}

bool ProductionCandidateMqttTransport::live() const {
  return this->session_ != nullptr && this->session_->live();
}

bool ProductionProfileLifecycleRuntime::configure(
    ProductionMqttSession *active_session,
    ProductionMqttSession *candidate_session,
    ActivationNonceSource *nonce_source, uint32_t connect_timeout_ms,
    uint32_t round_trip_timeout_ms) {
  if (active_session == nullptr || candidate_session == nullptr ||
      nonce_source == nullptr || active_session == candidate_session ||
      active_session->live() || candidate_session->live() ||
      connect_timeout_ms < 1000 || connect_timeout_ms > 60000 ||
      round_trip_timeout_ms < 1000 || round_trip_timeout_ms > 60000)
    return false;
  this->clear_all_material_();
  this->active_session_ = active_session;
  this->candidate_session_ = candidate_session;
  this->nonce_source_ = nonce_source;
  this->connect_timeout_ms_ = connect_timeout_ms;
  this->round_trip_timeout_ms_ = round_trip_timeout_ms;
  this->configured_ = true;
  return true;
}

CandidateMqttProfile ProductionProfileLifecycleRuntime::profile_from_bundle_(
    const RamCredentialBundle &credentials) {
  return profile_from_bundle(credentials);
}

CandidateMqttProfile ProductionProfileLifecycleRuntime::clone_profile_(
    const CandidateMqttProfile &source) {
  return clone_profile(source);
}

bool ProductionProfileLifecycleRuntime::profiles_equal_(
    const CandidateMqttProfile &left, const CandidateMqttProfile &right) {
  return profiles_equal(left, right);
}

bool ProductionProfileLifecycleRuntime::valid_nonce_(
    const std::string &nonce_hex) {
  return valid_nonce(nonce_hex);
}

bool ProductionProfileLifecycleRuntime::build_exchange_(
    const CandidateMqttProfile &profile, const std::string &nonce_hex,
    CandidateMqttProbeExchange *exchange) {
  return build_exchange(profile, nonce_hex, exchange);
}

bool ProductionProfileLifecycleRuntime::configure_session_(
    ProductionMqttSession *session, const CandidateMqttProfile &profile,
    const CandidateMqttProbeExchange &exchange, bool require_round_trip) {
  return session != nullptr && !session->live() && profile.valid() &&
         (!require_round_trip || exchange.valid()) &&
         session->configure(clone_profile_(profile), exchange,
                            require_round_trip);
}

bool ProductionProfileLifecycleRuntime::bind_active_profile(
    const RamCredentialBundle &active_credentials) {
  if (!this->configured_ || this->staged_ || this->promotion_pending_ ||
      this->active_session_ == nullptr || this->active_session_->live() ||
      !active_credentials.valid())
    return false;
  CandidateMqttProfile profile = profile_from_bundle_(active_credentials);
  CandidateMqttProbeExchange empty_exchange;
  if (!profile.valid() ||
      !this->configure_session_(this->active_session_, profile, empty_exchange,
                                false) ||
      !this->active_session_->start() ||
      !this->active_session_->wait_connected(this->connect_timeout_ms_)) {
    this->active_session_->destroy();
    profile.clear();
    return false;
  }
  this->active_profile_ = std::move(profile);
  this->active_generation_ = this->active_profile_.credential_generation;
  return this->active_session_->live() &&
         this->active_session_->generation() == this->active_generation_;
}

bool ProductionProfileLifecycleRuntime::finalize_activation_promotion() {
  if (!this->promotion_pending_ || this->active_session_ == nullptr ||
      this->candidate_session_ == nullptr || this->active_session_->live() ||
      !this->candidate_session_->live() || !this->active_profile_.valid() ||
      this->active_profile_.credential_generation != this->active_generation_)
    return false;
  std::swap(this->active_session_, this->candidate_session_);
  this->promotion_pending_ = false;
  this->staged_ = false;
  return this->active_session_->live() && !this->candidate_session_->live();
}

bool ProductionProfileLifecycleRuntime::reset() {
  if (!this->configured_ || this->promotion_pending_ ||
      (this->active_session_ != nullptr && this->active_session_->live()) ||
      (this->candidate_session_ != nullptr && this->candidate_session_->live()))
    return false;
  this->clear_all_material_();
  return true;
}

bool ProductionProfileLifecycleRuntime::stage_recovered_profiles(
    const RamCredentialBundle *active_credentials,
    const RamCredentialBundle &candidate_credentials) {
  if (!this->configured_ || this->staged_ || this->promotion_pending_ ||
      this->candidate_session_ == nullptr || this->active_session_ == nullptr ||
      this->candidate_session_->live() || !candidate_credentials.valid())
    return false;

  CandidateMqttProfile candidate = profile_from_bundle_(candidate_credentials);
  if (!candidate.valid())
    return false;

  if (active_credentials == nullptr) {
    if (this->active_session_->live() || this->active_generation_ != 0 ||
        this->active_profile_.present()) {
      candidate.clear();
      return false;
    }
  } else {
    if (!active_credentials->valid() || !this->active_session_->live()) {
      candidate.clear();
      return false;
    }
    CandidateMqttProfile recovered_active =
        profile_from_bundle_(*active_credentials);
    const bool active_matches =
        recovered_active.valid() && this->active_profile_.valid() &&
        profiles_equal_(recovered_active, this->active_profile_) &&
        this->active_session_->generation() ==
            recovered_active.credential_generation &&
        this->active_generation_ == recovered_active.credential_generation;
    recovered_active.clear();
    if (!active_matches) {
      candidate.clear();
      return false;
    }
  }

  if (candidate.credential_generation <= this->active_generation_) {
    candidate.clear();
    return false;
  }
  this->candidate_profile_ = std::move(candidate);
  this->candidate_generation_ =
      this->candidate_profile_.credential_generation;
  this->staged_ = true;
  return true;
}

bool ProductionProfileLifecycleRuntime::staged_generations_match(
    uint32_t active_generation, uint32_t candidate_generation) const {
  return this->staged_ && !this->promotion_pending_ &&
         active_generation == this->active_generation_ &&
         candidate_generation == this->candidate_generation_ &&
         candidate_generation > active_generation &&
         this->candidate_profile_.valid();
}

bool ProductionProfileLifecycleRuntime::stop_old_active() {
  if (!this->staged_ || this->active_session_ == nullptr)
    return false;
  if (this->active_generation_ == 0)
    return !this->active_session_->live();
  if (!this->active_session_->live() ||
      this->active_session_->generation() != this->active_generation_)
    return false;
  if (!this->active_session_->stop())
    return false;
  this->active_session_->destroy();
  return !this->active_session_->live();
}

bool ProductionProfileLifecycleRuntime::start_candidate() {
  if (!this->staged_ || this->candidate_session_ == nullptr ||
      this->candidate_session_->live() || !this->candidate_profile_.valid() ||
      this->nonce_source_ == nullptr)
    return false;
  std::string nonce_hex;
  if (!this->nonce_source_->next_nonce_hex(&nonce_hex) ||
      !valid_nonce_(nonce_hex) ||
      !build_exchange_(this->candidate_profile_, nonce_hex,
                       &this->candidate_exchange_)) {
    std::fill(nonce_hex.begin(), nonce_hex.end(), '\0');
    return false;
  }
  std::fill(nonce_hex.begin(), nonce_hex.end(), '\0');
  nonce_hex.clear();
  if (!this->configure_session_(this->candidate_session_,
                                this->candidate_profile_,
                                this->candidate_exchange_, true) ||
      !this->candidate_session_->start()) {
    this->candidate_session_->destroy();
    return false;
  }
  return this->candidate_session_->live() &&
         this->candidate_session_->generation() ==
             this->candidate_generation_;
}

bool ProductionProfileLifecycleRuntime::confirm_candidate_round_trip() {
  return this->staged_ && this->candidate_session_ != nullptr &&
         this->candidate_session_->live() &&
         this->candidate_session_->generation() ==
             this->candidate_generation_ &&
         this->candidate_session_->wait_round_trip(
             this->round_trip_timeout_ms_);
}

bool ProductionProfileLifecycleRuntime::stop_candidate() {
  if (this->candidate_session_ == nullptr)
    return false;
  if (!this->candidate_session_->live()) {
    this->candidate_session_->destroy();
    return true;
  }
  if (!this->candidate_session_->stop())
    return false;
  this->candidate_session_->destroy();
  return !this->candidate_session_->live();
}

bool ProductionProfileLifecycleRuntime::restore_old_active() {
  if (!this->staged_ || this->active_session_ == nullptr)
    return false;
  if (this->active_generation_ == 0)
    return !this->active_session_->live();
  if (this->active_session_->live() || !this->active_profile_.valid())
    return false;
  CandidateMqttProbeExchange empty_exchange;
  if (!this->configure_session_(this->active_session_, this->active_profile_,
                                empty_exchange, false) ||
      !this->active_session_->start() ||
      !this->active_session_->wait_connected(this->connect_timeout_ms_)) {
    this->active_session_->destroy();
    return false;
  }
  return this->active_session_->live() &&
         this->active_session_->generation() == this->active_generation_;
}

void ProductionProfileLifecycleRuntime::quiesce_all() {
  if (this->candidate_session_ != nullptr) {
    if (this->candidate_session_->live())
      this->candidate_session_->stop();
    this->candidate_session_->destroy();
  }
  if (this->active_session_ != nullptr) {
    if (this->active_session_->live())
      this->active_session_->stop();
    this->active_session_->destroy();
  }
  this->promotion_pending_ = false;
}

void ProductionProfileLifecycleRuntime::clear_candidate_material() {
  const bool candidate_is_new_active =
      this->candidate_session_ != nullptr && this->candidate_session_->live() &&
      (this->active_session_ == nullptr || !this->active_session_->live()) &&
      this->candidate_profile_.valid() && this->candidate_generation_ != 0;
  if (candidate_is_new_active) {
    this->active_profile_.clear();
    this->active_profile_ = std::move(this->candidate_profile_);
    this->active_generation_ = this->candidate_generation_;
    this->candidate_generation_ = 0;
    this->candidate_exchange_.clear();
    this->promotion_pending_ = true;
    return;
  }
  this->candidate_profile_.clear();
  this->candidate_exchange_.clear();
  this->candidate_generation_ = 0;
  this->staged_ = false;
}

bool ProductionProfileLifecycleRuntime::old_active_live() const {
  return this->active_session_ != nullptr && this->active_session_->live();
}

bool ProductionProfileLifecycleRuntime::candidate_active_live() const {
  return this->candidate_session_ != nullptr &&
         this->candidate_session_->live();
}

void ProductionProfileLifecycleRuntime::clear_all_material_() {
  this->active_profile_.clear();
  this->candidate_profile_.clear();
  this->candidate_exchange_.clear();
  this->active_generation_ = 0;
  this->candidate_generation_ = 0;
  this->staged_ = false;
  this->promotion_pending_ = false;
}

bool ProductionPersistenceAdapter::configure(
    PairingPersistenceBackend *backend, PersistenceKeyProvider *key_provider) {
  this->reset();
  if (backend == nullptr || key_provider == nullptr)
    return false;
  this->backend_ = backend;
  this->key_provider_ = key_provider;
  this->crypto_ = std::make_unique<PairingPersistenceCrypto>(key_provider);
  this->store_ =
      std::make_unique<PairingPersistentStore>(backend, this->crypto_.get());
  return this->ready();
}

void ProductionPersistenceAdapter::reset() {
  this->store_.reset();
  this->crypto_.reset();
  this->backend_ = nullptr;
  this->key_provider_ = nullptr;
}

#ifdef USE_ESP32

bool EspIdfActivationNonceSource::next_nonce_hex(std::string *nonce_hex) {
  if (nonce_hex == nullptr)
    return false;
  std::array<uint8_t, 16> bytes{};
  esp_fill_random(bytes.data(), bytes.size());
  static constexpr char HEX[] = "0123456789abcdef";
  nonce_hex->assign(bytes.size() * 2, '0');
  for (size_t index = 0; index < bytes.size(); index++) {
    (*nonce_hex)[index * 2] = HEX[(bytes[index] >> 4) & 0x0F];
    (*nonce_hex)[index * 2 + 1] = HEX[bytes[index] & 0x0F];
  }
  std::fill(bytes.begin(), bytes.end(), 0);
  return true;
}

EspIdfProductionMqttSession::~EspIdfProductionMqttSession() {
  this->destroy();
}

bool EspIdfProductionMqttSession::configure(
    CandidateMqttProfile profile, CandidateMqttProbeExchange exchange,
    bool require_round_trip) {
  if (this->live() || this->client_ != nullptr || !profile.valid() ||
      (require_round_trip && !exchange.valid())) {
    profile.clear();
    exchange.clear();
    return false;
  }
  this->clear_material_();
  this->profile_ = std::move(profile);
  this->exchange_ = std::move(exchange);
  this->require_round_trip_ = require_round_trip;
  this->reset_observation_();
  return true;
}

bool EspIdfProductionMqttSession::start() {
  if (this->client_ != nullptr || !this->profile_.valid() ||
      (this->require_round_trip_ && !this->exchange_.valid()))
    return false;

  this->config_ = {};
  this->config_.broker.address.hostname = this->profile_.broker_host.c_str();
  this->config_.broker.address.port = this->profile_.broker_port;
  this->config_.broker.address.transport = MQTT_TRANSPORT_OVER_SSL;
  this->config_.broker.verification.certificate = this->profile_.ca_pem.c_str();
  this->config_.credentials.username = this->profile_.mqtt_username.c_str();
  this->config_.credentials.client_id = this->profile_.mqtt_client_id.c_str();
  this->config_.credentials.authentication.password =
      this->profile_.mqtt_password.c_str();
  this->config_.session.keepalive = 30;
  this->config_.session.disable_clean_session = false;

  this->client_ = esp_mqtt_client_init(&this->config_);
  if (this->client_ == nullptr) {
    this->mark_failure_(ProductionMqttSessionFailure::CREATE_FAILED);
    return false;
  }
  this->client_created_.store(true);
  if (esp_mqtt_client_register_event(this->client_, MQTT_EVENT_ANY,
                                     &EspIdfProductionMqttSession::event_handler_,
                                     this) != ESP_OK) {
    this->mark_failure_(ProductionMqttSessionFailure::CREATE_FAILED);
    this->destroy();
    return false;
  }
  if (esp_mqtt_client_start(this->client_) != ESP_OK) {
    this->mark_failure_(ProductionMqttSessionFailure::START_FAILED);
    this->destroy();
    return false;
  }
  this->started_.store(true);
  return true;
}

bool EspIdfProductionMqttSession::poll(
    ProductionMqttSessionObservation *observation) {
  if (observation == nullptr)
    return false;
  observation->client_created = this->client_created_.load();
  observation->started = this->started_.load();
  observation->connected = this->connected_.load();
  observation->authenticated = this->authenticated_.load();
  observation->subscribe_ready = this->subscribe_ready_.load();
  observation->round_trip = this->round_trip_.load();
  observation->terminal_failure = this->terminal_failure_.load();
  observation->failure = this->failure_.load();
  return true;
}

bool EspIdfProductionMqttSession::wait_connected(uint32_t timeout_ms) {
  return this->wait_for_(false, timeout_ms);
}

bool EspIdfProductionMqttSession::wait_round_trip(uint32_t timeout_ms) {
  if (!this->require_round_trip_)
    return false;
  return this->wait_for_(true, timeout_ms);
}

bool EspIdfProductionMqttSession::wait_for_(bool round_trip,
                                            uint32_t timeout_ms) {
  if (!this->live() || timeout_ms < 1000 || timeout_ms > 60000)
    return false;
  const int64_t started_us = esp_timer_get_time();
  const int64_t timeout_us = static_cast<int64_t>(timeout_ms) * 1000;
  while ((esp_timer_get_time() - started_us) <= timeout_us) {
    if (this->terminal_failure_.load())
      return false;
    if (round_trip ? this->round_trip_.load() : this->connected_.load())
      return true;
    vTaskDelay(pdMS_TO_TICKS(10));
  }
  this->mark_failure_(ProductionMqttSessionFailure::TIMEOUT);
  return false;
}

bool EspIdfProductionMqttSession::stop() {
  if (this->client_ == nullptr) {
    this->started_.store(false);
    this->connected_.store(false);
    return true;
  }
  this->stopping_.store(true);
  const esp_err_t status = this->started_.load()
                               ? esp_mqtt_client_stop(this->client_)
                               : ESP_OK;
  if (status != ESP_OK) {
    this->stopping_.store(false);
    return false;
  }
  this->started_.store(false);
  this->connected_.store(false);
  this->authenticated_.store(false);
  this->subscribe_ready_.store(false);
  return true;
}

void EspIdfProductionMqttSession::destroy() {
  if (this->client_ != nullptr) {
    if (this->started_.load())
      this->stop();
    esp_mqtt_client_destroy(this->client_);
    this->client_ = nullptr;
  }
  this->reset_observation_();
  this->clear_material_();
}

bool EspIdfProductionMqttSession::live() const {
  return this->client_ != nullptr && this->started_.load() &&
         !this->stopping_.load();
}

uint32_t EspIdfProductionMqttSession::generation() const {
  return this->profile_.credential_generation;
}

void EspIdfProductionMqttSession::event_handler_(
    void *handler_args, esp_event_base_t, int32_t, void *event_data) {
  auto *instance = static_cast<EspIdfProductionMqttSession *>(handler_args);
  if (instance == nullptr || event_data == nullptr)
    return;
  instance->handle_event_(static_cast<esp_mqtt_event_handle_t>(event_data));
}

void EspIdfProductionMqttSession::handle_event_(
    esp_mqtt_event_handle_t event) {
  if (event == nullptr)
    return;
  switch (event->event_id) {
    case MQTT_EVENT_CONNECTED:
      this->connected_.store(true);
      this->authenticated_.store(true);
      if (this->require_round_trip_) {
        const int message_id = esp_mqtt_client_subscribe(
            event->client, this->exchange_.subscribe_topic.c_str(), 1);
        if (message_id < 0) {
          this->mark_failure_(ProductionMqttSessionFailure::SUBSCRIBE_FAILED);
          return;
        }
        this->subscribe_message_id_ = message_id;
      }
      break;
    case MQTT_EVENT_SUBSCRIBED:
      if (!this->require_round_trip_)
        break;
      if (this->subscribe_message_id_ >= 0 &&
          event->msg_id != this->subscribe_message_id_)
        break;
      this->subscribe_ready_.store(true);
      this->publish_message_id_ = esp_mqtt_client_publish(
          event->client, this->exchange_.publish_topic.c_str(),
          this->exchange_.request_payload.data(),
          static_cast<int>(this->exchange_.request_payload.size()), 1, false);
      if (this->publish_message_id_ < 0)
        this->mark_failure_(ProductionMqttSessionFailure::PUBLISH_FAILED);
      break;
    case MQTT_EVENT_DATA: {
      if (!this->require_round_trip_ || event->total_data_len <= 0 ||
          event->total_data_len > 2048 || event->current_data_offset < 0 ||
          event->data_len < 0)
        break;
      if (event->current_data_offset == 0) {
        this->incoming_topic_.assign(event->topic, event->topic_len);
        this->incoming_payload_.clear();
        this->incoming_total_length_ =
            static_cast<size_t>(event->total_data_len);
        this->incoming_payload_.reserve(this->incoming_total_length_);
      }
      if (static_cast<size_t>(event->current_data_offset) !=
              this->incoming_payload_.size() ||
          this->incoming_total_length_ !=
              static_cast<size_t>(event->total_data_len)) {
        this->mark_failure_(
            ProductionMqttSessionFailure::ROUND_TRIP_MISMATCH);
        break;
      }
      this->incoming_payload_.append(event->data,
                                     static_cast<size_t>(event->data_len));
      if (this->incoming_payload_.size() > this->incoming_total_length_) {
        this->mark_failure_(
            ProductionMqttSessionFailure::ROUND_TRIP_MISMATCH);
        break;
      }
      if (this->incoming_payload_.size() == this->incoming_total_length_) {
        if (this->incoming_topic_ == this->exchange_.subscribe_topic &&
            this->incoming_payload_ == this->exchange_.expected_payload) {
          this->round_trip_.store(true);
        } else {
          this->mark_failure_(
              ProductionMqttSessionFailure::ROUND_TRIP_MISMATCH);
        }
      }
      break;
    }
    case MQTT_EVENT_ERROR:
      if (event->error_handle != nullptr &&
          event->error_handle->error_type ==
              MQTT_ERROR_TYPE_CONNECTION_REFUSED) {
        this->mark_failure_(
            ProductionMqttSessionFailure::AUTHENTICATION_FAILED);
      } else {
        this->mark_failure_(ProductionMqttSessionFailure::TRANSPORT_ERROR);
      }
      break;
    case MQTT_EVENT_DISCONNECTED:
      this->connected_.store(false);
      this->authenticated_.store(false);
      if (!this->stopping_.load() && !this->round_trip_.load())
        this->mark_failure_(ProductionMqttSessionFailure::TRANSPORT_ERROR);
      break;
    default:
      break;
  }
}

void EspIdfProductionMqttSession::mark_failure_(
    ProductionMqttSessionFailure failure) {
  if (failure == ProductionMqttSessionFailure::NONE)
    return;
  this->failure_.store(failure);
  this->terminal_failure_.store(true);
}

void EspIdfProductionMqttSession::reset_observation_() {
  this->subscribe_message_id_ = -1;
  this->publish_message_id_ = -1;
  this->incoming_topic_.clear();
  this->incoming_payload_.clear();
  this->incoming_total_length_ = 0;
  this->client_created_.store(false);
  this->started_.store(false);
  this->connected_.store(false);
  this->authenticated_.store(false);
  this->subscribe_ready_.store(false);
  this->round_trip_.store(false);
  this->stopping_.store(false);
  this->terminal_failure_.store(false);
  this->failure_.store(ProductionMqttSessionFailure::NONE);
}

void EspIdfProductionMqttSession::clear_material_() {
  this->profile_.clear();
  this->exchange_.clear();
  std::fill(this->incoming_topic_.begin(), this->incoming_topic_.end(), '\0');
  this->incoming_topic_.clear();
  std::fill(this->incoming_payload_.begin(), this->incoming_payload_.end(),
            '\0');
  this->incoming_payload_.clear();
  this->incoming_total_length_ = 0;
  this->require_round_trip_ = false;
  this->config_ = {};
}

bool EspIdfProductionPersistenceAdapter::configure(
    const std::string &partition_label, const std::string &namespace_name,
    uint8_t hmac_key_id, bool allow_read_write) {
  this->reset();
  if (partition_label.size() > 15 || namespace_name.empty() ||
      namespace_name.size() > 15 || hmac_key_id > 5)
    return false;
  this->partition_label_ = partition_label;
  this->namespace_name_ = namespace_name;
  this->hmac_key_id_ = hmac_key_id;
  this->allow_read_write_ = allow_read_write;
  this->configured_ = true;
  return true;
}

bool EspIdfProductionPersistenceAdapter::open(PersistenceOpenMode mode) {
  if (!this->configured_ || this->backend_ != nullptr ||
      (mode == PersistenceOpenMode::READ_WRITE && !this->allow_read_write_))
    return false;
  this->backend_ = std::make_unique<EspIdfNvsPersistenceBackend>(
      this->partition_label_, this->namespace_name_);
  if (!this->backend_->open(mode)) {
    this->backend_.reset();
    return false;
  }
  this->key_provider_ =
      std::make_unique<EfuseHmacPersistenceKeyProvider>(this->hmac_key_id_);
  this->crypto_ =
      std::make_unique<PairingPersistenceCrypto>(this->key_provider_.get());
  this->store_ = std::make_unique<PairingPersistentStore>(
      this->backend_.get(), this->crypto_.get());
  return this->ready();
}

void EspIdfProductionPersistenceAdapter::reset() {
  this->store_.reset();
  this->crypto_.reset();
  this->key_provider_.reset();
  this->backend_.reset();
  std::fill(this->partition_label_.begin(), this->partition_label_.end(), '\0');
  this->partition_label_.clear();
  std::fill(this->namespace_name_.begin(), this->namespace_name_.end(), '\0');
  this->namespace_name_.clear();
  this->hmac_key_id_ = 0;
  this->configured_ = false;
  this->allow_read_write_ = false;
}

bool EspIdfProductionPersistenceAdapter::opened() const {
  return this->backend_ != nullptr && this->backend_->opened();
}

bool EspIdfProductionPersistenceAdapter::writable() const {
  return this->backend_ != nullptr && this->backend_->writable();
}

#endif

}  // namespace esphome::greenhouse_pairing_client
