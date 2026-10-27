#pragma once

#include <cstdint>
#include <string>

#include "n3w_manager_discovery.h"
#include "n3w_registration_discovery.h"

namespace esphome::greenhouse_n3w_core {

inline constexpr char kRegistrationConfirmSchema[] = "gh.registration.confirm/1";
inline constexpr char kRegistrationConfirmResultSchema[] =
    "gh.registration.confirm-result/1";
inline constexpr char kRegistrationStatusSchema[] = "gh.registration.status/1";
inline constexpr char kRegistrationStatusResultSchema[] =
    "gh.registration.status-result/1";
inline constexpr char kRegistrationStatusPath[] = "/v1/registration/status";
inline constexpr uint16_t kRegistrationPairingPort = 47112;
inline constexpr char kRegistrationPairingPath[] = "/v2/pairing";
inline constexpr uint16_t kRegistrationTransactionMaxSeconds = 1800;

enum class RegistrationBootstrapConfirmAction : uint8_t {
  ACCEPTED = 0,
  RETRY,
  TERMINAL,
};

enum class RegistrationBootstrapStatusAction : uint8_t {
  COMMITTED = 0,
  WAIT,
  TERMINAL,
};

struct RegistrationBootstrapRecoveryBinding {
  std::string pairing_id;
  std::string manager_id;
  std::string system_id;
  std::string bootstrap_host;
  uint16_t bootstrap_port{kRegistrationBootstrapPort};
  std::string bootstrap_tls_sha256;

  bool valid() const;
};

struct RegistrationBootstrapConfirmResult {
  RegistrationBootstrapConfirmAction action{
      RegistrationBootstrapConfirmAction::RETRY};
  SimpleManagerCandidateV2 pairing_target{};
  RegistrationBootstrapRecoveryBinding recovery{};
  uint64_t transaction_deadline_ms{0};
  std::string reason{};
};

struct RegistrationBootstrapStatusResult {
  RegistrationBootstrapStatusAction action{
      RegistrationBootstrapStatusAction::WAIT};
  std::string reason{};
};

bool build_registration_confirm_request(
    const RegistrationCandidateV1 &selected,
    const std::string &hardware_id,
    const std::string &pairing_id,
    const std::string &setup_secret_base64url,
    std::string *request_json);

bool parse_registration_confirm_response(
    int http_status,
    const std::string &response_json,
    const RegistrationCandidateV1 &selected,
    const std::string &pairing_id,
    const std::string &local_ipv4,
    const std::string &subnet_mask,
    uint64_t received_ms,
    RegistrationBootstrapConfirmResult *result);

bool build_registration_status_request(
    const RegistrationBootstrapRecoveryBinding &binding,
    const std::string &hardware_id,
    const std::string &delivery_digest_base64url,
    std::string *request_json);

bool parse_registration_status_response(
    int http_status,
    const std::string &response_json,
    RegistrationBootstrapStatusResult *result);

bool registration_bootstrap_host_allowed(
    const std::string &host,
    const std::string &local_ipv4,
    const std::string &subnet_mask);

bool registration_relocation_matches(
    const RegistrationCandidateV1 &candidate,
    const RegistrationBootstrapRecoveryBinding &binding);

}  // namespace esphome::greenhouse_n3w_core
