#pragma once

#include <cstdint>
#include <string>

#include "pairing_mqtt_activation_contract.h"

namespace esphome::greenhouse_pairing_client {

enum class CandidateMqttProbePhase : uint8_t {
  IDLE = 0,
  CANDIDATE_STAGED = 1,
  CONNECTING = 2,
  SUBSCRIBING = 3,
  ROUND_TRIP = 4,
  VERIFIED = 5,
  FAILED = 6,
  CANCELLED = 7,
};

enum class CandidateMqttProbeFailure : uint8_t {
  NONE = 0,
  INVALID_PROFILE = 1,
  GENERATION_REJECTED = 2,
  INVALID_NONCE = 3,
  CREATE_FAILED = 4,
  START_FAILED = 5,
  AUTHENTICATION_FAILED = 6,
  SUBSCRIBE_FAILED = 7,
  PUBLISH_FAILED = 8,
  ROUND_TRIP_MISMATCH = 9,
  TIMEOUT = 10,
  TRANSPORT_ERROR = 11,
  TRANSPORT_INVARIANT = 12,
  CANCELLED = 13,
};

struct CandidateMqttProfile {
  CandidateMqttProfile() = default;
  ~CandidateMqttProfile();
  CandidateMqttProfile(const CandidateMqttProfile &) = delete;
  CandidateMqttProfile &operator=(const CandidateMqttProfile &) = delete;
  CandidateMqttProfile(CandidateMqttProfile &&other);
  CandidateMqttProfile &operator=(CandidateMqttProfile &&other);

  std::string system_id;
  std::string node_id;
  std::string broker_host;
  uint16_t broker_port{0};
  std::string broker_tls_server_name;
  std::string ca_pem;
  std::string mqtt_username;
  std::string mqtt_client_id;
  uint32_t credential_generation{0};
  std::string mqtt_password;

  bool valid() const;
  bool present() const;
  void clear();

 protected:
  void move_from_(CandidateMqttProfile *other);
};

struct CandidateMqttProbeExchange {
  std::string publish_topic;
  std::string subscribe_topic;
  std::string request_payload;
  std::string expected_payload;

  bool valid() const;
  void clear();
};

struct CandidateMqttTransportObservation {
  bool client_created{false};
  bool connected{false};
  bool authenticated{false};
  bool subscribe_ready{false};
  bool telemetry_round_trip{false};
  bool terminal_failure{false};
  CandidateMqttProbeFailure failure{CandidateMqttProbeFailure::NONE};
};

class CandidateMqttTransport {
 public:
  virtual ~CandidateMqttTransport() = default;
  virtual bool create(const CandidateMqttProfile &profile,
                      const CandidateMqttProbeExchange &exchange) = 0;
  virtual bool start() = 0;
  virtual bool poll(CandidateMqttTransportObservation *output) = 0;
  virtual void destroy() = 0;
  virtual bool live() const = 0;
};

struct CandidateMqttProbeSnapshot {
  CandidateMqttProbePhase phase{CandidateMqttProbePhase::IDLE};
  CandidateMqttProbeFailure failure{CandidateMqttProbeFailure::NONE};
  uint32_t active_generation{0};
  uint32_t candidate_generation{0};
  bool authenticated{false};
  bool subscribe_ready{false};
  bool telemetry_round_trip{false};
  bool candidate_client_live{false};
  bool active_profile_unchanged{true};
};

class CandidateMqttProfileValidator {
 public:
  bool configure(uint32_t active_generation, uint32_t timeout_ms = 15000);
  bool stage(CandidateMqttProfile profile, const std::string &nonce_hex);
  bool begin(CandidateMqttTransport *transport);
  bool poll(CandidateMqttTransport *transport, uint32_t elapsed_ms);
  bool cancel(CandidateMqttTransport *transport);
  bool reset();

  const CandidateMqttProbeSnapshot &snapshot() const { return this->snapshot_; }
  const CandidateMqttProbeExchange &exchange() const { return this->exchange_; }
  bool candidate_material_present() const { return this->profile_.present(); }

  static const char *phase_name(CandidateMqttProbePhase phase);
  static const char *failure_name(CandidateMqttProbeFailure failure);

 protected:
  static bool valid_nonce_(const std::string &value);
  static bool build_exchange_(const CandidateMqttProfile &profile,
                              const std::string &nonce_hex,
                              CandidateMqttProbeExchange *output);
  bool fail_(CandidateMqttTransport *transport,
             CandidateMqttProbeFailure failure);
  void refresh_invariant_(CandidateMqttTransport *transport);

  uint32_t configured_active_generation_{0};
  uint32_t timeout_ms_{15000};
  CandidateMqttProfile profile_{};
  CandidateMqttProbeExchange exchange_{};
  CandidateMqttProbeSnapshot snapshot_{};
  MqttActivationContract activation_{};
};

}  // namespace esphome::greenhouse_pairing_client
