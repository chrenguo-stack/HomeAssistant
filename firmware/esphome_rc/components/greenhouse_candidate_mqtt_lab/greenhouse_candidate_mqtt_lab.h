#pragma once

#include <atomic>
#include <cstdint>
#include <string>

#include "mqtt_client.h"
#include "esphome/core/component.h"
#include "esphome/components/greenhouse_pairing_client/pairing_candidate_mqtt_validator.h"
#include "esphome/components/greenhouse_pairing_client/pairing_ram_credentials.h"

namespace esphome::greenhouse_candidate_mqtt_lab {

using greenhouse_pairing_client::CandidateMqttProbeExchange;
using greenhouse_pairing_client::CandidateMqttProbeFailure;
using greenhouse_pairing_client::CandidateMqttProfile;
using greenhouse_pairing_client::CandidateMqttProfileValidator;
using greenhouse_pairing_client::CandidateMqttTransport;
using greenhouse_pairing_client::CandidateMqttTransportObservation;
using greenhouse_pairing_client::RamCredentialBundle;

class EspIdfCandidateMqttTransport final : public CandidateMqttTransport {
 public:
  ~EspIdfCandidateMqttTransport() override;

  bool create(const CandidateMqttProfile &profile,
              const CandidateMqttProbeExchange &exchange) override;
  bool start() override;
  bool poll(CandidateMqttTransportObservation *output) override;
  void destroy() override;
  bool live() const override { return this->client_ != nullptr; }

 protected:
  static void event_handler_(void *handler_args, esp_event_base_t base,
                             int32_t event_id, void *event_data);
  void handle_event_(esp_mqtt_event_handle_t event);
  void fail_(CandidateMqttProbeFailure failure);
  void clear_material_();

  esp_mqtt_client_handle_t client_{nullptr};
  bool started_{false};
  int subscribe_message_id_{-1};

  std::string broker_host_;
  uint16_t broker_port_{0};
  std::string ca_pem_;
  std::string mqtt_username_;
  std::string mqtt_client_id_;
  std::string mqtt_password_;
  CandidateMqttProbeExchange exchange_{};

  std::atomic<bool> connected_{false};
  std::atomic<bool> authenticated_{false};
  std::atomic<bool> subscribe_ready_{false};
  std::atomic<bool> telemetry_round_trip_{false};
  std::atomic<bool> terminal_failure_{false};
  std::atomic<uint8_t> failure_{
      static_cast<uint8_t>(CandidateMqttProbeFailure::NONE)};
};

class GreenhouseCandidateMqttLab final : public Component {
 public:
  void set_probe_timeout_ms(uint32_t value) { this->probe_timeout_ms_ = value; }

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override;

  // Manual non-production entry point. No YAML action calls this method. The
  // caller transfers the candidate bundle into a separate ESP-IDF MQTT client;
  // the active ESPHome MQTT profile is never read or mutated.
  bool begin_for_lab(RamCredentialBundle *credentials,
                     uint32_t active_generation,
                     const std::string &nonce_hex);
  bool cancel_for_lab();

  const char *phase_name() const;
  const char *failure_name() const;
  bool active_profile_unchanged() const;
  bool candidate_client_live() const;

 protected:
  uint32_t probe_timeout_ms_{15000};
  uint32_t probe_started_ms_{0};
  bool probe_running_{false};
  CandidateMqttProfileValidator validator_{};
  EspIdfCandidateMqttTransport transport_{};
};

}  // namespace esphome::greenhouse_candidate_mqtt_lab
