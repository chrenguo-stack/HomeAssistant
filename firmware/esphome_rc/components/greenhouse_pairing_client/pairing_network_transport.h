#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "pairing_client_core.h"
#include "pairing_ram_credentials.h"
#include "pairing_transport_core.h"
#include "secure_pairing_channel.h"

namespace esphome::greenhouse_pairing_client {

enum class PairingNetworkResult : uint8_t {
  SUCCESS = 0,
  DISABLED = 1,
  INVALID_CONFIGURATION = 2,
  DISCOVERY_FAILED = 3,
  SELECTION_REQUIRED = 4,
  CLAIM_FAILED = 5,
  SECURE_OFFER_REJECTED = 6,
  CHANNEL_FAILED = 7,
  CREDENTIALS_FAILED = 8,
  ACK_FAILED = 9,
  UNSUPPORTED_SCHEME = 10,
};

struct PairingNetworkOptions {
  bool enabled{false};
  bool mdns_enabled{true};
  bool udp_enabled{true};
  std::string udp_target{"255.255.255.255"};
  PairingTransportLimits limits{};
};

class PairingNetworkTransport {
 public:
  PairingNetworkTransport() = default;
  ~PairingNetworkTransport();

  PairingNetworkTransport(const PairingNetworkTransport &) = delete;
  PairingNetworkTransport &operator=(const PairingNetworkTransport &) = delete;

  void set_options(const PairingNetworkOptions &options) { this->options_ = options; }
  const PairingNetworkOptions &options() const { return this->options_; }

  PairingNetworkResult discover(PairingClientCore *core, const std::string &query_json,
                                uint32_t now_ms);
  PairingNetworkResult complete_pairing(PairingClientCore *core,
                                        std::string *pairing_secret,
                                        const std::string &claim_json,
                                        RamCredentialBundle *credentials);
  void clear();

  const char *last_result_name() const;
  PairingNetworkResult last_result() const { return this->last_result_; }

  static std::string envelope_json(const SecureEnvelopeDocument &envelope);

 protected:
  struct HttpResponse {
    int status_code{0};
    std::string content_type;
    std::string body;
    bool redirect_observed{false};
  };

  bool browse_mdns_(PairingClientCore *core, uint32_t now_ms);
  bool discover_udp_(PairingClientCore *core, const std::string &query_json, uint32_t now_ms);
  bool post_json_(const std::string &url, const std::string &body, HttpResponse *response);
  bool parse_discovery_response_(const std::string &body, PairingClientCore *core,
                                 uint32_t now_ms) const;
  bool parse_offer_(const std::string &body, SecureOfferDocument *offer) const;
  bool parse_secure_status_(const std::string &body, const std::string &session_id,
                            const std::string &expected_state,
                            uint32_t expected_generation = 0) const;
  bool parse_envelope_(const std::string &body, SecureEnvelopeDocument *envelope) const;
  bool parse_credentials_(const std::string &plaintext, RamCredentialBundle *credentials) const;

  PairingNetworkResult set_result_(PairingNetworkResult result);

  PairingNetworkOptions options_{};
  PairingNetworkResult last_result_{PairingNetworkResult::DISABLED};
  SecurePairingChannel channel_{};
};

}  // namespace esphome::greenhouse_pairing_client
