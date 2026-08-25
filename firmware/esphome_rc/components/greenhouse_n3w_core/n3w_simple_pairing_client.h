#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>

#include "n3w_esp32_pairing_nvs.h"
#include "n3w_esp32_runtime_nvs.h"
#include "n3w_esp32_simple_nvs.h"
#include "n3w_radio.h"
#include "n3w_simple_crypto.h"

namespace esphome::greenhouse_n3w_core {

enum class SimplePairingClientError : uint8_t {
  NONE = 0,
  NOT_READY,
  IO_FAILED,
  DISCOVERY_FAILED,
  HTTP_FAILED,
  RESPONSE_REJECTED,
  CRYPTO_FAILED,
  PERSISTENCE_FAILED,
  ACK_PENDING,
  ALREADY_PROVISIONED,
};

struct SimpleManagerCandidateV2 {
  std::string manager_id;
  std::string system_id;
  std::string host;
  uint16_t port{0};
  std::string pairing_path;

  bool valid() const;
};

class SimplePairingClientNetwork {
 public:
  virtual ~SimplePairingClientNetwork() = default;
  virtual bool discover_manager(
      const std::string &request_json,
      std::string *response_json) = 0;
  virtual bool post_json(
      const SimpleManagerCandidateV2 &candidate,
      const std::string &path,
      const std::string &request_json,
      int *status_code,
      std::string *response_json) = 0;
  virtual bool post_json(
      const PendingPairingAckV2 &pending,
      const std::string &path,
      const std::string &request_json,
      int *status_code,
      std::string *response_json) = 0;
};

class SimplePairingClientRandom {
 public:
  virtual ~SimplePairingClientRandom() = default;
  virtual bool fill_pairing_random(uint8_t *data, std::size_t size) = 0;
};

class SimplePairingClient {
 public:
  SimplePairingClient(
      SimplePairingClientNetwork *network,
      SimplePairingClientRandom *random,
      NvsSetupSecretStore *setup_secret_store,
      NvsProvisionedPeerStoreV2 *peer_store,
      NvsProvisionedBrokerStoreV2 *broker_store,
      NvsPendingPairingAckStoreV2 *ack_store);

  SimplePairingClientError initialize(const MacAddress &local_mac);
  SimplePairingClientError run_once(uint64_t now_ms);
  SimplePairingClientError resume_pending_ack();

  bool provisioned() const { return provisioned_; }
  bool setup_secret_ready() const { return setup_secret_ready_; }
  const std::string &hardware_id() const { return hardware_id_; }
  const std::string &pairing_id() const { return pairing_id_; }
  std::string setup_secret_base64url() const;
  std::string pairing_qr_payload() const;

 private:
  SimplePairingClientError load_existing_();
  SimplePairingClientError prepare_bootstrap_();
  SimplePairingClientError discover_(SimpleManagerCandidateV2 *candidate);
  SimplePairingClientError send_hello_(const SimpleManagerCandidateV2 &candidate);
  SimplePairingClientError pair_with_(const SimpleManagerCandidateV2 &candidate);
  SimplePairingClientError persist_bundle_(
      const SimpleManagerCandidateV2 &candidate,
      const std::string &session_id,
      const std::array<uint8_t, 32> &delivery_digest,
      const ProvisionedPeerStateV2 &peer,
      const ProvisionedBrokerStateV2 &broker);
  SimplePairingClientError acknowledge_(const PendingPairingAckV2 &pending);
  bool fill_(uint8_t *data, std::size_t size);

  SimplePairingClientNetwork *network_{nullptr};
  SimplePairingClientRandom *random_{nullptr};
  NvsSetupSecretStore *setup_secret_store_{nullptr};
  NvsProvisionedPeerStoreV2 *peer_store_{nullptr};
  NvsProvisionedBrokerStoreV2 *broker_store_{nullptr};
  NvsPendingPairingAckStoreV2 *ack_store_{nullptr};
  NvsPendingPairingIntentStore pairing_intent_store_{};
  MacAddress local_mac_{};
  SetupSecret setup_secret_{};
  std::string hardware_id_{};
  std::string pairing_id_{};
  bool initialized_{false};
  bool setup_secret_ready_{false};
  bool provisioned_{false};
};

}  // namespace esphome::greenhouse_n3w_core
