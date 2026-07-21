#pragma once

#include <atomic>
#include <cstdint>
#include <memory>
#include <string>

#include "pairing_candidate_mqtt_validator.h"
#include "pairing_persistence_backend.h"
#include "pairing_persistence_crypto.h"
#include "pairing_persistent_store.h"
#include "pairing_profile_lifecycle_integration.h"

#ifdef USE_ESP32
#include "mqtt_client.h"
#endif

namespace esphome::greenhouse_pairing_client {

enum class ProductionMqttSessionFailure : uint8_t {
  NONE = 0,
  INVALID_CONFIGURATION = 1,
  CREATE_FAILED = 2,
  START_FAILED = 3,
  AUTHENTICATION_FAILED = 4,
  SUBSCRIBE_FAILED = 5,
  PUBLISH_FAILED = 6,
  ROUND_TRIP_MISMATCH = 7,
  TIMEOUT = 8,
  TRANSPORT_ERROR = 9,
};

struct ProductionMqttSessionObservation {
  bool client_created{false};
  bool started{false};
  bool connected{false};
  bool authenticated{false};
  bool subscribe_ready{false};
  bool round_trip{false};
  bool terminal_failure{false};
  ProductionMqttSessionFailure failure{ProductionMqttSessionFailure::NONE};
};

class ProductionMqttSession {
 public:
  virtual ~ProductionMqttSession() = default;

  virtual bool configure(CandidateMqttProfile profile,
                         CandidateMqttProbeExchange exchange,
                         bool require_round_trip) = 0;
  virtual bool start() = 0;
  virtual bool poll(ProductionMqttSessionObservation *observation) = 0;
  virtual bool wait_connected(uint32_t timeout_ms) = 0;
  virtual bool wait_round_trip(uint32_t timeout_ms) = 0;
  virtual bool stop() = 0;
  virtual void destroy() = 0;
  virtual bool live() const = 0;
  virtual uint32_t generation() const = 0;
};

class ProductionCandidateMqttTransport final : public CandidateMqttTransport {
 public:
  bool configure(ProductionMqttSession *session);

  bool create(const CandidateMqttProfile &profile,
              const CandidateMqttProbeExchange &exchange) override;
  bool start() override;
  bool poll(CandidateMqttTransportObservation *output) override;
  void destroy() override;
  bool live() const override;

 protected:
  static CandidateMqttProfile clone_profile_(
      const CandidateMqttProfile &source);
  static CandidateMqttProbeFailure map_failure_(
      ProductionMqttSessionFailure failure);

  ProductionMqttSession *session_{nullptr};
};

class ActivationNonceSource {
 public:
  virtual ~ActivationNonceSource() = default;
  virtual bool next_nonce_hex(std::string *nonce_hex) = 0;
};

class ProductionProfileLifecycleRuntime final : public ProfileLifecycleRuntime {
 public:
  bool configure(ProductionMqttSession *active_session,
                 ProductionMqttSession *candidate_session,
                 ActivationNonceSource *nonce_source,
                 uint32_t connect_timeout_ms = 15000,
                 uint32_t round_trip_timeout_ms = 15000);

  // The normal active connection must be bound before a rotation lifecycle is
  // recovered. This method is explicit and is never called by the compile-only
  // Stage 2D-5 targets.
  bool bind_active_profile(const RamCredentialBundle &active_credentials);
  bool finalize_activation_promotion();
  bool reset();

  bool stage_recovered_profiles(
      const RamCredentialBundle *active_credentials,
      const RamCredentialBundle &candidate_credentials) override;
  bool staged_generations_match(uint32_t active_generation,
                                uint32_t candidate_generation) const override;

  bool stop_old_active() override;
  bool start_candidate() override;
  bool confirm_candidate_round_trip() override;
  bool stop_candidate() override;
  bool restore_old_active() override;
  void quiesce_all() override;
  void clear_candidate_material() override;
  bool old_active_live() const override;
  bool candidate_active_live() const override;

  uint32_t active_generation() const { return this->active_generation_; }
  uint32_t candidate_generation() const { return this->candidate_generation_; }
  bool staged() const { return this->staged_; }
  bool promotion_pending() const { return this->promotion_pending_; }

 protected:
  static CandidateMqttProfile profile_from_bundle_(
      const RamCredentialBundle &credentials);
  static CandidateMqttProfile clone_profile_(
      const CandidateMqttProfile &source);
  static bool profiles_equal_(const CandidateMqttProfile &left,
                              const CandidateMqttProfile &right);
  static bool valid_nonce_(const std::string &nonce_hex);
  static bool build_exchange_(const CandidateMqttProfile &profile,
                              const std::string &nonce_hex,
                              CandidateMqttProbeExchange *exchange);
  bool configure_session_(ProductionMqttSession *session,
                          const CandidateMqttProfile &profile,
                          const CandidateMqttProbeExchange &exchange,
                          bool require_round_trip);
  void clear_all_material_();

