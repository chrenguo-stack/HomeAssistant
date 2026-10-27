#pragma once

#include <cstdint>
#include <string>

#include "n3w_manager_discovery.h"
#include "n3w_registration_discovery.h"

namespace esphome::greenhouse_n3w_core {

// Pure protocol seam. Transport must verify the TLS leaf certificate before
// transmitting the request (in particular the Setup Secret) on the wire.
enum class RegistrationConfirmDisposition : uint8_t {
  INVALID = 0,
  ACCEPTED,
  RETRY_SAME_PAIRING_ID,
  RENEW_PAIRING_ID,
};

struct RegistrationConfirmResult {
  RegistrationConfirmDisposition disposition{RegistrationConfirmDisposition::INVALID};
  SimpleManagerCandidateV2 pairing_target{};
  uint16_t remaining_seconds{0};
  std::string reason{};
};

bool build_registration_confirm_request(
    const RegistrationCandidateV1 &selected,
    const std::string &hardware_id,
    const std::string &pairing_id,
    const std::string &setup_secret_base64url,
    std::string *request_json);

bool parse_registration_confirm_result(
    const std::string &response_json,
    const RegistrationCandidateV1 &selected,
    RegistrationConfirmResult *result);

}  // namespace esphome::greenhouse_n3w_core
