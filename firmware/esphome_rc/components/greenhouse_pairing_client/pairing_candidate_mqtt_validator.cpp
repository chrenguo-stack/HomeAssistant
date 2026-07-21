#include "pairing_candidate_mqtt_validator.h"

#include <algorithm>
#include <cctype>
#include <utility>

namespace esphome::greenhouse_pairing_client {
namespace {

void secure_clear(std::string *value) {
  if (value == nullptr)
    return;
  std::fill(value->begin(), value->end(), '\0');
  value->clear();
  value->shrink_to_fit();
}

bool valid_identifier(const std::string &value) {
  if (value.empty() || value.size() > 128)
    return false;
  const auto first = static_cast<unsigned char>(value.front());
  if (std::isalnum(first) == 0)
    return false;
  for (const char character : value) {
    const auto current = static_cast<unsigned char>(character);
    if (std::isalnum(current) != 0 || character == '.' || character == '_' ||
        character == ':' || character == '-')
      continue;
    return false;
  }
  return true;
}

bool numeric_ipv4(const std::string &value) {
  if (value.empty())
    return false;
  size_t dots = 0;
  for (const char character : value) {
    if (character == '.') {
      dots++;
      continue;
    }
    if (std::isdigit(static_cast<unsigned char>(character)) == 0)
      return false;
  }
  return dots == 3;
}

bool valid_hostname(const std::string &value, bool reject_ip_literal) {
  if (value.empty() || value.size() > 253 || value.front() == '.' ||
      value.back() == '.' || value.find(':') != std::string::npos)
    return false;
  if (reject_ip_literal && numeric_ipv4(value))
    return false;

  size_t label_start = 0;
  while (label_start < value.size()) {
    const size_t label_end = value.find('.', label_start);
    const size_t end = label_end == std::string::npos ? value.size() : label_end;
    const size_t length = end - label_start;
    if (length == 0 || length > 63)
      return false;
    if (value[label_start] == '-' || value[end - 1] == '-')
      return false;
    for (size_t index = label_start; index < end; index++) {
      const char character = value[index];
      if (std::isalnum(static_cast<unsigned char>(character)) == 0 &&
          character != '-')
        return false;
    }
    if (label_end == std::string::npos)
      break;
    label_start = label_end + 1;
  }
  return true;
}

bool certificate_like(const std::string &value) {
  return !value.empty() && value.size() <= 8192 &&
         value.find("-----BEGIN CERTIFICATE-----") != std::string::npos &&
         value.find("-----END CERTIFICATE-----") != std::string::npos;
}

}  // namespace

CandidateMqttProfile::~CandidateMqttProfile() { this->clear(); }

CandidateMqttProfile::CandidateMqttProfile(CandidateMqttProfile &&other) {
  this->move_from_(&other);
}

CandidateMqttProfile &CandidateMqttProfile::operator=(CandidateMqttProfile &&other) {
  if (this == &other)
    return *this;
  this->clear();
  this->move_from_(&other);
  return *this;
}

void CandidateMqttProfile::move_from_(CandidateMqttProfile *other) {
  if (other == nullptr || other == this)
    return;
  this->system_id = other->system_id;
  this->node_id = other->node_id;
  this->broker_host = other->broker_host;
  this->broker_port = other->broker_port;
  this->broker_tls_server_name = other->broker_tls_server_name;
  this->ca_pem = other->ca_pem;
  this->mqtt_username = other->mqtt_username;
  this->mqtt_client_id = other->mqtt_client_id;
  this->credential_generation = other->credential_generation;
  this->mqtt_password = other->mqtt_password;
  other->clear();
}

bool CandidateMqttProfile::valid() const {
  return valid_identifier(this->system_id) && valid_identifier(this->node_id) &&
         valid_hostname(this->broker_host, true) && this->broker_port != 0 &&
         valid_hostname(this->broker_tls_server_name, true) &&
         this->broker_host == this->broker_tls_server_name &&
         certificate_like(this->ca_pem) && valid_identifier(this->mqtt_username) &&
         valid_identifier(this->mqtt_client_id) &&
         this->credential_generation != 0 && !this->mqtt_password.empty() &&
         this->mqtt_password.size() <= 512;
}

bool CandidateMqttProfile::present() const {
  return !this->system_id.empty() || !this->node_id.empty() ||
         !this->broker_host.empty() || !this->ca_pem.empty() ||
         !this->mqtt_username.empty() || !this->mqtt_client_id.empty() ||
         !this->mqtt_password.empty() || this->broker_port != 0 ||
         this->credential_generation != 0;
}

void CandidateMqttProfile::clear() {
  secure_clear(&this->system_id);
  secure_clear(&this->node_id);
  secure_clear(&this->broker_host);
  secure_clear(&this->broker_tls_server_name);
  secure_clear(&this->ca_pem);
  secure_clear(&this->mqtt_username);
  secure_clear(&this->mqtt_client_id);
  secure_clear(&this->mqtt_password);
  this->broker_port = 0;
  this->credential_generation = 0;
}

bool CandidateMqttProbeExchange::valid() const {
  return !this->publish_topic.empty() && !this->subscribe_topic.empty() &&
         !this->request_payload.empty() && !this->expected_payload.empty() &&
         this->publish_topic.size() <= 512 && this->subscribe_topic.size() <= 512 &&
         this->request_payload.size() <= 1024 && this->expected_payload.size() <= 1024;
}

void CandidateMqttProbeExchange::clear() {
  secure_clear(&this->publish_topic);
  secure_clear(&this->subscribe_topic);
  secure_clear(&this->request_payload);
  secure_clear(&this->expected_payload);
}

bool CandidateMqttProfileValidator::configure(uint32_t active_generation,
                                              uint32_t timeout_ms) {
  if (timeout_ms < 1000 || timeout_ms > 60000)
    return false;
  this->profile_.clear();
  this->exchange_.clear();
  this->configured_active_generation_ = active_generation;
  this->timeout_ms_ = timeout_ms;
  this->snapshot_ = {};
  this->snapshot_.active_generation = active_generation;
  this->activation_.configure(active_generation);
  return true;
}

bool CandidateMqttProfileValidator::valid_nonce_(const std::string &value) {
  if (value.size() < 16 || value.size() > 64 || (value.size() % 2) != 0)
    return false;
  return std::all_of(value.begin(), value.end(), [](char character) {
    return (character >= '0' && character <= '9') ||
           (character >= 'a' && character <= 'f');
  });
}

bool CandidateMqttProfileValidator::build_exchange_(
    const CandidateMqttProfile &profile, const std::string &nonce_hex,
    CandidateMqttProbeExchange *output) {
  if (output == nullptr || !profile.valid() || !valid_nonce_(nonce_hex))
    return false;
  output->clear();
  const std::string prefix = "gh/v1/" + profile.system_id;
  output->publish_topic = prefix + "/ingress/node/" + profile.node_id + "/telemetry";
  output->subscribe_topic = prefix + "/out/node/" + profile.node_id + "/confirm";
  output->request_payload =
      "{\"credential_generation\":" + std::to_string(profile.credential_generation) +
      ",\"node_id\":\"" + profile.node_id + "\",\"nonce\":\"" + nonce_hex +
      "\",\"schema\":\"gh.telemetry-probe/1\"}";
  output->expected_payload =
      "{\"credential_generation\":" + std::to_string(profile.credential_generation) +
      ",\"node_id\":\"" + profile.node_id + "\",\"nonce\":\"" + nonce_hex +
      "\",\"schema\":\"gh.telemetry-probe-confirm/1\",\"status\":\"accepted\"}";
  return output->valid();
}

bool CandidateMqttProfileValidator::stage(CandidateMqttProfile profile,
                                          const std::string &nonce_hex) {
  if (this->snapshot_.phase != CandidateMqttProbePhase::IDLE)
    return false;
  if (!profile.valid()) {
    profile.clear();
    this->snapshot_.phase = CandidateMqttProbePhase::FAILED;
    this->snapshot_.failure = CandidateMqttProbeFailure::INVALID_PROFILE;
    return false;
  }
  if (profile.credential_generation <= this->configured_active_generation_) {
    profile.clear();
    this->snapshot_.phase = CandidateMqttProbePhase::FAILED;
    this->snapshot_.failure = CandidateMqttProbeFailure::GENERATION_REJECTED;
    return false;
  }
  if (!valid_nonce_(nonce_hex)) {
    profile.clear();
    this->snapshot_.phase = CandidateMqttProbePhase::FAILED;
    this->snapshot_.failure = CandidateMqttProbeFailure::INVALID_NONCE;
    return false;
  }
  if (!this->activation_.stage(profile.credential_generation) ||
      !build_exchange_(profile, nonce_hex, &this->exchange_)) {
    profile.clear();
    this->exchange_.clear();
    this->snapshot_.phase = CandidateMqttProbePhase::FAILED;
    this->snapshot_.failure = CandidateMqttProbeFailure::GENERATION_REJECTED;
    return false;
  }
  this->profile_ = std::move(profile);
  this->snapshot_.phase = CandidateMqttProbePhase::CANDIDATE_STAGED;
  this->snapshot_.failure = CandidateMqttProbeFailure::NONE;
  this->snapshot_.candidate_generation = this->profile_.credential_generation;
  this->refresh_invariant_(nullptr);
  return true;
}

bool CandidateMqttProfileValidator::begin(CandidateMqttTransport *transport) {
  if (transport == nullptr ||
      this->snapshot_.phase != CandidateMqttProbePhase::CANDIDATE_STAGED ||
      !this->profile_.valid() || !this->exchange_.valid() || transport->live())
    return false;
  if (!this->activation_.begin_probe())
    return false;
  if (!transport->create(this->profile_, this->exchange_))
    return this->fail_(transport, CandidateMqttProbeFailure::CREATE_FAILED);
  if (!transport->start())
    return this->fail_(transport, CandidateMqttProbeFailure::START_FAILED);
  this->snapshot_.phase = CandidateMqttProbePhase::CONNECTING;
  this->refresh_invariant_(transport);
  return true;
}

bool CandidateMqttProfileValidator::poll(CandidateMqttTransport *transport,
                                         uint32_t elapsed_ms) {
  if (transport == nullptr ||
      (this->snapshot_.phase != CandidateMqttProbePhase::CONNECTING &&
       this->snapshot_.phase != CandidateMqttProbePhase::SUBSCRIBING &&
       this->snapshot_.phase != CandidateMqttProbePhase::ROUND_TRIP))
    return false;
  if (elapsed_ms > this->timeout_ms_)
    return this->fail_(transport, CandidateMqttProbeFailure::TIMEOUT);

  CandidateMqttTransportObservation observation{};
  if (!transport->poll(&observation))
    return this->fail_(transport, CandidateMqttProbeFailure::TRANSPORT_ERROR);
  if ((observation.authenticated && !observation.connected) ||
      (observation.subscribe_ready && !observation.authenticated) ||
      (observation.telemetry_round_trip && !observation.subscribe_ready))
    return this->fail_(transport, CandidateMqttProbeFailure::TRANSPORT_INVARIANT);

  this->snapshot_.authenticated = observation.authenticated;
  this->snapshot_.subscribe_ready = observation.subscribe_ready;
  this->snapshot_.telemetry_round_trip = observation.telemetry_round_trip;

  if (observation.terminal_failure) {
    const CandidateMqttProbeFailure failure =
        observation.failure == CandidateMqttProbeFailure::NONE
            ? CandidateMqttProbeFailure::TRANSPORT_ERROR
            : observation.failure;
    return this->fail_(transport, failure);
  }

  if (observation.telemetry_round_trip) {
    if (!this->activation_.record_probe(true, true, true))
      return this->fail_(transport, CandidateMqttProbeFailure::TRANSPORT_INVARIANT);
    transport->destroy();
    this->profile_.clear();
    this->exchange_.clear();
    this->snapshot_.phase = CandidateMqttProbePhase::VERIFIED;
    this->snapshot_.failure = CandidateMqttProbeFailure::NONE;
    this->refresh_invariant_(transport);
    return true;
  }
  if (observation.subscribe_ready)
    this->snapshot_.phase = CandidateMqttProbePhase::ROUND_TRIP;
  else if (observation.authenticated)
    this->snapshot_.phase = CandidateMqttProbePhase::SUBSCRIBING;
  else
    this->snapshot_.phase = CandidateMqttProbePhase::CONNECTING;
  this->refresh_invariant_(transport);
  return true;
}

bool CandidateMqttProfileValidator::fail_(CandidateMqttTransport *transport,
                                          CandidateMqttProbeFailure failure) {
  if (transport != nullptr)
    transport->destroy();
  if (this->activation_.snapshot().phase == MqttActivationPhase::PROBING) {
    this->activation_.record_probe(this->snapshot_.authenticated,
                                   this->snapshot_.subscribe_ready,
                                   this->snapshot_.telemetry_round_trip);
  }
  if (this->activation_.snapshot().phase == MqttActivationPhase::FAILED ||
      this->activation_.snapshot().phase == MqttActivationPhase::CANDIDATE_STAGED ||
      this->activation_.snapshot().phase == MqttActivationPhase::PROBING ||
      this->activation_.snapshot().phase == MqttActivationPhase::VERIFIED) {
    this->activation_.rollback();
  }
  this->profile_.clear();
  this->exchange_.clear();
  this->snapshot_.phase = CandidateMqttProbePhase::FAILED;
  this->snapshot_.failure = failure;
  this->refresh_invariant_(transport);
  return false;
}

bool CandidateMqttProfileValidator::cancel(CandidateMqttTransport *transport) {
  if (this->snapshot_.phase != CandidateMqttProbePhase::CANDIDATE_STAGED &&
      this->snapshot_.phase != CandidateMqttProbePhase::CONNECTING &&
      this->snapshot_.phase != CandidateMqttProbePhase::SUBSCRIBING &&
      this->snapshot_.phase != CandidateMqttProbePhase::ROUND_TRIP)
    return false;
  if (transport != nullptr)
    transport->destroy();
  this->activation_.rollback();
  this->profile_.clear();
  this->exchange_.clear();
  this->snapshot_.phase = CandidateMqttProbePhase::CANCELLED;
  this->snapshot_.failure = CandidateMqttProbeFailure::CANCELLED;
  this->refresh_invariant_(transport);
  return true;
}

bool CandidateMqttProfileValidator::reset() {
  if (this->snapshot_.phase != CandidateMqttProbePhase::VERIFIED &&
      this->snapshot_.phase != CandidateMqttProbePhase::FAILED &&
      this->snapshot_.phase != CandidateMqttProbePhase::CANCELLED)
    return false;
  return this->configure(this->configured_active_generation_, this->timeout_ms_);
}

void CandidateMqttProfileValidator::refresh_invariant_(
    CandidateMqttTransport *transport) {
  this->snapshot_.candidate_client_live = transport != nullptr && transport->live();
  this->snapshot_.active_profile_unchanged =
      this->activation_.snapshot().active_generation ==
      this->configured_active_generation_;
  this->snapshot_.active_generation = this->configured_active_generation_;
}

const char *CandidateMqttProfileValidator::phase_name(CandidateMqttProbePhase phase) {
  switch (phase) {
    case CandidateMqttProbePhase::IDLE: return "idle";
    case CandidateMqttProbePhase::CANDIDATE_STAGED: return "candidate_staged";
    case CandidateMqttProbePhase::CONNECTING: return "connecting";
    case CandidateMqttProbePhase::SUBSCRIBING: return "subscribing";
    case CandidateMqttProbePhase::ROUND_TRIP: return "round_trip";
    case CandidateMqttProbePhase::VERIFIED: return "verified";
    case CandidateMqttProbePhase::FAILED: return "failed";
    case CandidateMqttProbePhase::CANCELLED: return "cancelled";
  }
  return "unknown";
}

const char *CandidateMqttProfileValidator::failure_name(
    CandidateMqttProbeFailure failure) {
  switch (failure) {
    case CandidateMqttProbeFailure::NONE: return "none";
    case CandidateMqttProbeFailure::INVALID_PROFILE: return "invalid_profile";
    case CandidateMqttProbeFailure::GENERATION_REJECTED: return "generation_rejected";
    case CandidateMqttProbeFailure::INVALID_NONCE: return "invalid_nonce";
    case CandidateMqttProbeFailure::CREATE_FAILED: return "create_failed";
    case CandidateMqttProbeFailure::START_FAILED: return "start_failed";
    case CandidateMqttProbeFailure::AUTHENTICATION_FAILED: return "authentication_failed";
    case CandidateMqttProbeFailure::SUBSCRIBE_FAILED: return "subscribe_failed";
    case CandidateMqttProbeFailure::PUBLISH_FAILED: return "publish_failed";
    case CandidateMqttProbeFailure::ROUND_TRIP_MISMATCH: return "round_trip_mismatch";
    case CandidateMqttProbeFailure::TIMEOUT: return "timeout";
    case CandidateMqttProbeFailure::TRANSPORT_ERROR: return "transport_error";
    case CandidateMqttProbeFailure::TRANSPORT_INVARIANT: return "transport_invariant";
    case CandidateMqttProbeFailure::CANCELLED: return "cancelled";
  }
  return "unknown";
}

}  // namespace esphome::greenhouse_pairing_client