  ProductionMqttSession *active_session_{nullptr};
  ProductionMqttSession *candidate_session_{nullptr};
  ActivationNonceSource *nonce_source_{nullptr};
  uint32_t connect_timeout_ms_{15000};
  uint32_t round_trip_timeout_ms_{15000};
  uint32_t active_generation_{0};
  uint32_t candidate_generation_{0};
  CandidateMqttProfile active_profile_{};
  CandidateMqttProfile candidate_profile_{};
  CandidateMqttProbeExchange candidate_exchange_{};
  bool configured_{false};
  bool staged_{false};
  bool promotion_pending_{false};
};

class ProductionPersistenceAdapter {
 public:
  bool configure(PairingPersistenceBackend *backend,
                 PersistenceKeyProvider *key_provider);
  void reset();

  bool ready() const { return this->store_ != nullptr; }
  PairingPersistentStore *store() { return this->store_.get(); }
  const PairingPersistentStore *store() const { return this->store_.get(); }

 protected:
  PairingPersistenceBackend *backend_{nullptr};
  PersistenceKeyProvider *key_provider_{nullptr};
  std::unique_ptr<PairingPersistenceCrypto> crypto_{};
  std::unique_ptr<PairingPersistentStore> store_{};
};

#ifdef USE_ESP32

class EspIdfActivationNonceSource final : public ActivationNonceSource {
 public:
  bool next_nonce_hex(std::string *nonce_hex) override;
};

class EspIdfProductionMqttSession final : public ProductionMqttSession {
 public:
  EspIdfProductionMqttSession() = default;
  ~EspIdfProductionMqttSession() override;

  EspIdfProductionMqttSession(const EspIdfProductionMqttSession &) = delete;
  EspIdfProductionMqttSession &operator=(
      const EspIdfProductionMqttSession &) = delete;

  bool configure(CandidateMqttProfile profile,
                 CandidateMqttProbeExchange exchange,
                 bool require_round_trip) override;
  bool start() override;
  bool poll(ProductionMqttSessionObservation *observation) override;
  bool wait_connected(uint32_t timeout_ms) override;
  bool wait_round_trip(uint32_t timeout_ms) override;
  bool stop() override;
  void destroy() override;
  bool live() const override;
  uint32_t generation() const override;

 protected:
  static void event_handler_(void *handler_args, esp_event_base_t base,
                             int32_t event_id, void *event_data);
  void handle_event_(esp_mqtt_event_handle_t event);
  void mark_failure_(ProductionMqttSessionFailure failure);
  bool wait_for_(bool round_trip, uint32_t timeout_ms);
  void reset_observation_();
  void clear_material_();

  CandidateMqttProfile profile_{};
  CandidateMqttProbeExchange exchange_{};
  esp_mqtt_client_config_t config_{};
  esp_mqtt_client_handle_t client_{nullptr};
  int subscribe_message_id_{-1};
  int publish_message_id_{-1};
  std::string incoming_topic_{};
  std::string incoming_payload_{};
  size_t incoming_total_length_{0};
  bool require_round_trip_{false};
  std::atomic<bool> client_created_{false};
  std::atomic<bool> started_{false};
  std::atomic<bool> connected_{false};
  std::atomic<bool> authenticated_{false};
  std::atomic<bool> subscribe_ready_{false};
  std::atomic<bool> round_trip_{false};
  std::atomic<bool> stopping_{false};
  std::atomic<bool> terminal_failure_{false};
  std::atomic<ProductionMqttSessionFailure> failure_{ProductionMqttSessionFailure::NONE};
};

class EspIdfProductionPersistenceAdapter {
 public:
  bool configure(const std::string &partition_label,
                 const std::string &namespace_name, uint8_t hmac_key_id,
                 bool allow_read_write = false);
  bool open(PersistenceOpenMode mode = PersistenceOpenMode::READ_ONLY);
  void reset();

  bool opened() const;
  bool writable() const;
  bool ready() const { return this->store_ != nullptr; }
  PairingPersistentStore *store() { return this->store_.get(); }

 protected:
  std::string partition_label_{};
  std::string namespace_name_{};
  uint8_t hmac_key_id_{0};
  bool configured_{false};
  bool allow_read_write_{false};
  std::unique_ptr<EspIdfNvsPersistenceBackend> backend_{};
  std::unique_ptr<EfuseHmacPersistenceKeyProvider> key_provider_{};
  std::unique_ptr<PairingPersistenceCrypto> crypto_{};
  std::unique_ptr<PairingPersistentStore> store_{};
};

#endif

}  // namespace esphome::greenhouse_pairing_client
